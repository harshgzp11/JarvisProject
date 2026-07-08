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

class ChatRequest(BaseModel):
    message: str = Field(..., description="The user message", min_length=1, max_length=1000)

class Step(BaseModel):
    type: Literal["LAUNCH", "WAIT", "TYPE", "SHORTCUT", "PASTE"]
    payload: str

class ChatResponse(BaseModel):
    response: str = Field(..., description="The text response from the assistant")
    intent: str = Field(..., description="The detected intent (SYSTEM_COMMAND or GENERAL_QUERY)")
    action: str = Field(..., description="The specific action to execute, or none")
    execution_type: Optional[str] = Field(default=None, description="SHELL_COMMAND | PYTHON_SCRIPT | BROWSER_URL | None")
    payload: Optional[str] = Field(default=None, description="The raw shell command, Python snippet, or URL to execute")
    steps: Optional[list[Step]] = Field(default=None, description="Ordered list of GUI execution steps")



