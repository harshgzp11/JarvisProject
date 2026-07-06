from pydantic import BaseModel, Field, EmailStr
from typing import Literal, Optional

class GoogleAuthRequest(BaseModel):
    token: str = Field(..., description="Google OAuth2 ID Token")

class AuthResponse(BaseModel):
    status: str
    message: str
    token: Optional[str] = None

class ExecuteRequest(BaseModel):
    user_input: str = Field(..., description="The natural language command from the user", min_length=1, max_length=500)

class ExecuteResponse(BaseModel):
    status: str
    message: str
    intent: str

class LLMIntent(BaseModel):
    intent: Literal["open_app", "screenshot", "system_query"]
    target_param: Optional[str] = Field(default=None, description="The targeted application, specific media action, or null")


