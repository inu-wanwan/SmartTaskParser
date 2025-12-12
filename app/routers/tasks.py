from fastapi import APIRouter, HTTPException
from app.models.request import ParseAndCreateRequest
from app.models.task import Task as TaskModel
from app.services.task_service import create_task_from_text

router = APIRouter()

@router.post("/parse-and-create", response_model=TaskModel)
def parse_and_create_task(req: ParseAndCreateRequest):
    """
    自然文テキストを解析し、タスクを作成して返すエンドポイント。
    """
    try:
        task = create_task_from_text(
            text=req.text,
            source=req.source,
            user_id=req.user_id,
        )
        return task
    except Exception as e:
        print(f"[ERROR] /tasks/parse-and-create failed: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")