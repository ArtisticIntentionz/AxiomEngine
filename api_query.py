# Axiom - api_query.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.

import sqlite3

DB_NAME = "axiom_ledger.db"

def search_ledger_for_api(search_term, include_uncorroborated=False):
    """
    Searches the ledger for facts containing the search term.
    By default, only returns facts with status = 'trusted'.
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row 
        cursor = conn.cursor()
        
        # Base query now includes a check for the 'status' column.
        base_query = "SELECT fact_id, fact_content, source_url, ingest_timestamp_utc, trust_score, status FROM facts WHERE fact_content LIKE ?"
        params = [f'%{search_term}%']
        
        if not include_uncorroborated:
            # The default, safe query for public consumption.
            query = base_query + " AND status = 'trusted'"
        else:
            # For internal or advanced use, we can see all facts.
            query = base_query

        cursor.execute(query, params)
        results = cursor.fetchall()
        
        facts_list = [dict(row) for row in results]
        return facts_list

    except Exception as e:
        print(f"[API Query] An error occurred during database search: {e}")
        return []
    finally:
        if conn:
            conn.close()