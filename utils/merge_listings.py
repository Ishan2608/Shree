import pandas as pd
import os

def create_master_listings(nse_path: str, bse_path: str, output_path: str):
    """
    Technical Definition:
    Performs a full outer join on two CSV datasets using a standardized ISIN key. 
    It preserves all metadata columns from both exchange sources while 
    consolidating the join keys into a single 'ISIN' column.

    Intuitive Explanation:
    This script merges your NSE and BSE files into one master list. 
    If a company exists in both files (matched by ISIN), it combines them into one row. 
    If a company exists in only one file, it still keeps that record but leaves the 
    other exchange's columns empty. This creates a single source of truth for Shree.
    """
    
    # Check if input files exist to avoid FileNotFoundError
    if not os.path.exists(nse_path) or not os.path.exists(bse_path):
        print(f"Error: One or both input files not found.\nNSE: {nse_path}\nBSE: {bse_path}")
        return

    # 1. Load NSE and trim headers to handle leading spaces like ' ISIN NUMBER'
    nse = pd.read_csv(nse_path, dtype=str)
    nse.columns = [c.strip() for c in nse.columns]
    
    # 2. Load BSE and trim headers
    bse = pd.read_csv(bse_path, dtype=str)
    bse.columns = [c.strip() for c in bse.columns]

    # 3. Create standardized Join Keys
    # Using a temporary column 'ISIN_TEMP' to perform the merge
    nse['ISIN_TEMP'] = nse['ISIN NUMBER'].str.strip().str.upper()
    bse['ISIN_TEMP'] = bse['ISIN No'].str.strip().str.upper()

    # 4. Perform Outer Join
    # 
    master_df = pd.merge(
        nse, 
        bse, 
        on='ISIN_TEMP', 
        how='outer',
        suffixes=('_NSE', '_BSE')
    )

    # 5. Final ISIN Consolidation
    # Assign the successful join key to the final 'ISIN' column
    master_df['ISIN'] = master_df['ISIN_TEMP']

    # 6. Cleanup
    # Remove temporary merge key and original redundant ISIN columns
    cols_to_drop = ['ISIN_TEMP', 'ISIN NUMBER', 'ISIN No']
    master_df = master_df.drop(columns=[c for c in cols_to_drop if c in master_df.columns])
    
    # Fill NaN values with empty strings for a clean CSV output
    master_df = master_df.fillna("")

    # 7. Export to CSV
    # Ensure the directory exists before saving
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    master_df.to_csv(output_path, index=False)
    
    print(f"Master CSV created successfully at: {output_path}")
    print(f"Total Companies Processed: {len(master_df)}")
    print(f"Total Metadata Columns Retained: {len(master_df.columns)}")

if __name__ == "__main__":
    create_master_listings(
        nse_path="../data/listings/NSE_27_Jan_2026.csv",
        bse_path="../data/listings/BSE_LISTINGS_28_01_2026.csv",
        output_path="../data/listings/indian_listings.csv"
    )
