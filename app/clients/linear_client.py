import os
from datetime import date
from typing import Any, Dict, Optional, List
import requests

from dotenv import load_dotenv

load_dotenv()

LINEAR_API_KEY = os.getenv("LINEAR_API_KEY")
LINEAR_TEAM_ID = os.getenv("LINEAR_TEAM_ID")
LINEAR_USER_ID = os.getenv("LINEAR_USER_ID")

if not LINEAR_API_KEY:
    raise ValueError("Environment variable LINEAR_API_KEY is not set.")
if not LINEAR_TEAM_ID:
    raise ValueError("Environment variable LINEAR_TEAM_ID is not set.")
if not LINEAR_USER_ID:
    raise ValueError("Environment variable LINEAR_USER_ID is not set.")

def call_linear_api(query:str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Linear API を呼び出すためのユーティリティ関数。
    GraphQL クエリと変数を受け取り、API にリクエストを送る。
    """
    url = "https://api.linear.app/graphql"
    headers = {
        "Authorization": LINEAR_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "query": query,
        "variables": variables or {},
    }

    response = requests.post(url, json=payload, headers=headers)
    data = response.json()
    response.raise_for_status()  # HTTP エラーがあれば例外を発生させる
    if response.status_code != 200:
        raise Exception(f"Linear API returned status code {response.status_code}: {response.text}")
    return data["data"]

def create_linear_issue(
    title: str,
    due_date: Optional[date],
    description: Optional[str],
    priority: str = 0,
    project_id: Optional[str] = None,
) -> str:
    """
    Linear に新しい Issue を作成する関数。
    タイトル、期限、優先度、メモ、カテゴリを受け取り、Linear API を呼び出して Issue を作成する。
    成功したら作成された Issue の URL を返す。
    """
    query = """
    mutation CreateIssue($input: IssueCreateInput!) {
      issueCreate(input: $input) {
        success
        issue {
          id
          url
        }
      }
    }
    """
    variables = {
        "input": {
            "teamId": LINEAR_TEAM_ID,
            "title": title,
            "description": description or "",
            "dueDate": due_date.isoformat() if due_date else None,
            "priority": priority,  # Linear の優先度は 0 (lowest) から 4 (highest) までの整数
            "assigneeId": LINEAR_USER_ID,  # とりあえず自分にアサイン
            "projectId": project_id,  # プロジェクト ID があれば指定
        }
    }
    data = call_linear_api(query, variables)
    issue_data = data["issueCreate"]["issue"]
    return issue_data["url"]

def fetch_daily_summary_data() -> Dict[str, Any]:
    """
    自分にアサインされた未完了タスクと、チームのアクティブサイクル情報を取得する。
    """
    query = """
    query GetDailySummary($userId: String!, $teamId: String!) {
      user(id: $userId) {
        assignedIssues(filter: { state: { type: { neq: "completed" } } }) {
          nodes {
            id
            identifier
            title
            priority
            dueDate
            state { type name }
            cycle { id name progress }
            project { name }
          }
        }
      }
      team(id: $teamId) {
        activeCycle {
          id
          name
          progress
        }
        issues(filter: { state: { type: { eq: "triage" } } }) {
          nodes {
            id
            identifier
            title
          }
        }
      }
    }
    """
    variables = {
        "userId": LINEAR_USER_ID,
        "teamId": LINEAR_TEAM_ID
    }
    return call_linear_api(query, variables)