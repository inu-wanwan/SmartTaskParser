from datetime import datetime
from typing import Optional
from pydantic import BaseModel

# status の遷移:
#   scheduled → pre_sent → fired → acked
#   fired のまま止められなければ、30分後に dispatch が expired にする
#   どの段階からでも cancelled（取消・タスク完了済み）になりうる
STATUS_SCHEDULED = "scheduled"
STATUS_PRE_SENT = "pre_sent"
STATUS_FIRED = "fired"
STATUS_ACKED = "acked"
STATUS_CANCELLED = "cancelled"
STATUS_EXPIRED = "expired"

ACTIVE_STATUSES = (STATUS_SCHEDULED, STATUS_PRE_SENT, STATUS_FIRED)


class Reminder(BaseModel):
    id: Optional[str] = None
    user_id: str
    title: str
    label: str  # 通知に出す種別（出発 / リマインド / 締切）
    reminder_type: str  # departure / at_time / deadline
    event_at: datetime
    fire_at: datetime
    pre_fire_at: Optional[datetime] = None
    # 次に dispatch が拾う時刻。対応が終わったら None（Firestore からはフィールドごと消す）
    next_at: Optional[datetime] = None
    status: str = STATUS_SCHEDULED
    # 終わっていないリマインドだけを Firestore で絞り込むためのフラグ。
    # 一覧取得で過去分まで読むと、使うほど読み取り課金が増えるため
    active: bool = True
    place: Optional[str] = None
    source_text: Optional[str] = None
    linear_issue_id: Optional[str] = None
    linear_issue_url: Optional[str] = None
    pushover_receipt: Optional[str] = None
    created_at: Optional[datetime] = None
    fired_at: Optional[datetime] = None
    acked_at: Optional[datetime] = None
    cancelled_reason: Optional[str] = None

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_STATUSES
