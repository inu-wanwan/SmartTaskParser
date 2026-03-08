from fastapi import APIRouter, Depends, HTTPException, Request
from app.models.request import ParseAndCreateRequest
from app.models.task import Task as TaskModel
from app.services.task_service import TaskService

router = APIRouter()

def get_task_service(request: Request) -> TaskService:
    """
    FastAPI の Depends で TaskService を注入するための関数。
    """
    return request.app.state.task_service

def get_user_repo(request: Request):
    """
    FastAPI の Depends で UserRepository を注入するための関数。
    """
    return request.app.state.user_repo

@router.post("/parse-and-create", response_model=TaskModel)
def parse_and_create_task(
    req: ParseAndCreateRequest,
    service: TaskService = Depends(get_task_service),
    user_repo = Depends(get_user_repo)
):
    """
    自然文テキストを解析し、タスクを作成して返すエンドポイント。
    """
    try:
        user_config = user_repo.get_user_config(req.user_id)
        if not user_config:
            raise HTTPException(status_code=400, detail="User config not found")
        
        task = service.create_task_from_text(
            text=req.text,
            user_config=user_config,
            source=req.source,
            user_id=req.user_id,
        )
        return task
    except Exception as e:
        print(f"[ERROR] /tasks/parse-and-create failed: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
@router.get("/tasks/upcoming")
def get_upcoming_tasks(
    service: TaskService = Depends(get_task_service),
):
    return service.get_tasks_within_next_n_days(n_days=3, include_overdue=True)
