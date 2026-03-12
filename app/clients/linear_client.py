import os
from datetime import date
from typing import Any, Dict, Optional, List
import requests
from app.base.base_client import BaseHTTPClient

class LinearClient(BaseHTTPClient):
	"""
	Linear API とやりとりするクライアントクラス。
	タスクの作成や、日次サマリーのデータ取得などを行う。
	"""
	def __init__(self, api_key, team_id: str = None, user_id: str = None) -> None:
		self.api_key = api_key
		self.team_id = team_id
		self.user_id = user_id
		super().__init__(base_url="https://api.linear.app/graphql")

	def _validate_env(self) -> None:
		if not self.api_key:
			raise ValueError("Linear API key is not set.")
		
	def execute(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
		headers = {
			"Authorization": self.api_key,
			"Content-Type": "application/json",
		}
		payload = {
			"query": query,
			"variables": variables or {},
		}
		response = requests.post(
			self.base_url,
			json=payload,
			headers=headers,
		)
		response.raise_for_status()
		data = response.json()
		if "errors" in data:
			raise Exception(f"Linear API error: {data['errors']}")
		
		return data["data"]

	def create_linear_issue(
		self,
		title: str,
		due_date: Optional[date] = None,
		priority: int = 0,
		notes: Optional[str] = None,
		project_id: Optional[str] = None,
		state_id: Optional[str] = None,
	) -> str:
		"""
		Linear API を呼び出して新しい Issue を作成し、URLを返す。
		"""
		if not self.team_id or not self.user_id:
			raise ValueError("Team ID and User ID must be set to create an issue.")

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
				"teamId": self.team_id,
				"title": title,
				"priority": priority,
				"description": notes or "",
				"dueDate": due_date.isoformat() if due_date else None,
				"projectId": project_id,
				"assigneeId": self.user_id,
				"stateId": state_id,
			}
		}
		data = self.execute(query, variables)
		issue_url = data["issueCreate"]["issue"]["url"]
		return issue_url
				
	def fetch_daily_summary(self) -> Dict[str, Any]:
		"""
		自分にアサインされた未完了タスクとアクティブサイクル情報を取得する。
		"""
		query = """
		query GetDailySummary($userId: String!, $teamId: String!) {
		  user(id: $userId) {
			assignedIssues(filter: { state: { type: { neq: "completed" } } }) {
			  nodes {
				id identifier title priority dueDate
				state { type name }
				cycle { id name progress }
				project { name }
			  }
			}
		  }
		  team(id: $teamId) {
			activeCycle { id name progress }
			issues(filter: { state: { type: { eq: "triage" } } }) {
			  nodes { id identifier title }
			}
		  }
		}
		"""
		variables = {
			"userId": self.user_id,
			"teamId": self.team_id
		}
		return self.execute(query, variables)
	
	def fetch_viewer_info(self) -> Dict[str, Any]:
		"""
		Viewer の情報を取得する。
		"""
		query = """
		query {
			viewer {
				id
			}
			teams {
				nodes {
					id name
				}
			}
		}
		"""
		response = self.execute(query, {})

		return {
			"user_id": response["viewer"]["id"],
			"team_id": response["teams"]["nodes"][0]["id"] if response["teams"]["nodes"] else None,
		}