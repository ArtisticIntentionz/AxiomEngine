# Axiom - node.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import TypedDict
from urllib.parse import urlparse

from flask import Flask, jsonify, request, Response

from . import crucible, discovery_rss, p2p, zeitgeist_engine
from .api_query import search_ledger_for_api
from .ledger import (
    Block,
    create_genesis_block,
    ENGINE,
    Fact,
    get_latest_block,
    initialize_database,
    Proposal,
    SerializedFact,
    SessionMaker,
    Source,
    Votes,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("axiom-node")
stdout_handler = logging.StreamHandler(stream=sys.stdout)
formatter = logging.Formatter(
    "[%(name)s] %(asctime)s | %(levelname)s | %(filename)s:%(lineno)s >>> %(message)s"
)
stdout_handler.setFormatter(formatter)
logger.addHandler(stdout_handler)
logger.setLevel(logging.INFO)
logger.propagate = False
background_thread_logger = logging.getLogger("axiom-node-background-thread")
background_thread_logger.addHandler(stdout_handler)
background_thread_logger.setLevel(logging.INFO)
background_thread_logger.propagate = False


class Peer(TypedDict):
    reputation: float
    first_seen: str
    last_seen: str


class AxiomNode:
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 5000,
        bootstrap_peer: str | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.self_url = f"http://{self.host}:{port}"
        self.peers: dict[str, Peer] = {}
        if bootstrap_peer:
            self.peers[bootstrap_peer] = Peer(
                {
                    "reputation": 0.05,
                    "first_seen": datetime.now(timezone.utc).isoformat(),
                    "last_seen": datetime.now(timezone.utc).isoformat(),
                }
            )
        self.active_proposals: dict[int, Proposal] = {}
        self.thread_pool = ThreadPoolExecutor(max_workers=10)

        initialize_database(ENGINE)
        with SessionMaker() as session:
            create_genesis_block(session)

    def add_or_update_peer(self, peer_url: str) -> None:
        if (
            peer_url
            and peer_url not in self.peers
            and peer_url != self.self_url
        ):
            self.peers[peer_url] = Peer(
                {
                    "reputation": 0.05,
                    "first_seen": datetime.now(timezone.utc).isoformat(),
                    "last_seen": datetime.now(timezone.utc).isoformat(),
                }
            )
        elif peer_url in self.peers:
            self.peers[peer_url]["last_seen"] = datetime.now(
                timezone.utc
            ).isoformat()

    def _update_reputation(
        self, peer_url: str, sync_status: str, new_blocks_count: int
    ) -> None:
        if peer_url not in self.peers:
            return
        REP_PENALTY = 0.2
        REP_REWARD_UPTIME = 0.0001
        REP_REWARD_SEALED_BLOCK = 0.0075
        current_rep = self.peers[peer_url]["reputation"]

        if sync_status in ("CONNECTION_FAILED", "SYNC_ERROR"):
            new_rep = current_rep - REP_PENALTY
        elif sync_status == "SUCCESS_UP_TO_DATE":
            new_rep = current_rep + REP_REWARD_UPTIME
        elif sync_status == "SUCCESS_NEW_BLOCKS":
            new_rep = (
                current_rep
                + REP_REWARD_UPTIME
                + (new_blocks_count * REP_REWARD_SEALED_BLOCK)
            )
        else:
            new_rep = current_rep
        self.peers[peer_url]["reputation"] = max(0.0, min(1.0, new_rep))

    def _background_loop(self) -> None:
        background_thread_logger.info("starting continuous cycle.")
        with SessionMaker() as session:
            while True:
                background_thread_logger.info("axiom engine cycle start")
                try:
                    topics = zeitgeist_engine.get_trending_topics(top_n=1)
                    if not topics:
                        background_thread_logger.warning(
                            "Zeitgeist found no topics. Skipping cycle for 1 hour."
                        )
                        time.sleep(3600)
                        continue

                    content_list = (
                        discovery_rss.get_content_from_prioritized_feed()
                    )

                    facts_for_sealing: list[Fact] = []
                    if content_list:
                        for item in content_list:
                            domain = urlparse(item["source_url"]).netloc
                            source = session.query(Source).filter(
                                Source.domain == domain
                            ).one_or_none() or Source(domain=domain)
                            session.add(source)

                            new_facts = crucible.extract_facts_from_text(
                                item["content"]
                            )
                            adder = crucible.CrucibleFactAdder(session)
                            for fact in new_facts:
                                fact.sources.append(source)
                                session.add(fact)
                                session.commit()
                                adder.add(fact)
                                facts_for_sealing.append(fact)

                    if facts_for_sealing:
                        background_thread_logger.info(
                            f"Preparing to seal {len(facts_for_sealing)} new facts into a block..."
                        )
                        latest_block = get_latest_block(session)
                        assert latest_block is not None
                        fact_hashes = [f.hash for f in facts_for_sealing]
                        new_block = Block(
                            height=latest_block.height + 1,
                            previous_hash=latest_block.hash,
                            fact_hashes=json.dumps(fact_hashes),
                            timestamp=time.time(),
                        )
                        new_block.seal_block(difficulty=4)
                        session.add(new_block)
                        session.commit()
                        background_thread_logger.info(
                            f"Successfully sealed and added Block #{new_block.height}."
                        )

                except Exception as e:
                    background_thread_logger.exception(
                        f"Critical error in learning loop: {e}"
                    )

                background_thread_logger.info("axiom engine cycle finish")

                for peer_url in list(self.peers.keys()):
                    sync_status, new_blocks_count = p2p.sync_with_peer(
                        self, peer_url, session
                    )
                    self._update_reputation(
                        peer_url, sync_status, new_blocks_count
                    )

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

                time.sleep(10800)

    def start_background_tasks(self) -> None:
        background_thread = threading.Thread(
            target=self._background_loop, daemon=True
        )
        background_thread.start()


app = Flask(__name__)
node_instance: AxiomNode


@app.route("/get_chain_height", methods=["GET"])
def handle_get_chain_height() -> Response:
    with SessionMaker() as session:
        latest_block = get_latest_block(session)
        return jsonify({"height": latest_block.height if latest_block else -1})


@app.route("/get_blocks", methods=["GET"])
def handle_get_blocks() -> Response:
    since_height = int(request.args.get("since", -1))
    with SessionMaker() as session:
        blocks = (
            session.query(Block)
            .filter(Block.height > since_height)
            .order_by(Block.height.asc())
            .all()
        )
        blocks_data = [
            {
                "height": b.height,
                "hash": b.hash,
                "previous_hash": b.previous_hash,
                "timestamp": b.timestamp,
                "nonce": b.nonce,
                "fact_hashes": json.loads(b.fact_hashes),
            }
            for b in blocks
        ]
        return jsonify({"blocks": blocks_data})


@app.route("/local_query", methods=["GET"])
def handle_local_query() -> Response:
    search_term = request.args.get("term")
    with SessionMaker() as session:
        results = search_ledger_for_api(session, search_term or "")
        fact_models = [
            SerializedFact.from_fact(fact).model_dump() for fact in results
        ]
        return jsonify({"results": fact_models})


@app.route("/get_peers", methods=["GET"])
def handle_get_peers() -> Response:
    return jsonify({"peers": node_instance.peers})


@app.route("/get_fact_ids", methods=["GET"])
def handle_get_fact_ids() -> Response:
    with SessionMaker() as session:
        fact_ids: list[int] = [
            fact.id for fact in session.query(Fact).with_entities(Fact.id)
        ]
        return jsonify({"fact_ids": fact_ids})


@app.route("/get_fact_hashes", methods=["GET"])
def handle_get_fact_hashes() -> Response:
    with SessionMaker() as session:
        fact_hashes: list[str] = [
            fact.hash for fact in session.query(Fact).with_entities(Fact.hash)
        ]
        return jsonify({"fact_hashes": fact_hashes})


@app.route("/get_facts_by_id", methods=["POST"])
def handle_get_facts_by_id() -> Response:
    requested_ids: set[int] = set((request.json or {}).get("fact_ids", []))
    with SessionMaker() as session:
        facts = list(session.query(Fact).filter(Fact.id.in_(requested_ids)))
        fact_models = [
            SerializedFact.from_fact(fact).model_dump() for fact in facts
        ]
        return jsonify({"facts": fact_models})


@app.route("/get_facts_by_hash", methods=["POST"])
def handle_get_facts_by_hash() -> Response:
    requested_hashes: set[str] = set(
        (request.json or {}).get("fact_hashes", [])
    )
    with SessionMaker() as session:
        facts = list(
            session.query(Fact).filter(Fact.hash.in_(requested_hashes))
        )
        fact_models = [
            SerializedFact.from_fact(fact).model_dump() for fact in facts
        ]
        return jsonify({"facts": fact_models})


@app.route("/anonymous_query", methods=["POST"])
def handle_anonymous_query() -> Response | tuple[Response, int]:
    # This endpoint is complex and its logic is tied to the deprecated V2.5 P2P querying.
    # It will need a significant V3.1 redesign to work with the new architecture.
    # For now, we will mark it as not implemented.
    return jsonify({"error": "Anonymous query not implemented in V3.1"}), 501


@app.route("/dao/proposals", methods=["GET"])
def handle_get_proposals() -> Response:
    return jsonify(node_instance.active_proposals)


@app.route("/dao/submit_proposal", methods=["POST"])
def handle_submit_proposal() -> Response | tuple[Response, int]:
    data = request.json or {}
    proposer_url = data.get("proposer_url")
    aip_id = data.get("aip_id")
    aip_text = data.get("aip_text")
    if not all((proposer_url, aip_id, aip_text)):
        return jsonify(
            {"status": "error", "message": "Missing parameters."}
        ), 400
    if (
        proposer_url in node_instance.peers
        and node_instance.peers[str(proposer_url)]["reputation"] >= 0.75
    ):
        assert isinstance(aip_id, int)
        assert isinstance(aip_text, str)
        if aip_id not in node_instance.active_proposals:
            node_instance.active_proposals[aip_id] = Proposal(
                {"text": aip_text, "proposer": str(proposer_url), "votes": {}}
            )
            return jsonify(
                {"status": "success", "message": f"AIP {aip_id} submitted."}
            )
        else:
            return jsonify(
                {"status": "error", "message": "Proposal ID already exists."}
            ), 409
    else:
        return jsonify(
            {"status": "error", "message": "Insufficient reputation."}
        ), 403


@app.route("/dao/submit_vote", methods=["POST"])
def handle_submit_vote() -> Response | tuple[Response, int]:
    data = request.json or {}
    voter_url = data.get("voter_url")
    aip_id = data.get("aip_id")
    vote_choice = data.get("choice")
    if not all((voter_url, aip_id, vote_choice)):
        return jsonify(
            {"status": "error", "message": "Missing parameters."}
        ), 400
    assert isinstance(aip_id, int)
    if aip_id not in node_instance.active_proposals:
        return jsonify(
            {"status": "error", "message": "Proposal not found."}
        ), 404

    assert voter_url is not None and isinstance(vote_choice, str)

    voter_data = node_instance.peers.get(str(voter_url))
    if not voter_data:
        return jsonify({"status": "error", "message": "Unknown peer."}), 403
    voter_reputation = voter_data.get("reputation", 0.0)
    node_instance.active_proposals[aip_id]["votes"][str(voter_url)] = Votes(
        {"choice": vote_choice, "weight": voter_reputation}
    )
    return jsonify({"status": "success", "message": "Vote recorded."})


def build_instance() -> tuple[AxiomNode, int]:
    logger.info(
        f"initializing global instance for {'PRODUCTION' if 'gunicorn' in sys.argv[0] else 'DEVELOPMENT'}..."
    )
    port = int(os.environ.get("PORT", 5000))
    bootstrap = os.environ.get("BOOTSTRAP_PEER")
    global node_instance
    node_instance = AxiomNode(port=port, bootstrap_peer=bootstrap)
    node_instance.start_background_tasks()
    return node_instance, port


def host_server(port: int) -> None:
    logger.info(f"starting in DEVELOPMENT mode on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False)


def cli_run(do_host: bool = True) -> None:
    port = 5000
    try:
        node_instance_exists = (
            "node_instance" in globals() and node_instance is not None
        )
    except NameError:
        node_instance_exists = False
    if not node_instance_exists:
        _, port = build_instance()
    if do_host:
        host_server(port)


if __name__ == "__main__" or "gunicorn" in sys.argv[0]:
    cli_run(__name__ == "__main__")
