from fastapi import APIRouter, Depends, Header, HTTPException, Request
from app.services.task_service import TaskService
from app.services.line_push_service import LinePushService, get_line_push_service

router = APIRouter()

def get_task_service(request: Request) -> TaskService:
    """
    FastAPI の Depends で TaskService を注入するための関数。
    """
    return request.app.state.task_service

def get_line_push_service(request: Request) -> LinePushService:
    """
    FastAPI の Depends で LinePushService を注入するための関数。
    """
    return request.app.state.line_push_service

@router.post("/daily/push")
def daily_push(
    cron_token: str = Header(... , alias="X-Cron-Token"),
    task_service: TaskService = Depends(get_task_service),
    line_push_service: LinePushService = Depends(get_line_push_service),
):
    """
    デイリータスクサマリーを LINE にプッシュ送信するエンドポイント。
    CRON ジョブからのリクエストに含まれるトークンを検証する。
    """
    try:
        line_push_service.verify_cron_token(cron_token)
        grouped_tasks = task_service.get_daily_tasks_grouped_linear()
        line_push_service.push_daily_summary(grouped_tasks)
        return {
            "ok": True,
            "counts": {
                "urgent_overdue": len(grouped_tasks.get("urgent_overdue", [])),
                "in_progress": len(grouped_tasks.get("in_progress", [])),
                "current_cycle_todo": len(grouped_tasks.get("current_cycle_todo", [])),
                "triage": len(grouped_tasks.get("triage", [])),
            }
        }
    except PermissionError as e:
        raise HTTPException(status_code=401, detail="Unauthorized")
    except Exception as e:
        print(f"[ERROR] /daily/push failed: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
