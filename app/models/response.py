from pydantic import BaseModel
from typing import Optional

class UserConfigResponse(BaseModel):
    line_user_id: str
    is_linear_connected: bool = False
    is_llm_connected: bool = False