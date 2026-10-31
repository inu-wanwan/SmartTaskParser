"""
LINE に返すリマインド関連のメッセージと、クイックリプライの postback データ。

postback データは「アクション|引数|引数」の形にする（LINE の上限は 300 文字）。
URL エンコードすると日本語が膨らむので使わない。
"""
from datetime import datetime
from typing import List, Optional, Tuple

from linebot.models import PostbackAction, QuickReply, QuickReplyButton

from app.models.reminder import Reminder
from app.models.task import Task
from app.utils.reminder_time import fmt_day_time, fmt_time

SEP = "|"
ACTION_CANCEL = "cancel"
ACTION_SHIFT = "shift"
ACTION_TO_TASK = "to_task"
ACTION_TO_REMINDER = "to_reminder"

POSTBACK_TEXT_LIMIT = 200  # 付け替え用に持たせる元の文の上限
QUICK_REPLY_MAX_ITEMS = 13  # LINE のクイックリプライの上限
QUICK_REPLY_LABEL_MAX = 20  # ボタンのラベルの上限


def build_postback(action: str, *args: str) -> str:
    return SEP.join([action, *args])


def parse_postback(data: str) -> Tuple[str, List[str]]:
    """
    to_reminder の最後の引数（元の文）は区切り文字を含みうるので、分割数を固定する。
    """
    action = data.split(SEP, 1)[0]
    max_parts = {ACTION_TO_REMINDER: 3, ACTION_SHIFT: 3}.get(action, 2)
    parts = data.split(SEP, max_parts - 1)
    return parts[0], parts[1:]


def reminder_quick_reply(reminder: Reminder) -> QuickReply:
    rid = reminder.id or ""
    return QuickReply(
        items=[
            QuickReplyButton(action=PostbackAction(label="取消", data=build_postback(ACTION_CANCEL, rid), display_text="取消")),
            QuickReplyButton(action=PostbackAction(label="−15分", data=build_postback(ACTION_SHIFT, rid, "-15"), display_text="15分早める")),
            QuickReplyButton(action=PostbackAction(label="+15分", data=build_postback(ACTION_SHIFT, rid, "15"), display_text="15分遅らせる")),
            QuickReplyButton(action=PostbackAction(label="タスクにする", data=build_postback(ACTION_TO_TASK, rid), display_text="タスクにする")),
        ]
    )


def upcoming_quick_reply(reminders: List[Reminder]) -> Optional[QuickReply]:
    """
    一覧の返信に、予定ごとの取消ボタンを付ける。
    登録時のボタンは次のメッセージで消えるので、後から取り消す入り口はここになる。
    """
    items = []
    for r in reminders[:QUICK_REPLY_MAX_ITEMS]:
        label = f"取消: {r.title}"
        if len(label) > QUICK_REPLY_LABEL_MAX:
            label = label[: QUICK_REPLY_LABEL_MAX - 1] + "…"
        items.append(
            QuickReplyButton(
                action=PostbackAction(
                    label=label,
                    data=build_postback(ACTION_CANCEL, r.id or ""),
                    display_text=f"取消: {r.title}"[:300],
                )
            )
        )
    return QuickReply(items=items) if items else None


def task_quick_reply(task: Task, source_text: str) -> Optional[QuickReply]:
    if not task.issue_id:
        return None
    data = build_postback(ACTION_TO_REMINDER, task.issue_id, source_text[:POSTBACK_TEXT_LIMIT])
    return QuickReply(
        items=[
            QuickReplyButton(action=PostbackAction(label="リマインドにする", data=data, display_text="リマインドにする")),
        ]
    )


def fmt_reminder_registered(reminder: Reminder, now: datetime, has_pushover: bool) -> str:
    lines = [f"⏰ リマインド登録: {reminder.title}"]
    if reminder.event_at != reminder.fire_at:
        lines.append(f"予定 {fmt_day_time(reminder.event_at)}")
    lines.append(fmt_alert_line(reminder, now))
    if not has_pushover:
        lines.append("⚠️ Pushover が未設定のため iPhone では鳴りません")
    return "\n".join(lines)


def fmt_alert_line(reminder: Reminder, now: datetime) -> str:
    if reminder.fire_at <= now:
        return f"🔔 {reminder.label}の時刻を過ぎているので、すぐ鳴らします"
    if reminder.event_at == reminder.fire_at:
        # 予定時刻ちょうどに鳴らす場合は、予定の行がないので日付から出す
        line = f"🔔 {fmt_day_time(reminder.fire_at)}"
    else:
        line = f"🔔 {reminder.label} {fmt_time(reminder.fire_at, base=reminder.event_at)}"
    if reminder.pre_fire_at:
        line += f"（予告 {fmt_time(reminder.pre_fire_at, base=reminder.fire_at)}）"
    return line


def fmt_task_registered(task: Task) -> str:
    lines = [f"✅ タスク登録しました！\n{task.title}"]
    if task.due_date:
        lines.append(f"📅 期限: {task.due_date}")
    if task.page_url:
        lines.append(f"🔗 {task.page_url}")
    else:
        lines.append("⚠️ URLの取得に失敗しました")
    return "\n".join(lines)


def fmt_upcoming(reminders: List[Reminder]) -> str:
    if not reminders:
        return "今後24時間のリマインドはありません。"
    lines = ["⏰ 今後24時間のリマインド"]
    for r in reminders:
        lines.append(f"- {fmt_day_time(r.fire_at)} {r.label}: {r.title}")
    return "\n".join(lines)


TIME_UNKNOWN_MESSAGE = (
    "時刻が読み取れなかったので、リマインドは登録していません。\n"
    "「リマインド 18時 洗濯物」のように時刻を入れて送り直してください。"
)
