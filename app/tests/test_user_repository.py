from unittest.mock import MagicMock, patch

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


def test_get_all_users_only_decrypts_requested_secrets():
    repository, collection = _repository_with_mock_db()
    doc = MagicMock()
    doc.id = "internal-user-id"
    doc.to_dict.return_value = {
        "line_user_id": "U123",
        "linear_api_key": "encrypted-linear-key",
        "llm_api_key": "encrypted-llm-key",
        "notion_api_key": "invalid-notion-key",
    }
    collection.stream.return_value = iter([doc])

    with patch.object(repository, "_safe_decrypt", return_value="linear-key") as decrypt:
        users = repository.get_all_users(decrypt_fields={"linear_api_key"})

    decrypt.assert_called_once_with("linear_api_key", "encrypted-linear-key")
    assert users == {
        "U123": {
            "id": "internal-user-id",
            "line_user_id": "U123",
            "linear_api_key": "linear-key",
        }
    }
