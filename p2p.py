# Axiom - p2p.py
# This module handles all peer-to-peer networking logic.
# CORRECTED: No longer inserts facts directly. Returns them as leads.

import requests

def get_all_fact_ids_from_ledger(search_ledger_for_api_func):
    """A helper function to get a set of all fact_ids for quick comparison."""
    # We must include uncorroborated facts for sync.
    all_facts = search_ledger_for_api_func('', include_uncorroborated=True) 
    return {fact['fact_id'] for fact in all_facts}

def sync_with_peer(self_node, peer_url):
    """
    The core synchronization logic. Now returns new facts as "leads" instead of inserting them.
    
    Returns a tuple: (status_code, list_of_new_facts)
    """
    print(f"\n--- [P2P Sync] Attempting to sync with peer: {peer_url} ---")
    
    try:
        # 1. Gossip - Get the peer's list of peers.
        response = requests.get(f"{peer_url}/get_peers", timeout=5)
        response.raise_for_status()
        peers_of_peer = response.json().get('peers', {})
        for new_peer_url in peers_of_peer.keys():
            self_node.add_or_update_peer(new_peer_url)

        # 2. Compare Fact IDs
        response = requests.get(f"{peer_url}/get_fact_ids", timeout=5)
        response.raise_for_status()
        peer_fact_ids = set(response.json().get('fact_ids', []))
        
        # Use the node's own search function, passed via self_node reference
        our_fact_ids = get_all_fact_ids_from_ledger(self_node.search_ledger_for_api)
        missing_ids = peer_fact_ids - our_fact_ids
        
        if not missing_ids:
            print(f"[P2P Sync] Ledger is already up-to-date with {peer_url}.")
            return ('SUCCESS_UP_TO_DATE', [])

        print(f"[P2P Sync] Found {len(missing_ids)} new facts to download from {peer_url}.")
        
        # 3. Download full fact data.
        response = requests.post(f"{peer_url}/get_facts_by_id", json={'fact_ids': list(missing_ids)}, timeout=10)
        response.raise_for_status()
        new_facts = response.json().get('facts', [])
        
        if not new_facts:
            return ('SYNC_ERROR', [])

        print(f"[P2P Sync] Successfully downloaded {len(new_facts)} facts as new leads.")
        # Return the facts so the main loop can process them as leads.
        return ('SUCCESS_NEW_FACTS', new_facts)

    except requests.exceptions.RequestException:
        print(f"[P2P Sync] ERROR: Could not connect to peer {peer_url}. Peer may be offline.")
        return ('CONNECTION_FAILED', [])
    except Exception as e:
        print(f"[P2P Sync] ERROR: An unexpected error occurred during sync: {e}")
        return ('SYNC_ERROR', [])