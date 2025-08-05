# Axiom - node.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
# --- FINAL, COMPLETE VERSION WITH SYNTHESIZER SUPPORT ---

import time
import threading
import sys
import requests
import math
import os
import traceback
import sqlite3
from flask import Flask, jsonify, request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# Import all our system components, including the new Synthesizer
import zeitgeist_engine
import universal_extractor
import crucible
import synthesizer
from ledger import initialize_database
from api_query import search_ledger_for_api
from p2p import sync_with_peer

# --- GLOBAL APP AND NODE INSTANCE ---
app = Flask(__name__)
node_instance = None
# ------------------------------------

class AxiomNode:
    """
    A class representing a single, complete Axiom node.
    """
    def __init__(self, host='0.0.0.0', port=5000, bootstrap_peer=None):
        self.host = host
        self.port = port
        self.self_url = f"http://{self.host}:{port}"
        self.peers = {} 
        if bootstrap_peer:
            self.peers[bootstrap_peer] = {
                "reputation": 0.5,
                "first_seen": datetime.utcnow().isoformat(),
                "last_seen": datetime.utcnow().isoformat()
            }
        
        self.investigation_queue = []
        self.active_proposals = {}
        self.thread_pool = ThreadPoolExecutor(max_workers=10)
        self.search_ledger_for_api = search_ledger_for_api
        initialize_database()

    def add_or_update_peer(self, peer_url):
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
        if peer_url not in self.peers: return
        REP_PENALTY_CONNECTION_FAILED = 0.1; REP_REWARD_SUCCESS_UPTIME = 0.02; REP_REWARD_NEW_FACTS_BASE = 0.1
        current_rep = self.peers[peer_url]['reputation']
        if sync_status in ('CONNECTION_FAILED', 'SYNC_ERROR'): new_rep = current_rep - REP_PENALTY_CONNECTION_FAILED
        elif sync_status == 'SUCCESS_UP_TO_DATE': new_rep = current_rep + REP_REWARD_SUCCESS_UPTIME
        elif sync_status == 'SUCCESS_NEW_FACTS': new_rep = current_rep + REP_REWARD_NEW_FACTS_BASE + (math.log10(1 + new_facts_count) * 0.1)
        else: new_rep = current_rep
        self.peers[peer_url]['reputation'] = max(0.0, min(1.0, new_rep))

    def _fetch_from_peer(self, peer_url, search_term):
        try:
            # We add include_uncorroborated=True to get all relevant facts from peers
            query_url = f"{peer_url}/local_query?term={search_term}&include_uncorroborated=true"
            response = requests.get(query_url, timeout=5)
            response.raise_for_status()
            return response.json().get('results', [])
        except requests.exceptions.RequestException:
            print(f"[Federation] Failed to connect to peer {peer_url}.")
            return []

    def _background_loop(self):
        """The main, continuous loop for learning, synthesizing, and syncing."""
        print("[Background Thread] Starting continuous cycle.")
        while True:
            print("\n====== [AXIOM ENGINE CYCLE START] ======")
            
            try:
                topic_to_investigate = None
                if self.investigation_queue:
                    print(f"[Engine] Prioritizing {len(self.investigation_queue)} leads from peer network.")
                    lead = self.investigation_queue.pop(0)
                    topic_to_investigate = lead['fact_content'][:100]
                else:
                    print("[Engine] No leads in queue. Discovering new topics.")
                    topics = zeitgeist_engine.get_trending_topics(top_n=1)
                    if topics:
                        topic_to_investigate = topics[0]
                
                newly_created_facts_batch = []
                if topic_to_investigate:
                    content_list = universal_extractor.find_and_extract(topic_to_investigate, max_sources=1)
                    for item in content_list:
                        new_facts_from_source = crucible.extract_facts_from_text(item['source_url'], item['content'])
                        if new_facts_from_source:
                            newly_created_facts_batch.extend(new_facts_from_source)
                
                if newly_created_facts_batch:
                    synthesizer.link_related_facts(newly_created_facts_batch)

            except Exception:
                print(f"\n--- !!! CRITICAL ERROR IN LEARNING/SYNTHESIS LOOP !!! ---\n")
                traceback.print_exc()
                print("\n--- END OF CRITICAL ERROR ---\n")

            print("====== [AXIOM ENGINE CYCLE FINISH] ======")
            
            sorted_peers = sorted(self.peers.items(), key=lambda item: item[1]['reputation'], reverse=True)
            print(f"\n[P2P Sync] Beginning sync process with {len(sorted_peers)} known peers...")
            for peer_url, peer_data in sorted_peers:
                sync_status, new_facts = sync_with_peer(self, peer_url)
                self._update_reputation(peer_url, sync_status, len(new_facts))
                if sync_status == 'SUCCESS_NEW_FACTS' and new_facts:
                    self.investigation_queue.extend(new_facts)
            
            print("\n--- Current Peer Reputations ---")
            if not self.peers: print("No peers known.")
            else:
                for peer, data in sorted(self.peers.items(), key=lambda item: item[1]['reputation'], reverse=True):
                    print(f"  - {peer}: {data['reputation']:.4f}")
            print("------------------------------")
            
            time.sleep(21600)

    def start_background_tasks(self):
        background_thread = threading.Thread(target=self._background_loop, daemon=True)
        background_thread.start()

