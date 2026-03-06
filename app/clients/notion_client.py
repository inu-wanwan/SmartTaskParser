import os
from datetime import date
from typing import Any, Dict, Optional, List
from notion_client import Client
from app.base.base_client import BaseClient

class NotionClient(BaseClient):
    """
    Notion API との通信を担当するクライアント。
    SDK (notion-client) をラップして提供する。
    """

    def __init__(self):
        # BaseClient の初期化（.env の読み込みなど）
        super().__init__()
        
        # 環境変数の取得
        self.api_key = self.get_env_or_raise("NOTION_API_KEY")
        self.database_id = self.get_env_or_raise("NOTION_DATABASE_ID")
        
        # Notion SDK の初期化
        self.client = Client(auth=self.api_key)

    def _validate_env(self) -> None:
        """
        __init__ で get_env_or_raise を使っているため、
        追加で必要なチェックがあればここに記述する。
        """
        pass

    def create_task(
        self,
        title: str,
        due_date: Optional[date] = None,
        priority: str = "medium",
        notes: Optional[str] = None,
        category: Optional[str] = None,
        source: str = "line",
    ) -> tuple[str, str]:
        """
        Notion データベースに 1 件タスクを登録する。
        """
        properties: Dict[str, Any] = {
            "Title": {"title": [{"text": {"content": title}}]},
            "Status": {"status": {"name": "ToDo"}},
            "Priority": {"select": {"name": priority}},
            "Source": {"rich_text": [{"text": {"content": source}}]},
        }

        if due_date:
            properties["Due"] = {"date": {"start": due_date.isoformat()}}
        if notes:
            properties["Notes"] = {"rich_text": [{"text": {"content": notes}}]}
        if category:
            properties["Category"] = {"select": {"name": category}}

        page = self.client.pages.create(
            parent={"database_id": self.database_id},
            properties=properties,
        )
        return page["id"], page["url"]

    def _get_default_data_source_id(self) -> str:
        """
        データベースに関連付けられたデフォルトのデータソース ID を取得する。
        """
        database = self.client.databases.retrieve(database_id=self.database_id)
        data_sources = database.get("data_sources", [])
        if not data_sources:
            raise RuntimeError("データベースにデータソースが見つかりません。")
        return data_sources[0]["id"]

    def query_tasks_due_before(
        self,
        end_iso: str,
        limit: int = 50,
        exclude_done: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        指定した期限までのタスクを取得する。
        """
        and_filters = [{"property": "Due", "date": {"on_or_before": end_iso}}]
        if exclude_done:
            and_filters.append({"property": "Status", "status": {"does_not_equal": "Done"}})

        data_source_id = self._get_default_data_source_id()
        resp = self.client.data_sources.query(
            data_source_id=data_source_id,
            filter={"and": and_filters},
            page_size=limit,
            sorts=[{"property": "Due", "direction": "ascending"}],
        )
        return resp.get("results", [])

    def query_task_candidates_for_daily(self, end_iso: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        デイリー通知用に、期限切れまたは期限なしの未完了タスクを取得する。
        """
        data_source_id = self._get_default_data_source_id()
        resp = self.client.data_sources.query(
            data_source_id=data_source_id,
            filter={
                "and": [
                    {"property": "Status", "status": {"does_not_equal": "Done"}},
                    {
                        "or": [
                            {"property": "Due", "date": {"is_empty": True}},
                            {"property": "Due", "date": {"on_or_before": end_iso}}
                        ]
                    }
                ]
            },
            page_size=limit,
            sorts=[{"property": "Due", "direction": "ascending"}],
        )
        return resp.get("results", [])

    @staticmethod
    def extract_task_summary(page: Dict[str, Any]) -> Dict[str, Any]:
        """
        Notion のページオブジェクトから必要な情報を抽出する。
        """
        props = page.get("properties", {})

        def _get_val(p, t):
            prop = props.get(p, {})
            if t == "title": return prop.get("title", [{}])[0].get("text", {}).get("content", "")
            if t == "select": return prop.get("select", {}).get("name")
            if t == "status": return prop.get("status", {}).get("name")
            if t == "date": return prop.get("date", {}).get("start")
            return None

        return {
            "title": _get_val("Title", "title"),
            "due": _get_val("Due", "date"),
            "priority": _get_val("Priority", "select"),
            "status": _get_val("Status", "status"),
            "page_url": page.get("url"),
            "page_id": page.get("id"),
        }