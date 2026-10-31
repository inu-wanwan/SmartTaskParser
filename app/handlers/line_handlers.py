import os
import logging

from dotenv import load_dotenv
from linebot import LineBotApi, WebhookParser
from linebot.models import MessageEvent, PostbackEvent, TextMessage, TextSendMessage, FlexSendMessage, BubbleContainer, BoxComponent, TextComponent, ButtonComponent, URIAction

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from linebot.exceptions import InvalidSignatureError
from app.services.task_service import TaskService
from app.services.user_service import UserService
from app.repositories.user_repository import UserRepository
from app.services.reminder_service import ReminderService
from app.clients.linear_client import LinearClient
from app.models.user import User
from app.utils.reminder_time import (
    FORCE_REMINDER_PREFIX,
    INTENT_BOTH,
    INTENT_REMINDER,
    JST,
    ReminderTimeError,
)
from app.handlers import reminder_messages as msg

load_dotenv()

CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")

if not CHANNEL_SECRET:
    raise ValueError("LINE_CHANNEL_SECRET is not set.")
if not CHANNEL_ACCESS_TOKEN:
    raise ValueError("LINE_CHANNEL_ACCESS_TOKEN is not set.")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
parser = WebhookParser(CHANNEL_SECRET)


def handle_line_webhook(
    body: str,
    signature: str,
    task_service: TaskService,
    user_service: UserService,
    reminder_service: Optional[ReminderService] = None,
) -> None:
    """
    LINE Platform からの Webhook を処理するメイン関数。
    - 署名検証
    - イベントごとの処理
    reminder_service を渡さない場合は、従来通りすべてタスクとして登録する。
    """
    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        # FastAPI 側で 400 を返す想定
        print("[ERROR] Invalid LINE signature.")
        return

    for event in events:
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessage):
            _handle_text_message(event, task_service, user_service, reminder_service)
        elif isinstance(event, PostbackEvent) and reminder_service is not None:
            _handle_postback(event, task_service, user_service, reminder_service)


def _reply(event, text: str, quick_reply=None) -> None:
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=text.strip(), quick_reply=quick_reply),
    )


def _resolve_user(event, user_service: UserService) -> Optional[Tuple[User, Dict[str, Any]]]:
    """
    LINE ユーザーを内部ユーザーに解決する。初期設定が済んでいなければ案内を返信して None。
    """
    line_user_id = event.source.user_id
    try:
        user = user_service.register_user(line_user_id)
        print(f"[INFO] User resolved: internal_user_id={user.id}")
    except Exception as e:
        print(f"[ERROR] register_user failed: line_user_id={line_user_id}, error={e}")
        raise

    try:
        user_config = user_service.get_user_config(user.id)
        print(f"[INFO] user_config loaded: linear_team_id={user_config.get('linear_team_id')}, has_llm_key={bool(user_config.get('llm_api_key'))}, has_linear_key={bool(user_config.get('linear_api_key'))}")
    except Exception as e:
        print(f"[ERROR] get_user_config failed: user_id={user.id}, error={e}")
        raise

    if not user_service.has_task_integration(user_config):
        print(f"[INFO] Task integration not configured for user_id={user.id}. Sending setup prompt.")
        _reply(event, "こんにちは。利用を開始するには Linear と LLM の初期設定が必要です。設定完了後にもう一度メッセージを送ってください。")
        return None

    return user, user_config


def _handle_text_message(
    event: MessageEvent,
    task_service: TaskService,
    user_service: UserService,
    reminder_service: Optional[ReminderService] = None,
) -> None:
    text = event.message.text.strip()
    print(f"[INFO] LINE message received: line_user_id={event.source.user_id}, text={text!r}")

    resolved = _resolve_user(event, user_service)
    if resolved is None:
        return
    user, user_config = resolved

    if reminder_service is None:
        task = _create_task(task_service, text, user_config, user.id)
        _reply(event, msg.fmt_task_registered(task))
        return

    if _handle_command(event, text, user, user_service, reminder_service):
        return

    now = datetime.now(JST)
    result = reminder_service.classify(text, user_config, now=now)
    print(f"[INFO] Intent: {result.intent} (forced={result.forced})")

    if result.intent == INTENT_REMINDER:
        try:
            reminder = reminder_service.create_reminder(
                user_id=user.id,
                user_config=user_config,
                intake=result.intake,
                intent=result.intent,
                source_text=result.body,
                now=now,
            )
        except ReminderTimeError as e:
            print(f"[INFO] Reminder time unresolved: {e}")
            _reply(event, msg.TIME_UNKNOWN_MESSAGE)
            return
        _reply(
            event,
            msg.fmt_reminder_registered(reminder, now, has_pushover=bool(user_config.get("pushover_user_key"))),
            quick_reply=msg.reminder_quick_reply(reminder),
        )
        return

    task = _create_task(task_service, text, user_config, user.id)
    reply_text = msg.fmt_task_registered(task)

    if result.intent == INTENT_BOTH:
        # 締切つきタスク: タスクに加えて締切前のリマインドを入れる
        try:
            reminder = reminder_service.create_reminder(
                user_id=user.id,
                user_config=user_config,
                intake=result.intake,
                intent=result.intent,
                source_text=text,
                now=now,
                linear_issue_id=task.issue_id,
                linear_issue_url=task.page_url,
            )
            reply_text += "\n" + msg.fmt_alert_line(reminder, now)
            _reply(event, reply_text, quick_reply=msg.reminder_quick_reply(reminder))
            return
        except ReminderTimeError as e:
            print(f"[INFO] Deadline reminder skipped: {e}")

    _reply(event, reply_text, quick_reply=msg.task_quick_reply(task, text))


