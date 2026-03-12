from fastapi import APIRouter, Depends, Header, HTTPException, Request
from app.services.task_service import TaskService
from app.services.line_push_service import LinePushService, get_line_push_service
from app.services.user_service import UserService

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

def get_user_repo(request: Request):
    """
    FastAPI の Depends で UserRepository を注入するための関数。
    """
    return request.app.state.user_repo

def get_user_service(request: Request):
    """
    FastAPI の Depends で UserService を注入するための関数。
    """
    return request.app.state.user_service

@router.post("/daily/push")
def daily_push(
    cron_token: str = Header(... , alias="X-Cron-Token"),
    task_service: TaskService = Depends(get_task_service),
    line_push_service: LinePushService = Depends(get_line_push_service),
    user_service: UserService = Depends(get_user_service)
):
    """
    デイリータスクサマリーを LINE にプッシュ送信するエンドポイント。
    CRON ジョブからのリクエストに含まれるトークンを検証する。
    """
    line_push_service.verify_cron_token(cron_token)
    users = user_service.get_all_users()

    results = []

    for user_id, user_config in users.items():
        if not user_config:
            print(f"[WARN] No user config for user_id={user_id}, skipping daily push.")
        
        try:
            grouped_tasks = task_service.get_daily_tasks_grouped_linear(user_config=user_config)
            line_push_service.push_daily_summary(user_id=user_id, grouped=  grouped_tasks)
            results.append({"user_id": user_id, "status": "success"})
        except ValueError as e:
            print(f"[ERROR] Configuration error for user_id={user_id}: {e}")
            results.append({"user_id": user_id, "status": "config_error", "detail": str(e)})
        except PermissionError as e:
            raise HTTPException(status_code=401, detail="Unauthorized")
        except Exception as e:
            print(f"[ERROR] /daily/push failed: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")
        
    return {"results": results}
