"""Node - Implementation of a single, P2P-enabled node of the Axiom fact network."""

from __future__ import annotations

# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
import argparse
import hashlib
import json
import logging
import random
import sys
import threading
import time
from datetime import datetime
from urllib.parse import urlparse

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
    get_chain_as_dicts,
    get_latest_block,
    initialize_database,
    replace_chain,
)
from axiom_server.p2p.constants import (
    BOOTSTRAP_IP_ADDR,
    BOOTSTRAP_PORT,
)
from axiom_server.p2p.node import (
    ApplicationData,
    Message,
    Node as P2PBaseNode,
    PeerLink,
)

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


# --- We create a single class that combines Axiom logic and P2P networking ---
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

        # 1. We must call the parent constructor from the P2P library first.
        # This allows it to correctly handle both local and public connections.
        temp_p2p = P2PBaseNode.start(
            ip_address=host,
            port=port,
        )

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
        self.peer_links_lock = threading.Lock()

        self.initial_sync_complete = threading.Event()
        self.bootstrap_peer = bootstrap_peer
        self.new_block_received = threading.Event()
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
        peer_link: PeerLink,  # Renamed _link to peer_link for clarity and usage
        content: ApplicationData,
    ) -> None:
        """Dispatch all high-level P2P messages."""
        try:
            message = json.loads(content.data)
            msg_type = message.get("type")

            if msg_type == "CHAIN_RESPONSE":
                logger.info(
                    "Received full blockchain from peer. Beginning sync process...",
                )
                chain_data = message.get("chain")
                if not chain_data:
                    logger.warning(
                        "CHAIN_RESPONSE message received but contained no 'chain' data.",
                    )
                    return

                with db_lock, SessionMaker() as session:
                    success = replace_chain(session, chain_data)
                    if success:
                        logger.info("Blockchain synchronization successful!")
                        self.initial_sync_complete.set()
                    else:
                        logger.error("Blockchain synchronization failed.")

            elif msg_type == "GET_CHAIN_REQUEST":
                logger.info(
                    f"Peer {message.get('peer_addr')} requested our blockchain. Sending response...",
                )
                chain_data_json_str = self._get_chain_for_peer()
                response_message = Message.application_data(
                    chain_data_json_str,
                )
                # Use the 'peer_link' argument which represents the connection to the peer
                self._send_message(
                    peer_link,
                    response_message,
                )  # Changed 'link' to 'peer_link'

            elif msg_type == "new_block_header":
                msg_data = message.get("data")
                with db_lock, SessionMaker() as session:
                    new_block = add_block_from_peer_data(session, msg_data)
                    if new_block:
                        self.new_block_received.set()

        except Exception as e:
            background_thread_logger.error(
                f"Error processing peer message: {e}",
            )

    def _background_work_loop(self) -> None:
        """Refactor the main work cycle to be interruptible.

        handle database sessions correctly, and update the search index.
        """
        if self.bootstrap_peer:
            logger.info(
                "Worker node started. Waiting for initial blockchain sync from bootstrap peer...",
            )
            synced = self.initial_sync_complete.wait(timeout=60.0)
            if not synced:
                logger.warning(
                    "Initial sync timed out after 60 seconds. Proceeding with local chain. The network may be partitioned.",
                )
            else:
                logger.info("Initial sync complete.")

        background_thread_logger.info("Starting continuous Axiom work cycle.")

        while True:
            background_thread_logger.info(
                "Axiom engine cycle start: Listening for new content...",
            )

            new_block_candidate = None
            latest_block_before_mining = None
            facts_sealed_in_block: list[Fact] = []

            with db_lock, SessionMaker() as session:
                try:
                    topics = zeitgeist_engine.get_trending_topics(top_n=1)
                    content_list = []
                    if topics:
                        content_list = (
                            discovery_rss.get_content_from_prioritized_feed()
                        )

                        if not content_list:
                            background_thread_logger.info(
                                "No new content found. Proceeding to verification phase.",
                            )
                        else:
                            facts_for_sealing: list[Fact] = []
                            adder = crucible.CrucibleFactAdder(
                                session,
                                fact_indexer,
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
                                    # --- THIS IS THE FIX ---
                                    # Calculate the SHA256 hash of the fact's content.
                                    fact.hash = hashlib.sha256(
                                        fact.content.encode("utf-8"),
                                    ).hexdigest()
                                    # --- END OF FIX ---

                                    fact.sources.append(source)
                                    session.add(
                                        fact,
                                    )  # Add the fact with its new hash to the session.
                                    facts_for_sealing.append(fact)

                                # Bonus Performance Improvement: Commit once after processing all new facts from the item.
                                session.commit()

                                # Now that the facts are safely in the DB, add them to the search index.
                                with fact_indexer_lock:
                                    for fact in new_facts:
                                        adder.add(fact)

                        if facts_for_sealing:
                            background_thread_logger.info(
                                f"Preparing to mine a new block with {len(facts_for_sealing)} facts...",
                            )

                            latest_block_before_mining = get_latest_block(
                                session,
                            )
                            assert latest_block_before_mining is not None

                            fact_hashes = sorted(
                                [f.hash for f in facts_for_sealing],
                            )

                            new_block_candidate = Block(
                                height=latest_block_before_mining.height + 1,
                                previous_hash=latest_block_before_mining.hash,
                                fact_hashes=json.dumps(fact_hashes),
                                timestamp=time.time(),
                            )
                            # --- Store the actual fact objects for later indexing ---
                            facts_sealed_in_block = facts_for_sealing

                except Exception as e:
                    background_thread_logger.exception(
                        f"Error during fact gathering: {e}",
                    )

            if new_block_candidate:
                self.new_block_received.clear()

                was_sealed = self.seal_block_interruptibly(
                    new_block_candidate,
                    difficulty=4,
                )

                if was_sealed:
                    with db_lock, SessionMaker() as session:
                        current_chain_head = get_latest_block(session)
                        if (
                            current_chain_head.height
                            > latest_block_before_mining.height
                        ):
                            background_thread_logger.warning(
                                "Mined a block, but the chain grew while we worked. Discarding our block (stale).",
                            )
                        else:
                            session.add(new_block_candidate)
                            session.commit()
                            background_thread_logger.info(
                                f"Successfully sealed and added Block #{new_block_candidate.height}.",
                            )
                            broadcast_data = {
                                "type": "new_block_header",
                                "data": new_block_candidate.to_dict(),
                            }
                            self.broadcast_application_message(
                                json.dumps(broadcast_data),
                            )
                            background_thread_logger.info(
                                "Broadcasted new block header to network.",
                            )

                            if facts_sealed_in_block:
                                background_thread_logger.info(
                                    f"Updating search index with {len(facts_sealed_in_block)} new facts from the sealed block...",
                                )
                                with fact_indexer_lock:
                                    # Ensure your FactIndexer has an `add_facts` method.
                                    fact_indexer.add_facts(
                                        facts_sealed_in_block,
                                    )
                                background_thread_logger.info(
                                    "Search index update complete.",
                                )

                else:
                    background_thread_logger.info(
                        "Mining was interrupted by a new block from a peer. Abandoning our work and starting new cycle.",
                    )

            with db_lock, SessionMaker() as session:
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
                            claims = (
                                verification_engine.find_corroborating_claims(
                                    fact,
                                    session,
                                )
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

            background_thread_logger.info("Axiom cycle finished. Sleeping.")
            time.sleep(10800)

    def seal_block_interruptibly(self, block: Block, difficulty: int) -> bool:
        """Perform Proof of Work for a given block, but frequently check the self.new_block_received event to see if work should be aborted."""
        fact_hashes_list = json.loads(block.fact_hashes)
        if fact_hashes_list:
            merkle_tree = merkle.MerkleTree(fact_hashes_list)
            block.merkle_root = merkle_tree.root.hex()
        else:
            block.merkle_root = hashlib.sha256(b"").hexdigest()

        target = "0" * difficulty

        while True:
            if block.nonce % 1000 == 0 and self.new_block_received.is_set():
                return False

            block.hash = block.calculate_hash()
            if block.hash.startswith(target):
                logger.info(f"Block sealed! Hash: {block.hash}")
                return True

            block.nonce += 1

    def start(self) -> None:
        """Start all background tasks and the main P2P loop."""
        work_thread = threading.Thread(
            target=self._background_work_loop,
            daemon=True,
        )
        peer_thread = threading.Thread(
            target=self._peer_management_loop,
            daemon=True,
        )
        work_thread.start()
        peer_thread.start()

        logger.info("Starting P2P network update loop...")
        while True:
            time.sleep(0.1)
            self.update()

    def _get_chain_for_peer(self) -> str:
        """Get the entire blockchain as a JSON string using a thread-safe method."""
        with db_lock, SessionMaker() as session:
            chain_dicts = get_chain_as_dicts(session)
            response_data = {"type": "CHAIN_RESPONSE", "chain": chain_dicts}
            return json.dumps(response_data)

    def _peer_management_loop(self) -> None:
        """Maintain and expand the node's peer connections in a background thread."""
        logger.info("Starting peer management loop.")
        while True:
            try:
                # --- THIS IS THE NEW, SMARTER LOGIC ---
                with self.peer_links_lock:
                    if not self.peer_links:
                        # If we don't know any peers, wait a bit before checking again.
                        time.sleep(60)
                        continue

                    # Choose up to 3 random peers to ask.
                    # This prevents spamming the whole network and breaks simple loops.
                    num_to_ask = min(3, len(self.peer_links))
                    peers_to_ask = random.sample(self.peer_links, num_to_ask)

                logger.info(
                    f"Asking {len(peers_to_ask)} peer(s) for their peer lists...",
                )

                for peer_link in peers_to_ask:
                    self._send_message(peer_link, Message.peers_request())

                # Sleep for a while before the next cycle.
                time.sleep(300)  # e.g., run every 5 minutes

            except Exception as e:
                logger.error(
                    f"Error in peer management loop: {e}",
                    exc_info=True,
                )
                time.sleep(
                    60,
                )  # Wait a minute before retrying if an error occurs

    @classmethod
    def start_node(
        cls,
        host: str,
        port: int,
        bootstrap_peer: str | None,
    ) -> AxiomNode:
        """Create and initialize a complete AxiomNode.

        This is the preferred way to instantiate the node.
        """
        # 1. Use the parent's factory to create the low-level P2P components.
        p2p_instance = P2PBaseNode.start(ip_address=host, port=port)

        # 2. Create an instance of our AxiomNode, passing the bootstrap flag.
        axiom_instance = cls(
            host=p2p_instance.ip_address,
            port=p2p_instance.port,
            bootstrap_peer=bootstrap_peer,
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
fact_indexer: FactIndexer


@app.route("/chat", methods=["POST"])
def handle_chat_query() -> Response | tuple[Response, int]:
    """Handle natural language queries from the client.

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
    """Handle status request."""
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
    if node_instance is not None:
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
    """Handle merkle proof request."""
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
        except (ValueError, IndexError) as exc:
            logger.error(f"Error generating Merkle proof: {exc}")
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
    """Handle anonymous query request."""
    return jsonify({"error": "Anonymous query not implemented in V4"}), 501


@app.route("/dao/proposals", methods=["GET"])
def handle_get_proposals() -> tuple[Response, int]:
    """Handle dao proposals request."""
    return jsonify({"error": "DAO not implemented in V4"}), 501


@app.route("/dao/submit_proposal", methods=["POST"])
def handle_submit_proposal() -> Response | tuple[Response, int]:
    """Handle submit proposal request."""
    return jsonify({"error": "DAO not implemented in V4"}), 501


@app.route("/dao/submit_vote", methods=["POST"])
def handle_submit_vote() -> Response | tuple[Response, int]:
    """Handle submit vote request."""
    return jsonify({"error": "DAO not implemented in V4"}), 501


@app.route("/verify_fact", methods=["POST"])
def handle_verify_fact() -> Response | tuple[Response, int]:
    """Handle verify fact request."""
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
    """Handle get fact content request."""
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
    """Handle running an Axiom Node from the command line."""
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

        node_instance.get_chain_callback = node_instance._get_chain_for_peer

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
    except Exception as exc:
        logger.critical(
            f"A critical error occurred during node startup: {exc}",
            exc_info=True,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
