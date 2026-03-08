from datetime import date, datetime, timedelta, time
from zoneinfo import ZoneInfo
from typing import Optional, Dict, Any, List

from app.base.base_service import BaseService
from app.clients.llm_client import LLMClient
from app.clients.notion_client import NotionClient
from app.clients.linear_client import LinearClient
from app.models.task import Task

JST = ZoneInfo("Asia/Tokyo")

class TaskService(BaseService):
    def __init__(self, prompt_builder, linear_service) -> None:
        super().__init__()
        self.llm_client = LLMClient()
        self.notion_client = NotionClient()
        self.linear_client = LinearClient()
        self.prompt_builder = prompt_builder
        self.linear_service = linear_service

    def create_task_from_text(
        self,
        text: str,
        source: str = "line",
        user_id: Optional[str] = None,
    ) -> Task:
        """
        自然文のテキストからタスクを生成し、Linear に登録したうえで Task を返す。
        """

        project_context = self.linear_service.get_project_context()
        prompt = self.prompt_builder.build(text, project_context=project_context)
        parsed = self.llm_client.parse_task_text(prompt)
        id_resolved = self.linear_service.resolve_ids(parsed)

        title = id_resolved.get("title") or text
        due_date_str = id_resolved.get("dueDate")
        priority = id_resolved.get("priority") or 0
        description = id_resolved.get("description")
        project_id = id_resolved.get("projectId")
        assignee_id = id_resolved.get("assigneeId")
        state_id = id_resolved.get("stateId")

        due_date: Optional[date] = self._parse_date_str(due_date_str)

        task = Task(
            title=title,
            due_date=due_date,
            priority=priority,
            description=description,
            source=source,
            user_id=user_id,
            project_id=project_id,
            assignee_id=assignee_id,
            state_id=state_id,
        )

        page_url = self.linear_client.create_linear_issue(
            title=task.title,
            due_date=task.due_date,
            priority=task.priority,
            notes=task.description,
            project_id=task.project_id,
            assignee_id=task.assignee_id,
            state_id=task.state_id,
        )

        task.page_url = page_url

        return task

    def get_tasks_within_next_n_days(
        self,
        n_days: int = 3,
        limit: int = 50,
        include_overdue: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        今から n_days 日以内に期限が来るタスク一覧を取得する。
        """
        now = datetime.now(JST)
        today_start = datetime.combine(now.date(), time(0, 0, 0), tzinfo=JST)
        end_date = datetime.combine((now.date() + timedelta(days=n_days)), time(23, 59, 59), tzinfo=JST)

        pages = self.notion_client.query_tasks_due_before(end_iso=end_date.isoformat(), limit=limit, exclude_done=True)
        tasks = [self.notion_client.extract_task_summary(page) for page in pages]

        filtered: List[Dict[str, Any]] = []
        for task in tasks:
            due_dt = self._parse_due_iso(task.get("due"))
            if not due_dt:
                filtered.append(task)
                continue
            if due_dt <= end_date and (include_overdue or due_dt >= today_start):
                filtered.append(task)

        return filtered

    def get_daily_tasks_grouped_notion(
        self,
        n_days: int = 3,
        limit: int = 50,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        デイリー通知用に、Notionタスクを期限でグルーピングして取得する。
        """
        now = datetime.now(JST)
        today_start = datetime.combine(now.date(), time(0, 0, 0), tzinfo=JST)
        today_end = datetime.combine(now.date(), time(23, 59, 59), tzinfo=JST)
        end_date = datetime.combine((now.date() + timedelta(days=n_days)), time(23, 59, 59), tzinfo=JST)

        pages = self.notion_client.query_task_candidates_for_dayly(end_iso=end_date.isoformat(), limit=limit)
        tasks = [self.notion_client.extract_task_summary(page) for page in pages]

        overdue: List[Dict[str, Any]] = []
        today: List[Dict[str, Any]] = []
        no_due: List[Dict[str, Any]] = []
        upcoming: List[Dict[str, Any]] = []

        for task in tasks:
            due_dt = self._parse_due_iso(task.get("due"))
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

    def get_daily_tasks_grouped_linear(self) -> Dict[str, Any]:
        """
        Linearの流儀に則り、優先度やステータス、サイクルに基づいてタスクを分類する。
        """
        raw_data = self.linear_client.fetch_daily_summary()

        assigned_issues = raw_data.get("user", {}).get("assignedIssues", {}).get("nodes", [])
        team_data = raw_data.get("team", {})
        active_cycle = team_data.get("activeCycle")
        active_cycle_id = active_cycle["id"] if active_cycle else None
        triage_issues = team_data.get("issues", {}).get("nodes", [])

        today = date.today()

        grouped = {
            "cycle": active_cycle,
            "urgent_overdue": [],
            "in_progress": [],
            "current_cycle_todo": [],
            "triage": triage_issues,
        }

        for issue in assigned_issues:
            state_type = issue["state"]["type"]
            priority = issue["priority"]
            due_str = issue.get("dueDate")
            due_date = date.fromisoformat(due_str) if due_str else None

            if priority == 1 or (due_date and due_date < today):
                grouped["urgent_overdue"].append(issue)
                continue

            if state_type == "started":
                grouped["in_progress"].append(issue)
                continue

            if active_cycle_id and issue.get("cycle") and issue["cycle"]["id"] == active_cycle_id:
                if state_type == "unstarted":
                    grouped["current_cycle_todo"].append(issue)

        return grouped

    @staticmethod
    def _parse_date_str(s: Optional[str]) -> Optional[date]:
        if not s:
            return None
        try:
            return date.fromisoformat(s)
        except ValueError:
            return None

    @staticmethod
    def _parse_due_iso(due_iso: Optional[str]) -> Optional[datetime]:
        if not due_iso:
            return None
        try:
            if len(due_iso) == 10:
                y, m, d = map(int, due_iso.split("-"))
                return datetime(y, m, d, 0, 0, 0, tzinfo=JST)
            return datetime.fromisoformat(due_iso).astimezone(JST)
        except ValueError:
            return None