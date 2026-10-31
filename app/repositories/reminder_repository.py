from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from app.models.reminder import Reminder


class ReminderRepository:
    """
    Firestore の reminders コレクションを扱う。

    dispatch が拾う対象は next_at フィールドを持つドキュメントだけにしてある。
    対応が終わったリマインドは next_at をフィールドごと消すので、
    「next_at <= 現在時刻」の単一フィールド検索だけで済み、複合インデックスが要らない。
    """

    collection_name = "reminders"

    def __init__(self, db=None) -> None:
        # UserRepository が firebase_admin を初期化済みである前提
        self.db = db or firestore.client(database_id="stpmultiuser")

    def _col(self):
        return self.db.collection(self.collection_name)

    @staticmethod
    def _to_doc(reminder: Reminder) -> Dict[str, Any]:
        data = reminder.model_dump(exclude={"id"}, exclude_none=True)
        return data

    @staticmethod
    def _from_doc(doc) -> Reminder:
        data = doc.to_dict() or {}
        data["id"] = doc.id
        return Reminder(**data)

    def create(self, reminder: Reminder) -> Reminder:
        if reminder.created_at is None:
            reminder = reminder.model_copy(update={"created_at": datetime.now(timezone.utc)})
        ref = self._col().document()
        ref.set(self._to_doc(reminder))
        return reminder.model_copy(update={"id": ref.id})

    def get(self, reminder_id: str) -> Optional[Reminder]:
        doc = self._col().document(reminder_id).get()
        if not doc.exists:
            return None
        return self._from_doc(doc)

    def update(self, reminder_id: str, fields: Dict[str, Any]) -> None:
        """
        値が None のフィールドは Firestore から削除する（next_at を消す用途）。
        """
        payload = {k: (firestore.DELETE_FIELD if v is None else v) for k, v in fields.items()}
        self._col().document(reminder_id).update(payload)

    def list_due(self, now: datetime) -> List[Reminder]:
        docs = self._col().where(filter=FieldFilter("next_at", "<=", now)).stream()
        return [self._from_doc(d) for d in docs]

    def list_active_by_user(self, user_id: str) -> List[Reminder]:
        """
        ユーザーの終わっていないリマインドだけを返す。
        等価条件2つの組み合わせなので、単一フィールドのインデックスだけで処理できる。
        """
        docs = (
            self._col()
            .where(filter=FieldFilter("user_id", "==", user_id))
            .where(filter=FieldFilter("active", "==", True))
            .stream()
        )
        return [self._from_doc(d) for d in docs]
