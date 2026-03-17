import sqlite3

# %%
"""
1. CREATE A CONNECTION AND DATABASE
- The connect() method establishes a connection to the SQLite database.
- If the file does not exist, it will be created automatically.
- Passing ':memory:' creates a temporary in-memory database that is destroyed when the connection closes.

Syntax:
    import sqlite3
    conn = sqlite3.connect("database_name.db")
"""

# Establish a connection to a local file-based database
conn = sqlite3.connect("./db/shree_financials.db")

# Create a cursor object to execute SQL commands
cursor = conn.cursor()

# %%
"""
2. CREATE TABLES
- Use the execute() method on the cursor to run Data Definition Language (DDL) queries.
- Using IF NOT EXISTS prevents errors if the script runs multiple times.
- SQLite is dynamically typed, but standard SQL types (TEXT, INTEGER, REAL) are recommended for clarity.
"""
# 

create_table_query = """
CREATE TABLE IF NOT EXISTS portfolio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    shares INTEGER NOT NULL,
    purchase_price REAL NOT NULL,
    purchase_date TEXT
)
"""
cursor.execute(create_table_query)

# Commit the transaction to save changes to the file
conn.conn() if hasattr(conn, 'conn') else conn.commit()

# %%
"""
3. INSERT DATA (PARAMETERIZED QUERIES)
- NEVER use string formatting (e.g., f-strings) to insert variables into SQL queries.
- Always use parameterized queries (?) to prevent SQL injection attacks and improve performance.
"""

insert_query = """
INSERT INTO portfolio (ticker, shares, purchase_price, purchase_date)
VALUES (?, ?, ?, ?)
"""

# Single insertion
single_record = ("TCS.NS", 50, 4100.50, "2026-03-15")
cursor.execute(insert_query, single_record)
conn.commit()

# %%
"""
4. BATCH INSERTION (EXECUTEMANY)
- For inserting multiple rows, executemany() is significantly faster than looping over execute().
"""

multiple_records = [
    ("INFY.NS", 100, 1500.00, "2026-03-16"),
    ("WIPRO.NS", 200, 450.75, "2026-03-16"),
    ("HDFCBANK.NS", 75, 1600.20, "2026-03-17")
]

cursor.executemany(insert_query, multiple_records)
conn.commit()

# %%
"""
5. QUERY DATA (FETCHING)
- After executing a SELECT query, use fetchone(), fetchmany(size), or fetchall() to retrieve the results.
- fetchall() returns a list of tuples representing the rows.
"""

cursor.execute("SELECT * FROM portfolio WHERE shares >= ?", (100,))

# Fetch all matching rows
large_holdings = cursor.fetchall()

print("Holdings with 100 or more shares:")
for row in large_holdings:
    # row is a tuple: (id, ticker, shares, purchase_price, purchase_date)
    print(f"Ticker: {row[1]}, Shares: {row[2]}, Price: {row[3]}")

# %%
"""
6. ROW FACTORY (DICTIONARY-LIKE ACCESS)
- By default, SQLite returns rows as tuples.
- Changing the row_factory to sqlite3.Row allows you to access columns by their names, similar to a dictionary.
"""

# Enable column access by name
conn.row_factory = sqlite3.Row
dict_cursor = conn.cursor()

dict_cursor.execute("SELECT ticker, purchase_price FROM portfolio WHERE ticker = ?", ("TCS.NS",))
tcs_record = dict_cursor.fetchone()

if tcs_record:
    # Accessing data using column names as keys
    print(f"\nFound {tcs_record['ticker']} bought at {tcs_record['purchase_price']}")

# %%
"""
7. UPDATE AND DELETE RECORDS
- Execute standard SQL UPDATE and DELETE statements using parameterized inputs.
"""

# Update a record
update_query = "UPDATE portfolio SET shares = ? WHERE ticker = ?"
cursor.execute(update_query, (60, "TCS.NS"))
conn.commit()

# Delete a record
delete_query = "DELETE FROM portfolio WHERE ticker = ?"
cursor.execute(delete_query, ("WIPRO.NS",))
conn.commit()

# %%
"""
8. DATABASE BACKUP
- The backup() method provides a safe way to create a binary copy of the database.
- This handles locking and concurrency automatically, making it superior to simple file copying.
"""

# Example: Backing up to an in-memory database
memory_backup = sqlite3.connect(':memory:')
conn.backup(memory_backup)
memory_backup.close()

# %%
"""
9. CLOSING THE CONNECTION
- Always close the cursor and connection when database operations are complete to release file locks.
- Best practice dictates doing this in a finally block or using context managers in production code.
"""

cursor.close()
conn.close()
