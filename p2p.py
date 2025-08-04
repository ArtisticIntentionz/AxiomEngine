# Axiom - p2p.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License.
# See the LICENSE file for details.

import requests
from ledger import insert_fact
from api_query import search_ledger_for_api

def get_all_fact_ids_from_ledger():
    """A helper function to get a set of all fact_ids for quick comparison."""
    all_facts = search_ledger_for_api('')
    return {fact['fact_id'] for fact in all_facts}

def sync_with_peer(self_node, peer_url):
    """
    The core synchronization logic. It now returns a status report for reputation adjustment.
    
    Returns a tuple: (status_code, new_facts_count)
    status_code can be:
        'SUCCESS_NEW_FACTS' - Synced and downloaded new facts.
        'SUCCESS_UP_TO_DATE' - Synced, but ledger was already current.
        'CONNECTION_FAILED' - Could not connect to the peer.
        'SYNC_ERROR' - A different error occurred during the process.
    """
    print(f"\n--- [P2P Sync] Attempting to sync with peer: {peer_url} ---")
    
    try:
        # --- Step 1: Gossip - Get the peer's list of peers ---
        response = requests.get(f"{peer_url}/get_peers", timeout=5)
        response.raise_for_status()
        peers_of_peer = response.json().get('peers', {}) # Expecting a dictionary now
        
        # Add any newly discovered peers to our own list using our node's method.
        for new_peer_url in peers_of_peer.keys():
            self_node.add_or_update_peer(new_peer_url)

        # --- Step 2: Knowledge Sync - Compare Fact IDs ---
        response = requests.get(f"{peer_url}/get_fact_ids", timeout=5)
        response.raise_for_status()
        peer_fact_ids = set(response.json().get('fact_ids', []))
        
        our_fact_ids = get_all_fact_ids_from_ledger()
        
        missing_ids = peer_fact_ids - our_fact_ids
        
        # --- Step 3: Act based on comparison ---
        if not missing_ids:
            print(f"[P2P Sync] Ledger is already up-to-date with {peer_url}.")
            return ('SUCCESS_UP_TO_DATE', 0)

        print(f"[P2P Sync] Found {len(missing_ids)} new facts to download from {peer_url}.")
        
        # Request the full data for only the facts we are missing.
        response = requests.post(f"{peer_url}/get_facts_by_id", json={'fact_ids': list(missing_ids)}, timeout=10)
        response.raise_for_status()
        new_facts = response.json().get('facts', [])
        
        if not new_facts:
            # This can happen if there's a race condition or error on the peer's side.
            return ('SYNC_ERROR', 0)

        # Add each new fact to our own ledger.
        for fact in new_facts:
            insert_fact(fact['fact_id'], fact['fact_content'], fact['source_url'])
        
        print(f"[P2P Sync] Successfully downloaded and stored {len(new_facts)} new facts.")
        return ('SUCCESS_NEW_FACTS', len(new_facts))

    except requests.exceptions.RequestException:
        print(f"[P2P Sync] ERROR: Could not connect to peer {peer_url}. Peer may be offline.")
        return ('CONNECTION_FAILED', 0)
    except Exception as e:
        print(f"[P2P Sync] ERROR: An unexpected error occurred during sync: {e}")
        return ('SYNC_ERROR', 0)