"""Node - Implementation of a single, P2P-enabled node of the Axiom fact network."""

from __future__ import annotations

# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
import argparse
import json
import logging
import sys
# --- FIX: Import the 'threading' module for synchronization ---
import threading
import time
from urllib.parse import urlparse
from datetime import datetime

from flask import Flask, Response, jsonify, request
from flask_cors import CORS

from axiom_server import (
    crucible,
    discovery_rss,
    merkle,
    verification_engine,
    zeitgeist_engine,
)
from axiom_server.api_query import semantic_search_ledger
from axiom_server.crucible import _extract_dates
from axiom_server.hasher import FactIndexer
# --- FIX: Import the new ledger functions ---
from axiom_server.ledger import (
    ENGINE,
    Block,
    Fact,
    FactLink,
    Proposal,
    SerializedFact,
    SessionMaker,
    Source,
    add_block_from_peer_data,
    create_genesis_block,
    get_latest_block,
    initialize_database,
    get_chain_as_dicts, # <-- New Import
    replace_chain,      # <-- New Import
)
from axiom_server.p2p.constants import (
    BOOTSTRAP_IP_ADDR,
    BOOTSTRAP_PORT,
)
# --- FIX: Import the Message class for creating responses ---
from axiom_server.p2p.node import ApplicationData, Message, Node as P2PBaseNode

__version__ = "3.1.3"

logger = logging.getLogger("axiom-node")
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    stdout_handler = logging.StreamHandler(stream=sys.stdout)
    formatter = logging.Formatter(
        "[%(name)s] %(asctime)s | %(levelname)s | %(filename)s:%(lineno)s >>> %(message)s",
    )
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)
logger.propagate = False
background_thread_logger = logging.getLogger("axiom-node.background-thread")


CORROBORATION_THRESHOLD = 2
db_lock = threading.Lock()
fact_indexer_lock = threading.Lock()
fact_indexer: FactIndexer | None = None

