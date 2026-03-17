from typing import Any
from collections import defaultdict

docs = """
Structure of Conversation Histories is a simple Python Dictionary of Dictionaries.
Highest Level of Key: session_id. For each 'chat', we have a different session_id to identify it.
For each session, we have its history and its files. Thus two keys for dict in it.
Each entry in 'history', is a dict with these keys -> role, contet.
Each entry in 'files', is a dict with these keys -> file_id, filepath, filename
{
    `session_id`: {
        `history`: [
            {
            `role`: `user` | `assistant` | `system`,
            `content`: str
            },
        ],
        `files`: [
            { `file_id`: str, `filepath`: str, `filename`:str },
        ]
    }
}
"""

def default_session() -> dict[str, Any]:
    return {"history": [], "files": []}

_store: dict[str, dict[str, Any]] = defaultdict(default_session)

def get_session(session_id: str) -> dict[str, Any]:
    """
    Retrieve the full session dict for a given session_id.
    If the session does not exist, the defaultdict creates an empty one automatically.
    Args:
        session_id: The unique identifier from the frontend request.
    Returns:
        Dict with keys "history" and "files".
    """
    return _store[session_id]


def get_history(session_id: str) -> list[dict]:
    """
    Return the message history list for a session.
    Args:
        session_id: Target session.
    Returns:
        List of message dicts in chronological order.
    """
    return _store[session_id]["history"]


def append_message(session_id: str, role: str, content: str) -> None:
    """
    Append a single message to a session's history.
    Args:
        session_id: Target session.
        role: One of "user", "assistant", or "system".
        content: The text content of the message.
    """
    message = {"role": role, "content": content}
    _store[session_id]["history"].append(message)
    return


def add_file(session_id: str, file_id: str, filepath: str, filename: str) -> None:
    """
    Register an uploaded file in the session so the agent can reference it later.
    Args:
        session_id: Target session.
        file_id: UUID string assigned at upload time.
        filepath: Absolute path to the saved file on disk.
        filename: Original filename as provided by the user.
    """
    fileMessage = {"file_id": file_id, "filepath": filepath, "filename": filename}
    _store[session_id]["files"].append(fileMessage)


def get_files(session_id: str) -> list[dict]:
    """
    Return the list of files registered for a session.
    Args:
        session_id: Target session.
    Returns:
        List of file metadata dicts. Each dict has file_id, filepath, filename.
    """
    return _store[session_id]["files"]


def clear_session(session_id: str) -> None:
    """
    Delete a session and all its data from the in-memory store.
    Does NOT delete uploaded files from disk — the caller (main.py route) handles that.
    Args:
        session_id: The session to destroy.
    """
    del _store[session_id]
