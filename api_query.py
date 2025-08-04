# Axiom - api_query.py
# Provides query logic that returns structured data for API responses.

import sqlite3

# Define the constant for our database file name
DB_NAME = "axiom_ledger.db"

def search_ledger_for_api(search_term):
    """
    Searches the ledger for facts containing the search term.
    Returns a list of dictionaries, where each dictionary is a fact.
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        # This powerful line makes the database return dictionary-like rows
        # instead of tuples. This is perfect for JSON conversion.
        conn.row_factory = sqlite3.Row 
        cursor = conn.cursor()
        
        # The query now selects all columns to provide complete data.
        query = "SELECT fact_id, fact_content, source_url, ingest_timestamp_utc FROM facts WHERE fact_content LIKE ?"
        cursor.execute(query, (f'%{search_term}%',))
        
        results = cursor.fetchall()
        
        # Convert the list of sqlite3.Row objects into a standard list of dictionaries.
        facts_list = [dict(row) for row in results]
        return facts_list

    except Exception as e:
        print(f"[API Query] An error occurred during database search: {e}")
        return [] # Return an empty list in case of an error.
    finally:
        if conn:
            conn.close()