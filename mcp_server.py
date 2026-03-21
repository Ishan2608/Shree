"""
mcp_server.py — Artha MCP Tool Server (FastMCP)

Single source of truth for all tool definitions.
Both the LangChain agent (via MultiServerMCPClient) and any external
MCP-compatible client connect here to discover and call tools.

Architecture:
  tools/        -> plain Python functions, no framework dependency
  mcp_server.py -> FastMCP wrappers (this file) — only place tools are defined
  agent.py      -> fetches tools from here, defines none itself

All wrapper functions follow the same pattern:
  - Descriptive docstring (this is what the LLM reads to decide when to call it)
  - Body calls the real function from tools/ or utils/
  - No business logic beyond routing + the document tools which need session_store

Run standalone:  python mcp_server.py
Launched automatically as subprocess by agent.py via MultiServerMCPClient.
"""

from mcp.server.fastmcp import FastMCP

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
from tools.web_search   import search_web
from tools.news_search  import search_news
from tools.ticker_lookup import search_ticker
from tools.ts_model     import predict_stock_prices

from utils.doc_parser   import parse_uploaded_file
from utils.rag_engine   import index_document, query_documents
from utils.session_store import get_files

mcp = FastMCP("artha-tools")


# ─────────────────────────────────────────────────────────────────────────────
# STOCK DATA TOOLS
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def get_stock_info_tool(symbol: str, exchange: str = "NSE") -> dict:
    """
    Get current snapshot for a listed Indian stock: real-time price, previous close,
    day high/low, 52-week range, PE ratio, forward PE, P/B ratio, dividend yield,
    market cap, debt-to-equity, ROE, gross/operating/profit margins, analyst price
    targets (mean, high, low) and consensus recommendation.

    Use this as the FIRST data call whenever the user asks about a stock's current
    state, valuation, or fundamentals. Call it for EACH company when doing a
    multi-company analysis.

    symbol   : NSE/BSE ticker WITHOUT exchange suffix.
               Examples: TCS, WIPRO, INFY, HDFCBANK, SBIN, RELIANCE, TATAMOTORS.
    exchange : "NSE" (default) or "BSE".
    """
    return get_stock_info(symbol, exchange)


@mcp.tool()
def get_stock_history_tool(
    symbol: str,
    exchange: str = "NSE",
    period: str = "1mo",
    interval: str = "1d",
) -> dict:
    """
    Get OHLCV (Open, High, Low, Close, Volume) historical price data.

    Use when the user asks for a price chart, trend analysis, historical performance,
    support/resistance levels, or any question needing past price data.
    Also call this before running a forecast — the model needs recent history.

    period   : How far back to fetch. Options: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y.
    interval : Candle size. Options: 1m (last 7d only), 1h, 1d, 1wk.
    """
    return get_stock_history(symbol, exchange, period, interval)


@mcp.tool()
def get_financials_tool(
    symbol: str,
    exchange: str = "NSE",
    statement: str = "income",
    quarterly: bool = False,
) -> dict:
    """
    Get a company's financial statements.

    statement : Which statement to fetch:
                "income"        -> P&L: revenue, EBITDA, net income, EPS
                "balance_sheet" -> Assets, liabilities, shareholder equity
                "cashflow"      -> Operating, investing, financing cash flows
    quarterly : True = last 4 quarters | False = last 4 annual periods (default).

    Call for deep fundamental analysis, margin trends, debt levels, or when the
    user asks about revenue, profit, earnings, or balance sheet metrics.
    """
    return get_financials(symbol, exchange, statement, quarterly)


@mcp.tool()
def get_corporate_actions_tool(symbol: str, exchange: str = "NSE") -> dict:
    """
    Get dividend payment history and stock split history for a company.

    Call when the user asks about dividends, dividend yield track record,
    shareholder returns, or whether the company has done splits/bonuses.
    """
    return get_corporate_actions(symbol, exchange)


@mcp.tool()
def get_analyst_data_tool(symbol: str, exchange: str = "NSE") -> dict:
    """
    Get Wall Street / sell-side analyst consensus for a stock:
    mean, high, and low 12-month price targets plus buy/hold/sell vote counts.

    Call when the user asks what analysts think, for upside potential calculations,
    or as part of a full stock analysis report.
    """
    return get_analyst_data(symbol, exchange)


@mcp.tool()
def get_holders_tool(symbol: str, exchange: str = "NSE") -> dict:
    """
    Get the top institutional shareholders and top mutual fund holders.

    Call when the user asks about ownership structure, FII/DII activity,
    promoter holding, or institutional interest in a stock.
    """
    return get_holders(symbol, exchange)


@mcp.tool()
def get_esg_data_tool(symbol: str, exchange: str = "NSE") -> dict:
    """
    Get ESG (Environmental, Social, Governance) risk scores from Sustainalytics.

    Call when the user asks about sustainability, ESG ratings, or ethical investing.
    Note: only available for large-cap and mid-cap stocks; may return empty for small-caps.
    """
    return get_esg_data(symbol, exchange)


@mcp.tool()
def get_upcoming_events_tool(symbol: str, exchange: str = "NSE") -> dict:
    """
    Get upcoming earnings announcement dates and ex-dividend dates.

    Call when the user asks when the next earnings report is, upcoming dividends,
    or wants to know about near-term catalysts for a stock.
    """
    return get_upcoming_events(symbol, exchange)


