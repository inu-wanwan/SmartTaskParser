from unittest.mock import MagicMock

from app.repositories.reminder_repository import ReminderRepository


def test_list_active_by_user_filters_in_firestore():
    db = MagicMock()
    repo = ReminderRepository(db=db)
    col = db.collection.return_value
    col.where.return_value.where.return_value.stream.return_value = iter([])

    repo.list_active_by_user("u1")

    # 過去分まで読まないよう、Firestore 側で user_id と active の両方を絞り込む
    first = col.where.call_args.kwargs["filter"]
    second = col.where.return_value.where.call_args.kwargs["filter"]
    assert (first.field_path, first.op_string, first.value) == ("user_id", "==", "u1")
    assert (second.field_path, second.op_string, second.value) == ("active", "==", True)