# --- NEW: We create a single class that combines Axiom logic and P2P networking ---
class AxiomNode(P2PBaseNode):
    """A class representing a single Axiom node, inheriting P2P capabilities."""

    def __init__(
        self,
        host: str,
        port: int,
        bootstrap_peer: str | None,
        public_ip: str | None,
    ) -> None:
        """Initialize both the P2P layer and the Axiom logic layer."""
        logger.info(f"Initializing Axiom Node on {host}:{port}")

        temp_p2p = P2PBaseNode.start(ip_address="0.0.0.0", port=port, public_ip=public_ip)
        
        super().__init__(
            ip_address=temp_p2p.ip_address,
            port=temp_p2p.port,
            public_ip=temp_p2p.public_ip,
            serialized_port=temp_p2p.serialized_port,
            private_key=temp_p2p.private_key,
            public_key=temp_p2p.public_key,
            serialized_public_key=temp_p2p.serialized_public_key,
            peer_links=temp_p2p.peer_links,
            server_socket=temp_p2p.server_socket,
        )

        # --- FIX: Add the synchronization event and store bootstrap peer info ---
        # A threading.Event is a signal flag. It starts in the "waiting" state.
        self.initial_sync_complete = threading.Event()
        # We store this to know if this node is a worker that needs to sync.
        self.bootstrap_peer = bootstrap_peer
        # --- END OF FIX ---

        self.active_proposals: dict[int, Proposal] = {}

        initialize_database(ENGINE)
        with SessionMaker() as session:
            create_genesis_block(session)

        if bootstrap_peer:
            parsed_url = urlparse(bootstrap_peer)
            bootstrap_host = parsed_url.hostname or BOOTSTRAP_IP_ADDR
            bootstrap_port = parsed_url.port or BOOTSTRAP_PORT
            threading.Thread(
                target=self.bootstrap,
                args=(bootstrap_host, bootstrap_port),
                daemon=True,
            ).start()

    def _handle_application_message(
        self,
        link: any, # This is a PeerLink object
        content: ApplicationData,
    ) -> None:
        """This method is the central dispatcher for all high-level P2P messages."""
        try:
            message = json.loads(content.data)
            msg_type = message.get("type")

            # --- FIX: Handle the new sync-related messages ---
            if msg_type == "CHAIN_RESPONSE":
                logger.info("Received full blockchain from peer. Beginning sync process...")
                chain_data = message.get("chain")
                if not chain_data:
                    logger.warning("CHAIN_RESPONSE message received but contained no 'chain' data.")
                    return

                with db_lock, SessionMaker() as session:
                    success = replace_chain(session, chain_data)
                    if success:
                        logger.info("Blockchain synchronization successful!")
                        # This is the crucial signal! It "un-pauses" the work loop.
                        self.initial_sync_complete.set()
                    else:
                        logger.error("Blockchain synchronization failed.")

            elif msg_type == "GET_CHAIN_REQUEST":
                logger.info(f"Peer {message.get('peer_addr')} requested our blockchain. Sending response...")
                chain_data_json_str = self._get_chain_for_peer()
                response_message = Message.application_data(chain_data_json_str)
                # Use the low-level _send_message to send back to the specific peer.
                self._send_message(link, response_message)

            elif msg_type == "new_block_header":
                msg_data = message.get("data")
                with db_lock, SessionMaker() as session:
                    add_block_from_peer_data(session, msg_data)
            # --- END OF FIX ---

        except Exception as e:
            background_thread_logger.error(
                f"Error processing peer message: {e}",
            )

    def _background_work_loop(self) -> None:
        """The main work cycle for fact-gathering and block-sealing."""
        background_thread_logger.info("Starting continuous Axiom work cycle.")
        while True:
            if self.bootstrap_peer:
                logger.info("Worker node started. Waiting for initial blockchain sync from bootstrap peer...")
                # The thread will pause here until `self.initial_sync_complete.set()` is called,
                # or until the timeout is reached.
                synced = self.initial_sync_complete.wait(timeout=60.0)
                if not synced:
                    logger.warning("Initial sync timed out after 60 seconds. Proceeding with local chain. The network may be partitioned.")
                else:
                    logger.info("Initial sync complete. Starting engine cycle.")
            while True:
                background_thread_logger.info("Axiom engine cycle start")

                # --- PHASE 1: Fact Gathering & Sealing ---
                # Acquire the lock only for the duration of this phase.
                with db_lock:
                    with SessionMaker() as session:
                        try:
                            topics = zeitgeist_engine.get_trending_topics(top_n=1)
                            content_list = []
                            if topics:
                                content_list = discovery_rss.get_content_from_prioritized_feed()

                            if not content_list:
                                background_thread_logger.info(
                                    "No new content found. Proceeding to verification phase.",
                                )
                            else:
                                facts_for_sealing: list[Fact] = []
                                adder = crucible.CrucibleFactAdder(
                                    session,
                                    fact_indexer,
                                    fact_indexer_lock,
                                )
                                for item in content_list:
                                    domain = urlparse(item["source_url"]).netloc
                                    source = session.query(Source).filter(
                                        Source.domain == domain,
                                    ).one_or_none() or Source(domain=domain)
                                    session.add(source)

                                    new_facts = crucible.extract_facts_from_text(
                                        item["content"],
                                    )
                                    for fact in new_facts:
                                        fact.sources.append(source)
                                        session.add(fact)
                                        session.commit()
                                        adder.add(fact)
                                        facts_for_sealing.append(fact)

                                if facts_for_sealing:
                                    background_thread_logger.info(
                                        f"Preparing to seal {len(facts_for_sealing)} new facts into a block...",
                                    )
                                    latest_block = get_latest_block(session)
                                    assert latest_block is not None
                                    fact_hashes = sorted(
                                        [f.hash for f in facts_for_sealing],
                                    )
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
                                        f"Successfully sealed and added Block #{new_block.height}.",
                                    )
                                    broadcast_data = {
                                        "type": "new_block_header",
                                        "data": new_block.to_dict(),
                                    }
                                    self.broadcast_application_message(
                                        json.dumps(broadcast_data),
                                    )
                                    background_thread_logger.info(
                                        "Broadcasted new block header to network.",
                                    )
                        except Exception as e:
                            background_thread_logger.exception(
                                f"Critical error in learning loop: {e}",
                            )

                # --- The database lock is now RELEASED. The API is fully responsive. ---

                # --- PHASE 2: Verification ---
                # Acquire the lock again for this separate database transaction.
                with db_lock:
                    with SessionMaker() as session:
                        try:
                            background_thread_logger.info(
                                "Starting verification phase...",
                            )
                            facts_to_verify = (
                                session.query(Fact)
                                .filter(Fact.status == "ingested")
                                .all()
                            )
                            if not facts_to_verify:
                                background_thread_logger.info(
                                    "No new facts to verify.",
                                )
                            else:
                                background_thread_logger.info(
                                    f"Found {len(facts_to_verify)} facts to verify.",
                                )
                                for fact in facts_to_verify:
                                    claims = verification_engine.find_corroborating_claims(
                                        fact,
                                        session,
                                    )
                                    if len(claims) >= CORROBORATION_THRESHOLD:
                                        fact.status = "corroborated"
                                        background_thread_logger.info(
                                            f"Fact '{fact.hash[:8]}' has been corroborated with {len(claims)} pieces of evidence.",
                                        )
                                        fact.score += 10
                                session.commit()
                        except Exception as e:
                            background_thread_logger.exception(
                                f"Error during verification phase: {e}",
                            )

                # --- The database lock is RELEASED again. ---

                background_thread_logger.info("Axiom cycle finished. Sleeping.")
                # The long sleep happens while NO locks are held.
                time.sleep(10800)

    def start(self) -> None:
        """Start all background tasks and the main P2P loop."""
        work_thread = threading.Thread(
            target=self._background_work_loop,
            daemon=True,
        )
        work_thread.start()

        logger.info("Starting P2P network update loop...")
        while True:
            time.sleep(0.1)
            self.update()

    def _get_chain_for_peer(self) -> str:
        """A thread-safe method to get the entire blockchain as a JSON string."""
        with db_lock, SessionMaker() as session:
            chain_dicts = get_chain_as_dicts(session)
            response_data = {"type": "CHAIN_RESPONSE", "chain": chain_dicts}
            return json.dumps(response_data)

    @classmethod
    def start_node(cls, host: str, port: int, bootstrap: bool) -> AxiomNode:
        """A factory method to create and initialize a complete AxiomNode.
        This is the preferred way to instantiate the node.
        """
        # 1. Use the parent's factory to create the low-level P2P components.
        p2p_instance = P2PBaseNode.start(ip_address=host, port=port)

        # 2. Create an instance of our AxiomNode, passing the bootstrap flag.
        axiom_instance = cls(
            host=p2p_instance.ip_address,
            port=p2p_instance.port,
            bootstrap=bootstrap,
        )

        # 3. Transfer the initialized P2P components to our instance.
        axiom_instance.serialized_port = p2p_instance.serialized_port
        axiom_instance.private_key = p2p_instance.private_key
        axiom_instance.public_key = p2p_instance.public_key
        axiom_instance.serialized_public_key = (
            p2p_instance.serialized_public_key
        )
        axiom_instance.peer_links = p2p_instance.peer_links
        axiom_instance.server_socket = p2p_instance.server_socket

        return axiom_instance


