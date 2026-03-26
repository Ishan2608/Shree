"""
multi_agent.py — Artha Multi-Agent System (Production Grade)

Architecture:
  guide_agent (Groq / llama-3.3-70b)
      ├── call_stock_analysis_agent (Gemini 2.5 Flash Lite) -> Fundamental/Market Data Specialist
      └── call_stock_aggregator_agent (Gemini 2.5 Flash Lite) -> Research/RAG/Forecasting Specialist

Key Features:
  1. Multi-Agent Orchestration: Guide agent routes complex queries to domain specialists.
  2. Context Propagation: Guide provides resolved entities and chat state to stateless specialists.
  3. Resilience: Sub-agent failures are caught and reported gracefully to the orchestrator.
  4. Data Integrity: Strict instructions for the preservation of markdown-wrapped JSON data blocks.
  5. Singleton Pattern: LLMs and Agent executors are initialized once and reused.
"""

import json
import re
import os
import asyncio
from typing import Dict, Any, Optional

from config import settings

from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool

from utils.session_store import get_history

# ─────────────────────────────────────────────────────────────────────────────
# LLM MODELS
# ─────────────────────────────────────────────────────────────────────────────

GEMINI_3 = "gemini-3.1-flash-lite-preview"

ORCHESTRATOR = "llama-3.3-70b-versatile"
ORCHESTRATOR_2 = "gemma-3-27b-it"
ANALYST = "gemini-3.1-flash-lite-preview"
AGGREGATOR = "gemini-3.1-flash-lite-preview"

# ─────────────────────────────────────────────────────────────────────────────
# SPECIALIST SYSTEM PROMPTS
# ─────────────────────────────────────────────────────────────────────────────

STOCK_ANALYSIS_SYSTEM_PROMPT = """You are Artha's Stock Analysis specialist for Indian retail investors.
Task: Retrieve and analyze structured financial data.

# YOUR TOOLS
- get_stock_info_tool: Price, valuation, fundamental margins.
- get_stock_history_tool: OHLCV data for charts.
- get_financials_tool: P&L, Balance Sheet, Cash Flow.
- get_corporate_actions_tool: Dividends, bonuses, splits.
- get_analyst_data_tool: Price targets, ratings.
- get_holders_tool: FII/DII/Promoter ownership.
- get_esg_data_tool: Sustainability scores.
- get_upcoming_events_tool: Earnings dates.
- search_ticker_tool: Resolve company name to ticker.

# RULES
1. Use the provided Context to identify the company if the Task refers to "it" or "the company".
2. Always resolve company names to NSE/BSE tickers using search_ticker_tool first.
3. For charts, output exactly one candlestick data block in the specified format.
4. End every response with: "This is not financial advice."
"""

STOCK_AGGREGATOR_SYSTEM_PROMPT = """You are Artha's Research & Forecasting specialist for Indian retail investors.
Task: Search unstructured data (web/news/docs) and perform time-series forecasting.

# YOUR TOOLS
- search_web_tool: General internet research.
- search_news_tool: Latest news sentiment.
- parse_document_tool: Full text extraction from uploaded session files.
- search_documents_tool: RAG-based search across uploaded session files.
- predict_stock_tool: Amazon Chronos price forecasting.

# RULES
1. Pass the session_id exactly to all document tools.
2. For forecasting, provide the forecast data block exactly.
3. Clearly explain that forecasts are probabilistic and based on zero-shot patterns.
4. End every response with: "This is not financial advice."
"""

GUIDE_SYSTEM_PROMPT = """You are Artha's Guide Agent, the central orchestrator for an Indian financial AI system.

# SPECIALISTS
1. call_stock_analysis_agent: For hard data, fundamentals, and financials.
2. call_stock_aggregator_agent: For research, news, documents, and forecasts.

# WORKFLOW
1. RESOLVE: Identify entities and resolve pronouns using conversation history.
2. STATE: Summarize relevant background for the specialist (e.g., "Analyzing TCS").
3. DELEGATE: Call specialists. For complex tasks (e.g., "analyze and forecast"), call both.
4. PRESERVE: Copy any ```data``` blocks from specialists into your final response verbatim.
5. INTEGRATE: Synthesize specialist findings into a single, cohesive professional response.
6. DISCLAIM: End every response with: "This is not financial advice."
"""

# ─────────────────────────────────────────────────────────────────────────────
# STOCK ANALYSIS TOOLS
# ─────────────────────────────────────────────────────────────────────────────

@tool
def get_stock_info_tool(symbol: str, exchange: str = "NSE") -> dict:
    """
    Get current snapshot for a listed Indian stock: price, PE, PB, margins, 
    market cap, and analyst consensus targets.
    """
    from tools.stock_data import get_stock_info
    return get_stock_info(symbol, exchange)

