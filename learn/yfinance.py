# %%
import json

import yfinance as yf

from learn_utility import display_news_article, print_separation

# %%
# pd.set_option('display.max_rows', None)
# pd.set_option('display.max_columns', None)
# pd.set_option('display.width', None)

# %%
"""
1. CREATE A TICKER OBJECT
- The Ticker class is the primary entry point for accessing data related to a specific financial instrument.
- It acts as an object-oriented wrapper around the Yahoo Finance API for a given symbol.
- You instantiate it by passing the ticker string (e.g., "AAPL" for Apple Inc. or "BTC-USD" for Bitcoin).

Syntax:
    import yfinance as yf
    ticker_object = yf.Ticker("SYMBOL")

For Indian Stock Market, append the suffic .NS and .BO for NSE and BSE data respectively.
Example:
    ticker_NSE = yf.Ticker('TCS.NS')
    ticker_BSE = yf.Ticker('TCS.BO')

Use `.info` propertyfor getting information about the stock. This returns a dictionary.
"""
ticker_NSE = yf.Ticker("TCS.NS")
ticker_BSE = yf.Ticker("TCS.BO")


# View all available key in info dictionary
def get_all_info_keys(ticker):
    print_separation("Available Keys in Info Dictionary")
    for key in ticker.info:
        print(f"{key}: {ticker.info[key]}")


# get_all_info_keys(ticker_NSE)

# print(f"===============================================================================")
# print(f"Current price: {ticker_NSE.info['currentPrice']}")
# print(f"Lowest price in last one year: {ticker_NSE.info['fiftyTwoWeekLow']}")
# print(f"Highest price in last one year: {ticker_NSE.info['fiftyTwoWeekHigh']}")
# print(f"===============================================================================")

# %%
"""
NOTE:
    - Accessing ticker.info multiple times (as in your loops and print statements) is inefficnet.
    - It triggers a fresh network request each time, which can lead to rate limiting.
    - It is more efficient to store the dictionary in a variable first.
"""

tcs_info = ticker_NSE.info
print_separation("Accessing Info Keys")
print(f"Complete Company Name: {tcs_info.get('longName')}")
print(f"Type: {tcs_info.get('typeDisp')}")
print(f"Currency: {tcs_info.get('financialCurrency')}")
print(f"Current price: {tcs_info.get('currentPrice')}")
print(f"52-Week Low: {tcs_info.get('fiftyTwoWeekLow')}")
print(f"52-Week High: {tcs_info.get('fiftyTwoWeekHigh')}")
print(f"52-Week Change %: {tcs_info.get('fiftyTwoWeekChangePercent')}")
# print(f"52-Week High: {tcs_info.get('')}")

# %%
"""
2. UPCOMING FINANCIAL EVENTS FOR THE TICKER
- The .calendar property provides a dictionary of upcoming corporate events.
- Such as earnings announcement dates and ex-dividend dates.
"""

cal = ticker_NSE.calendar
print_separation("Upcoming Financial Events")
for k, v in cal.items():
    print(f"{k}: {v}")

# %%
"""
3. READ NEWS ARTICLES ASSOCIATED WITH THE TICKER
- The .news property returns a list of dictionaries, where each dictionary represents a recent article.
- Properties: 'title', 'publisher', 'link', and 'provider_publish_time'.
- The time is provided in Unix epoch format.
"""

print_separation("News Articles")
news = ticker_NSE.news
article1 = news[0]

print_separation("View a Single Article Dictionary")
formatted_json = json.dumps(article1, indent=4)
print(formatted_json)

print_separation("View a Single Formatted Article")
display_news_article(article1)

# for article in news:
#     display_news_article(article)

# %%
"""
5. HISTORICAL DATA
- Use the .history() method to retrieve OHLCV data.
- Returns a pandas DataFrame with Date as the index.
- Automatically adjusts for stock splits and dividends by default (auto_adjust=True).

Examples:
- Today's price: Uses period='1d' with small intervals like '1m'.
- 30-day price: Uses period='1mo' with '1d' intervals.
- 1-year price: Uses period='1y' with '1d' intervals.
"""
# Initialize Ticker for Wipro
wipro = yf.Ticker("WIPRO.NS")

print_separation(f"Fetch Historical Data for {wipro.info['longName']}")

# Fetching today's price data (Intraday)
# Note: 1m interval data is only available for the last 7 days.
today_df = wipro.history(period="1d", interval="1m")
current_price = today_df["Close"].iloc[-1] if not today_df.empty else "N/A"
print(f"Current Wipro Price (NSE): {current_price}")

# Fetching previous 30 days data
monthly_df = wipro.history(period="1mo", interval="1d")
print("\nLast 30 Days High/Low:")
print(monthly_df[["High", "Low"]].tail())

# Fetching 1 year data
yearly_df = wipro.history(period="1y", interval="1d")
print("\nYearly Data Summary (First 5 rows):")
print(yearly_df.head())

# %%
"""
6. FUNDAMENTAL ANALYSES
Three core financial statements:
    - The Income Statement: <ticker_obj>.financials, and <ticker_obj>.quaterly_financials
    - Balance Sheet: <ticker_obj>.balance_sheet, and <ticker_obj>.quarterly_balance_sheet
    - Cash Flow Statement. <ticker_obj>.cashflow and <ticker_obj>.quarterly_cashflow
"""

tata_steel = yf.Ticker("TATASTEEL.NS")

