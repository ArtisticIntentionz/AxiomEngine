# Axiom - api_query.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
# --- UPGRADED TO HANDLE DISPUTED FACTS ---

import sqlite3

DB_NAME = "axiom_ledger.db"

def search_ledger_for_api(search_term, include_uncorroborated=False, include_disputed=False):
    """
    Searches the ledger for facts containing the search term.
    - By default, ONLY returns 'trusted' facts.
    - By default, ALWAYS excludes 'disputed' facts.
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row 
        cursor = conn.cursor()
        
        # Base query now selects all columns to provide complete data to the client.
        base_query = "SELECT * FROM facts WHERE fact_content LIKE ?"
        params = [f'%{search_term}%']
        
        # --- NEW: Logic to handle disputed facts ---
        # By default, we protect users from seeing information that the network
        # has identified as contradictory.
        if not include_disputed:
            base_query += " AND status != 'disputed'"
        # ------------------------------------------

        if not include_uncorroborated:
            # The default, safe query for public consumption, returns only trusted facts.
            query = base_query + " AND status = 'trusted'"
        else:
            # For internal use (like P2P sync), we can see all non-disputed facts.
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