# --- All Flask API endpoints are UNCHANGED ---
app = Flask(__name__)
CORS(app)
node_instance: AxiomNode
fact_indexer: FactIndexer | None = None


@app.route("/chat", methods=["POST"])
def handle_chat_query():
    """Handles natural language queries from the client.

    Finding the most semantically similar facts in the ledger.
    """
    data = request.get_json()
    if not data or "query" not in data:
        return jsonify({"error": "Missing 'query' in request body"}), 400

    query = data["query"]

    with fact_indexer_lock:
        closest_facts = fact_indexer.find_closest_facts(query)

    # Return the results to the client.
    return jsonify({"results": closest_facts})


@app.route("/get_timeline/<topic>", methods=["GET"])
def handle_get_timeline(topic: str) -> Response:
    """Assembles a verifiable timeline of facts related to a topic."""
    with db_lock:
        with SessionMaker() as session:
            initial_facts = semantic_search_ledger(
                session,
                topic,
                min_status="ingested",
                top_n=50,
            )
            if not initial_facts:
                return jsonify(
                    {
                        "timeline": [],
                        "message": "No facts found for this topic.",
                    },
                )

            def get_date_from_fact(fact: Fact) -> datetime:
                dates = _extract_dates(fact.content)
                return min(dates) if dates else datetime.min

            sorted_facts = sorted(initial_facts, key=get_date_from_fact)
            timeline_data = [
                SerializedFact.from_fact(f).model_dump() for f in sorted_facts
            ]
            return jsonify({"timeline": timeline_data})


@app.route("/get_chain_height", methods=["GET"])
def handle_get_chain_height() -> Response:
    """Handle get chain height request."""
    with db_lock:
        with SessionMaker() as session:
            latest_block = get_latest_block(session)
            return jsonify(
                {"height": latest_block.height if latest_block else -1},
            )


@app.route("/get_blocks", methods=["GET"])
def handle_get_blocks() -> Response:
    """Handle get blocks request."""
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
                "merkle_root": b.merkle_root,
            }
            for b in blocks
        ]
        return jsonify({"blocks": blocks_data})


