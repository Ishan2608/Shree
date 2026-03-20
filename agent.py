"""
agent.py — Shree Agent

Tools are plain Python functions passed directly to the ADK Agent.
No MCP server, no subprocess, no stdio. Just functions.

The ADK reads each function's docstring and type hints to know
when and how to call it. Write docstrings precisely — they are the
agent's decision-making guide.

Public entry point: run_agent(session_id, message) -> {"text": str, "data": dict | None}
"""

import json
import os
import re

# The ADK reads GOOGLE_API_KEY from os.environ directly — it does not use .env files.
# We load it from our config (which reads .env) and push it into os.environ
# before any ADK class is instantiated.
from config import settings
os.environ["GOOGLE_API_KEY"] = settings.GEMINI_API_KEY

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

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
from utils.doc_parser import parse_uploaded_file
from utils.rag_engine import query_documents
from utils.session_store import get_files


# ─────────────────────────────────────────────────────────────────────────────
# TOOL WRAPPERS
# The ADK reads the docstring + type hints to decide when to call each tool.
# Keep docstrings precise and descriptive.
# ─────────────────────────────────────────────────────────────────────────────

def tool_get_stock_info(symbol: str, exchange: str = "NSE") -> dict:
    """Get real-time price, 52-week range, PE ratio, margins, debt ratios, and analyst targets.
    Call this when the user asks about a stock's current state, price, or basic fundamentals.
    symbol: NSE/BSE ticker WITHOUT exchange suffix. Examples: TCS, WIPRO, INFY, HDFCBANK, SBIN.
    exchange: NSE (default) or BSE."""
    return get_stock_info(symbol, exchange)


def tool_get_stock_history(symbol: str, exchange: str = "NSE", period: str = "1mo", interval: str = "1d") -> dict:
    """Get OHLCV historical price data formatted for candlestick or line charts.
    Call this when the user asks for a price chart, trend analysis, or historical performance.
    symbol: Ticker without suffix. exchange: NSE or BSE.
    period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y.
    interval: 1m (last 7d only), 1h, 1d, 1wk."""
    return get_stock_history(symbol, exchange, period, interval)


def tool_get_financials(symbol: str, exchange: str = "NSE", statement: str = "income", quarterly: bool = False) -> dict:
    """Get financial statements: income statement, balance sheet, or cash flow statement.
    Call this when analyzing revenue, profit, debt levels, or cash generation.
    statement: 'income' for P&L, 'balance_sheet' for assets/liabilities, 'cashflow' for cash flows.
    quarterly: True for last 4 quarters, False for last 4 annual periods."""
    return get_financials(symbol, exchange, statement, quarterly)


def tool_get_corporate_actions(symbol: str, exchange: str = "NSE") -> dict:
    """Get dividend history and stock split history.
    Call this when the user asks about dividends, shareholder returns, or historical splits."""
    return get_corporate_actions(symbol, exchange)


def tool_get_analyst_data(symbol: str, exchange: str = "NSE") -> dict:
    """Get analyst consensus: price targets (mean/high/low) and buy/hold/sell recommendation counts.
    Call this when the user asks what analysts think, or to add analyst consensus to an analysis."""
    return get_analyst_data(symbol, exchange)


def tool_get_holders(symbol: str, exchange: str = "NSE") -> dict:
    """Get top institutional and mutual fund shareholders.
    Call this when the user asks about ownership structure or institutional interest."""
    return get_holders(symbol, exchange)


def tool_get_esg_data(symbol: str, exchange: str = "NSE") -> dict:
    """Get ESG (Environmental, Social, Governance) risk scores from Sustainalytics.
    Call this when the user asks about sustainability, ESG rating, or ethical investing.
    Note: only available for large-cap stocks."""
    return get_esg_data(symbol, exchange)


def tool_get_upcoming_events(symbol: str, exchange: str = "NSE") -> dict:
    """Get upcoming earnings dates and ex-dividend dates from the stock calendar.
    Call this when the user asks when the next earnings report or dividend is."""
    return get_upcoming_events(symbol, exchange)


def tool_search_web(query: str, max_results: int = 5) -> dict:
    """Search the internet for current information using Tavily.
    Call this for macro events, regulatory changes, sector news, or anything needing live data.
    Do NOT use for stock prices or financials — use the stock tools for that.
    Keep queries specific: 'RBI rate decision impact on bank stocks' not just 'banks'."""
    return {"results": search_web(query, max_results)}


