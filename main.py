"""
main.py — FastAPI Application

All HTTP routes for the Shree_v2 backend.
Entry point for uvicorn: `uvicorn main:app --reload`

Routes
------
POST   /chat                    -> Send a message to the agent
POST   /upload?session_id=...   -> Upload a file (PDF, DOCX, Excel, CSV, TXT, PPT)
POST   /context                 -> Inject raw text context into a session
DELETE /session/{session_id}    -> Delete a session and all its uploaded files
GET    /session/{session_id}/files -> List files uploaded in a session
GET    /health                  -> Health check

Swagger UI: http://localhost:8000/docs
"""

import os
import uuid
import shutil

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from models.schemas import (
    ChatRequest,
    ChatResponse,
    UploadResponse,
    ContextRequest,
    ClearSessionResponse,
)
from utils.session_store import append_message, add_file, get_files, clear_session
from agent import run_agent


# ─────────────────────────────────────────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Shree_v2 Backend",
    description=(
        "AI Financial Analyst Agent API for Indian retail investors. "
        "Powered by Google ADK + Gemini 2.0 Flash."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # Tighten to specific frontend origin in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Supported upload extensions — validated on upload
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".csv", ".txt", ".ppt", ".pptx"}


# ─────────────────────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main conversational endpoint.

    Flow:
    1. Append the user message to session history.
    2. Run the ADK agent (may call multiple MCP tools internally).
    3. Append the agent reply to session history.
    4. Return structured response: text for the chat bubble + optional data block
       for the frontend chart renderer.

    The 'data' field is None for plain conversational replies and populated with
    chart-ready JSON for stock analysis / forecast responses.
    """
    append_message(request.session_id, "user", request.message)

    # Inject session_id so document tools can look up uploaded files
    files = get_files(request.session_id)
    message = request.message
    if files:
        file_names = ", ".join(f["filename"] for f in files)
        message = (
            f"{request.message}\n\n"
            f"[System note: session_id='{request.session_id}'. "
            f"Files uploaded in this session: {file_names}. "
            f"Use tool_parse_document or tool_search_documents with this session_id to access them.]"
        )

    try:
        result = await run_agent(request.session_id, message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

    append_message(request.session_id, "assistant", result["text"])

    return ChatResponse(
        session_id=request.session_id,
        text=result["text"],
        data=result.get("data"),
    )


@app.post("/upload", response_model=UploadResponse)
async def upload_file(
    session_id: str = Query(...),
    file: UploadFile = File(...),
):
    """
    File upload endpoint.

    Saves the uploaded file to the uploads/ directory with a UUID prefix to prevent
    filename collisions across sessions. Registers the file in the session store so
    the agent can access it later via tool_parse_document or tool_search_documents.

    Supported file types: PDF, DOCX, DOC, XLSX, XLS, CSV, TXT, PPT, PPTX.
    Returns the file_id which the user (and the agent) use to reference this file.
    """
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{ext}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            ),
        )

    file_id = str(uuid.uuid4())
    safe_name = file_id + "_" + (file.filename or "upload")
    dest = os.path.join(settings.UPLOAD_DIR, safe_name)

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    with open(dest, "wb") as out:
        shutil.copyfileobj(file.file, out)

    add_file(session_id, file_id, dest, file.filename or safe_name)

    return UploadResponse(
        file_id=file_id,
        filename=file.filename or safe_name,
        message=(
            f"'{file.filename}' uploaded successfully. "
            "You can now ask questions about it."
        ),
    )


@app.post("/context")
async def add_text_context(request: ContextRequest):
    """
    Text context injection endpoint.

    Lets the user paste raw text into the session — a company description, a news
    excerpt, personal research notes, or any context they want the agent to consider.
    Stored as a system message in session history so the agent sees it on the next turn.

    Returns the character count so the frontend can warn if the context is very large
    (large contexts slow the agent down and may truncate older history).
    """
    content = f"[User-provided context]:\n{request.context}"
    append_message(request.session_id, "system", content)
    return {
        "message": "Context added to your session.",
        "char_count": len(request.context),
    }


@app.delete("/session/{session_id}", response_model=ClearSessionResponse)
async def delete_session(session_id: str):
    """
    Session cleanup endpoint.

    Deletes all uploaded files for this session from disk, then clears the session
    from the in-memory store. File deletion MUST happen before clearing the session
    because we need the file list from the session to know what to delete.

    Call this when the user explicitly resets or when the frontend detects a new
    conversation should start from scratch.
    """
    files = get_files(session_id)
    deleted_count = 0
    for f in files:
        if os.path.exists(f["filepath"]):
            os.remove(f["filepath"])
            deleted_count += 1

    clear_session(session_id)

    return ClearSessionResponse(
        message=(
            f"Session '{session_id}' cleared. "
            f"{deleted_count} uploaded file(s) deleted from disk."
        )
    )


@app.get("/session/{session_id}/files")
async def list_session_files(session_id: str):
    """
    List files uploaded in a session.

    Returns file_id and filename for each file. Does NOT expose filepaths —
    those are internal server details. Used by the frontend to show the user
    which documents are available for the agent to reference.
    """
    files = get_files(session_id)
    return {
        "session_id": session_id,
        "file_count": len(files),
        "files": [
            {"file_id": f["file_id"], "filename": f["filename"]}
            for f in files
        ],
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint. Returns 200 OK with version info.
    Used by deployment monitors and the test_run.py startup check.
    """
    return {"status": "ok", "version": "1.0.0", "agent": "shree_v2"}
