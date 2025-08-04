# The Axiom Node - FINAL VERSION WITH DAO GOVERNANCE & CORRECTED P2P LOGIC
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.

import time
import threading
import sys
import requests
import math
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
    peer reputations, anonymous query relaying, and DAO governance.
    """
    def __init__(self, host='0.0.0.0', port=5000, bootstrap_peer=None):
        self.host = host
        self.port = port
        self.self_url = f"http://{self.host}:{port}"
        
        # REPUTATION SYSTEM DATA STRUCTURE
        self.peers = {} 
        if bootstrap_peer:
            self.peers[bootstrap_peer] = {
                "reputation": 0.5,
                "first_seen": datetime.utcnow().isoformat(),
                "last_seen": datetime.utcnow().isoformat()
            }

        # A queue to hold "leads" - facts discovered by peers for our own engine to verify.
        self.investigation_queue = []

        # DAO GOVERNANCE DATA STRUCTURE
        self.active_proposals = {}

        self.api_app = Flask(__name__)
        self.thread_pool = ThreadPoolExecutor(max_workers=10)
        self._configure_api_routes()
        initialize_database()

        # Pass a reference to the node's own search function to be used by P2P logic
        self.search_ledger_for_api = search_ledger_for_api

    def add_or_update_peer(self, peer_url):
        """A centralized method to add new peers or update their 'last_seen' timestamp."""
        if peer_url and peer_url not in self.peers and peer_url != self.self_url:
            self.peers[peer_url] = {
                "reputation": 0.1,
                "first_seen": datetime.utcnow().isoformat(),
                "last_seen": datetime.utcnow().isoformat()
            }
            print(f"[Peer Management] Discovered new peer via gossip: {peer_url}")
        elif peer_url in self.peers:
             self.peers[peer_url]['last_seen'] = datetime.utcnow().isoformat()

    def _update_reputation(self, peer_url, sync_status, new_facts_count):
        """Adjusts a peer's reputation score based on the result of a sync attempt."""
        if peer_url not in self.peers:
            return

        REP_PENALTY_CONNECTION_FAILED = 0.1
        REP_REWARD_SUCCESS_UPTIME = 0.02
        REP_REWARD_NEW_FACTS_BASE = 0.1
        
        current_rep = self.peers[peer_url]['reputation']

        if sync_status in ('CONNECTION_FAILED', 'SYNC_ERROR'):
            new_rep = current_rep - REP_PENALTY_CONNECTION_FAILED
        elif sync_status == 'SUCCESS_UP_TO_DATE':
            new_rep = current_rep + REP_REWARD_SUCCESS_UPTIME
        elif sync_status == 'SUCCESS_NEW_FACTS':
            log_reward = math.log10(1 + new_facts_count)
            new_rep = current_rep + REP_REWARD_NEW_FACTS_BASE + (log_reward * 0.1)
        else:
            new_rep = current_rep

        self.peers[peer_url]['reputation'] = max(0.0, min(1.0, new_rep))

    def _configure_api_routes(self):
        """A private method to define all the API endpoints for this node."""
        
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
            return jsonify({'fact_ids': list(get_all_fact_ids_from_ledger(self.search_ledger_for_api))})

        @self.api_app.route('/get_facts_by_id', methods=['POST'])
        def handle_get_facts_by_id():
            requested_ids = request.json.get('fact_ids', [])
            all_facts = search_ledger_for_api('', include_uncorroborated=True)
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
                except requests.exceptions.RequestException:
                    return jsonify({"error": f"Relay node {next_node_url} is offline."}), 504

        @self.api_app.route('/dao/proposals', methods=['GET'])
        def handle_get_proposals():
            return jsonify(self.active_proposals)

        @self.api_app.route('/dao/submit_proposal', methods=['POST'])
        def handle_submit_proposal():
            data = request.json
            proposer_url = data.get('proposer_url')
            aip_id = data.get('aip_id')
            aip_text = data.get('aip_text')
            if not all([proposer_url, aip_id, aip_text]):
                return jsonify({"status": "error", "message": "Missing parameters."}), 400
            if proposer_url in self.peers and self.peers[proposer_url]['reputation'] >= 0.75:
                if aip_id not in self.active_proposals:
                    self.active_proposals[aip_id] = {"text": aip_text, "proposer": proposer_url, "votes": {}}
                    return jsonify({"status": "success", "message": f"AIP {aip_id} submitted."})
                else:
                    return jsonify({"status": "error", "message": "Proposal ID already exists."}), 409
            else:
                return jsonify({"status": "error", "message": "Insufficient reputation."}), 403

        @self.api_app.route('/dao/submit_vote', methods=['POST'])
        def handle_submit_vote():
            data = request.json
            voter_url = data.get('voter_url')
            aip_id = data.get('aip_id')
            vote_choice = data.get('choice')
            if not all([voter_url, aip_id, vote_choice]):
                return jsonify({"status": "error", "message": "Missing parameters."}), 400
            if aip_id not in self.active_proposals:
                return jsonify({"status": "error", "message": "Proposal not found."}), 404
            voter_data = self.peers.get(voter_url)
            if not voter_data:
                return jsonify({"status": "error", "message": "Unknown peer."}), 403
            voter_reputation = voter_data.get('reputation', 0)
            self.active_proposals[aip_id]['votes'][voter_url] = {"choice": vote_choice, "weight": voter_reputation}
            return jsonify({"status": "success", "message": "Vote recorded."})

    def _background_loop(self):
        """The combined background thread with corrected logic for peer-sourced leads."""
        print("[Background Thread] Starting continuous cycle.")
        while True:
            print("\n====== [AXIOM ENGINE CYCLE START] ======")
            
            # Part 1: Prioritize investigating leads from the peer network.
            if self.investigation_queue:
                print(f"[Engine] Prioritizing {len(self.investigation_queue)} leads from peer network.")
                lead = self.investigation_queue.pop(0) # Process one lead per cycle
                # The 'lead' is a fact dictionary. We use its content as a new search topic.
                # This triggers our own independent verification of the peer's information.
                content_list = universal_extractor.find_and_extract(lead['fact_content'][:100], max_sources=1)
                for item in content_list:
                    crucible.extract_facts_from_text(item['source_url'], item['content'])
            else:
                # Part 2: If no leads, discover new topics autonomously.
                print("[Engine] No leads in queue. Discovering new topics.")
                topics = zeitgeist_engine.get_trending_topics(top_n=1)
                if topics:
                    for topic in topics:
                        content_list = universal_extractor.find_and_extract(topic, max_sources=1)
                        for item in content_list:
                            crucible.extract_facts_from_text(item['source_url'], item['content'])
            
            print("====== [AXIOM ENGINE CYCLE FINISH] ======")

            # Part 3: P2P Knowledge Sharing
            sorted_peers = sorted(self.peers.items(), key=lambda item: item[1]['reputation'], reverse=True)
            print(f"\n[P2P Sync] Beginning sync process with {len(sorted_peers)} known peers...")
            for peer_url, peer_data in sorted_peers:
                sync_status, new_facts = sync_with_peer(self, peer_url)
                self._update_reputation(peer_url, sync_status, len(new_facts))
                
                # Add any newly downloaded facts to our own investigation queue.
                if sync_status == 'SUCCESS_NEW_FACTS' and new_facts:
                    self.investigation_queue.extend(new_facts)
                    print(f"[Engine] Added {len(new_facts)} new leads to the investigation queue.")
            
            # Part 4: Reporting and Rest
            print("\n--- Current Peer Reputations ---")
            if not self.peers:
                print("No peers known.")
            else:
                for peer, data in sorted(self.peers.items(), key=lambda item: item[1]['reputation'], reverse=True):
                    print(f"  - {peer}: {data['reputation']:.4f}")
            print("------------------------------")
            
            sleep_duration_seconds = 21600
            print(f"\n[Background Thread] Sleeping for {sleep_duration_seconds / 3600:.0f} hours before next cycle.")
            time.sleep(sleep_duration_seconds)

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