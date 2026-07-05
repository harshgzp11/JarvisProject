from pydantic import BaseModel, Field

class ExecuteRequest(BaseModel):
    user_input: str = Field(..., description="The natural language command from the user", min_length=1, max_length=500)

class ExecuteResponse(BaseModel):
    status: str
    message: str
    intent: str
