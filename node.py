# The Axiom Node - UPGRADED FOR REPUTATION & ANONYMITY
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License.
# See the LICENSE file for details.

import time
import threading
import sys
import requests
from flask import Flask, jsonify, request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# Import all our system components
import zeitgeist_engine
import universal_extractor
import crucible
from ledger import initialize_database
from api_query import search_ledger_for_api
from p2p import sync_with_peer, get_all_fact_ids_from_ledger

class AxiomNode:
    """
    A class representing a single, complete Axiom node.
    It handles autonomous learning, P2P synchronization, API requests,
    peer reputations, and anonymous query relaying.
    """
    def __init__(self, host='0.0.0.0', port=5000, bootstrap_peer=None):
        self.host = host
        self.port = port
        self.self_url = f"http://{self.host}:{port}"
        
        # --- REPUTATION SYSTEM DATA STRUCTURE ---
        # self.peers is a dictionary to store metadata about each peer.
        # Structure: {"peer_url": {"reputation": float, "first_seen": str, "last_seen": str}}
        self.peers = {} 
        if bootstrap_peer:
            # Initialize the bootstrap peer with a neutral-to-positive reputation.
            self.peers[bootstrap_peer] = {
                "reputation": 0.5,
                "first_seen": datetime.utcnow().isoformat(),
                "last_seen": datetime.utcnow().isoformat()
            }
        # ------------------------------------

        self.api_app = Flask(__name__)
        self.thread_pool = ThreadPoolExecutor(max_workers=10)
        self._configure_api_routes() # Call the method containing your provided code
        initialize_database()

    def add_or_update_peer(self, peer_url):
        """A centralized method to add new peers or update the 'last_seen' timestamp of existing ones."""
        if peer_url and peer_url not in self.peers and peer_url != self.self_url:
            self.peers[peer_url] = {
                "reputation": 0.1, # New peers discovered via gossip start with low reputation.
                "first_seen": datetime.utcnow().isoformat(),
                "last_seen": datetime.utcnow().isoformat()
            }
            print(f"[Peer Management] Discovered new peer via gossip: {peer_url}")
        elif peer_url in self.peers:
             self.peers[peer_url]['last_seen'] = datetime.utcnow().isoformat()

    def _configure_api_routes(self):
        """A private method to define all the API endpoints for this node."""

        # --- User-Facing Endpoints ---
        
        # /query is now deprecated for direct user access, but useful for testing.
        @self.api_app.route('/query', methods=['GET'])
        def handle_query():
            search_term = request.args.get('term', '')
            results = search_ledger_for_api(search_term)
            return jsonify({"query_term": search_term, "results": results})

        # --- Peer-to-Peer API Endpoints (Updated for Reputation) ---
        @self.api_app.route('/get_peers', methods=['GET'])
        def handle_get_peers():
            # Returns the full dictionary of peers, including their reputation data.
            return jsonify({'peers': self.peers})

        @self.api_app.route('/get_fact_ids', methods=['GET'])
        def handle_get_fact_ids():
            return jsonify({'fact_ids': list(get_all_fact_ids_from_ledger())})

        @self.api_app.route('/get_facts_by_id', methods=['POST'])
        def handle_get_facts_by_id():
            requested_ids = request.json.get('fact_ids', [])
            all_facts = search_ledger_for_api('')
            facts_to_return = [fact for fact in all_facts if fact['fact_id'] in requested_ids]
            return jsonify({'facts': facts_to_return})

        # --- Anonymity Layer Endpoints (Your provided code, integrated) ---
        
        @self.api_app.route('/anonymous_query', methods=['POST'])
        def handle_anonymous_query():
            """
            Handles a query that is being relayed through the anonymous network.
            """
            data = request.json
            search_term = data.get('term')
            circuit = data.get('circuit', []) # The list of nodes the query must still travel
            
            # Use our new centralized method to manage the peer who sent the request.
            sender_peer = data.get('sender_peer')
            self.add_or_update_peer(sender_peer)

            if not circuit:
                # This is the EXIT NODE. The end of the line.
                # It performs a local query and returns the results up the chain.
                print(f"[Anonymity] Exit node reached. Querying for '{search_term}'.")
                results = search_ledger_for_api(search_term)
                return jsonify({"results": results})
            else:
                # This is a RELAY NODE.
                # Pop the next node from the circuit list.
                next_node_url = circuit.pop(0)
                print(f"[Anonymity] Relaying anonymous query for '{search_term}' to {next_node_url}")
                
                try:
                    # Forward the modified request (with a shorter circuit) to the next node.
                    # We also tell the next node who we are, so it can add us to its peer list.
                    response = requests.post(
                        f"{next_node_url}/anonymous_query",
                        json={'term': search_term, 'circuit': circuit, 'sender_peer': self.self_url},
                        timeout=10
                    )
                    response.raise_for_status()
                    # Pass the results from the end of the chain back to the previous node.
                    return jsonify(response.json())
                except requests.exceptions.RequestException as e:
                    print(f"[Anonymity] Relay failed: Could not connect to {next_node_url}.")
                    return jsonify({"error": f"Relay node {next_node_url} is offline."}), 504 # Gateway Timeout

    def _background_loop(self):
        """
        The combined background thread for learning AND syncing.
        This loop now prioritizes syncing with higher-reputation peers.
        """
        print("[Background Thread] Starting continuous cycle.")
        while True:
            # --- SCRUBBER LOGIC ---
            print("\n====== [AXIOM ENGINE CYCLE START] ======")
            topics = zeitgeist_engine.get_trending_topics(top_n=1)
            if topics:
                for topic in topics:
                    content_list = universal_extractor.find_and_extract(topic, max_sources=1)
                    for item in content_list:
                        crucible.extract_facts_from_text(item['source_url'], item['content'])
            print("====== [AXIOM ENGINE CYCLE FINISH] ======")

            # --- P2P SYNC LOGIC (Reputation-Aware) ---
            
            # Sort peers by reputation in descending order before syncing.
            sorted_peers = sorted(self.peers.items(), key=lambda item: item[1]['reputation'], reverse=True)
            
            print(f"\n[P2P Sync] Beginning sync process with {len(sorted_peers)} known peers (highest reputation first).")
            for peer_url, peer_data in sorted_peers:
                sync_with_peer(self, peer_url)
            
            print(f"\n[Background Thread] Current known peers: {len(self.peers)}")
            
            # --- REST PERIOD ---
            print(f"[Background Thread] Sleeping for 10 minutes before next cycle.")
            time.sleep(600)

    def start(self):
        """Starts all node functions in their own threads."""
        print(f"--- [Axiom Node] Starting node at {self.self_url} ---")
        background_thread = threading.Thread(target=self._background_loop, daemon=True)
        background_thread.start()
        self.api_app.run(host=self.host, port=self.port)

# Main execution block
if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    bootstrap_peer_url = sys.argv[2] if len(sys.argv) > 2 else None
    
    node = AxiomNode(port=port, bootstrap_peer=bootstrap_peer_url)
    try:
        node.start()
    except KeyboardInterrupt:
        print(f"\n--- [Axiom Node at port {port}] Shutdown signal received. ---")