from app.services.line_push_service import build_daily_summary


def test_build_daily_summary_no_none_and_skip_empty_sections():
    grouped = {
        "overdue": [],
        "today": [{"title": "タスクA", "due": "2025-12-14"}],
        "upcoming": [],
        "no_due": [],
    }

    msg = build_daily_summary(grouped)

    # None を出さない
    assert "None" not in msg

    # Todayセクションは出る
    assert "Today" in msg
    assert "タスクA" in msg

    # 空セクションは出さない（実装がそうなっている前提）
    assert "Overdue" not in msg
    assert "Upcoming" not in msg
    assert "No Due" not in msg


def test_build_daily_summary_all_empty_nice_message():
    grouped = {"overdue": [], "today": [], "upcoming": [], "no_due": []}
    msg = build_daily_summary(grouped)

    assert "🎉 Nice!" in msg
    assert "None" not in msg