# %%
"""
- financials: Returns annual data for the last 4 years.
- quarterly_financials: Returns data for the last 4 quarters.
- Rows represent metrics (Revenue, EBITDA, Net Income), columns represent dates.
"""

# Fetch and display the annual Income Statement
income_stmt = tata_steel.financials
q_income_stmt = tata_steel.quarterly_financials

print_separation("Annual Income Statement (Latest 2 Years):")
# Use .iloc to slice the first two columns (most recent years)

print(income_stmt.iloc[:, :2])
# Access a specific metric like 'Total Revenue'
if "Total Revenue" in income_stmt.index:
    latest_revenue = income_stmt.loc["Total Revenue"].iloc[0]
    print(f"\nLatest Annual Revenue: {latest_revenue}")

# %%
"""
- balance_sheet: Annual snapshot of Assets, Liabilities, and Equity.
- quarterly_balance_sheet: Snapshot for the last 4 reporting quarters.
"""

annual_bs = tata_steel.balance_sheet
quarterly_bs = tata_steel.quarterly_balance_sheet

print_separation("Quarterly Balance Sheet (Most Recent Quarter):")
# Display only the most recent quarter (first column)
print(quarterly_bs.iloc[:, 0])

# %%
"""
- cashflow: Tracks annual cash movements.
- quarterly_cashflow: Tracks quarterly cash movements.
"""
# Fetch annual Cash Flow
cash_flow = tata_steel.cashflow
quaterly_cash_flow = tata_steel.quarterly_cashflow

print_separation("Annual Cash Flow (Top 5 Rows):")
print(cash_flow.head(5))

# %%
"""
7. CORPORATE ACTIONS
Corporate actions are events initiated by a public company that bring material change to the stock.
The two most common are Dividends (cash distribution to shareholders) and
Stock Splits (increasing the number of shares while lowering the price per share).

- ticker_object.actions -> # Returns a combined DataFrame of Dividends and Splits
- ticker_object.dividends -> # Returns only Dividends
- ticker_object.splits -> # Returns only Stock Splits
"""

itc = yf.Ticker("ITC.NS")
print_separation(f"Corporate Actions for {itc.info.get('longName')} are:")

actions = itc.actions
divs = itc.dividends
splits = itc.splits

if not actions.empty:
    print("Recent Corporate Actions (Latest 5):")
    print(actions.tail(5))


if not divs.empty:
    print(f"\nLast Dividend Amount: {divs.iloc[-1]} {itc.info.get('currency')}")

if not splits.empty:
    print("\nHistorical Stock Splits:")
    print(splits)
else:
    print("\nNo historical stock splits found for this ticker.")
# %%
"""
8. ANALYST RECOMMENDATIONS & PRICE TARGETS
- .recommendations_summary: Returns a table showing counts of Strong Buy, Buy, Hold, and Sell.
- .info: Contains price targets like 'targetMeanPrice', 'targetHighPrice', and 'targetLowPrice'.
- Analyst coverage varies; mid-cap or small-cap Indian stocks may have limited or no data.
"""

sbi = yf.Ticker("SBIN.NS")

print_separation(f"Analyst Insights for {sbi.info.get('longName')}")

# 1. Price Targets
sbi_info = sbi.info
print(f"Current Price: {sbi_info.get('currentPrice')}")
print(f"Mean Target Price: {sbi_info.get('targetMeanPrice')}")
print(f"Target High: {sbi_info.get('targetHighPrice')}")
print(f"Target Low: {sbi_info.get('targetLowPrice')}")

# 2. Recommendation Summary
rec_summary = sbi.recommendations_summary
if rec_summary is not None:
    print("\nRecommendation Summary Counts:")
    print(rec_summary)
else:
    print("\nNo analyst recommendation summary found.")

# %%
"""
9. MAJOR HOLDERS AND INSTITUTIONAL OWNERSHIP
- .major_holders: Returns a DataFrame showing ownership percentages (e.g., % held by insiders).
- .institutional_holders: Returns a DataFrame of top institutional investors and their shares.
- .mutualfund_holders: Returns a DataFrame of top mutual funds invested in the company.
- Note: This data is updated periodically based on regulatory filings (like SEBI filings in India).
"""

# Initialize Ticker for HDFC Bank
hdfc = yf.Ticker("HDFCBANK.NS")

print_separation(f"Ownership Structure: {hdfc.info.get('longName')}")

major = hdfc.major_holders
insts = hdfc.institutional_holders
mutual = hdfc.mutualfund_holders

print("Major Holders Summary:")
print(major)

if insts is not None:
    print("Top 5 major institutional holders")
    print(insts.head(5))

if mutual is not None:
    print("Top 5 major mutual funds holders")
    print(mutual.head(5))

# %%
"""
10. SUSTAINABILITY (ESG) SCORES
- .sustainability: Provides scores for Environment, Social, and Governance risk.
- Total ESG Risk score: A lower score indicates lower risk.
- Percentile: Shows how the company ranks compared to global peers in the same industry.
- This data is provided to Yahoo Finance by Sustainalytics.
"""

infy = yf.Ticker("INFY.NS")

print_separation(f"Sustainability Data for {infy.info.get('longName')}")

esg_data = infy.sustainability

if esg_data is not None:
    print("ESG Risk Scores & Ratings:")
    print(esg_data)

    # Accessing specific score if needed
    if "totalEsg" in esg_data.index:
        print(f"\nTotal ESG Risk Score: {esg_data.loc['totalEsg', 'Value']}")
else:
    print("ESG/Sustainability data is not available for this ticker.")
