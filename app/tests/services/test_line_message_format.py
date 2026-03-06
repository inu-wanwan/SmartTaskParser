from app.services.line_push_service import build_daily_summary


def test_build_daily_summary_has_expected_sections_and_task_content():
    grouped = {
        "cycle": {"progress": 0.4},
        "urgent_overdue": [
            {"title": "至急タスク", "priority": 1, "state": {"type": "unstarted"}, "dueDate": "2025-12-14"}
        ],
        "in_progress": [],
        "current_cycle_todo": [],
        "triage": [],
    }

    msg = build_daily_summary(grouped)

    assert "None" not in msg
    assert "LINEAR DAILY FOCUS" in msg
    assert "Progress" in msg
    assert "⚠️[ATTENTION]" in msg
    assert "至急タスク" in msg


def test_build_daily_summary_all_empty_inbox_zero_message():
    grouped = {
        "urgent_overdue": [],
        "in_progress": [],
        "current_cycle_todo": [],
        "triage": [],
    }
    msg = build_daily_summary(grouped)

    assert "Inbox zero." in msg
    assert "LINEAR DAILY FOCUS" in msg
    assert "None" not in msg
