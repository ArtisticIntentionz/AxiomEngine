# Axiom - p2p.py
# This module will handle all peer-to-peer networking logic.

import requests
from ledger import insert_fact
from api_query import search_ledger_for_api # We re-use this to get all facts.

def get_all_fact_ids_from_ledger():
    """A helper function to get a set of all fact_ids for quick comparison."""
    all_facts = search_ledger_for_api('') # An empty search term returns all facts.
    return {fact['fact_id'] for fact in all_facts}

def sync_with_peer(self_node, peer_url):
    """
    The core synchronization logic between this node and a single peer.
    'self_node' is the instance of the AxiomNode class running this code.
    """
    print(f"\n--- [P2P Sync] Attempting to sync with peer: {peer_url} ---")
    
    try:
        # Step 1: Ask the peer for its list of all known peers (the "gossip").
        response = requests.get(f"{peer_url}/get_peers", timeout=5)
        response.raise_for_status()
        peers_of_peer = response.json().get('peers', [])
        
        # Add any newly discovered peers to our own peer list.
        for new_peer in peers_of_peer:
            # We don't add ourselves or peers we already know.
            if new_peer not in self_node.peers and new_peer != self_node.self_url:
                self_node.peers.add(new_peer)
                print(f"[P2P Sync] Discovered new peer via gossip: {new_peer}")

        # Step 2: Ask the peer for its full list of fact IDs.
        response = requests.get(f"{peer_url}/get_fact_ids", timeout=5)
        response.raise_for_status()
        peer_fact_ids = set(response.json().get('fact_ids', []))
        
        # Step 3: Get our own full list of fact IDs.
        our_fact_ids = get_all_fact_ids_from_ledger()
        
        # Step 4: Use set mathematics to determine which facts we are missing.
        missing_ids = peer_fact_ids - our_fact_ids
        
        if not missing_ids:
            print(f"[P2P Sync] Ledger is already up-to-date with {peer_url}.")
            return

        print(f"[P2P Sync] Found {len(missing_ids)} new facts to download from {peer_url}.")
        
        # Step 5: Request the full data for only the facts we are missing.
        # We use a POST request here because we are sending a list of IDs.
        response = requests.post(f"{peer_url}/get_facts_by_id", json={'fact_ids': list(missing_ids)}, timeout=10)
        response.raise_for_status()
        new_facts = response.json().get('facts', [])
        
        # Step 6: Add each new fact to our own ledger.
        # The ledger's built-in duplicate prevention will provide a final safeguard.
        for fact in new_facts:
            insert_fact(fact['fact_id'], fact['fact_content'], fact['source_url'])
        
        print(f"[P2P Sync] Successfully downloaded and stored {len(new_facts)} new facts.")

    except requests.exceptions.RequestException as e:
        print(f"[P2P Sync] ERROR: Could not connect to peer {peer_url}. It may be offline.")
    except Exception as e:
        print(f"[P2P Sync] ERROR: An unexpected error occurred during sync: {e}")