# ─────────────────────────────────────────────────────────────────────────────
# WEB AND NEWS TOOLS
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def search_web_tool(query: str, max_results: int = 5) -> dict:
    """
    Search the live internet using Tavily for any general information.

    Use for: macro-economic data, regulatory changes, government policy, industry
    trends, company announcements, or any factual question needing current data.

    Do NOT use for stock prices — use get_stock_info_tool for that.
    Prefer search_news_tool when the user explicitly asks about news articles.

    For multi-step research tasks (e.g. 'find top 5 impacted industries'), call
    this tool FIRST to gather context, then use ticker/stock tools for each company.
    """
    return {"results": search_web(query, max_results)}


@mcp.tool()
def search_news_tool(query: str, days_back: int = 7) -> dict:
    """
    Search recent news articles. Returns title, source, date, and description
    for each article — structured for easier parsing than raw web results.

    Use when the user asks about:
    - Latest news about a company or sector
    - Recent market events
    - Sentiment around a stock or industry
    - Breaking developments affecting Indian markets

    days_back : How many days back to search (default 7, max ~30).
    """
    return {"results": search_news(query, days_back)}


# ─────────────────────────────────────────────────────────────────────────────
# TICKER LOOKUP
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def search_ticker_tool(query: str) -> dict:
    """
    Resolve a company name to its NSE/BSE ticker symbol using the India listings database.

    ALWAYS call this FIRST when the user gives a company name instead of a ticker.
    Do not guess tickers — always look them up.

    Examples:
      "HDFC Bank"       -> HDFCBANK
      "Tata Motors"     -> TATAMOTORS
      "Infosys"         -> INFY
      "Reliance"        -> RELIANCE

    For multi-company workflows, call this once per company name before fetching data.
    """
    return {"results": search_ticker(query)}


# ─────────────────────────────────────────────────────────────────────────────
# DOCUMENT TOOLS
#
# Both tools ensure the document is indexed into ChromaDB before any query is
# run. This makes each tool independently safe to call — the caller (agent) does
# not need to worry about call ordering.
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def parse_document_tool(session_id: str) -> dict:
    """
    Parse all uploaded documents in this session and return their FULL raw content.

    Use for BROAD questions about an uploaded file:
      - "Summarise this document"
      - "What is this file about?"
      - "Give me an overview of the uploaded report"

    This tool also indexes the documents into the vector store so that
    search_documents_tool can be called afterwards for specific questions.

    session_id : Provided in the system note appended to the user's message.
    """
    files = get_files(session_id)
    if not files:
        return {"error": "No documents uploaded in this session."}

    results = []
    for f in files:
        parsed = parse_uploaded_file(f["filepath"])
        parsed["filename"] = f["filename"]
        results.append(parsed)

        # Index into ChromaDB so search_documents_tool works immediately after.
        # Uses the file_id as doc_id for stable, idempotent chunk IDs.
        if parsed.get("type") != "error":
            index_document(f["file_id"], parsed)

    return {"documents": results}


@mcp.tool()
def search_documents_tool(session_id: str, query: str, top_k: int = 5) -> dict:
    """
    Semantically search across uploaded documents for a specific answer.

    Use for SPECIFIC questions about an uploaded file:
      - "What was the revenue in FY24?"
      - "What does the document say about risk factors?"
      - "Find the section about capital allocation"

    Prefer this over parse_document_tool for targeted questions — it returns
    only the most relevant passages rather than the entire document.

    This tool automatically parses and indexes any un-indexed documents before
    searching, so it is safe to call even if parse_document_tool was not called first.

    session_id : Provided in the system note appended to the user's message.
    query      : Natural-language question to search for.
    top_k      : Number of most relevant passages to return (default 5).
    """
    files = get_files(session_id)
    if not files:
        return {"error": "No documents uploaded in this session."}

    # Ensure every file in the session is indexed before we query.
    # index_document() uses upsert so calling it on an already-indexed file is free.
    for f in files:
        parsed = parse_uploaded_file(f["filepath"])
        if parsed.get("type") != "error":
            index_document(f["file_id"], parsed)

    chunks = query_documents(query=query, n_results=top_k)

    if not chunks:
        return {
            "status": "no_results",
            "message": "No relevant passages found. Try rephrasing the query.",
            "results": [],
        }

    return {
        "status": "success",
        "query": query,
        "results": chunks,
    }


# ─────────────────────────────────────────────────────────────────────────────
# FORECAST TOOL
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def predict_stock_tool(
    symbol: str,
    exchange: str = "NSE",
    horizon_days: int = 10,
) -> dict:
    """
    Forecast the next N daily closing prices using Amazon Chronos (zero-shot time-series model).

    Call ONLY when the user explicitly asks for a price forecast, prediction, or outlook.
    Do NOT call for current prices — use get_stock_info_tool for that.

    For a complete forecast report, the recommended call sequence is:
      1. search_ticker_tool  (if company name given)
      2. get_stock_history_tool (period="3mo") to show recent trend context
      3. predict_stock_tool  (this tool) for the forward projection
      4. get_analyst_data_tool for comparison with analyst targets

    horizon_days : Number of trading days to forecast ahead.
                   Recommended range: 5 to 20. Default: 10.
    """
    return predict_stock_prices(symbol, exchange, horizon_days)


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")
