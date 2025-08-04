# The Axiom Node - UPGRADED FOR SYBIL RESISTANCE & REPUTATION
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.

import time
import threading
import sys
import requests
import math # Import math for logarithmic scaling
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
        
        # REPUTATION SYSTEM DATA STRUCTURE
        self.peers = {} 
        if bootstrap_peer:
            self.peers[bootstrap_peer] = {
                "reputation": 0.5, # Start with a neutral-to-positive score
                "first_seen": datetime.utcnow().isoformat(),
                "last_seen": datetime.utcnow().isoformat()
            }

        self.api_app = Flask(__name__)
        self.thread_pool = ThreadPoolExecutor(max_workers=10)
        self._configure_api_routes()
        initialize_database()

    def add_or_update_peer(self, peer_url):
        """A centralized method to add new peers or update the 'last_seen' timestamp of existing ones."""
        if peer_url and peer_url not in self.peers and peer_url != self.self_url:
            self.peers[peer_url] = {
                "reputation": 0.1, # New peers start with low reputation
                "first_seen": datetime.utcnow().isoformat(),
                "last_seen": datetime.utcnow().isoformat()
            }
            print(f"[Peer Management] Discovered new peer via gossip: {peer_url}")
        elif peer_url in self.peers:
             self.peers[peer_url]['last_seen'] = datetime.utcnow().isoformat()

    def _update_reputation(self, peer_url, sync_status, new_facts_count):
        """
        Adjusts a peer's reputation score based on the result of a sync attempt.
        This is the core of the Sybil resistance mechanism.
        """
        if peer_url not in self.peers:
            return

        # Define reputation adjustments
        REP_PENALTY_CONNECTION_FAILED = 0.1
        REP_REWARD_SUCCESS_UPTIME = 0.02 # Small reward for just being online
        REP_REWARD_NEW_FACTS_BASE = 0.1 # Base reward for sharing any number of new facts
        
        current_rep = self.peers[peer_url]['reputation']

        if sync_status == 'CONNECTION_FAILED' or sync_status == 'SYNC_ERROR':
            # Penalize offline or faulty nodes heavily.
            new_rep = current_rep - REP_PENALTY_CONNECTION_FAILED
        elif sync_status == 'SUCCESS_UP_TO_DATE':
            # Reward stable, online nodes to encourage uptime.
            new_rep = current_rep + REP_REWARD_SUCCESS_UPTIME
        elif sync_status == 'SUCCESS_NEW_FACTS':
            # Reward nodes that contribute new knowledge.
            # The reward scales logarithmically with the number of new facts.
            # This gives a large initial boost but has diminishing returns,
            # preventing a single node from gaining too much reputation too quickly.
            log_reward = math.log10(1 + new_facts_count)
            new_rep = current_rep + REP_REWARD_NEW_FACTS_BASE + (log_reward * 0.1)
        else:
            new_rep = current_rep # No change for unknown status

        # Clamp the reputation score between 0.0 and 1.0
        self.peers[peer_url]['reputation'] = max(0.0, min(1.0, new_rep))
        #print(f"[Reputation] Updated {peer_url} reputation to {self.peers[peer_url]['reputation']:.4f}")

    def _configure_api_routes(self):
        """A private method to define all the API endpoints for this node."""
        # --- This entire method remains the same as your last provided version ---
        # It includes /query, /get_peers, /get_fact_ids, /get_facts_by_id, and /anonymous_query
        
        @self.api_app.route('/query', methods=['GET'])
        def handle_query():
            search_term = request.args.get('term', '')
            results = search_ledger_for_api(search_term)
            return jsonify({"query_term": search_term, "results": results})

        @self.api_app.route('/get_peers', methods=['GET'])
        def handle_get_peers():
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

        @self.api_app.route('/anonymous_query', methods=['POST'])
        def handle_anonymous_query():
            data = request.json
            search_term = data.get('term')
            circuit = data.get('circuit', [])
            sender_peer = data.get('sender_peer')
            self.add_or_update_peer(sender_peer)

            if not circuit:
                print(f"[Anonymity] Exit node reached. Querying for '{search_term}'.")
                results = search_ledger_for_api(search_term)
                return jsonify({"results": results})
            else:
                next_node_url = circuit.pop(0)
                print(f"[Anonymity] Relaying anonymous query for '{search_term}' to {next_node_url}")
                try:
                    response = requests.post(
                        f"{next_node_url}/anonymous_query",
                        json={'term': search_term, 'circuit': circuit, 'sender_peer': self.self_url},
                        timeout=10
                    )
                    response.raise_for_status()
                    return jsonify(response.json())
                except requests.exceptions.RequestException as e:
                    print(f"[Anonymity] Relay failed: Could not connect to {next_node_url}.")
                    return jsonify({"error": f"Relay node {next_node_url} is offline."}), 504

    def _background_loop(self):
        """The combined background thread, now fully reputation-aware."""
        print("[Background Thread] Starting continuous cycle.")
        while True:
            # --- SCRUBBER LOGIC ---
            print("\n====== [AXIOM ENGINE CYCLE START] ======")
            # ... (omitted for brevity, this part is unchanged) ...
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
                # The sync_with_peer function now returns a status report.
                sync_status, new_facts_count = sync_with_peer(self, peer_url)
                
                # We use the status report to update the peer's reputation.
                self._update_reputation(peer_url, sync_status, new_facts_count)
            
            # Periodically print the reputation list for debugging/observation.
            print("\n--- Current Peer Reputations ---")
            if not self.peers:
                print("No peers known.")
            else:
                for peer, data in sorted(self.peers.items(), key=lambda item: item[1]['reputation'], reverse=True):
                    print(f"  - {peer}: {data['reputation']:.4f}")
            print("------------------------------")
            
            # --- REST PERIOD ---
            print(f"\n[Background Thread] Sleeping for 10 minutes before next cycle.")
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