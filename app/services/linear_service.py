from app.base.base_service import BaseService
from typing import Dict, Any
from datetime import datetime, timedelta


class LinearService(BaseService):
    def __init__(self, client, ttl_hours=24) -> None:
        super().__init__()
        self.client = client
        self.user_id = None # 自分のUUID for Assignee
        self.team_id = None # チームID
        self.state_mapping = {} # {todo: UUID, backlog: UUID}
        self.project_mapping = {} # {'研究': {'id': UUID, 'description': str}, '仕事': {'id': UUID, 'description': str}, ...}
        self.last_synced_at = None
        self.ttl_hours = ttl_hours

    def _is_stale(self) -> bool:
        """
        キャッシュしたプロジェクトや状態の情報が古くなっていないかを判定する。
        現状は単純に24時間以上経過していたら古いとみなす。
        """
        if not self.last_synced_at:
            return True
        return datetime.now() - self.last_synced_at > timedelta(hours=self.ttl_hours)
    
    def ensure_synced(self) -> None:
        """
        プロジェクトや状態の情報が古くなっていたら、Linear API から最新の情報を取得してキャッシュする。
        """
        if self._is_stale():
            print("Linear metadata is stale. Syncing...")
            self.sync_metadata()

    def sync_metadata(self) -> None:
        """
        Linear API からプロジェクトの状態やラベルの情報を取得してキャッシュする。
        """
        query = """
        query {
            viewer { id }
            workflowStates { nodes { id type name } }
            projects { nodes { id name description } }
            teams { nodes { id name } }
        }
        """
        response = self.client.execute(query, {})
        self._parse_metadata(response)
        self.last_synced_at = datetime.now()

    def _parse_metadata(self, data: Dict[str, Any]) -> None:
        self.user_id = data["viewer"]["id"]
        self.team_id = data["teams"]["nodes"][0]["id"] if data["teams"]["nodes"] else None
        for state in data["workflowStates"]["nodes"]:
            s_type = state["type"].lower() # todo, unstarted, started, completed, backlog など
            s_id = state["id"]

            if s_type == "unstarted" and "todo" not in self.state_mapping:
                self.state_mapping["todo"] = s_id
            elif s_type == "backlog" and "backlog" not in self.state_mapping:
                self.state_mapping["backlog"] = s_id

        for project in data["projects"]["nodes"]:
            self.project_mapping[project["name"]] = {
                "id": project["id"],
                "description": project["description"] or "",
            }

    def get_project_context(self) -> str:
        """
        プロジェクトの説明をまとめたテキストを返す。
        """
        lines = ["プロジェクト一覧:"]
        for name, info in self.project_mapping.items():
            desc = info["description"]
            lines.append(f"- {name}: {desc}")
        return "\n".join(lines)
    
    def resolve_ids(self, llm_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        LLM の結果からプロジェクト名や状態を解釈して、Linear API に渡すための ID に変換する。
        """
        result = llm_result.copy()
        self.ensure_synced()

        # todo or backlog の解釈
        state_str = llm_result.get("state", "todo").lower()
        if "backlog" in state_str:
            result["stateId"] = self.state_mapping.get("backlog")
        else:
            result["stateId"] = self.state_mapping.get("todo")

        # プロジェクト名の解釈
        project_name = llm_result.get("project")
        if project_name and project_name in self.project_mapping:
            result["projectId"] = self.project_mapping[project_name]["id"]
        else:
            result["projectId"] = None

        # アサイン先は常に自分
        result["assigneeId"] = self.user_id
        
        return result