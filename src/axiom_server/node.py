# Axiom - node.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
# --- V2.1: FINAL, CORRECTED VERSION WITH REPUTATION FIX ---

import json
import time
import threading
import sys
from urllib.parse import urlparse
import requests
import math
import os
import logging
from flask import Flask, jsonify, request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

# Import all our system components
from axiom_server import zeitgeist_engine
from axiom_server import universal_extractor
from axiom_server import crucible
from axiom_server import synthesizer
from axiom_server.ledger import ENGINE, Fact, FactModel, SessionMaker, Source, initialize_database
from axiom_server.api_query import search_ledger_for_api
from axiom_server.p2p import sync_with_peer

__version__ = "0.1.0"

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("axiom-node")

stdout_handler = logging.StreamHandler(stream=sys.stdout)
stdout_handler.setFormatter(
    logging.Formatter(
        "[%(name)s] %(asctime)s | %(levelname)s | %(filename)s:%(lineno)s >>> %(message)s"
    )
)

logger.addHandler(stdout_handler)
logger.setLevel(logging.INFO)

background_thread_logger = logging.getLogger("axiom-node-background-thread")

background_thread_logger.addHandler(stdout_handler)
background_thread_logger.setLevel(logging.INFO)

# --- GLOBAL APP AND NODE INSTANCE ---
app = Flask(__name__)
node_instance = None
# ------------------------------------


class AxiomNode:
    """
    A class representing a single, complete Axiom node.
    """

    def __init__(self, host="0.0.0.0", port=5000, bootstrap_peer=None):
        self.host = host
        self.port = port
        self.self_url = f"http://{self.host}:{port}"
        self.peers = {}
        if bootstrap_peer:
            self.peers[bootstrap_peer] = {
                "reputation": 0.5,
                "first_seen": datetime.now(timezone.utc).isoformat(),
                "last_seen": datetime.now(timezone.utc).isoformat(),
            }

        self.investigation_queue = (
            []
        )  # Now used only for special, high-priority topics.
        self.active_proposals = {}
        self.thread_pool = ThreadPoolExecutor(max_workers=10)
        self.search_ledger_for_api = search_ledger_for_api
        initialize_database(ENGINE)

    def add_or_update_peer(self, peer_url):
        if peer_url and peer_url not in self.peers and peer_url != self.self_url:
            self.peers[peer_url] = {
                "reputation": 0.1,
                "first_seen": datetime.now(timezone.utc).isoformat(),
                "last_seen": datetime.now(timezone.utc).isoformat(),
            }
        elif peer_url in self.peers:
            self.peers[peer_url]["last_seen"] = datetime.now(timezone.utc).isoformat()

    def _update_reputation(self, peer_url, sync_status, new_facts_count):
        if peer_url not in self.peers:
            return
        REP_PENALTY = 0.1
        REP_REWARD_UPTIME = 0.02
        REP_REWARD_NEW_DATA = 0.1
        current_rep = self.peers[peer_url]["reputation"]

        if sync_status in ("CONNECTION_FAILED", "SYNC_ERROR"):
            new_rep = current_rep - REP_PENALTY
        elif sync_status == "SUCCESS_UP_TO_DATE":
            new_rep = current_rep + REP_REWARD_UPTIME
        elif sync_status == "SUCCESS_NEW_FACTS":
            # A bigger reward for sharing new, valuable information
            new_rep = (
                current_rep
                + REP_REWARD_UPTIME
                + (math.log10(1 + new_facts_count) * REP_REWARD_NEW_DATA)
            )
        else:
            new_rep = current_rep

        self.peers[peer_url]["reputation"] = max(0.0, min(1.0, new_rep))

    def _fetch_from_peer(self, peer_url, search_term):
        try:
            query_url = (
                f"{peer_url}/local_query?term={search_term}&include_uncorroborated=true"
            )
            response = requests.get(query_url, timeout=5)
            response.raise_for_status()
            return response.json().get("results", [])
        except requests.exceptions.RequestException:
            return []

    def _background_loop(self):
        """
        The main, continuous loop. This version has the corrected logic.
        """
        background_thread_logger.info("starting continuous cycle.")
        
        with SessionMaker() as session:
            while True:
                background_thread_logger.info("axiom engine cycle start")

                try:
                    topic_to_investigate = None
                    if self.investigation_queue:
                        topic_to_investigate = self.investigation_queue.pop(0)
                    else:
                        topics = zeitgeist_engine.get_trending_topics(top_n=1)
                        if topics:
                            topic_to_investigate = topics[0]

                    if topic_to_investigate:
                        content_list = universal_extractor.find_and_extract(
                            topic_to_investigate, max_sources=1
                        )

                        for item in content_list:
                            domain = urlparse(item["source_url"]).netloc
                            source = session.query(Source).filter(Source.domain == domain).one_or_none()

                            if source is None:
                                source = Source(domain=domain)
                                session.add(source)
                                session.commit()

                            new_facts = crucible.extract_facts_from_text(item["content"])
                            adder = crucible.CrucibleFactAdder(session)

                            for fact in new_facts:
                                session.add(fact)
                                fact.sources.append(source)
                                session.commit()
                                adder.add(fact)

                except Exception as e:
                    background_thread_logger.exception(e)

                background_thread_logger.info("axiom engine cycle finish")

                sorted_peers = sorted(
                    self.peers.items(), key=lambda item: item[1]["reputation"], reverse=True
                )
                for peer_url, peer_data in sorted_peers:
                    # --- THIS IS THE FIX ---
                    # The new p2p.sync_with_peer is smarter and will return the correct status.
                    # The reputation system will now correctly reward good peers.
                    sync_status, new_facts = sync_with_peer(self, peer_url)
                    self._update_reputation(peer_url, sync_status, len(new_facts))
                    # We NO LONGER add synced facts to the investigation queue, which was the source of the bug.

                background_thread_logger.info("Current Peer Reputations")
                if not self.peers:
                    background_thread_logger.info("No peers known.")
                else:
                    for peer, data in sorted(
                        self.peers.items(),
                        key=lambda item: item[1]["reputation"],
                        reverse=True,
                    ):
                        background_thread_logger.info(
                            f"  - {peer}: {data['reputation']:.4f}"
                        )

                time.sleep(10800)  # Sleep for 3 hours

    def start_background_tasks(self):
        background_thread = threading.Thread(target=self._background_loop, daemon=True)
        background_thread.start()


