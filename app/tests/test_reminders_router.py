from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import reminders


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(reminders.router)
    app.state.reminder_service = MagicMock()
    app.state.line_push_service = MagicMock()
    return TestClient(app), app.state


def test_dispatch_requires_cron_token(client):
    c, state = client
    state.line_push_service.verify_cron_token.side_effect = PermissionError()
    assert c.post("/reminders/dispatch", headers={"X-Cron-Token": "bad"}).status_code == 401
    state.reminder_service.dispatch.assert_not_called()


def test_dispatch_runs(client):
    c, state = client
    state.reminder_service.dispatch.return_value = [{"id": "r1", "result": "fired"}]
    res = c.post("/reminders/dispatch", headers={"X-Cron-Token": "ok"})
    assert res.status_code == 200
    assert res.json() == {"results": [{"id": "r1", "result": "fired"}]}


def test_pushover_callback_parses_form(client):
    c, state = client
    state.reminder_service.handle_pushover_callback.return_value = True
    res = c.post(
        "/reminders/pushover-callback?rid=r1",
        content="receipt=abc123&acknowledged=1&acknowledged_by=u",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert res.status_code == 200
    state.reminder_service.handle_pushover_callback.assert_called_once_with("r1", "abc123")
