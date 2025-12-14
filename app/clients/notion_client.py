import os
from datetime import date
from typing import Any, Dict, Optional, List

from dotenv import load_dotenv
from notion_client import Client


# .env から環境変数読み込み
load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

if not NOTION_API_KEY:
    raise ValueError("Environment variable NOTION_API_KEY is not set.")
if not NOTION_DATABASE_ID:
    raise ValueError("Environment variable NOTION_DATABASE_ID is not set.")

# Notion クライアント初期化
notion = Client(auth=NOTION_API_KEY)


def create_notion_task(
    title: str,
    due_date: Optional[date],
    priority: str,
    notes: Optional[str],
    category: Optional[str],
    user_id: Optional[str],
    source: str = "line",
) -> tuple[str, str]:
    """
    Notion のタスク用データベースに 1 件タスクを登録する。

    Args:
        title: タスク名
        due_date: 期限（日付オブジェクト。None の場合は未設定）
        priority: "low" | "medium" | "high"
        notes: メモ（任意）
        source: "line" や "web" など、どこから来たタスクか

    Returns:
        作成された Notion ページの ID（文字列）
    """
    properties: Dict[str, Any] = {
        # タイトル (Title プロパティ)
        "Title": {
            "title": [
                {
                    "text": {
                        "content": title,
                    }
                }
            ]
        },
        # ステータス (Select) - デフォルトは「ToDo」
        "Status": {
            "status": {
                "name": "ToDo",
            }
        },
        # 優先度 (Select)
        "Priority": {
            "select": {
                "name": priority,
            }
        },
        # ソース (Select)
        "Source": {
            "rich_text": [
                {
                    "text": {
                        "content": source,
                    }
                }
            ]
        },
    }

    # 期限 (Date)
    if due_date:
        properties["Due"] = {
            "date": {
                "start": due_date.isoformat(),
            }
        }

    # メモ (RichText)
    if notes:
        properties["Notes"] = {
            "rich_text": [
                {
                    "text": {
                        "content": notes,
                    }
                }
            ]
        }

    # カテゴリ (Select)
    if category:
        properties["Category"] = {
            "select": {
                "name": category,
            }
        }

    page = notion.pages.create(
        parent={"database_id": NOTION_DATABASE_ID},
        properties=properties,
    )

    # page["id"] は "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" 形式
    return page["id"], page["url"]

def _get_default_data_source_id(database_id: str) -> str:
    """
    指定したデータベースのデフォルトのデータソース ID を取得する。

    Args:
        database_id: Notion データベースの ID

    Returns:
        デフォルトのデータソース ID
    """
    database = notion.databases.retrieve(database_id=database_id)
    data_sources = database.get("data_sources", [])
    if not data_sources:
        raise RuntimeError("No data sources found for the database.")
    return data_sources[0]["id"]
    
def query_tasks_due_before(
    end_iso: str,
    limit: int = 50,
    exclude_done: bool = True,
):
    and_filters = [{"property": "Due", "date": {"on_or_before": end_iso}}]
    if exclude_done:
        and_filters.append({"property": "Status", "status": {"does_not_equal": "Done"}})

    data_source_id = _get_default_data_source_id(NOTION_DATABASE_ID)

    resp = notion.data_sources.query(
        data_source_id=data_source_id,
        filter={"and": and_filters},
        page_size=limit,
        sorts=[{"property": "Due", "direction": "ascending"}],
    )
    return resp.get("results", [])

def query_task_candidates_for_dayly(end_iso: str, limit: int = 50):
    """
    デイリータスク通知用に、指定日時までのタスクを取得する。
    候補 = (Due が空) OR (Due <= end_iso)
    かつ Status != Done のタスク。

    Args:
        end_iso: 期限の上限（ISO 8601 形式文字列）
        limit: 取得するタスクの最大数
    Returns:
        タスクのリスト（Notion のページオブジェクトのリスト）
    """
    not_done = {
        "property": "Status",
        "status": {"does_not_equal": "Done"}
    }

    due_empty = {
        "property": "Due",
        "date": {"is_empty": True}
    }
    due_before = {
        "property": "Due",
        "date": {"on_or_before": end_iso}
    }

    data_source_id = _get_default_data_source_id(NOTION_DATABASE_ID)

    resp = notion.data_sources.query(
        data_source_id=data_source_id,
        filter={
            "and": [
                not_done,
                {
                    "or": [
                        due_empty,
                        due_before
                    ]
                }
            ]
        },
        page_size=limit,
        sorts=[{"property": "Due", "direction": "ascending"}],
    )
    return resp.get("results", [])

def extract_task_summary(page: Dict[str, Any]) -> str:
    """
    Notion のページオブジェクトからタスクの要約文字列を作成する。

    Args:
        page: Notion API から取得したページオブジェクト

    Returns:
        タスクの要約文字列
    """
    props = page.get("properties", {})

    def _title(prop_name: str) -> str:
        title = props.get(prop_name, {}).get("title", [])
        return (title[0]["text"]["content"] if title else "")
    
    def _select(prop_name: str) -> Optional[str]:
        select = props.get(prop_name, {}).get("select")
        return select.get("name") if select else None
    
    def _status(prop_name: str) -> Optional[str]:
        status = props.get(prop_name, {}).get("status")
        return status.get("name") if status else None
    
    def _date(prop_name: str) -> Optional[str]:
        date_prop = props.get(prop_name, {}).get("date")
        return date_prop.get("start") if date_prop else None
    
    return {
        "title": _title("Title"),
        "due": _date("Due"),
        "priority": _select("Priority"),
        "status": _status("Status"),
        "page_url": page.get("url"),
        "page_id": page.get("id"),
    }