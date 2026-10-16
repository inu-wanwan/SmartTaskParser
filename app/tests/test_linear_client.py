import re
from unittest.mock import patch

from app.clients.linear_client import LinearClient


def test_fetch_daily_summary_excludes_inactive_states():
    """
    fetch_daily_summary のクエリが completed / canceled / backlog の
    タスクを assignedIssues から除外していることを確認する。
    """
    client = LinearClient(api_key="lin_test_key", team_id="team-123", user_id="user-123")

    with patch.object(LinearClient, "execute", return_value={}) as mock_execute:
        client.fetch_daily_summary()

    query, variables = mock_execute.call_args.args
    match = re.search(r"assignedIssues\(filter: \{ state: \{ type: \{ nin: \[(.*?)\]", query)
    assert match is not None
    excluded = {s.strip().strip('"') for s in match.group(1).split(",")}
    assert excluded == {"completed", "canceled", "backlog"}
    assert variables == {"userId": "user-123", "teamId": "team-123"}


def test_fetch_custom_view_queries_view_issues():
    client = LinearClient(api_key="lin_test_key")
    view = {"id": "view-1", "slugId": "abc123", "organization": {"urlKey": "example"}}

    with patch.object(LinearClient, "execute", return_value={"customView": view}) as mock_execute:
        result = client.fetch_custom_view("view-1")

    query, variables = mock_execute.call_args.args
    assert "customView(id: $viewId)" in query
    assert "issues(" in query
    assert variables == {"viewId": "view-1"}
    assert result == view
    assert LinearClient.build_view_url(view) == "https://linear.app/example/view/abc123"
