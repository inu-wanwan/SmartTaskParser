from typing import Dict, Any, List, Optional
from linebot import LineBotApi
from linebot.models import TextSendMessage
from datetime import datetime, date
from zoneinfo import ZoneInfo
import os
from dotenv import load_dotenv

from app.base.base_service import BaseService

load_dotenv()

CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
CRON_SECRET_TOKEN = os.getenv("CRON_SECRET_TOKEN")

if not CHANNEL_SECRET:
    raise ValueError("LINE_CHANNEL_SECRET is not set.")
if not CHANNEL_ACCESS_TOKEN:
    raise ValueError("LINE_CHANNEL_ACCESS_TOKEN is not set.")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
JST = ZoneInfo("Asia/Tokyo")

class LinePushService(BaseService):
    def __init__(self) -> None:
        super().__init__()
        self.line_bot_api = line_bot_api

    def verify_cron_token(self, token: str) -> bool:
        """
        CRON ジョブからのリクエストに含まれるトークンを検証する。
        """
        if not CRON_SECRET_TOKEN:
            raise ValueError("CRON_SECRET_TOKEN is not set.")
        if token != CRON_SECRET_TOKEN:
            raise PermissionError("Invalid CRON secret token.")
        return True

    def build_daily_summary(self, data: Dict[str, Any]) -> str:
        """
        LinearのデータをLINE送信用メッセージに組み立てる。
        """
        lines: List[str] = ["📅 LINEAR DAILY FOCUS", ""]

        cycle = data.get("cycle")
        if cycle:
            progress = int(cycle.get("progress", 0) * 100)
            bar = "#" * (progress // 10) + "." * (10 - (progress // 10))
            lines.append(f"Progress \n{bar} {progress}%")
            lines.append("")

        has_any = False
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
                    lines.append(self._fmt_task(task))
                lines.append("")

        if not has_any:
            return "📅 LINEAR DAILY FOCUS\n\n Progress\n ##########\n\n現在進行中のタスクはありません。"

        return "\n".join(lines).strip()

    def push_daily_summary(self, user_id: str, grouped: Dict[str, List[Dict[str, Any]]]) -> None:
        """
        LINE ユーザーに日次タスクサマリーをプッシュ送信する。
        """

        message_text = self.build_daily_summary(grouped)
        self.line_bot_api.push_message(
            to=user_id,
            messages=TextSendMessage(text=message_text),
        )

    @staticmethod
    def _fmt_due(due: Optional[str]) -> str:
        if not due:
            return ""
        try:
            if len(due) == 10:
                dt = datetime.strptime(due, "%Y-%m-%d").date()
            else:
                dt = datetime.fromisoformat(due.replace("Z", "+00:00")).astimezone(JST).date()
            return dt.strftime("%m/%d (%a)")
        except Exception:
            return due

    def _fmt_task(self, task: Dict[str, Any]) -> str:
        priority = task.get("priority")
        state_type = (task.get("state") or {}).get("type")

        if priority == 1:
            mark = "!"
        elif state_type == "started":
            mark = "･"
        elif state_type == "triage":
            mark = "?"
        else:
            mark = "-"

        title = task.get("title", "No Title")
        res = f"{mark} {title}"

        due_str = task.get("dueDate")
        if due_str:
            due_date = date.fromisoformat(due_str)
            rel_date = self._get_relative_date(due_date)
            res += f"\n └ Due: {due_date.strftime('%m/%d')}{rel_date}"
        elif state_type == "triage":
            res += "\n  (Inbox/Triage)"
        return res

    @staticmethod
    def _get_relative_date(due_date: date) -> str:
        diff = (due_date - date.today()).days
        if diff == 0:
            return " [今日]"
        if diff == -1:
            return " [昨日]"
        if diff < 0:
            return f" [{abs(diff)}日前]"
        return ""


line_push_service = LinePushService()

def get_line_push_service() -> LinePushService:
    return line_push_service


def verify_cron_token(token: str) -> bool:
    return line_push_service.verify_cron_token(token)


def build_daily_summary(data: Dict[str, Any]) -> str:
    return line_push_service.build_daily_summary(data)


def push_daily_summary(user_id: str, grouped: Dict[str, List[Dict[str, Any]]]) -> None:
    line_push_service.push_daily_summary(user_id=user_id, grouped=grouped)
