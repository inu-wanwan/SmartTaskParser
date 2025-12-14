from typing import Dict, Any, List, Optional
from linebot import LineBotApi, WebhookParser
from linebot.models import TextSendMessage
from datetime import datetime
import os
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

load_dotenv()

CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
CRON_SECRET_TOKEN = os.getenv("CRON_SECRET_TOKEN")


if not CHANNEL_SECRET:
    raise ValueError("LINE_CHANNEL_SECRET is not set.")
if not CHANNEL_ACCESS_TOKEN:
    raise ValueError("LINE_CHANNEL_ACCESS_TOKEN is not set.")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
parser = WebhookParser(CHANNEL_SECRET)

JST = ZoneInfo("Asia/Tokyo")

def verify_cron_token(token: str) -> bool:
    """
    CRON ジョブからのリクエストに含まれるトークンを検証する。
    """
    if not CRON_SECRET_TOKEN:
        raise ValueError("CRON_SECRET_TOKEN is not set.")
    if token != CRON_SECRET_TOKEN:
        raise PermissionError("Invalid CRON secret token.")
    
def _fmt_due(due: Optional[str]) -> str:
    """
    期限文字列を LINE メッセージ用にフォーマットする。
    """
    if not due:
        return ""
    
    try:
        if len(due) == 10:
            dt = datetime.strptime(due, "%Y-%m-%d").date()
        else:
            dt = datetime.fromisoformat(due.replace("Z", "+00:00")).astimezone(JST).date()
        return dt.strftime("%m/%d (%a)")
    except Exception:
        return due  # フォーマット失敗時はそのまま返す
    
def _fmt_task(task: Dict[str, Any]) -> str:
    """
    タスク情報を LINE メッセージ用にフォーマットする。
    """
    due = _fmt_due(task.get("due"))
    title = task.get("title")
    
    if due:
        return f"- {title}\n └ Due: {due}"
    else:
        return f"- {title}"

def build_daily_summary(grouped: Dict[str, List[Dict[str, Any]]]) -> str:
    """
    日次タスクサマリーのメッセージ本文を組み立てる。
    """
    lines: List[str] = ["📅 Daily Task Summary", ""]

    has_any = False

    if grouped.get("overdue"):
        has_any = True
        lines.append("⚠️ Overdue")
        for task in grouped["overdue"]:
            lines.append(_fmt_task(task))
        lines.append("")

    if grouped.get("today"):
        has_any = True
        lines.append("✔︎ Today")
        for task in grouped["today"]:
            lines.append(_fmt_task(task))
        lines.append("")

    if grouped.get("upcoming"):
        has_any = True
        lines.append("👉 Upcoming")
        for task in grouped["upcoming"]:
            lines.append(_fmt_task(task))
        lines.append("")

    if grouped.get("no_due"):
        has_any = True
        lines.append("❓ No Due")
        for task in grouped["no_due"]:
            lines.append(_fmt_task(task))
        lines.append("")
    
    if not has_any:
        lines.append("🎉 Nice!")
        lines.append("今日 ~ 3日以内のタスクはありません")
        return "\n".join(lines)
    
    if not grouped.get("overdue") and not grouped.get("no_due"):
        lines.append("🎉 Nice!")
        lines.append("期限切れ・期限未設定のタスクはありません")

    return "\n".join(lines)

def push_daily_summary(grouped: Dict[str, List[Dict[str, Any]]]) -> None:
    """
    LINE ユーザーに日次タスクサマリーをプッシュ送信する。
    """
    user_id = os.getenv("LINE_USER_ID")
    if not user_id:
        raise ValueError("LINE_USER_ID is not set.")

    message_text = build_daily_summary(grouped)

    line_bot_api.push_message(
        to=user_id,
        messages=TextSendMessage(text=message_text)
    )