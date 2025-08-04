# Axiom - query.py
# A command-line tool to search the Axiom Ledger.

import sqlite3
import sys

DB_NAME = "axiom_ledger.db"

def query_ledger(search_term):
    """
    Connects to the database and searches for facts containing the search term.
    """
    print(f"\n>>> Searching Axiom Ledger for: '{search_term}'...")
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Use the SQL LIKE operator with wildcards (%) for a flexible search.
        query = "SELECT fact_content, source_url, ingest_timestamp_utc FROM facts WHERE fact_content LIKE ?"
        cursor.execute(query, (f'%{search_term}%',))
        
        results = cursor.fetchall()
        
        if not results:
            print("--> No results found.")
        else:
            # Iterate through the results and display them cleanly.
            for i, result in enumerate(results):
                print(f"\n[Result {i+1}]")
                print(f"  Fact: \"{result[0]}\"")
                print(f"  Source: {result[1]}")
                print(f"  Ingested: {result[2]}")
                
        print(f"\n--> Found {len(results)} matching facts.")

    except Exception as e:
        print(f"An error occurred while querying the database: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # Ensure the user provides a search term.
    if len(sys.argv) < 2:
        print("Usage: python3 query.py <search_term>")
        print("Example: python3 query.py \"Apple Inc\"")
    else:
        # Join all command line arguments into a single search phrase.
        query_ledger(" ".join(sys.argv[1:]))