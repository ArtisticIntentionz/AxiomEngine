# Axiom - p2p.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
# --- V2.1: HARDENED SYNC LOGIC ---

import requests
import sqlite3
from ledger import DB_NAME

def sync_with_peer(node_instance, peer_url):
    """
    Synchronizes the local ledger with a peer's ledger.
    This version correctly handles database integrity errors during sync.
    """
    print(f"\n--- [P2P Sync] Attempting to sync with peer: {peer_url} ---")
    
    try:
        # Step 1: Get the peer's list of all fact IDs
        response = requests.get(f"{peer_url}/get_fact_ids", timeout=10)
        response.raise_for_status()
        peer_fact_ids = set(response.json().get('fact_ids', []))

        # Step 2: Get the local list of all fact IDs
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT fact_id FROM facts")
        local_fact_ids = set(row[0] for row in cursor.fetchall())
        
        # Step 3: Determine which facts are missing locally
        missing_fact_ids = list(peer_fact_ids - local_fact_ids)

        if not missing_fact_ids:
            print(f"[P2P Sync] Ledger is already up-to-date with {peer_url}.")
            conn.close()
            return 'SUCCESS_UP_TO_DATE', []

        # Step 4: Request the full data for only the missing facts
        print(f"[P2P Sync] Found {len(missing_fact_ids)} new facts to download from {peer_url}.")
        response = requests.post(f"{peer_url}/get_facts_by_id", json={'fact_ids': missing_fact_ids}, timeout=30)
        response.raise_for_status()
        new_facts = response.json().get('facts', [])
        
        # Step 5: Insert the new facts into the local ledger
        facts_added_count = 0
        for fact in new_facts:
            try:
                cursor.execute("""
                    INSERT INTO facts (fact_id, fact_content, source_url, ingest_timestamp_utc, trust_score, status, corroborating_sources, contradicts_fact_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    fact['fact_id'], fact['fact_content'], fact['source_url'], fact['ingest_timestamp_utc'],
                    fact['trust_score'], fact['status'], fact.get('corroborating_sources'), fact.get('contradicts_fact_id')
                ))
                facts_added_count += 1
            except sqlite3.IntegrityError:
                # This is not a failure. It means we discovered this fact on our own
                # in the short time between starting and finishing the sync. We can safely ignore it.
                continue
        
        conn.commit()
        conn.close()
        
        if facts_added_count > 0:
            return 'SUCCESS_NEW_FACTS', new_facts
        else:
            return 'SUCCESS_UP_TO_DATE', []

    except requests.exceptions.RequestException as e:
        print(f"[P2P Sync] FAILED to connect or communicate with peer {peer_url}. Error: {e}")
        return 'CONNECTION_FAILED', []
    except Exception as e:
        print(f"[P2P Sync] An unexpected error occurred during sync with {peer_url}. Error: {e}")
        if 'conn' in locals() and conn:
            conn.close()
        return 'SYNC_ERROR', []