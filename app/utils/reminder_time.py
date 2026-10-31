"""
リマインドの通知時刻を決める純粋関数群。

LLM には「文から何が書かれているか」だけを抽出させ、
通知時刻の計算（出発時間の逆算・予告時刻・過去時刻の扱い）はここで行う。
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")

# 文頭にこの文字列があれば、LLM の判定に関係なくリマインドとして扱う
FORCE_REMINDER_PREFIX = "リマインド"

DEFAULT_DEPARTURE_BUFFER_MIN = 45  # 外出を伴う予定は、この分数前に出発通知
DEFAULT_PRE_ALERT_MIN = 10  # 本通知のこの分数前に予告を1回鳴らす
DEFAULT_DEADLINE_LEAD_MIN = 60  # 締切つきタスク（both）は締切のこの分数前に通知

INTENT_TASK = "task"
INTENT_REMINDER = "reminder"
INTENT_BOTH = "both"
INTENTS = (INTENT_TASK, INTENT_REMINDER, INTENT_BOTH)

TYPE_DEPARTURE = "departure"
TYPE_AT_TIME = "at_time"
TYPE_DEADLINE = "deadline"


class ReminderTimeError(ValueError):
    """通知時刻を決められない（時刻が曖昧・読み取れない）ときの例外。"""


@dataclass(frozen=True)
class ReminderSchedule:
    event_at: datetime  # 予定（締切）の時刻
    fire_at: datetime  # 本通知の時刻
    pre_fire_at: Optional[datetime]  # 予告の時刻（既に過ぎている場合は None）
    reminder_type: str  # departure / at_time / deadline
    label: str  # 通知に出す種別（「出発」「リマインド」「締切」）


def split_force_prefix(text: str) -> tuple[bool, str]:
    """
    文頭の「リマインド」を検出する。

    Returns:
        (強制リマインドかどうか, 「リマインド」を取り除いた本文)
    """
    stripped = text.strip()
    if not stripped.startswith(FORCE_REMINDER_PREFIX):
        return False, stripped
    body = stripped[len(FORCE_REMINDER_PREFIX):].lstrip(" 　:：、,")
    return True, body


def parse_local_datetime(value: Any) -> Optional[datetime]:
    """
    LLM が返した日時文字列を JST の aware datetime にする。
    タイムゾーンなしの値は JST とみなす。読めない値は None。
    """
    if not value or not isinstance(value, str):
        return None
    s = value.strip().replace(" ", "T")
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    # 日付だけ（時刻なし）はリマインドの時刻として使えない
    if len(s) <= 10:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)
    return dt.astimezone(JST)


def _positive_int(value: Any) -> Optional[int]:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def compute_schedule(
    intake: Dict[str, Any],
    now: datetime,
    intent: str,
    departure_buffer_min: int = DEFAULT_DEPARTURE_BUFFER_MIN,
    pre_alert_min: int = DEFAULT_PRE_ALERT_MIN,
    deadline_lead_min: int = DEFAULT_DEADLINE_LEAD_MIN,
) -> ReminderSchedule:
    """
    受付プロンプトの出力から通知時刻を決める。

    優先順位:
      1. leave_at（文中で明示された出発時刻）
      2. lead_min（「30分前に」など明示された分数）
      3. both → 締切の deadline_lead_min 分前
      4. departure → 予定の departure_buffer_min 分前
      5. at_time → 予定時刻ちょうど
    予告は本通知の pre_alert_min 分前。既に過ぎていれば付けない。
    """
    if intake.get("time_ambiguous"):
        raise ReminderTimeError("時刻が曖昧です")

    event_at = parse_local_datetime(intake.get("event_at"))
    leave_at = parse_local_datetime(intake.get("leave_at"))
    lead_min = _positive_int(intake.get("lead_min"))
    reminder_type = intake.get("reminder_type")

    if event_at is None and leave_at is None:
        raise ReminderTimeError("時刻が読み取れません")

    if intent == INTENT_BOTH:
        if event_at is None:
            raise ReminderTimeError("締切の時刻が読み取れません")
        reminder_type = TYPE_DEADLINE
        fire_at = event_at - timedelta(minutes=lead_min or deadline_lead_min)
        label = "締切"
    elif leave_at is not None:
        reminder_type = TYPE_DEPARTURE
        fire_at = leave_at
        label = "出発"
        event_at = event_at or leave_at
    elif lead_min is not None:
        fire_at = event_at - timedelta(minutes=lead_min)
        label = "出発" if reminder_type == TYPE_DEPARTURE else "リマインド"
        reminder_type = reminder_type or TYPE_AT_TIME
    elif reminder_type == TYPE_DEPARTURE:
        fire_at = event_at - timedelta(minutes=departure_buffer_min)
        label = "出発"
    else:
        reminder_type = TYPE_AT_TIME
        fire_at = event_at
        label = "リマインド"

    pre_fire_at: Optional[datetime] = None
    if pre_alert_min > 0:
        candidate = fire_at - timedelta(minutes=pre_alert_min)
        if candidate > now:
            pre_fire_at = candidate

    return ReminderSchedule(
        event_at=event_at,
        fire_at=fire_at,
        pre_fire_at=pre_fire_at,
        reminder_type=reminder_type,
        label=label,
    )


WEEKDAYS_JA = ["月", "火", "水", "木", "金", "土", "日"]


def fmt_day_time(dt: datetime) -> str:
    """10/31(土) 15:00 形式。"""
    local = dt.astimezone(JST)
    return f"{local.month}/{local.day}({WEEKDAYS_JA[local.weekday()]}) {local:%H:%M}"


def fmt_time(dt: datetime, base: Optional[datetime] = None) -> str:
    """base と同じ日なら HH:MM、違えば日付つき。"""
    local = dt.astimezone(JST)
    if base is not None and local.date() == base.astimezone(JST).date():
        return f"{local:%H:%M}"
    return fmt_day_time(local)
