import os
import logging

from dotenv import load_dotenv
from linebot import LineBotApi, WebhookParser
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FlexSendMessage, BubbleContainer, BoxComponent, TextComponent, ButtonComponent, URIAction

from typing import Any, Dict, List
from linebot.exceptions import InvalidSignatureError
from app.services.task_service import TaskService
from app.services.user_service import UserService
from app.repositories.user_repository import UserRepository

load_dotenv()

CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")

if not CHANNEL_SECRET:
    raise ValueError("LINE_CHANNEL_SECRET is not set.")
if not CHANNEL_ACCESS_TOKEN:
    raise ValueError("LINE_CHANNEL_ACCESS_TOKEN is not set.")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
parser = WebhookParser(CHANNEL_SECRET)


def handle_line_webhook(body: str, signature: str, task_service: TaskService, user_service: UserService) -> None:
    """
    LINE Platform からの Webhook を処理するメイン関数。
    - 署名検証
    - イベントごとの処理
    """
    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        # FastAPI 側で 400 を返す想定
        print("[ERROR] Invalid LINE signature.")
        return

    for event in events:
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessage):
            _handle_text_message(event, task_service, user_service)
        # ここに postback イベントなども将来足せる


def _handle_text_message(event: MessageEvent, task_service: TaskService, user_service: UserService) -> None:
    line_user_id = event.source.user_id
    text = event.message.text

    print(f"[INFO] LINE message received: line_user_id={line_user_id}, text={text!r}")

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
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text="こんにちは。利用を開始するには Linear と LLM の初期設定が必要です。設定完了後にもう一度メッセージを送ってください。"
            )
        )
        return

    # タスク登録実行
    try:
        print(f"[INFO] Creating task from text: user_id={user.id}")
        task = task_service.create_task_from_text(
            text=text,
            user_config=user_config,
            source="line",
            user_id=user.id,
        )
        print(f"[INFO] Task created: title={task.title!r}, page_url={task.page_url}")
    except Exception as e:
        print(f"[ERROR] create_task_from_text failed: user_id={user.id}, error={e}")
        raise

    # テキストメッセージを組み立て
    reply_lines = [
        f"✅ タスク登録しました！\n{task.title}",
    ]

    if task.due_date:
        reply_lines.append(f"📅 期限: {task.due_date}")

    if task.page_url:
        reply_lines.append(f"🔗 {task.page_url}")
    else:
        reply_lines.append("⚠️ URLの取得に失敗しました")

    # リストを改行で結合
    reply_text = "\n".join(reply_lines)

    # 返信を送信
    try:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_text.strip())
        )
        print(f"[INFO] Reply sent successfully: user_id={user.id}")
    except Exception as e:
        print(f"[ERROR] reply_message failed: user_id={user.id}, error={e}")
        raise
