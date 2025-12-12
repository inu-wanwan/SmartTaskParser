from datetime import date
from typing import Optional
from pydantic import BaseModel

class Task(BaseModel):
    title: str
    due_date: Optional[date] = None
    priority: str = "medium"  # "low" | "medium" | "high"
    notes: Optional[str] = None
    category: Optional[str] = None
    source: str = "line"
    user_id: Optional[str] = None
    page_id: Optional[str] = None  # Notion ページ ID
    page_url: Optional[str] = None  # Notion ページ URL
