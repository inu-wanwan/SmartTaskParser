from fastapi import APIRouter, Depends, HTTPException
from app.models.request import ParseAndCreateRequest
from app.models.task import Task as TaskModel
from app.services.task_service import TaskService, get_task_service

router = APIRouter()

@router.post("/parse-and-create", response_model=TaskModel)
def parse_and_create_task(
    req: ParseAndCreateRequest,
    service: TaskService = Depends(get_task_service),
):
    """
    自然文テキストを解析し、タスクを作成して返すエンドポイント。
    """
    try:
        task = service.create_task_from_text(
            text=req.text,
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
