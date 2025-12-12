from typing import Optional
from pydantic import BaseModel

class ParseAndCreateRequest(BaseModel):
    text: str
    source: str = "line"
    user_id: Optional[str] = None
