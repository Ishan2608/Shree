import os
import pandas as pd
import config import settings

_LOOKUP_TABLE: dict[str, dict] = {}
_LISTING_PATH: os.path.join("data", "listings", "indian_listings.csv")

def _load_listings() -> None:
    """
    Populates the in-memory hash map from the master CSV file.
    """
    global _lookup_table

    # TODO: Define column constants matching the headers in indian_listings.csv
    # Hint: Use 'NAME OF COMPANY', 'Listed_Company_Name', 'SYMBOL', 'BSE_Security_Code', and 'ISIN'

    # TODO: Validate that the master CSV file exists at _listings_path
    # If missing, print a warning and return early to prevent crashes

    # TODO: Load the CSV using pandas with dtype=str to preserve codes like '000001'
    # Use .fillna("") to handle missing exchange data (e.g., companies only on NSE)

    # TODO: Iterate through the DataFrame rows using .itertuples()
    # 1. Resolve 'raw_name' by checking NSE name first, then falling back to BSE name
    # 2. Extract and strip nse_symbol, bse_code, and isin
    # 3. Create a dictionary 'entry' containing these 4 key-value pairs

    # TODO: Index the 'entry' in _lookup_table under multiple keys for O(1) access:
    # 1. Key: lowercase company_name
    # 2. Key: lowercase nse_symbol
    # 3. Key: bse_code
    
    # TODO: Print a success message showing the total number of keys loaded into memory
    pass


def search_ticker(query: str) -> list[dict]:
    """
    Finds up to 5 relevant stock matches based on a user query.
    """
    # TODO: Check if _lookup_table is empty; if so, trigger _load_listings()
    
    # TODO: Sanitize the input query (strip whitespace and convert to lowercase)
    # Return an empty list immediately if the resulting query is empty

    # TODO: [Pass 1] Perform an exact key lookup in _lookup_table
    # If found, return the result immediately as a single-item list

    # TODO: [Pass 2 & 3] Perform fuzzy search by iterating over _lookup_table keys
    # Use a 'seen_isins' set to ensure unique companies (avoid name/symbol duplicates)
    # 1. If key.startswith(query), add to 'starts_with' list
    # 2. Else if query in key, add to 'contains' list

    # TODO: Concatenate 'starts_with' and 'contains' results
    # Return the first 5 matches to maintain a clean AI context
    pass

# TODO: Call _load_listings() to ensure data is ready as soon as the module is imported
_load_listings()

# import os
# import pandas as pd
# from config import settings

# # Module-level lookup table loaded once at startup.
# _lookup_table: dict[str, dict] = {}
# _listings_path = os.path.join("data", "listings", "indian_listings.csv")

# def _load_listings() -> None:
#     """
#     Parses the consolidated CSV and populates a hash map where keys are both 
#     company names and ticker symbols for O(1) retrieval.
#     """
#     global _lookup_table

#     # Column constants based on the master CSV merge result
#     COL_NAME = "NAME OF COMPANY"  # Primary name from NSE source
#     COL_NAME_BSE = "Listed_Company_Name" # Fallback from BSE source
#     COL_NSE = "SYMBOL"
#     COL_BSE = "BSE_Security_Code"
#     COL_ISIN = "ISIN"

#     if not os.path.exists(_listings_path):
#         print(f"Warning: {_listings_path} not found. Ticker lookup will return no results.")
#         return

#     # Load CSV into DataFrame
#     df = pd.read_csv(_listings_path, dtype=str).fillna("")

#     for row in df.itertuples():
#         # Resolve company name (prefer NSE, fallback to BSE)
#         raw_name = getattr(row, COL_NAME, "") or getattr(row, COL_NAME_BSE, "")
#         company_name = raw_name.strip().lower()
        
#         nse_symbol = getattr(row, COL_NSE, "").strip().upper()
#         bse_code = getattr(row, COL_BSE, "").strip()
#         isin = getattr(row, COL_ISIN, "").strip()

#         entry = {
#             "company_name": raw_name.strip(),
#             "nse_symbol": nse_symbol,
#             "bse_code": bse_code,
#             "isin": isin
#         }

#         # Indexing: Map both the name and the symbols to the same entry
#         if company_name:
#             _lookup_table[company_name] = entry
#         if nse_symbol:
#             _lookup_table[nse_symbol.lower()] = entry
#         if bse_code:
#             _lookup_table[bse_code] = entry

#     print(f"Loaded {len(_lookup_table)} lookup keys from {_listings_path}.")


# def search_ticker(query: str) -> list[dict]:
#     """
#     Resolves natural language queries into structured ticker data.
#     Search Strategy:
#     1. Exact Match: Highest priority.
#     2. Starts With: Secondary priority.
#     3. Contains: Tertiary priority.
#     """
#     if not _lookup_table:
#         _load_listings()

#     query_lower = query.strip().lower()
#     if not query_lower:
#         return []

#     # Pass 1: Exact Match
#     if query_lower in _lookup_table:
#         return [_lookup_table[query_lower]]

#     # Pass 2 & 3: Fuzzy search
#     starts_with = []
#     contains = []
#     seen_isins = set()

#     for key, entry in _lookup_table.items():
#         # Prevent duplicate results for the same company (name vs symbol keys)
#         isin = entry["isin"]
#         if isin in seen_isins:
#             continue

#         if key.startswith(query_lower):
#             starts_with.append(entry)
#             seen_isins.add(isin)
#         elif query_lower in key:
#             contains.append(entry)
#             seen_isins.add(isin)

#     # Combine results and deduplicate by keeping the most relevant first
#     results = (starts_with + contains)[:5]
#     return results

# # Load listings at import time.
# _load_listings()
