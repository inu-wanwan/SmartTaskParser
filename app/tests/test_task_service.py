from app.services import task_service as task_service_module


def test_create_task_from_text_uses_llm_and_linear(monkeypatch):
    def mock_parse_task_text(text):
        assert "スライド" in text
        return {
            "title": "研究スライド修正",
            "due_date": "2026-03-07",
            "priority": 2,
            "description": "発表用のスライドを更新",
            "label": "Research",
        }

    def mock_create_linear_issue(title, due_date, description, priority, project_id):
        assert title == "研究スライド修正"
        assert due_date.isoformat() == "2026-03-07"
        assert description == "発表用のスライドを更新"
        assert priority == 2
        assert project_id == "484c0d7b-f027-4a08-b433-6e9984b50436"
        return "https://linear.app/example/issue/ABC-123"

    monkeypatch.setattr(task_service_module.llm_client, "parse_task_text", mock_parse_task_text, raising=False)
    monkeypatch.setattr(task_service_module.linear_client, "create_linear_issue", mock_create_linear_issue, raising=False)

    task = task_service_module.create_task_from_text(
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


def test_get_daily_tasks_grouped_linear_groups_by_priority_state_and_cycle(monkeypatch):
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

    monkeypatch.setattr(task_service_module.linear_client, "fetch_daily_summary_data", lambda: raw_data, raising=False)

    grouped = task_service_module.get_daily_tasks_grouped_linear()

    assert grouped["cycle"]["id"] == "cycle-1"
    assert [i["id"] for i in grouped["urgent_overdue"]] == ["1"]
    assert [i["id"] for i in grouped["in_progress"]] == ["2"]
    assert [i["id"] for i in grouped["current_cycle_todo"]] == ["3"]
    assert [i["id"] for i in grouped["triage"]] == ["t1"]

    
