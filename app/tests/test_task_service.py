import pytest
from unittest.mock import MagicMock

from app.services.task_service import TaskService


@pytest.fixture
def service(monkeypatch):
    # 依存クライアントをモック差し替え
    mock_llm_client = MagicMock()
    mock_notion_client = MagicMock()
    mock_linear_client = MagicMock()

    import app.services.task_service as task_service_module

    monkeypatch.setattr(task_service_module, "LLMClient", lambda: mock_llm_client)
    monkeypatch.setattr(task_service_module, "NotionClient", lambda: mock_notion_client)
    monkeypatch.setattr(task_service_module, "LinearClient", lambda: mock_linear_client)

    mock_prompt_builder = MagicMock()
    mock_prompt_builder.build.side_effect = lambda text, project_context: text

    mock_linear_service = MagicMock()
    mock_linear_service.get_project_context.return_value = "Test Context"

    def resolve_ids(payload):
        data = dict(payload)
        if data.get("label") == "Research":
            data["projectId"] = "484c0d7b-f027-4a08-b433-6e9984b50436"
        return data

    mock_linear_service.resolve_ids.side_effect = resolve_ids

    return TaskService(prompt_builder=mock_prompt_builder, linear_service=mock_linear_service)


def test_create_task_from_text_uses_llm_and_linear(service):
    def mock_parse_task_text(text):
        assert "スライド" in text
        return {
            "title": "研究スライド修正",
            "dueDate": "2026-03-07",
            "priority": 2,
            "description": "発表用のスライドを更新",
            "label": "Research",
        }

    def mock_create_linear_issue(
        title,
        due_date,
        priority,
        notes,
        project_id,
        assignee_id,
        state_id,
    ):
        assert title == "研究スライド修正"
        assert due_date.isoformat() == "2026-03-07"
        assert notes == "発表用のスライドを更新"
        assert priority == 2
        assert project_id == "484c0d7b-f027-4a08-b433-6e9984b50436"
        assert assignee_id is None
        assert state_id is None
        return "https://linear.app/example/issue/ABC-123"

    service.llm_client.parse_task_text.side_effect = mock_parse_task_text
    service.linear_client.create_linear_issue.side_effect = mock_create_linear_issue

    task = service.create_task_from_text(
        "明日の午前までに研究のスライド直す",
        source="test",
        user_id="test-user",
    )

    assert task.title == "研究スライド修正"
    assert task.due_date is not None
    assert task.due_date.isoformat() == "2026-03-07"
    assert task.priority == 2
    assert task.description == "発表用のスライドを更新"
    assert task.source == "test"
    assert task.user_id == "test-user"
    assert task.project_id == "484c0d7b-f027-4a08-b433-6e9984b50436"
    assert task.page_url == "https://linear.app/example/issue/ABC-123"


def test_get_daily_tasks_grouped_linear_groups_by_priority_state_and_cycle(service):
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

    service.linear_client.fetch_daily_summary.return_value = raw_data

    grouped = service.get_daily_tasks_grouped_linear()

    assert grouped["cycle"]["id"] == "cycle-1"
    assert [i["id"] for i in grouped["urgent_overdue"]] == ["1"]
    assert [i["id"] for i in grouped["in_progress"]] == ["2"]
    assert [i["id"] for i in grouped["current_cycle_todo"]] == ["3"]
    assert [i["id"] for i in grouped["triage"]] == ["t1"]
