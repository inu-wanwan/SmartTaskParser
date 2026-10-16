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

    assert "現在進行中のタスクはありません" in msg
    assert "LINEAR DAILY FOCUS" in msg
    assert "None" not in msg


def test_build_daily_summary_appends_view_link():
    grouped = {
        "urgent_overdue": [],
        "in_progress": [{"title": "作業中", "priority": 3, "state": {"type": "started"}, "dueDate": None}],
        "current_cycle_todo": [],
        "triage": [],
        "view_url": "https://linear.app/example/view/abc123",
    }
    msg = build_daily_summary(grouped)

    assert msg.endswith("🔗 https://linear.app/example/view/abc123")


def test_build_daily_summary_appends_view_link_even_when_empty():
    grouped = {"view_url": "https://linear.app/example/view/abc123"}
    msg = build_daily_summary(grouped)

    assert "現在進行中のタスクはありません" in msg
    assert msg.endswith("🔗 https://linear.app/example/view/abc123")


def test_build_daily_summary_without_view_url_has_no_link():
    msg = build_daily_summary({"urgent_overdue": [], "in_progress": [], "current_cycle_todo": [], "triage": []})

    assert "🔗" not in msg
