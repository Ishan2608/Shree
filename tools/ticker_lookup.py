import os
import pandas as pd

# Global dictionary for O(1) lookup.
_lookup_table: dict[str, dict] = {}
_listings_path = os.path.join("data", "listings", "INDIA_LIST.csv")

def _load_listings() -> None:
    global _lookup_table

    # TODO 1: Check if _listings_path exists. If not, print a warning and return.
    if not os.path.exists(_listings_path):
        print(f"WARNING: LISTING TABLE MISSING")
        return
    
    # TODO 2: Read the CSV using pandas.
    # - Use dtype=str to prevent pandas from auto-converting codes/ISINs.
    # - Use df.replace(["N/A", "nan", "NA", "-"], "") to clean literal string artifacts.
    # - Use df.fillna("") to replace actual NaN values with empty strings.

    # TODO 3: Iterate through the rows. (Use `for index, row in df.iterrows():` since column names have spaces like 'Security Code')
    
    # TODO 4: Inside the loop, extract and clean the 5 core variables:
    # - isin = str(row['ISIN']).strip()
    # - company_name = str(row['Company_Name']).strip()
    # - nse_symbol = str(row['NSE_Symbol']).strip()
    # - bse_symbol = str(row['BSE_Symbol']).strip()
    # - bse_code_raw = str(row['Security Code']).strip()
    
    # TODO 5: Fix the BSE Code float issue. 
    # If bse_code_raw ends with ".0", remove it (e.g., "890232.0" -> "890232").
    # Save the cleaned result as `bse_code`.

    # TODO 6: Skip this row entirely if `isin` is empty.

    # TODO 7: Create the `entry` dictionary for this row:
    # { "company_name": company_name, "nse_symbol": nse_symbol, "bse_symbol": bse_symbol, "bse_code": bse_code, "isin": isin }

    # TODO 8: Add the entry to _lookup_table under 4 possible keys (convert alphabetic keys to lowercase!):
    # - if company_name != "": _lookup_table[company_name.lower()] = entry
    # - if nse_symbol != "": _lookup_table[nse_symbol.lower()] = entry
    # - if bse_symbol != "": _lookup_table[bse_symbol.lower()] = entry
    # - if bse_code != "": _lookup_table[bse_code] = entry

    # TODO 9: Print an initialization message: f"Loaded {len(_lookup_table)} lookup keys from INDIA_LIST."
    pass


def search_ticker(query: str) -> list[dict]:
    # TODO 10: If _lookup_table is empty, call _load_listings().

    # TODO 11: Clean the query: `query_lower = query.strip().lower()`. If empty, return [].

    # TODO 12: EXACT MATCH PASS
    # Check `if query_lower in _lookup_table`. If True, return `[_lookup_table[query_lower]]` immediately.

    # TODO 13: Setup for fuzzy search. 
    # Initialize `starts_with = []`, `contains = []`, and `seen_isins = set()`.

    # TODO 14: FUZZY MATCH PASS
    # Iterate through `for key, entry in _lookup_table.items():`
    # Extract `current_isin = entry['isin']`.
    # If `current_isin` is already in `seen_isins`, `continue` (skip to next iteration to prevent duplicates).

    # TODO 15: Check for partial matches inside the loop:
    # - If `key.startswith(query_lower)`: append `entry` to `starts_with` and add `current_isin` to `seen_isins`.
    # - Elif `query_lower in key`: append `entry` to `contains` and add `current_isin` to `seen_isins`.

    # TODO 16: Combine and return the top 5 results: `return (starts_with + contains)[:5]`
    pass

# Run on import
_load_listings()
