"""
mcp_server.py — MCP Tool Server

Every tool the agent can call is registered here using @mcp.tool() decorators.
The docstring on each tool function is the agent's selection guide — write them precisely.

Run mode: This file is launched as a subprocess by agent.py via MCPToolset.
          The agent communicates with it over stdin/stdout using the MCP protocol.
          Do NOT run this file manually during normal operation.

To test tools in isolation, use test_tools.py instead.
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
from tools.web_search import search_web
from tools.news_search import search_news
from tools.ticker_lookup import search_ticker
from tools.ts_model import predict_stock_prices
from utils.doc_parser import parse_uploaded_file
from utils.rag_engine import query_documents


mcp = FastMCP("shree-tools")


# ─────────────────────────────────────────────────────────────────────────────
# STOCK DATA TOOLS
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def tool_get_stock_info(symbol: str, exchange: str = "NSE") -> dict:
    """
    Get real-time price, 52-week range, PE ratio, margins, debt ratios, and analyst targets.
    Call this when the user asks about a stock's current state, price, or basic fundamentals.
    symbol: NSE/BSE ticker WITHOUT suffix. Examples: TCS, WIPRO, INFY, HDFCBANK, SBIN.
    exchange: NSE (default) or BSE.
    """
    return get_stock_info(symbol, exchange)


@mcp.tool()
def tool_get_stock_history(
    symbol: str,
    exchange: str = "NSE",
    period: str = "1mo",
    interval: str = "1d",
) -> dict:
    """
    Get OHLCV historical price data formatted for candlestick or line charts.
    Call this when the user asks for a price chart, trend analysis, or historical performance.
    period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y.
    interval: 1m (last 7d only), 1h, 1d, 1wk.
    """
    return get_stock_history(symbol, exchange, period, interval)


@mcp.tool()
def tool_get_financials(
    symbol: str,
    exchange: str = "NSE",
    statement: str = "income",
    quarterly: bool = False,
) -> dict:
    """
    Get financial statements: income statement, balance sheet, or cash flow statement.
    Call this when analyzing revenue, profit, debt levels, or cash generation.
    statement: "income" (P&L), "balance_sheet" (assets/liabilities), or "cashflow".
    quarterly: True for last 4 quarters, False for last 4 annual periods.
    """
    return get_financials(symbol, exchange, statement, quarterly)


@mcp.tool()
def tool_get_corporate_actions(symbol: str, exchange: str = "NSE") -> dict:
    """
    Get dividend history and stock split history.
    Call this when the user asks about dividends, shareholder returns, or historical splits.
    """
    return get_corporate_actions(symbol, exchange)


@mcp.tool()
def tool_get_analyst_data(symbol: str, exchange: str = "NSE") -> dict:
    """
    Get analyst consensus: price targets (mean/high/low) and buy/hold/sell recommendation counts.
    Call this when the user asks what analysts think, or to add analyst consensus to an analysis.
    """
    return get_analyst_data(symbol, exchange)


@mcp.tool()
def tool_get_holders(symbol: str, exchange: str = "NSE") -> dict:
    """
    Get top institutional and mutual fund shareholders.
    Call this when the user asks about ownership structure or institutional interest.
    """
    return get_holders(symbol, exchange)


@mcp.tool()
def tool_get_esg_data(symbol: str, exchange: str = "NSE") -> dict:
    """
    Get ESG (Environmental, Social, Governance) risk scores from Sustainalytics.
    Call this when the user asks about sustainability, ESG rating, or ethical investing.
    Note: only available for large-cap stocks. Returns error dict for uncovered stocks.
    """
    return get_esg_data(symbol, exchange)


@mcp.tool()
def tool_get_upcoming_events(symbol: str, exchange: str = "NSE") -> dict:
    """
    Get upcoming earnings dates and ex-dividend dates from the stock calendar.
    Call this when the user asks when the next earnings report or dividend is.
    """
    return get_upcoming_events(symbol, exchange)


# ─────────────────────────────────────────────────────────────────────────────
# WEB AND NEWS TOOLS
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def tool_search_web(query: str, max_results: int = 5) -> dict:
    """
    Search the internet for current information using Tavily.
    Call this for macro events, regulatory changes, sector news, or anything needing live data.
    Do NOT call this for stock prices or financial statements — use the stock tools above instead.
    Keep queries specific: "RBI rate decision impact on bank stocks" not just "banks".
    """
    return {"results": search_web(query, max_results)}


@mcp.tool()
def tool_search_news(query: str, days_back: int = 7) -> dict:
    """
    Search recent news articles with source, date, and description metadata.
    Prefer this over tool_search_web when the user explicitly asks about news,
    press releases, or recent company/sector events with structured metadata.
    days_back: How many days of history to search. Default 7.
    """
    return {"results": search_news(query, days_back)}


# ─────────────────────────────────────────────────────────────────────────────
# TICKER LOOKUP TOOL
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def tool_search_ticker(query: str) -> dict:
    """
    Find the NSE/BSE ticker symbol for an Indian company by name or partial name.
    Call this FIRST when the user mentions a company by name instead of ticker symbol.
    Example: user says "analyze HDFC Bank" -> call this with "hdfc bank" -> get "HDFCBANK".
    Returns up to 5 matches with company_name, nse_symbol, bse_code, and ISIN.
    """
    return {"results": search_ticker(query)}


# ─────────────────────────────────────────────────────────────────────────────
# DOCUMENT TOOLS
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def tool_parse_document(filepath: str) -> dict:
    """
    Parse a user-uploaded document and return its full extractable content.
    Supports PDF, DOCX, Excel (.xlsx/.xls), CSV, TXT, and PPT/PPTX.
    Call this when the user asks questions about a file they uploaded in the current session.
    Call tool_search_documents instead if the user wants to search/query across the document.
    filepath: The absolute path to the uploaded file on disk (provided in the system note).
    """
    if not filepath:
        return {"error": "No filepath provided."}
    return parse_uploaded_file(filepath)


@mcp.tool()
def tool_search_documents(filepaths: str, query: str, top_k: int = 5) -> dict:
    """
    Semantically search across uploaded documents.
    Use this when the user asks a question that should be answered from their uploaded files,
    especially for long documents where reading the whole file would be unnecessary.
    Prefer this over tool_parse_document for question-answering over documents.
    filepaths: Comma-separated absolute paths to uploaded files (provided in the system note).
    query: The natural-language question or keyword to search for.
    top_k: Number of most relevant passages to return. Default 5.
    """
    if not filepaths:
        return {"error": "No filepaths provided."}
    path_list = [p.strip() for p in filepaths.split(",") if p.strip()]
    return query_documents(path_list, query, top_k)


# ─────────────────────────────────────────────────────────────────────────────
# TIME SERIES FORECAST TOOL
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def tool_predict_stock(
    symbol: str,
    exchange: str = "NSE",
    horizon_days: int = 10,
) -> dict:
    """
    Forecast the next N closing prices for a stock using Amazon Chronos (zero-shot model).
    Call this ONLY when the user explicitly asks for a price prediction or forecast.
    Do NOT call this for current prices — use tool_get_stock_info for that.
    Always pair this forecast with news context and fundamental analysis in your response.
    The model uses price patterns only and cannot account for news or macro events.
    horizon_days: Future trading days to forecast. Recommended range: 5 to 20.
    """
    return predict_stock_prices(symbol, exchange, horizon_days)


# ─────────────────────────────────────────────────────────────────────────────
# SERVER ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")
