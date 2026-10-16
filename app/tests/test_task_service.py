import pytest
from unittest.mock import MagicMock, patch
from datetime import date

from app.clients.linear_client import LinearClient
from app.services.task_service import TaskService


# テスト用のダミーユーザー設定
USER_CONFIG = {
    "linear_api_key": "lin_test_key",
    "linear_team_id": "team-123",
    "linear_user_id": "user-123",
    "llm_api_key": "llm_test_key",
}


@pytest.fixture
def service():
    mock_prompt_builder = MagicMock()
    mock_prompt_builder.build.side_effect = lambda text, project_context: text
    return TaskService(prompt_builder=mock_prompt_builder)


def test_create_task_from_text_uses_llm_and_linear(service):
    """
    create_task_from_text が LLM・Linear API を正しく呼び出し、
    プロジェクトIDを含む Task を返すことを確認する。
    """
    mock_llm = MagicMock()
    mock_llm.parse_task_text.return_value = {
        "title": "研究スライド修正",
        "dueDate": "2026-03-07",
        "priority": 2,
        "description": "発表用のスライドを更新",
        "project_name": "Research",
    }

    mock_linear_client = MagicMock()
    mock_linear_client.create_linear_issue.return_value = "https://linear.app/example/issue/ABC-123"

    mock_linear_service = MagicMock()
    mock_linear_service.get_project_context.return_value = "プロジェクト一覧:\n- Research: 研究関連"
    mock_linear_service.resolve_ids.return_value = {
        "title": "研究スライド修正",
        "dueDate": "2026-03-07",
        "priority": 2,
        "description": "発表用のスライドを更新",
        "projectId": "484c0d7b-f027-4a08-b433-6e9984b50436",
        "stateId": None,
        "assigneeId": "user-123",
    }

    import app.services.task_service as ts_module

    with patch.object(ts_module, "LLMClient", return_value=mock_llm), \
         patch.object(ts_module, "LinearClient", return_value=mock_linear_client), \
         patch.object(ts_module, "LinearService", return_value=mock_linear_service):

        task = service.create_task_from_text(
            text="明日の午前までに研究のスライド直す",
            user_config=USER_CONFIG,
            source="test",
            user_id="test-user",
        )

    assert task.title == "研究スライド修正"
    assert task.due_date == date(2026, 3, 7)
    assert task.priority == 2
    assert task.description == "発表用のスライドを更新"
    assert task.source == "test"
    assert task.user_id == "test-user"
    assert task.project_id == "484c0d7b-f027-4a08-b433-6e9984b50436"
    assert task.page_url == "https://linear.app/example/issue/ABC-123"

    # ensure_synced が get_project_context より先に呼ばれていることを確認
    call_order = mock_linear_service.method_calls
    method_names = [c[0] for c in call_order]
    assert method_names.index("ensure_synced") < method_names.index("get_project_context")


def test_get_daily_tasks_grouped_linear_groups_by_priority_state_and_cycle(service):
    """
    get_daily_tasks_grouped_linear が優先度・ステータス・サイクルで
    正しくグループ分けされることを確認する。
    """
    raw_data = {
        "user": {
            "assignedIssues": {
                "nodes": [
                    {
                        "id": "1",
                        "title": "Urgent task",
                        "priority": 1,
                        "dueDate": None,
                        "state": {"type": "unstarted"},
                        "cycle": {"id": "cycle-1"},
                    },
                    {
                        "id": "2",
                        "title": "In progress task",
                        "priority": 3,
                        "dueDate": None,
                        "state": {"type": "started"},
                        "cycle": {"id": "cycle-1"},
                    },
                    {
                        "id": "3",
                        "title": "Cycle todo task",
                        "priority": 3,
                        "dueDate": None,
                        "state": {"type": "unstarted"},
                        "cycle": {"id": "cycle-1"},
                    },
                ]
            }
        },
        "team": {
            "activeCycle": {"id": "cycle-1", "name": "Current Cycle", "progress": 0.5},
            "issues": {"nodes": [{"id": "t1", "title": "Triage item"}]},
        },
    }

    mock_linear_client = MagicMock()
    mock_linear_client.fetch_daily_summary.return_value = raw_data

    import app.services.task_service as ts_module

    with patch.object(ts_module, "LinearClient", return_value=mock_linear_client):
        grouped = service.get_daily_tasks_grouped_linear(user_config=USER_CONFIG)

    assert grouped["cycle"]["id"] == "cycle-1"
    assert [i["id"] for i in grouped["urgent_overdue"]] == ["1"]
    assert [i["id"] for i in grouped["in_progress"]] == ["2"]
    assert [i["id"] for i in grouped["current_cycle_todo"]] == ["3"]
    assert [i["id"] for i in grouped["triage"]] == ["t1"]
    assert grouped["view_url"] is None


