from unittest.mock import MagicMock

from app.repositories.user_repository import UserRepository


def _repository_with_mock_db() -> tuple[UserRepository, MagicMock]:
    repository = UserRepository.__new__(UserRepository)
    repository.db = MagicMock()
    repository.collection_name = "users"
    return repository, repository.db.collection.return_value


def _assert_line_user_filter(collection: MagicMock, line_user_id: str) -> None:
    collection.where.assert_called_once()
    assert collection.where.call_args.args == ()
    field_filter = collection.where.call_args.kwargs["filter"]
    assert field_filter.field_path == "line_user_id"
    assert field_filter.op_string == "=="
    assert field_filter.value == line_user_id


def test_get_doc_ref_by_line_user_id_uses_keyword_filter():
    repository, collection = _repository_with_mock_db()
    query = collection.where.return_value
    query.limit.return_value.stream.return_value = iter([])

    repository.get_doc_ref_by_line_user_id("U123")

    _assert_line_user_filter(collection, "U123")


def test_find_doc_by_line_user_id_uses_keyword_filter():
    repository, collection = _repository_with_mock_db()
    query = collection.where.return_value
    query.limit.return_value.stream.return_value = iter([])

    repository._find_doc_by_line_user_id("U123")

    _assert_line_user_filter(collection, "U123")