@tool
def get_stock_history_tool(
    symbol: str, 
    exchange: str = "NSE", 
    period: str = "1mo", 
    interval: str = "1d"
) -> dict:
    """
    Get OHLCV historical price data. Use when the user asks for charts or trend analysis.
    """
    from tools.stock_data import get_stock_history
    return get_stock_history(symbol, exchange, period, interval)

@tool
def get_financials_tool(
    symbol: str, 
    exchange: str = "NSE", 
    statement: str = "income", 
    quarterly: bool = False
) -> dict:
    """
    Get financial statements: 'income', 'balance_sheet', or 'cashflow'.
    """
    from tools.stock_data import get_financials
    return get_financials(symbol, exchange, statement, quarterly)

@tool
def get_corporate_actions_tool(symbol: str, exchange: str = "NSE") -> dict:
    """
    Get dividend history and stock split history for a company.
    """
    from tools.stock_data import get_corporate_actions
    return get_corporate_actions(symbol, exchange)

@tool
def get_analyst_data_tool(symbol: str, exchange: str = "NSE") -> dict:
    """
    Get analyst price targets and buy/hold/sell vote counts.
    """
    from tools.stock_data import get_analyst_data
    return get_analyst_data(symbol, exchange)

@tool
def get_holders_tool(symbol: str, exchange: str = "NSE") -> dict:
    """
    Get institutional and mutual fund shareholding patterns.
    """
    from tools.stock_data import get_holders
    return get_holders(symbol, exchange)

@tool
def get_esg_data_tool(symbol: str, exchange: str = "NSE") -> dict:
    """
    Get ESG risk scores from Sustainalytics for large-cap and mid-cap stocks.
    """
    from tools.stock_data import get_esg_data
    return get_esg_data(symbol, exchange)

@tool
def get_upcoming_events_tool(symbol: str, exchange: str = "NSE") -> dict:
    """
    Get upcoming earnings announcement dates and ex-dividend dates.
    """
    from tools.stock_data import get_upcoming_events
    return get_upcoming_events(symbol, exchange)

@tool
def search_ticker_tool(query: str) -> dict:
    """
    Resolve a company name to its ticker. Call this FIRST if the user gives a name instead of a symbol.
    """
    from tools.ticker_lookup import search_ticker
    return {"results": search_ticker(query)}

STOCK_ANALYSIS_TOOLS = [
    get_stock_info_tool, get_stock_history_tool, get_financials_tool,
    get_corporate_actions_tool, get_analyst_data_tool, get_holders_tool,
    get_esg_data_tool, get_upcoming_events_tool, search_ticker_tool
]

# ─────────────────────────────────────────────────────────────────────────────
# RESEARCH & AGGREGATOR TOOLS
# ─────────────────────────────────────────────────────────────────────────────

@tool
def search_web_tool(query: str, max_results: int = 5) -> dict:
    """
    Search live internet for macro-data, industry trends, or company announcements.
    """
    from tools.web_search import search_web
    return {"results": search_web(query, max_results)}

@tool
def search_news_tool(query: str, days_back: int = 2) -> dict:
    """
    Search recent news articles for market sentiment or breaking developments.
    """
    from tools.news_search import search_news
    return {"results": search_news(query, days_back)}

@tool
def parse_document_tool(session_id: str) -> dict:
    """
    Parse uploaded documents in the session and return full raw content for overview questions.
    """
    from utils.session_store import get_files
    from utils.doc_parser import parse_uploaded_file
    from utils.rag_engine import index_document

    files = get_files(session_id)
    if not files:
        return {"error": "No documents uploaded in this session."}

    results = []
    for f in files:
        parsed = parse_uploaded_file(f["filepath"])
        parsed["filename"] = f["filename"]
        results.append(parsed)
        if parsed.get("type") != "error":
            index_document(f["file_id"], parsed)

    return {"documents": results}

@tool
def search_documents_tool(session_id: str, query: str, top_k: int = 5) -> dict:
    """
    Semantically search inside uploaded session documents for specific data points.
    """
    from utils.session_store import get_files
    from utils.doc_parser import parse_uploaded_file
    from utils.rag_engine import index_document, query_documents

    files = get_files(session_id)
    if not files:
        return {"error": "No documents uploaded in this session."}

    for f in files:
        parsed = parse_uploaded_file(f["filepath"])
        if parsed.get("type") != "error":
            index_document(f["file_id"], parsed)

    chunks = query_documents(query=query, n_results=top_k)
    if not chunks:
        return {"status": "no_results", "results": []}
    return {"status": "success", "results": chunks}

@tool
def predict_stock_tool(
    symbol: str, 
    exchange: str = "NSE", 
    horizon_days: int = 10
) -> dict:
    """
    Forecast the next N closing prices using Amazon Chronos. Only call if forecasting is explicitly requested.
    """
    from tools.ts_model import predict_stock_prices
    return predict_stock_prices(symbol, exchange, horizon_days)

