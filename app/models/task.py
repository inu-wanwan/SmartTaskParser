from datetime import date
from typing import Optional
from pydantic import BaseModel

class Task(BaseModel):
    title: str
    due_date: Optional[date] = None
    priority: int = 0  # 0: low, 1: medium, 2: high
    description: Optional[str] = None
    project_id: Optional[str] = None
    source: str = "line"
    user_id: Optional[str] = None
    page_url: Optional[str] = None