@app.route("/status", methods=["GET"])
def handle_get_status() -> Response:
    """Provides a simple status check for the node."""
    with SessionMaker() as session:
        latest_block = get_latest_block(session)
        height = latest_block.height if latest_block else 0
        return jsonify(
            {
                "status": "ok",
                "latest_block_height": height,
                "version": __version__,
            },
        )


@app.route("/local_query", methods=["GET"])
def handle_local_query() -> Response:
    """Handle local query request using semantic vector search."""
    search_term = request.args.get("term") or ""
    with SessionMaker() as session:
        results = semantic_search_ledger(session, search_term)
        fact_models = [
            SerializedFact.from_fact(fact).model_dump() for fact in results
        ]
        return jsonify({"results": fact_models})


@app.route("/get_peers", methods=["GET"])
def handle_get_peers() -> Response:
    """Handle get peers request."""
    known_peers = []
    if node_instance:
        known_peers = [link.fmt_addr() for link in node_instance.iter_links()]
    return jsonify({"peers": known_peers})


@app.route("/get_fact_ids", methods=["GET"])
def handle_get_fact_ids() -> Response:
    """Handle get fact ids request."""
    with SessionMaker() as session:
        fact_ids: list[int] = [
            fact.id for fact in session.query(Fact).with_entities(Fact.id)
        ]
        return jsonify({"fact_ids": fact_ids})


@app.route("/get_fact_hashes", methods=["GET"])
def handle_get_fact_hashes() -> Response:
    """Handle get fact hashes request."""
    with SessionMaker() as session:
        fact_hashes: list[str] = [
            fact.hash for fact in session.query(Fact).with_entities(Fact.hash)
        ]
        return jsonify({"fact_hashes": fact_hashes})


@app.route("/get_facts_by_id", methods=["POST"])
def handle_get_facts_by_id() -> Response:
    """Handle get facts by id request."""
    requested_ids: set[int] = set((request.json or {}).get("fact_ids", []))
    with SessionMaker() as session:
        facts = list(session.query(Fact).filter(Fact.id.in_(requested_ids)))
        fact_models = [
            SerializedFact.from_fact(fact).model_dump() for fact in facts
        ]
        return jsonify({"facts": fact_models})


@app.route("/get_facts_by_hash", methods=["POST"])
def handle_get_facts_by_hash() -> Response:
    """Handle get facts by hash request."""
    requested_hashes: set[str] = set(
        (request.json or {}).get("fact_hashes", []),
    )
    with SessionMaker() as session:
        facts = list(
            session.query(Fact).filter(Fact.hash.in_(requested_hashes)),
        )
        fact_models = [
            SerializedFact.from_fact(fact).model_dump() for fact in facts
        ]
        return jsonify({"facts": fact_models})


@app.route("/get_merkle_proof", methods=["GET"])
def handle_get_merkle_proof() -> Response | tuple[Response, int]:
    fact_hash = request.args.get("fact_hash")
    block_height_str = request.args.get("block_height")
    if not fact_hash or not block_height_str:
        return jsonify(
            {"error": "fact_hash and block_height are required parameters"},
        ), 400
    try:
        block_height = int(block_height_str)
    except ValueError:
        return jsonify({"error": "block_height must be an integer"}), 400
    with SessionMaker() as session:
        block = (
            session.query(Block)
            .filter(Block.height == block_height)
            .one_or_none()
        )
        if not block:
            return jsonify(
                {"error": f"Block at height {block_height} not found"},
            ), 404
        fact_hashes_in_block = json.loads(block.fact_hashes)
        if fact_hash not in fact_hashes_in_block:
            return jsonify(
                {"error": "Fact hash not found in the specified block"},
            ), 404
        merkle_tree = merkle.MerkleTree(fact_hashes_in_block)
        try:
            fact_index = fact_hashes_in_block.index(fact_hash)
            proof = merkle_tree.get_proof(fact_index)
        except (ValueError, IndexError) as e:
            logger.error(f"Error generating Merkle proof: {e}")
            return jsonify({"error": "Failed to generate Merkle proof"}), 500
        return jsonify(
            {
                "fact_hash": fact_hash,
                "block_height": block_height,
                "merkle_root": block.merkle_root,
                "proof": proof,
            },
        )


@app.route("/anonymous_query", methods=["POST"])
def handle_anonymous_query() -> Response | tuple[Response, int]:
    return jsonify({"error": "Anonymous query not implemented in V4"}), 501


@app.route("/dao/proposals", methods=["GET"])
def handle_get_proposals() -> Response:
    return jsonify({"error": "DAO not implemented in V4"}), 501


@app.route("/dao/submit_proposal", methods=["POST"])
def handle_submit_proposal() -> Response | tuple[Response, int]:
    return jsonify({"error": "DAO not implemented in V4"}), 501


