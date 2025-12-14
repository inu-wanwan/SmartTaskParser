from datetime import date, datetime, timedelta, time
from zoneinfo import ZoneInfo
from typing import Optional, Dict, Any, List

from app.clients import llm_client, notion_client
from app.models.task import Task

JST = ZoneInfo("Asia/Tokyo")

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
        user_id=task.user_id,
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

def _parse_due_iso(due_iso: Optional[str]) -> Optional[datetime]:
    """
    Notion API から返ってくる ISO 8601 形式の期限文字列を datetime に変換するヘルパー関数。
    None や空文字列、不正なフォーマットなら None を返す。
    """
    if not due_iso:
        return None
    try:
        if len(due_iso) == 10:
            # 日付のみ (YYYY-MM-DD)
            y, m, d = map(int, due_iso.split("-"))
            return datetime(y, m, d, 0, 0, 0, tzinfo=JST)
        else:
            # 日付と時刻 (YYYY-MM-DDTHH:MM:SS±HH:MM)
            return datetime.fromisoformat(due_iso).astimezone(JST)
    except ValueError:
        return None
    
def get_tasks_within_next_n_days(
        n_days: int = 3,
        limit: int = 50,
        include_overdue: bool = True,
    ) -> List[Dict[str, Any]]:
    """
    今から n_days 日以内に期限が来るタスク一覧を取得する。
    include_overdue が True の場合、期限切れタスクも含める。
    Args:
        n_days: 期限が来るまでの日数
        limit: 取得するタスクの最大数
        include_overdue: 期限切れタスクを含めるかどうか
    Returns:
        タスクのリスト（Notion のページオブジェクトのリスト）
    """
    now = datetime.now(JST)
    today_start = datetime.combine(now.date(), time(0, 0, 0), tzinfo=JST)
    end_date = datetime.combine((now.date() + timedelta(days=n_days)), time(23, 59, 59), tzinfo=JST)

    # Notion側で Due<= end まで絞り、Python で最終判定
    pages = notion_client.query_tasks_due_before(end_iso=end_date.isoformat(), limit=limit, exclude_done=True)
    tasks = [notion_client.extract_task_summary(page) for page in pages]

    filtered: List[Dict[str, Any]] = []
    for task in tasks:
        due_dt = _parse_due_iso(task.get("due"))
        if not due_dt:
            filtered.append(task)
            continue
        if due_dt <= end_date and (include_overdue or due_dt >= today_start):
            filtered.append(task)

    return filtered

def get_daily_tasks_grouped(
        n_days: int = 3,
        limit: int = 50,
    ) -> Dict[str, List[Dict[str, Any]]]:
    """
    デイリータスク通知用に、今から n_days 日以内に期限が来るタスクを日付ごとにグルーピングして取得する。
    候補取得 -> サーバー側で分類
    Args:
        n_days: 期限が来るまでの日数
        limit: 取得するタスクの最大数
    Returns:
        {"orverdue": [...], "today": [...], "no_due":[...], "upcoming": [...]}
    """
    now = datetime.now(JST)
    today_start = datetime.combine(now.date(), time(0, 0, 0), tzinfo=JST)
    today_end = datetime.combine(now.date(), time(23, 59, 59), tzinfo=JST)
    end_date = datetime.combine((now.date() + timedelta(days=n_days)), time(23, 59, 59), tzinfo=JST)

    pages = notion_client.query_task_candidates_for_dayly(end_iso=end_date.isoformat(), limit=limit)
    tasks = [notion_client.extract_task_summary(page) for page in pages]

    overdue: List[Dict[str, Any]] = []
    today: List[Dict[str, Any]] = []
    no_due: List[Dict[str, Any]] = []
    upcoming: List[Dict[str, Any]] = []

    for task in tasks:
        due_dt = _parse_due_iso(task.get("due"))
        if not due_dt:
            no_due.append(task)
            continue
        if due_dt < today_start:
            overdue.append(task)
        elif today_start <= due_dt <= today_end:
            today.append(task)
        elif today_end < due_dt <= end_date:
            upcoming.append(task)

    return {
        "overdue": overdue,
        "today": today,
        "no_due": no_due,
        "upcoming": upcoming,
    }