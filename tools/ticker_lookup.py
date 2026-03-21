"""
ticker_lookup.py — Resolve company names to NSE/BSE ticker symbols.

The listings CSV is loaded LAZILY on the first search_ticker() call.
It is NOT loaded at module import time, which avoids the pandas CSV read
(~200ms, ~30MB RAM) on every process startup even when ticker lookup is unused.

After the first call, _lookup_table is populated in-memory for O(1) lookups.
"""

import os

_lookup_table: dict[str, dict] = {}
_listings_path = os.path.join("data", "listings", "INDIA_LIST.csv")
_loaded = False


def _load_listings() -> None:
    """
    Load stock market listings from CSV into the global in-memory lookup dict.
    Called automatically on the first search_ticker() call (lazy load).
    Safe to call multiple times — subsequent calls are no-ops.
    """
    global _lookup_table, _loaded
    if _loaded:
        return

    import pandas as pd

    if not os.path.exists(_listings_path):
        import sys
        print(f"Warning: {_listings_path} not found. Ticker lookup will return no results.", file=sys.stderr)
        _loaded = True
        return

    df = pd.read_csv(_listings_path, dtype=str)
    df = df.replace(["N/A", "nan", "NA", "-", "NaN"], "")
    df = df.fillna("")

    for _, row in df.iterrows():
        isin         = str(row.get("ISIN", "")).strip()
        company_name = str(row.get("Company_Name", "")).strip()
        nse_symbol   = str(row.get("NSE_Symbol", "")).strip()
        bse_symbol   = str(row.get("BSE_Symbol", "")).strip()
        bse_code_raw = str(row.get("Security Code", "")).strip()

        # Fix float suffix: "890232.0" -> "890232"
        bse_code = bse_code_raw[:-2] if bse_code_raw.endswith(".0") else bse_code_raw

        if not isin:
            continue

        entry = {
            "company_name": company_name,
            "nse_symbol":   nse_symbol,
            "bse_symbol":   bse_symbol,
            "bse_code":     bse_code,
            "isin":         isin,
        }

        if company_name:
            _lookup_table[company_name.lower()] = entry
        if nse_symbol:
            _lookup_table[nse_symbol.lower()] = entry
        if bse_symbol:
            _lookup_table[bse_symbol.lower()] = entry
        if bse_code:
            _lookup_table[bse_code] = entry

    import sys
    print(f"Loaded {len(_lookup_table)} lookup keys from INDIA_LIST.", file=sys.stderr)
    _loaded = True


def search_ticker(query: str) -> list[dict]:
    """
    Search the in-memory lookup table for a stock using a user's query.

    Triggers a one-time CSV load on first call. Subsequent calls are instant.

    Args:
        query: Company name, ticker symbol, or BSE security code.

    Returns:
        List of up to 5 matching dicts with company_name, nse_symbol,
        bse_symbol, bse_code, isin. Prioritised: exact > prefix > substring.
    """
    _load_listings()

    query_lower = query.strip().lower()
    if not query_lower:
        return []

    # O(1) exact match
    if query_lower in _lookup_table:
        return [_lookup_table[query_lower]]

    starts_with = []
    contains    = []
    seen_isins  = set()

    for key, entry in _lookup_table.items():
        isin = entry["isin"]
        if isin in seen_isins:
            continue
        if key.startswith(query_lower):
            starts_with.append(entry)
            seen_isins.add(isin)
        elif query_lower in key:
            contains.append(entry)
            seen_isins.add(isin)

    return (starts_with + contains)[:5]


# ── Manual test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n--- Exact match: TCS ---")
    for r in search_ticker("TCS"):
        print(r)

    print("\n--- Fuzzy match: HDFC ---")
    for r in search_ticker("HDFC"):
        print(r)

    print("\n--- BSE code: 500180 ---")
    for r in search_ticker("500180"):
        print(r)

    print("\n--- Invalid query ---")
    print(search_ticker("FAKECOMPANYNAME123"))
