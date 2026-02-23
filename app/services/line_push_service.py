from typing import Dict, Any, List, Optional
from linebot import LineBotApi, WebhookParser
from linebot.models import TextSendMessage
from datetime import datetime, date
from zoneinfo import ZoneInfo
import os
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

load_dotenv()

CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
CRON_SECRET_TOKEN = os.getenv("CRON_SECRET_TOKEN")

# Linearスタイルの優先度アイコン
PRIORITY_ICONS = {
    1: "⚡", # Urgent
    2: "🔴", # High
    3: "🟡", # Medium
    4: "🟢", # Low
    0: "⚪", # No Priority
}

# ステータス別のアイコン
STATE_ICONS = {
    "started": "🔵",    # In Progress
    "unstarted": "⚪",  # Todo
    "triage": "❓",     # Triage
    "backlog": "📥",    # Backlog
}


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
    """タスクを2行のミニマル形式に整形する"""
    priority = task.get("priority")
    state_type = (task.get("state") or {}).get("type")
    
    # 記号の選定
    if priority == 1:
        mark = "!" # Urgent
    elif state_type == "started":
        mark = "･" # In Progress
    elif state_type == "triage":
        mark = "?" # Triage
    else:
        mark = "-" # Todo / Others

    title = task.get("title", "No Title")
    
    # 1行目: 状態記号 + タイトル
    res = f"{mark} {title}"
    
    # 2行目: 期限情報
    due_str = task.get("dueDate")
    if due_str:
        due_date = date.fromisoformat(due_str)
        rel_date = _get_relative_date(due_date)
        res += f"\n └ Due: {due_date.strftime('%m/%d')}{rel_date}"
    elif state_type == "triage":
        res += "\n  (Inbox/Triage)"
        
    return res

def _get_relative_date(due_date: date) -> str:
    diff = (due_date - date.today()).days
    if diff == 0:
        return " [今日]"
    if diff == -1:
        return " [昨日]"
    if diff < 0:
        return f" [{abs(diff)}日前]"
    return ""

def build_daily_summary(data: Dict[str, Any]) -> str:
    """
    LinearのデータをLINE送信用メッセージに組み立てる
    """
    lines: List[str] = ["📅 LINEAR DAILY FOCUS", ""]
    
    # サイクル進捗バー（あれば）
    cycle = data.get("cycle")
    if cycle:
        progress = int(cycle.get("progress", 0) * 100)
        # メカニカルな進行バー表示
        bar = "#" * (progress // 10) + "." * (10 - (progress // 10))
        lines.append(f"Progress \n{bar} {progress}%")
        lines.append("")

    has_any = False
    
    # 各セクションの定義
    sections = [
        ("urgent_overdue", "⚠️[ATTENTION]"),
        ("in_progress", "🔵[IN PROGRESS]"),
        ("current_cycle_todo", "👉[NEXT IN CYCLE]"),
        ("triage", "📥[INBOX]"),
    ]

    for key, label in sections:
        tasks = data.get(key, [])
        if tasks:
            has_any = True
            lines.append(label)
            for task in tasks:
                lines.append(_fmt_task(task))
            lines.append("")

    if not has_any:
        return "■ LINEAR DAILY FOCUS\n\n✨ Inbox zero.\n現在進行中のタスクはありません。"

    return "\n".join(lines).strip()

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