# --- CONFIGURE API ROUTES ---
@app.route("/local_query", methods=["GET"])
def handle_local_query():
    assert node_instance is not None
    search_term = request.args.get("term", "")
    include_uncorroborated = (
        request.args.get("include_uncorroborated", "false").lower() == "true"
    )

    with SessionMaker() as session:
        results = node_instance.search_ledger_for_api(
            session, search_term, include_uncorroborated=include_uncorroborated
        )
        return jsonify({"results": results})


@app.route("/get_peers", methods=["GET"])
def handle_get_peers():
    assert node_instance is not None
    return jsonify({"peers": node_instance.peers})


@app.route("/get_fact_ids", methods=["GET"])
def handle_get_fact_ids():
    with SessionMaker() as session:
        fact_ids: list[int] = [ fact.id for fact in session.query(Fact).all() ]
        return jsonify({"fact_ids": fact_ids})


@app.route("/get_fact_hashes", methods=["GET"])
def handle_get_fact_hashes():
    with SessionMaker() as session:
        fact_ids: list[str] = [ fact.hash for fact in session.query(Fact).all() ]
        return jsonify({"fact_hashes": fact_ids})


@app.route("/get_facts_by_id", methods=["POST"])
def handle_get_facts_by_id():
    assert request.json is not None
    requested_ids: set[int] = set(request.json.get("fact_ids", []))
    
    with SessionMaker() as session:
        facts = list(session.query(Fact).filter(Fact.id.in_(requested_ids)))
        fact_models = [FactModel.from_fact(fact).model_dump() for fact in facts]
        return jsonify({"facts": json.dumps(fact_models)})

@app.route("/get_facts_by_hash", methods=["POST"])
def handle_get_facts_by_hash():
    assert request.json is not None
    requested_hashes: set[int] = set(request.json.get("fact_hashes", []))
    
    with SessionMaker() as session:
        facts = list(session.query(Fact).filter(Fact.hash.in_(requested_hashes)))
        fact_models = [FactModel.from_fact(fact).model_dump() for fact in facts]
        return jsonify({"facts": json.dumps(fact_models)})

