from datetime import date
from typing import Optional

from app.clients import llm_client, notion_client
from app.models.task import Task


def create_task_from_text(
    text: str,
    source: str = "line",
    user_id: Optional[str] = None,
) -> Task:
    """
    自然文のテキストからタスクを生成し、Notion に登録したうえで Task を返す。

    フロー:
      1. llm_client.parse_task_text() で JSON にパース
      2. JSON から Task モデルを組み立て
      3. notion_client.create_notion_task() で Notion に保存
      4. 保存した内容を表す Task を返す
    """

    # 1. LLM でタスク情報を抽出
    parsed = llm_client.parse_task_text(text)

    title = parsed.get("title") or text
    due_date_str = parsed.get("due_date")
    priority = parsed.get("priority") or "medium"
    notes = parsed.get("notes")
    category = parsed.get("category")

    # 2. 文字列の日付を date 型に変換（不正なら None）
    due_date: Optional[date] = _parse_date_str(due_date_str)

    # 3. アプリ内部で扱う Task モデルを組み立て
    task = Task(
        title=title,
        due_date=due_date,
        priority=priority,
        notes=notes,
        source=source,
        user_id=user_id,
        category=category,
    )

    # 4. Notion に保存
    page_id, page_url = notion_client.create_notion_task(
        title=task.title,
        due_date=task.due_date,
        priority=task.priority,
        notes=task.notes,
        source=task.source,
        category=task.category,
    )
    task.page_id = page_id
    task.page_url = page_url

    return task


def _parse_date_str(s: Optional[str]) -> Optional[date]:
    """
    YYYY-MM-DD 形式の文字列を date に変換するヘルパー関数。
    None や空文字列、不正なフォーマットなら None を返す。
    """
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None
