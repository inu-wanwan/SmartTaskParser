from unittest.mock import MagicMock

import pytest

from app.routers.daily import daily_push
from app.services.line_push_service import LinePushService
from app.utils.line import is_valid_line_user_id


def test_line_user_id_format():
    assert is_valid_line_user_id("U" + "a" * 32)
    assert not is_valid_line_user_id("32e94fa9-7ef5-4514-906d-a3103b365094")
    assert not is_valid_line_user_id("U123")
    assert not is_valid_line_user_id(None)


def test_push_daily_summary_rejects_invalid_line_user_id():
    service = LinePushService.__new__(LinePushService)
    service.line_bot_api = MagicMock()

    with pytest.raises(ValueError, match="Invalid LINE user ID"):
        service.push_daily_summary(user_id="internal-uuid", grouped={})

    service.line_bot_api.push_message.assert_not_called()


def test_daily_push_skips_empty_user_config():
    task_service = MagicMock()
    line_push_service = MagicMock()
    user_service = MagicMock()
    user_service.get_all_users.return_value = {"invalid-user": {}}

    result = daily_push(
        cron_token="cron-token",
        task_service=task_service,
        line_push_service=line_push_service,
        user_service=user_service,
    )

    assert result == {
        "results": [{"user_id": "invalid-user", "status": "skipped"}]
    }
    task_service.get_daily_tasks_grouped_linear.assert_not_called()
    line_push_service.push_daily_summary.assert_not_called()
