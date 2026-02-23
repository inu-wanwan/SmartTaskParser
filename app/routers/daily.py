from fastapi import APIRouter, Header, HTTPException
from app.services.task_service import get_daily_tasks_grouped_linear
from app.services.line_push_service import push_daily_summary, verify_cron_token

router = APIRouter()

@router.post("/daily/push")
def daily_push(cron_token: str = Header(... , alias="X-Cron-Token")):
    """
    デイリータスクサマリーを LINE にプッシュ送信するエンドポイント。
    CRON ジョブからのリクエストに含まれるトークンを検証する。
    """
    try:
        verify_cron_token(cron_token)
        grouped_tasks = get_daily_tasks_grouped_linear()
        push_daily_summary(grouped_tasks)
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