def _raw_daily_summary():
    return {
        "user": {
            "assignedIssues": {
                "nodes": [
                    {"id": "a1", "title": "Not in view", "priority": 3, "dueDate": None,
                     "state": {"type": "started"}, "cycle": None},
                ]
            }
        },
        "team": {
            "activeCycle": {"id": "cycle-1", "name": "Current Cycle", "progress": 0.5},
            "issues": {"nodes": [{"id": "t1", "title": "Triage item"}]},
        },
    }


def test_get_daily_tasks_grouped_linear_uses_view_issues_and_url(service):
    """
    linear_view_id が設定されている場合、assignedIssues ではなくビューの課題を分類し、
    ビューの URL を付与することを確認する。
    """
    view = {
        "id": "view-1",
        "name": "Current cycle for me",
        "slugId": "abc123",
        "modelName": "Issue",
        "organization": {"urlKey": "example"},
        "issues": {
            "nodes": [
                {"id": "v1", "title": "In progress", "priority": 3, "dueDate": None,
                 "state": {"type": "started"}, "cycle": {"id": "cycle-1"}},
                # 別チームのサイクルでも、ビューに含まれていれば NEXT に載せる
                {"id": "v2", "title": "Todo", "priority": 3, "dueDate": None,
                 "state": {"type": "unstarted"}, "cycle": {"id": "other-cycle"}},
                {"id": "v3", "title": "Done", "priority": 1, "dueDate": None,
                 "state": {"type": "completed"}, "cycle": {"id": "cycle-1"}},
                {"id": "v4", "title": "Canceled", "priority": 3, "dueDate": None,
                 "state": {"type": "canceled"}, "cycle": {"id": "cycle-1"}},
            ]
        },
    }

    mock_linear_client = MagicMock()
    mock_linear_client.fetch_daily_summary.return_value = _raw_daily_summary()
    mock_linear_client.fetch_custom_view.return_value = view

    import app.services.task_service as ts_module

    with patch.object(ts_module, "LinearClient", wraps=LinearClient) as mock_cls:
        mock_cls.return_value = mock_linear_client
        mock_cls.build_view_url = LinearClient.build_view_url
        grouped = service.get_daily_tasks_grouped_linear(user_config={**USER_CONFIG, "linear_view_id": "view-1"})

    mock_linear_client.fetch_custom_view.assert_called_once_with("view-1")
    assert grouped["view_url"] == "https://linear.app/example/view/abc123"
    assert grouped["urgent_overdue"] == []
    assert [i["id"] for i in grouped["in_progress"]] == ["v1"]
    assert [i["id"] for i in grouped["current_cycle_todo"]] == ["v2"]
    assert [i["id"] for i in grouped["triage"]] == ["t1"]


def test_get_daily_tasks_grouped_linear_falls_back_when_view_fetch_fails(service):
    """
    ビューの取得に失敗しても日報は止めず、assignedIssues で分類することを確認する。
    """
    mock_linear_client = MagicMock()
    mock_linear_client.fetch_daily_summary.return_value = _raw_daily_summary()
    mock_linear_client.fetch_custom_view.side_effect = Exception("Entity not found")

    import app.services.task_service as ts_module

    with patch.object(ts_module, "LinearClient", wraps=LinearClient) as mock_cls:
        mock_cls.return_value = mock_linear_client
        mock_cls.build_view_url = LinearClient.build_view_url
        grouped = service.get_daily_tasks_grouped_linear(user_config={**USER_CONFIG, "linear_view_id": "deleted"})

    assert grouped["view_url"] is None
    assert [i["id"] for i in grouped["in_progress"]] == ["a1"]