@app.route("/dao/submit_vote", methods=["POST"])
def handle_submit_vote() -> Response | tuple[Response, int]:
    return jsonify({"error": "DAO not implemented in V4"}), 501


@app.route("/verify_fact", methods=["POST"])
def handle_verify_fact() -> Response | tuple[Response, int]:
    fact_id = (request.json or {}).get("fact_id")
    if not fact_id:
        return jsonify({"error": "fact_id is required"}), 400
    with SessionMaker() as session:
        fact_to_verify = session.get(Fact, fact_id)
        if not fact_to_verify:
            return jsonify({"error": "Fact not found"}), 404
        corroborating_claims = verification_engine.find_corroborating_claims(
            fact_to_verify,
            session,
        )
        citations_report = verification_engine.verify_citations(fact_to_verify)
        verification_report = {
            "target_fact_id": fact_to_verify.id,
            "target_content": fact_to_verify.content,
            "corroboration_analysis": {
                "status": f"Found {len(corroborating_claims)} corroborating claims from other sources.",
                "corroborations": corroborating_claims,
            },
            "citation_analysis": {
                "status": f"Found {len(citations_report)} citations within the fact content.",
                "citations": citations_report,
            },
        }
        return jsonify(verification_report)


@app.route("/get_fact_context/<fact_hash>", methods=["GET"])
def handle_get_fact_context(fact_hash: str) -> Response | tuple[Response, int]:
    with SessionMaker() as session:
        target_fact = (
            session.query(Fact).filter(Fact.hash == fact_hash).one_or_none()
        )
        if not target_fact:
            return jsonify({"error": "Fact not found"}), 404
        links = (
            session.query(FactLink)
            .filter(
                (FactLink.fact1_id == target_fact.id)
                | (FactLink.fact2_id == target_fact.id),
            )
            .all()
        )
        related_facts_data = []
        for link in links:
            other_fact = (
                link.fact2 if link.fact1_id == target_fact.id else link.fact1
            )
            related_facts_data.append(
                {
                    "relationship": link.relationship_type.value,
                    "fact": SerializedFact.from_fact(other_fact).model_dump(),
                },
            )
        return jsonify(
            {
                "target_fact": SerializedFact.from_fact(
                    target_fact,
                ).model_dump(),
                "related_facts": related_facts_data,
            },
        )


def main() -> None:
    """The main entry point for running an Axiom Node from the command line."""
    global node_instance, fact_indexer

    # 1. Setup the argument parser
    parser = argparse.ArgumentParser(description="Run an Axiom P2P Node.")
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host IP to bind to.",
    )
    parser.add_argument(
        "--p2p-port",
        type=int,
        default=5000,
        help="Port for P2P communication.",
    )
    parser.add_argument(
        "--api-port",
        type=int,
        default=8000,
        help="Port for the Flask API server.",
    )
    parser.add_argument(
        "--bootstrap-peer",
        type=str,
        default=None,
        help="Full URL of a peer to connect to for bootstrapping (e.g., http://host:port).",
    )
    parser.add_argument(
        "--public-ip",
        type=str,
        default=None,
        help="The public IP address of this node for self-discovery.",
    )
    args = parser.parse_args()

    try:
        # 2. Create the AxiomNode instance, passing the arguments directly.
        node_instance = AxiomNode(
            host=args.host,
            port=args.p2p_port,
            bootstrap_peer=args.bootstrap_peer,
            public_ip=args.public_ip,
        )

        node_instance.p2p_node.get_chain_callback = node_instance._get_chain_for_peer

        logger.info("--- Initializing Fact Indexer for Hybrid Search ---")
        with SessionMaker() as db_session:
            # Create the indexer instance, passing it the session it needs.
            fact_indexer = FactIndexer(db_session)
            # Build the initial index.
            fact_indexer.index_facts_from_db()

        # 3. Start the Flask API server in its own thread.
        api_thread = threading.Thread(
            target=lambda: app.run(
                host=args.host,
                port=args.api_port,
                debug=False,
                use_reloader=False,
            ),
            daemon=True,
        )
        api_thread.start()
        logger.info(
            f"Flask API server started on http://{args.host}:{args.api_port}",
        )

        # 4. Start the main P2P and Axiom work loops.
        node_instance.start()

    except KeyboardInterrupt:
        logger.info("Shutdown signal received. Exiting.")
    except Exception as e:
        logger.critical(
            f"A critical error occurred during node startup: {e}",
            exc_info=True,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