@app.route("/anonymous_query", methods=["POST"])
def handle_anonymous_query():
    data = request.json
    assert data is not None
    assert node_instance is not None
    search_term = data.get("term")
    circuit = data.get("circuit", [])
    sender_peer = data.get("sender_peer")
    node_instance.add_or_update_peer(sender_peer)

    with SessionMaker() as session:
        if not circuit:
            all_facts: dict[int, Fact] = { }

            local_results = node_instance.search_ledger_for_api(
                session, search_term, include_uncorroborated=True
            )

            for fact in local_results:
                all_facts[fact.id] = fact

            future_to_peer = {
                node_instance.thread_pool.submit(
                    node_instance._fetch_from_peer, peer, search_term
                ): peer
                for peer in node_instance.peers
            }
            for future in future_to_peer:
                peer_results = future.result()
                for fact in peer_results:
                    if fact["fact_id"] not in all_facts:
                        all_facts[fact["fact_id"]] = fact
            return jsonify({"results": list(all_facts.values())})
        else:
            next_node_url = circuit.pop(0)
            try:
                response = requests.post(
                    f"{next_node_url}/anonymous_query",
                    json={
                        "term": search_term,
                        "circuit": circuit,
                        "sender_peer": node_instance.self_url,
                    },
                    timeout=10,
                )
                response.raise_for_status()
                return jsonify(response.json())
            except requests.exceptions.RequestException:
                return jsonify({"error": f"Relay node {next_node_url} is offline."}), 504


@app.route("/dao/proposals", methods=["GET"])
def handle_get_proposals():
    return jsonify(node_instance.active_proposals)


@app.route("/dao/submit_proposal", methods=["POST"])
def handle_submit_proposal():
    data = request.json
    proposer_url = data.get("proposer_url")
    aip_id = data.get("aip_id")
    aip_text = data.get("aip_text")
    if not all([proposer_url, aip_id, aip_text]):
        return jsonify({"status": "error", "message": "Missing parameters."}), 400
    if (
        proposer_url in node_instance.peers
        and node_instance.peers[proposer_url]["reputation"] >= 0.75
    ):
        if aip_id not in node_instance.active_proposals:
            node_instance.active_proposals[aip_id] = {
                "text": aip_text,
                "proposer": proposer_url,
                "votes": {},
            }
            return jsonify({"status": "success", "message": f"AIP {aip_id} submitted."})
        else:
            return (
                jsonify({"status": "error", "message": "Proposal ID already exists."}),
                409,
            )
    else:
        return jsonify({"status": "error", "message": "Insufficient reputation."}), 403


@app.route("/dao/submit_vote", methods=["POST"])
def handle_submit_vote():
    data = request.json
    voter_url = data.get("voter_url")
    aip_id = data.get("aip_id")
    vote_choice = data.get("choice")
    if not all([voter_url, aip_id, vote_choice]):
        return jsonify({"status": "error", "message": "Missing parameters."}), 400
    if aip_id not in node_instance.active_proposals:
        return jsonify({"status": "error", "message": "Proposal not found."}), 404
    voter_data = node_instance.peers.get(voter_url)
    if not voter_data:
        return jsonify({"status": "error", "message": "Unknown peer."}), 403
    voter_reputation = voter_data.get("reputation", 0)
    node_instance.active_proposals[aip_id]["votes"][voter_url] = {
        "choice": vote_choice,
        "weight": voter_reputation,
    }
    return jsonify({"status": "success", "message": "Vote recorded."})


def build_instance() -> AxiomNode:
    logger.info(
        f"initializing global instance for {'PRODUCTION' if 'gunicorn' in sys.argv[0] else 'DEVELOPMENT'}..."
    )
    port = int(os.environ.get("PORT", 5000))
    bootstrap = os.environ.get("BOOTSTRAP_PEER")
    node_instance = AxiomNode(port=port, bootstrap_peer=bootstrap)
    node_instance.start_background_tasks()
    return node_instance, port


def host_server(port) -> None:
    logger.info(f"starting in DEVELOPMENT mode on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False)


def cli_run(do_host: bool = True) -> None:
    """Server entrypoint."""
    # Setup instance
    global node_instance
    port = 5000 # Default port
    if node_instance is None:
        # We now receive both values back from the build function.
        node_instance, port = build_instance()
    # Run server
    if do_host:
        host_server(port) # And we pass the port to the host function.


# --- MAIN EXECUTION BLOCK ---
if __name__ == "__main__" or "gunicorn" in sys.argv[0]:
    cli_run(__name__ == "__main__")