STOCK_AGGREGATOR_TOOLS = [
    search_web_tool, search_news_tool, parse_document_tool,
    search_documents_tool, predict_stock_tool
]

# ─────────────────────────────────────────────────────────────────────────────
# AGENT SINGLETONS & DELEGATION WRAPPERS
# ─────────────────────────────────────────────────────────────────────────────

_analysis_agent = None
_aggregator_agent = None
_guide_agent = None

def _build_agents():
    global _analysis_agent, _aggregator_agent, _guide_agent
    if _guide_agent:
        return

    # Initialize Gemini Specialists
    gemini_analysis_llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite", 
        google_api_key=settings.GEMINI_API_KEY_ANALYSIS, 
        temperature=0.1
    )
    gemini_aggregator_llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite", 
        google_api_key=settings.GEMINI_API_KEY_AGGREGATOR, 
        temperature=0.1
    )
    
    # Initialize Groq Orchestrator
    groq_llm = ChatGroq(
        model="llama-3.3-70b-versatile", 
        api_key=settings.GROQ_API_KEY, 
        temperature=0.1
    )

    _analysis_agent = create_react_agent(model=gemini_analysis_llm, tools=STOCK_ANALYSIS_TOOLS)
    _aggregator_agent = create_react_agent(model=gemini_aggregator_llm, tools=STOCK_AGGREGATOR_TOOLS)

    @tool
    async def call_stock_analysis_agent(task: str, context: str, session_id: str) -> str:
        """
        Delegate to Stock Analysis specialist for prices, fundamentals, or financials.
        task: Instruction (e.g. 'Get P&L for TCS').
        context: Context to resolve pronouns (e.g. 'User is asking about TCS').
        """
        try:
            prompt = f"Context: {context}\nTask: {task}\n[session_id: {session_id}]"
            messages = [SystemMessage(content=STOCK_ANALYSIS_SYSTEM_PROMPT), HumanMessage(content=prompt)]
            # res = await _analysis_agent.ainvoke({"messages": messages})
            # return res["messages"][-1].content
            result = await _stock_analysis_agent.ainvoke({"messages": messages}) # Or _stock_aggregator_agent
            last = result["messages"][-1]
            content = getattr(last, "content", "")
            if isinstance(content, list):
                return "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
            return str(content)
        except Exception as e:
            return f"Analysis Agent Error: {str(e)}"

    @tool
    async def call_stock_aggregator_agent(task: str, context: str, session_id: str) -> str:
        """
        Delegate to Research specialist for news, forecasting, or uploaded documents.
        task: Instruction (e.g. 'Forecast Reliance price').
        context: Context to resolve pronouns (e.g. 'User is asking about Reliance').
        """
        try:
            prompt = f"Context: {context}\nTask: {task}\n[session_id: {session_id}]"
            messages = [SystemMessage(content=STOCK_AGGREGATOR_SYSTEM_PROMPT), HumanMessage(content=prompt)]
            # res = await _aggregator_agent.ainvoke({"messages": messages})
            # return res["messages"][-1].content
            result = await _stock_analysis_agent.ainvoke({"messages": messages}) # Or _stock_aggregator_agent
            last = result["messages"][-1]
            content = getattr(last, "content", "")
            if isinstance(content, list):
                return "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
            return str(content)
        except Exception as e:
            return f"Aggregator Agent Error: {str(e)}"

    _guide_agent = create_react_agent(
        model=groq_llm, 
        tools=[call_stock_analysis_agent, call_stock_aggregator_agent]
    )

# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

async def run_agent(session_id: str, message: str) -> dict:
    """
    Executes one conversational turn through the Guide Agent.
    """
    _build_agents()

    messages = [SystemMessage(content=GUIDE_SYSTEM_PROMPT)]

    for msg in get_history(session_id):
        role, content = msg["role"], msg["content"]
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
        elif role == "system":
            messages.append(HumanMessage(content=f"[Context]\n{content}"))

    messages.append(HumanMessage(content=message))

    # result = await _guide_agent.ainvoke({"messages": messages})
    result = await _guide_agent.ainvoke({"messages": messages})
    final_text = ""
    if result.get("messages"):
        last = result["messages"][-1]
        content = getattr(last, "content", "")
        if isinstance(content, list):
            final_text = "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
        else:
            final_text = str(content)

    data = _extract_data_block(final_text)
    clean_text = _strip_data_block(final_text)

    return {"text": clean_text, "data": data}

# ─────────────────────────────────────────────────────────────────────────────
# DATA BLOCK HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _extract_data_block(text: str) -> Optional[Dict[str, Any]]:
    match = re.search(r"```data\s*\n(.*?)```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            return None
    return None

def _strip_data_block(text: str) -> str:
    return re.sub(r"```data\s*\n.*?```", "", text, flags=re.DOTALL).strip()
