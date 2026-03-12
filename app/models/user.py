from typing import Optional
from pydantic import BaseModel

class User(BaseModel):
    id: str
    line_user_id: str
    linear_api_key: Optional[str] = None
    linear_team_id: Optional[str] = None
    linear_user_id: Optional[str] = None
    llm_api_key: Optional[str] = None
    notion_api_key: Optional[str] = None
    notion_database_id: Optional[str] = None
