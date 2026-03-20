"""
agent.py — Shree Agent (ADK wiring layer)

Responsibilities
----------------
1. Import raw tool functions from tools/ and utils/.
2. Pass them directly to ADK Agent.tools[].
   The ADK framework auto-wraps each plain Python function as a FunctionTool,
   reading its name, docstring, and type hints to build the schema sent to Gemini.
   No wrapper, no re-docstring needed for stateless tools.
3. Define thin session-aware wrappers ONLY for the two document tools, because
   they need to resolve session_id → file paths via the session store — logic
   that does not belong in tools/.
4. Expose run_agent(session_id, message) as the single public entry point
   consumed by main.py (FastAPI) and test_run.py (CLI).

Architecture note
-----------------
mcp_server.py is a completely separate server that wraps the same raw tool
functions with @mcp.tool() for external MCP clients.
Do NOT import agent.py from mcp_server.py or vice versa.
"""

import json
import os
import re

# The ADK reads GOOGLE_API_KEY from os.environ directly.
# Load from config (which reads .env) and push into os.environ before any ADK
# class is instantiated.
from config import settings
os.environ["GOOGLE_API_KEY"] = settings.GEMINI_API_KEY

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# ── Raw tool functions — passed directly to tools=[] ─────────────────────────
# ADK reads each function's existing docstring + type hints. No re-wrapping.
from tools.stock_data import (
    get_stock_info,
    get_stock_history,
    get_financials,
    get_corporate_actions,
    get_analyst_data,
    get_holders,
    get_esg_data,
    get_upcoming_events,
)
from tools.web_search import search_web
from tools.news_search import search_news
from tools.ticker_lookup import search_ticker
from tools.ts_model import predict_stock_prices
from tools.document_search import search_uploaded_documents
from utils.session_store import get_files


# ─────────────────────────────────────────────────────────────────────────────
# SESSION-AWARE DOCUMENT TOOL WRAPPERS
#
# These are the only wrappers in this file. They exist purely to bridge the gap
# between the agent (which knows session_id) and the raw utilities (which need
# file paths). The logic — not just a signature rename — justifies the wrapper.
# ─────────────────────────────────────────────────────────────────────────────

def parse_document(session_id: str) -> dict:
    """
    Parse all documents uploaded in this session and return their full text content.

    Use this when the user asks a broad question about an uploaded file,
    such as "summarise this document" or "what is this file about?".
    Supports PDF, DOCX, Excel (.xlsx/.xls), CSV, TXT, and PPT/PPTX.

    Args:
        session_id: The current conversation session ID. Always provided in the
                    system note at the bottom of the user's message.

    Returns:
        A dict with a "documents" list (one entry per file, each containing
        filename and extracted text), or {"error": "..."} if no files exist.
    """
    from utils.doc_parser import parse_uploaded_file
    files = get_files(session_id)
    if not files:
        return {"error": "No documents uploaded in this session."}
    results = []
    for f in files:
        parsed = parse_uploaded_file(f["filepath"])
        parsed["filename"] = f["filename"]
        results.append(parsed)
    return {"documents": results}


def search_documents(session_id: str, query: str) -> dict:
    """
    Semantically search across all documents uploaded in this session.

    Prefer this over parse_document when the user asks a specific question
    that should be answered from their uploaded files. Returns only the most
    relevant passages rather than the full document text.

    Args:
        session_id: The current conversation session ID. Always provided in the
                    system note at the bottom of the user's message.
        query: The natural-language question or keywords to search for.

    Returns:
        A dict with a "results" list of relevant passages, or {"error": "..."}.
    """
    files = get_files(session_id)
    if not files:
        return {"error": "No documents uploaded in this session."}
    return search_uploaded_documents(query)


# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are Shree, an AI financial analyst for Indian retail investors.

TOOLS AVAILABLE:
  Stock data   — get_stock_info, get_stock_history, get_financials,
                 get_corporate_actions, get_analyst_data, get_holders,
                 get_esg_data, get_upcoming_events
  Web / news   — search_web, search_news
  Ticker       — search_ticker
  Documents    — parse_document, search_documents
  Forecasting  — predict_stock_prices

STOCK ANALYSIS WORKFLOW:
  If given a company name, call search_ticker first to get the symbol.
  Then call get_stock_info, get_financials, get_analyst_data, search_news.
  Reply with sections: Summary | Fundamental Picture | Analyst View |
  Recent News | Key Risks | Disclaimer.
  Always end with: "This is not financial advice."

DOCUMENTS:
  session_id is provided in the system note on every turn.
  For broad questions → call parse_document(session_id).
  For specific questions → call search_documents(session_id, query).

CHARTS:
  If the response includes chart data, append at the very end:
  ```data
  {"chart_type": "candlestick", "dates": [...], ...}
  ```

RULES: Never fabricate data. Always use tools for live data. Acknowledge errors gracefully."""


# ─────────────────────────────────────────────────────────────────────────────
# ADK WIRING
# ─────────────────────────────────────────────────────────────────────────────

_agent = Agent(
    model="gemini-2.0-flash-lite",
    name="shree_agent",
    instruction=SYSTEM_PROMPT,
    tools=[
        # Stock data — raw functions, ADK reads their docstrings directly
        get_stock_info,
        get_stock_history,
        get_financials,
        get_corporate_actions,
        get_analyst_data,
        get_holders,
        get_esg_data,
        get_upcoming_events,
        # Web / news / ticker — raw functions
        search_web,
        search_news,
        search_ticker,
        # Forecasting — raw function
        predict_stock_prices,
        # Documents — session-aware wrappers (logic differs from raw util)
        parse_document,
        search_documents,
    ],
)

_session_service = InMemorySessionService()

_runner = Runner(
    agent=_agent,
    app_name="shree_v2",
    session_service=_session_service,
)


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

async def run_agent(session_id: str, message: str) -> dict:
    """
    Run the agent for one conversation turn.

    Creates the ADK session on first call, reuses it on subsequent calls.
    Extracts and strips the ```data``` block so callers receive clean text
    and structured chart data separately.

    Returns:
        {"text": str, "data": dict | None}
    """
    session = await _session_service.get_session(
        app_name="shree_v2",
        user_id=session_id,
        session_id=session_id,
    )
    if session is None:
        await _session_service.create_session(
            app_name="shree_v2",
            user_id=session_id,
            session_id=session_id,
        )

    content = types.Content(role="user", parts=[types.Part(text=message)])

    final_text = ""
    async for event in _runner.run_async(
        user_id=session_id,
        session_id=session_id,
        new_message=content,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    final_text += part.text

    data = _extract_data_block(final_text)
    clean_text = _strip_data_block(final_text)
    return {"text": clean_text, "data": data}


# ─────────────────────────────────────────────────────────────────────────────
# DATA BLOCK HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _extract_data_block(text: str) -> dict | None:
    """Parse and return the JSON payload inside a ```data ... ``` fence, or None."""
    match = re.search(r"```data\s*\n(.*?)```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            return None
    return None


def _strip_data_block(text: str) -> str:
    """Remove the ```data ... ``` fence from the agent's reply."""
    return re.sub(r"```data\s*\n.*?```", "", text, flags=re.DOTALL).strip()