def _create_task(task_service: TaskService, text: str, user_config: Dict[str, Any], user_id: str):
    try:
        print(f"[INFO] Creating task from text: user_id={user_id}")
        task = task_service.create_task_from_text(
            text=text,
            user_config=user_config,
            source="line",
            user_id=user_id,
        )
        print(f"[INFO] Task created: title={task.title!r}, page_url={task.page_url}")
        return task
    except Exception as e:
        print(f"[ERROR] create_task_from_text failed: user_id={user_id}, error={e}")
        raise


DEPARTURE_BUFFER_PATTERN = re.compile(r"出発余裕\s*(\d+)\s*分?")


def _handle_command(
    event,
    text: str,
    user: User,
    user_service: UserService,
    reminder_service: ReminderService,
) -> bool:
    """
    設定・一覧などのコマンド。処理した場合は True。
    """
    if text in (FORCE_REMINDER_PREFIX, f"{FORCE_REMINDER_PREFIX}一覧"):
        upcoming = reminder_service.list_upcoming(user.id)
        _reply(event, msg.fmt_upcoming(upcoming), quick_reply=msg.upcoming_quick_reply(upcoming))
        return True

    m = DEPARTURE_BUFFER_PATTERN.fullmatch(text)
    if m:
        minutes = int(m.group(1))
        try:
            user_service.set_departure_buffer(user.id, minutes)
        except ValueError as e:
            _reply(event, str(e))
            return True
        _reply(event, f"出発の通知を予定の{minutes}分前にしました。")
        return True

    return False


def _handle_postback(
    event: PostbackEvent,
    task_service: TaskService,
    user_service: UserService,
    reminder_service: ReminderService,
) -> None:
    resolved = _resolve_user(event, user_service)
    if resolved is None:
        return
    user, user_config = resolved
    action, args = msg.parse_postback(event.postback.data or "")
    print(f"[INFO] LINE postback: action={action}, args={args}")
    now = datetime.now(JST)

    if action == msg.ACTION_CANCEL and args:
        reminder = reminder_service.cancel(args[0], user.id)
        _reply(event, f"取り消しました: {reminder.title}" if reminder else "リマインドが見つかりませんでした。")
        return

    if action == msg.ACTION_SHIFT and len(args) == 2:
        try:
            minutes = int(args[1])
        except ValueError:
            return
        reminder = reminder_service.shift(args[0], user.id, minutes, now=now)
        if reminder is None:
            _reply(event, "もう鳴った後か、取り消し済みなので変更できません。")
            return
        _reply(event, f"変更しました: {reminder.title}\n" + msg.fmt_alert_line(reminder, now), quick_reply=msg.reminder_quick_reply(reminder))
        return

    if action == msg.ACTION_TO_TASK and args:
        reminder = reminder_service.get(args[0], user_id=user.id)
        if reminder is None or not reminder.source_text:
            _reply(event, "リマインドが見つかりませんでした。")
            return
        reminder_service.cancel(reminder.id, user.id, reason="converted_to_task")
        task = _create_task(task_service, reminder.source_text, user_config, user.id)
        _reply(event, "リマインドを取り消して、タスクとして登録しました。\n" + msg.fmt_task_registered(task))
        return

    if action == msg.ACTION_TO_REMINDER and len(args) == 2:
        issue_id, source_text = args
        result = reminder_service.classify(f"{FORCE_REMINDER_PREFIX} {source_text}", user_config, now=now)
        try:
            reminder = reminder_service.create_reminder(
                user_id=user.id,
                user_config=user_config,
                intake=result.intake,
                intent=INTENT_REMINDER,
                source_text=result.body,
                now=now,
            )
        except ReminderTimeError:
            _reply(event, msg.TIME_UNKNOWN_MESSAGE)
            return
        _archive_issue_quietly(user_config, issue_id)
        _reply(
            event,
            "タスクを取り消して、リマインドとして登録しました。\n"
            + msg.fmt_reminder_registered(reminder, now, has_pushover=bool(user_config.get("pushover_user_key"))),
            quick_reply=msg.reminder_quick_reply(reminder),
        )
        return

    print(f"[WARN] Unknown postback: {event.postback.data!r}")


def _archive_issue_quietly(user_config: Dict[str, Any], issue_id: str) -> None:
    try:
        LinearClient(api_key=user_config.get("linear_api_key")).archive_issue(issue_id)
    except Exception as e:
        print(f"[WARN] Failed to archive Linear issue {issue_id}: {e}")