# --- CONFIGURE API ROUTES ---
@app.route('/local_query', methods=['GET'])
def handle_local_query():
    search_term = request.args.get('term', '')
    # The string 'true' from a URL parameter needs to be converted to a boolean
    include_uncorroborated = request.args.get('include_uncorroborated', 'false').lower() == 'true'
    results = node_instance.search_ledger_for_api(search_term, include_uncorroborated=include_uncorroborated)
    return jsonify({"results": results})

@app.route('/get_peers', methods=['GET'])
def handle_get_peers(): return jsonify({'peers': node_instance.peers})

@app.route('/get_fact_ids', methods=['GET'])
def handle_get_fact_ids():
    conn = sqlite3.connect('axiom_ledger.db')
    cursor = conn.cursor()
    cursor.execute("SELECT fact_id FROM facts")
    fact_ids = [row[0] for row in cursor.fetchall()]
    conn.close()
    return jsonify({'fact_ids': fact_ids})

@app.route('/get_facts_by_id', methods=['POST'])
def handle_get_facts_by_id():
    requested_ids = request.json.get('fact_ids', []); all_facts = node_instance.search_ledger_for_api('', include_uncorroborated=True)
    facts_to_return = [fact for fact in all_facts if fact['fact_id'] in requested_ids]
    return jsonify({'facts': facts_to_return})

@app.route('/anonymous_query', methods=['POST'])
def handle_anonymous_query():
    data = request.json; search_term = data.get('term'); circuit = data.get('circuit', []); sender_peer = data.get('sender_peer')
    node_instance.add_or_update_peer(sender_peer)
    if not circuit:
        all_facts = {}
        # --- THIS IS THE FIX ---
        # We now correctly call the API to include uncorroborated facts by default.
        local_results = node_instance.search_ledger_for_api(search_term, include_uncorroborated=True)
        for fact in local_results: all_facts[fact['fact_id']] = fact
        
        future_to_peer = {node_instance.thread_pool.submit(node_instance._fetch_from_peer, peer, search_term): peer for peer in node_instance.peers}
        for future in future_to_peer:
            peer_results = future.result()
            for fact in peer_results:
                if fact['fact_id'] not in all_facts:
                    all_facts[fact['fact_id']] = fact
        return jsonify({"results": list(all_facts.values())})
    else:
        next_node_url = circuit.pop(0)
        try:
            response = requests.post(f"{next_node_url}/anonymous_query", json={'term': search_term, 'circuit': circuit, 'sender_peer': node_instance.self_url}, timeout=10)
            response.raise_for_status(); return jsonify(response.json())
        except requests.exceptions.RequestException: return jsonify({"error": f"Relay node {next_node_url} is offline."}), 504

@app.route('/dao/proposals', methods=['GET'])
def handle_get_proposals(): return jsonify(node_instance.active_proposals)

@app.route('/dao/submit_proposal', methods=['POST'])
def handle_submit_proposal():
    data = request.json; proposer_url = data.get('proposer_url'); aip_id = data.get('aip_id'); aip_text = data.get('aip_text')
    if not all([proposer_url, aip_id, aip_text]): return jsonify({"status": "error", "message": "Missing parameters."}), 400
    if proposer_url in node_instance.peers and node_instance.peers[proposer_url]['reputation'] >= 0.75:
        if aip_id not in node_instance.active_proposals:
            node_instance.active_proposals[aip_id] = {"text": aip_text, "proposer": proposer_url, "votes": {}}
            return jsonify({"status": "success", "message": f"AIP {aip_id} submitted."})
        else: return jsonify({"status": "error", "message": "Proposal ID already exists."}), 409
    else: return jsonify({"status": "error", "message": "Insufficient reputation."}), 403

@app.route('/dao/submit_vote', methods=['POST'])
def handle_submit_vote():
    data = request.json; voter_url = data.get('voter_url'); aip_id = data.get('aip_id'); vote_choice = data.get('choice')
    if not all([voter_url, aip_id, vote_choice]): return jsonify({"status": "error", "message": "Missing parameters."}), 400
    if aip_id not in node_instance.active_proposals: return jsonify({"status": "error", "message": "Proposal not found."}), 404
    voter_data = node_instance.peers.get(voter_url)
    if not voter_data: return jsonify({"status": "error", "message": "Unknown peer."}), 403
    voter_reputation = voter_data.get('reputation', 0)
    node_instance.active_proposals[aip_id]['votes'][voter_url] = {"choice": vote_choice, "weight": voter_reputation}
    return jsonify({"status": "success", "message": "Vote recorded."})

# --- MAIN EXECUTION BLOCK ---
if __name__ == "__main__" or "gunicorn" in sys.argv[0]:
    if node_instance is None:
        print(f"--- [Axiom Node] Initializing global instance for {'PRODUCTION' if 'gunicorn' in sys.argv[0] else 'DEVELOPMENT'}... ---")
        port = int(os.environ.get("PORT", 5000))
        bootstrap = os.environ.get("BOOTSTRAP_PEER")
        node_instance = AxiomNode(port=port, bootstrap_peer=bootstrap)
        node_instance.start_background_tasks()
    if __name__ == "__main__":
        print("--- [Axiom Node] Starting in DEVELOPMENT mode... ---")
        app.run(host='0.0.0.0', port=port, debug=False)