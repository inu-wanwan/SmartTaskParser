import os
from datetime import date
from typing import Any, Dict, Optional, List
import requests
from app.base.base_client import BaseHTTPClient
from app.models import response

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
		return self.create_linear_issue_detail(
			title=title,
			due_date=due_date,
			priority=priority,
			notes=notes,
			project_id=project_id,
			state_id=state_id,
		)["url"]

	def create_linear_issue_detail(
		self,
		title: str,
		due_date: Optional[date] = None,
		priority: int = 0,
		notes: Optional[str] = None,
		project_id: Optional[str] = None,
		state_id: Optional[str] = None,
	) -> Dict[str, str]:
		"""
		Issue を作成し、{"id": ..., "url": ...} を返す。
		リマインドと紐づけるために Issue の ID も必要な場合はこちらを使う。
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
		issue = data["issueCreate"]["issue"]
		return {"id": issue["id"], "url": issue["url"]}

	def fetch_issue_state_type(self, issue_id: str) -> Optional[str]:
		"""
		Issue の状態の種類（backlog / unstarted / started / completed / canceled など）を返す。
		"""
		query = """
		query IssueState($id: String!) {
		  issue(id: $id) { id state { type } }
		}
		"""
		data = self.execute(query, {"id": issue_id})
		issue = data.get("issue") or {}
		return (issue.get("state") or {}).get("type")

	def archive_issue(self, issue_id: str) -> bool:
		"""
		Issue をアーカイブする（タスクとして登録したものをリマインドに付け替えたとき）。
		"""
		query = """
		mutation ArchiveIssue($id: String!) {
		  issueArchive(id: $id) { success }
		}
		"""
		data = self.execute(query, {"id": issue_id})
		return bool((data.get("issueArchive") or {}).get("success"))
				
	def fetch_daily_summary(self) -> Dict[str, Any]:
		"""
		自分にアサインされた未完了タスクとアクティブサイクル情報を取得する。
		"""
		query = """
		query GetDailySummary($userId: String!, $teamId: String!) {
		  user(id: $userId) {
			assignedIssues(filter: { state: { type: { nin: ["completed", "canceled", "backlog"] } } }) {
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
	
	def fetch_custom_view(self, view_id: str) -> Dict[str, Any]:
		"""
		カスタムビューの情報と、ビューのフィルターを適用した課題を取得する。
		"""
		query = """
		query GetCustomView($viewId: String!) {
		  customView(id: $viewId) {
			id name slugId modelName
			organization { urlKey }
			issues(first: 100) {
			  nodes {
				id identifier title priority dueDate
				state { type name }
				cycle { id name progress }
				project { name }
			  }
			}
		  }
		}
		"""
		return self.execute(query, {"viewId": view_id})["customView"]

	@staticmethod
	def build_view_url(view: Dict[str, Any]) -> str:
		"""
		カスタムビューの Web URL を組み立てる。
		"""
		return f"https://linear.app/{view['organization']['urlKey']}/view/{view['slugId']}"

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