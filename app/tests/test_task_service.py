from app.services.task_service import create_task_from_text

def test_create_task_from_text():
    task = create_task_from_text(
        "明日の午前までに研究のスライド直す",
        source="test",
        user_id="test-user",
    )

    assert isinstance(task.title, str)
    assert len(task.title) > 0
    assert "スライド" in task.title

    assert task.due_date is not None
    assert task.source == "test"
    assert task.user_id == "test-user"
    assert task.page_id is not None
    assert task.page_url is not None
    assert task.priority in ["low", "medium", "high"]

    