def tool_search_news(query: str, days_back: int = 7) -> dict:
    """Search recent news articles with source, date, and description metadata.
    Prefer this over tool_search_web when the user asks specifically about news or press releases.
    days_back: How many days of history to search. Default 7."""
    return {"results": search_news(query, days_back)}


def tool_search_ticker(query: str) -> dict:
    """Find the NSE/BSE ticker symbol for an Indian company by name or partial name.
    Call this FIRST when the user mentions a company by name instead of a ticker symbol.
    Example: 'analyze HDFC Bank' -> call this with 'hdfc bank' -> returns 'HDFCBANK'.
    Returns up to 5 matches with company_name, nse_symbol, bse_code, and ISIN."""
    return {"results": search_ticker(query)}


def tool_parse_document(session_id: str) -> dict:
    """Parse all uploaded documents in the session and return their full content.
    Call this when the user asks broad questions about an uploaded file like 'summarise this'.
    Supports PDF, DOCX, Excel, CSV, TXT, PPT.
    session_id: The current conversation session ID."""
    files = get_files(session_id)
    if not files:
        return {"error": "No documents uploaded in this session."}
    results = []
    for f in files:
        parsed = parse_uploaded_file(f["filepath"])
        parsed["filename"] = f["filename"]
        results.append(parsed)
    return {"documents": results}


def tool_search_documents(session_id: str, query: str, top_k: int = 5) -> dict:
    """Semantically search across all documents uploaded in the current session.
    Prefer this over tool_parse_document when the user asks a specific question
    that should be answered from their uploaded files.
    session_id: The current conversation session ID.
    query: The natural-language question or keyword to search for.
    top_k: Number of most relevant passages to return. Default 5."""
    files = get_files(session_id)
    if not files:
        return {"error": "No documents uploaded in this session."}
    filepaths = [f["filepath"] for f in files]
    return query_documents(filepaths, query, top_k)


def tool_predict_stock(symbol: str, exchange: str = "NSE", horizon_days: int = 10) -> dict:
    """Forecast the next N closing prices for a stock using Amazon Chronos (zero-shot model).
    Call this ONLY when the user explicitly asks for a price prediction or forecast.
    Do NOT use for current prices — use tool_get_stock_info for that.
    Always pair this forecast with news context and fundamental analysis.
    horizon_days: Future trading days to forecast. Recommended range: 5 to 20."""
    return predict_stock_prices(symbol, exchange, horizon_days)


# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are Artha, an AI financial analyst for Indian retail investors.
 
TOOLS: stock info, history, financials, corporate actions, analyst data, holders, ESG, upcoming events, web search, news search, ticker lookup, document parsing, document search, price forecasting.
 
STOCK ANALYSIS: If given a company name call search_ticker_tool first. Then call get_stock_info_tool, get_financials_tool, get_analyst_data_tool, search_news_tool. Reply with sections: Summary, Fundamental Picture, Analyst View, Recent News, Key Risks, Disclaimer. End with: "This is not financial advice."
 
DOCUMENTS: session_id is in the system note. For broad questions call parse_document_tool(session_id). For specific questions call search_documents_tool(session_id, query).
 
CHARTS: If response includes chart data, append at the very end:
```data
{{"chart_type": "candlestick", "dates": [...], ...}}
```
 
RULES: Never fabricate data. Always use tools. Acknowledge errors gracefully."""


# ─────────────────────────────────────────────────────────────────────────────
# ADK WIRING
# ─────────────────────────────────────────────────────────────────────────────

_agent = Agent(
    model="gemini-2.0-flash-lite",
    name="shree_agent",
    instruction=SYSTEM_PROMPT,
    tools=[
        tool_get_stock_info,
        tool_get_stock_history,
        tool_get_financials,
        tool_get_corporate_actions,
        tool_get_analyst_data,
        tool_get_holders,
        tool_get_esg_data,
        tool_get_upcoming_events,
        tool_search_web,
        tool_search_news,
        tool_search_ticker,
        tool_parse_document,
        tool_search_documents,
        tool_predict_stock,
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

    Creates the ADK session on the first call, reuses it on subsequent calls.
    Extracts and strips the data block from the agent's response before returning.

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
    match = re.search(r"```data\s*\n(.*?)```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            return None
    return None


def _strip_data_block(text: str) -> str:
    return re.sub(r"```data\s*\n.*?```", "", text, flags=re.DOTALL).strip()
