from unittest.mock import MagicMock, patch

import pytest

import app.services.user_service as us_module
from app.models.user import User
from app.services.user_service import UserService


VIEW = {
    "id": "view-uuid",
    "name": "Current cycle for me",
    "slugId": "abc123def456",
    "modelName": "Issue",
    "organization": {"urlKey": "example"},
}


def _service_with_user(linear_api_key="lin_test_key"):
    repository = MagicMock()
    repository.get_user_by_id.return_value = User(id="user-1", line_user_id="U" + "a" * 32, linear_api_key=linear_api_key)
    return UserService(user_repository=repository), repository


def test_view_id_candidates_from_url():
    candidates = UserService._view_id_candidates(
        "https://linear.app/example/view/current-cycle-for-me-abc123def456?foo=bar"
    )
    assert candidates == ["current-cycle-for-me-abc123def456", "abc123def456"]


def test_view_id_candidates_from_raw_id():
    assert UserService._view_id_candidates(" view-uuid ") == ["view-uuid", "uuid"]


def test_setup_linear_view_saves_resolved_id_from_url():
    """
    URL の末尾セグメントで見つからなくても slugId で解決し、正規の ID を保存する。
    """
    service, repository = _service_with_user()
    mock_client = MagicMock()
    mock_client.fetch_custom_view.side_effect = [Exception("Entity not found"), VIEW]

    with patch.object(us_module, "LinearClient", wraps=us_module.LinearClient) as mock_cls:
        mock_cls.return_value = mock_client
        mock_cls.build_view_url = us_module.LinearClient.build_view_url
        result = service.setup_linear_view(
            user_id="user-1",
            view_ref="https://linear.app/example/view/current-cycle-for-me-abc123def456",
        )

    assert mock_client.fetch_custom_view.call_args_list[1].args == ("abc123def456",)
    repository.update_user_doc.assert_called_once_with("user-1", {"linear_view_id": "view-uuid"})
    assert result == {
        "id": "view-uuid",
        "name": "Current cycle for me",
        "url": "https://linear.app/example/view/abc123def456",
    }


def test_setup_linear_view_rejects_non_issue_view():
    service, repository = _service_with_user()
    mock_client = MagicMock()
    mock_client.fetch_custom_view.return_value = {**VIEW, "modelName": "Project"}

    with patch.object(us_module, "LinearClient", return_value=mock_client):
        with pytest.raises(ValueError, match="issue view"):
            service.setup_linear_view(user_id="user-1", view_ref="view-uuid")

    repository.update_user_doc.assert_not_called()


def test_setup_linear_view_requires_linear_integration():
    service, repository = _service_with_user(linear_api_key=None)

    with pytest.raises(ValueError, match="Linear integration"):
        service.setup_linear_view(user_id="user-1", view_ref="view-uuid")

    repository.update_user_doc.assert_not_called()
