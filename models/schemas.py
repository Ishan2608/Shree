from pydantic import BaseModel, Field
from typing import Optional, Any

class ChatRequest(BaseModel):
    """
    Request body for POST /chat.
    session_id groups all messages belonging to one conversation.
    message is the user's raw text input sent to the agent.
    """
    session_id: str = Field(..., description="Unique session identifier.")
    message: str = Field(..., description="User message text.")


class ChatResponse(BaseModel):
    """
    Response for POST /chat.
    text is the agent's plain-language reply shown in the chat bubble.
    data carries structured chart/table output for frontend rendering.
    The frontend checks data for a 'chart_type' key to decide which
    visualization component to render. If data is None, render text only.
    """
    session_id: str
    text: str
    data: Optional[dict[str, Any]] = None


class UploadResponse(BaseModel):
    """
    Response for POST /upload.
    file_id is the UUID the agent uses to locate the file later via tool_parse_document.
    """
    file_id: str
    filename: str
    message: str


class ContextRequest(BaseModel):
    """
    Request body for POST /context.
    Lets the user paste raw text (a news excerpt, a company description,
    personal notes) that the agent should consider in its replies.
    """
    session_id: str
    context: str


class ClearSessionResponse(BaseModel):
    """Response for DELETE /session/{session_id}."""
    message: str


# TODO: In future phases, add:
# ForecastRequest(ticker, horizon_days) for a dedicated /forecast endpoint.
# AnalysisReport with typed sections if you add a structured /report endpoint.
