"""Node - Implementation of a single, P2P-enabled node of the Axiom fact network."""

from __future__ import annotations

# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
import argparse
import hashlib
import json
import logging
import sys
import threading
import time
from datetime import datetime
from urllib.parse import urlparse

import requests
from flask import Flask, Response, jsonify, request
from flask_cors import CORS

from axiom_server import (
    crucible,
    discovery_rss,
    merkle,
    synthesizer,
    verification_engine,
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
    Validator,
    create_genesis_block,
    get_latest_block,
    initialize_database,
)
from axiom_server.p2p.constants import (
    BOOTSTRAP_IP_ADDR,
    BOOTSTRAP_PORT,
)
from axiom_server.p2p.node import (
    ApplicationData,
    MessageType,
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

API_PORT = 0
CORROBORATION_THRESHOLD = 2
SECONDS_PER_SLOT = 12
VOTING_THRESHOLD = 0.67
MAX_SEALERS_PER_REGION = 20

# This lock ensures only one thread can access the database at a time.
db_lock = threading.Lock()

# This lock ensures only one thread can read from or write to the fact indexer at a time.
fact_indexer_lock = threading.Lock()


# --- NEW: We create a single class that combines Axiom logic and P2P networking ---
class AxiomNode(P2PBaseNode):
    """A class representing a single Axiom node, inheriting P2P capabilities."""

    def _get_geo_region(self) -> str:
        """Determines the node's geographic region based on its public IP."""
        try:
            response = requests.get("http://ip-api.com/json/", timeout=5)
            response.raise_for_status()
            data = response.json()
            region = data.get("continent", "Unknown")
            logger.info(f"Node's geographic region determined as: {region}")
            return region
        except requests.RequestException as e:
            logger.warning(
                f"Could not determine geographic region, defaulting to 'Unknown'. Error: {e}",
            )
            return "Unknown"

    def __init__(
        self,
        host: str,
        port: int,
        bootstrap_peer: str | None,
    ) -> None:
        """Initialize both the P2P layer and the Axiom logic layer."""
        logger.info(f"Initializing Axiom Node on {host}:{port}")
        temp_p2p = P2PBaseNode.start(ip_address=host, port=port)
        super().__init__(
            ip_address=temp_p2p.ip_address,
            port=temp_p2p.port,
            serialized_port=temp_p2p.serialized_port,
            private_key=temp_p2p.private_key,
            public_key=temp_p2p.public_key,
            serialized_public_key=temp_p2p.serialized_public_key,
            peer_links=temp_p2p.peer_links,
            server_socket=temp_p2p.server_socket,
        )

        self.peers_lock = threading.Lock()
        self.region = self._get_geo_region()
        self.is_validator = False
        self.is_syncing = True
        self.known_network_height = 0
        self.pending_attestations: dict[str, dict] = {}
        self.attestation_lock = threading.Lock()
        self.active_proposals: dict[int, Proposal] = {}

        initialize_database(ENGINE)
        with SessionMaker() as session:
            create_genesis_block(session)
            validator_record = session.get(
                Validator,
                self.serialized_public_key.hex(),
            )
            if validator_record and validator_record.is_active:
                self.is_validator = True
                logger.info("This node is already an active validator.")

        if bootstrap_peer:
            parsed_url = urlparse(bootstrap_peer)
            bootstrap_host = parsed_url.hostname or BOOTSTRAP_IP_ADDR
            bootstrap_port = parsed_url.port or BOOTSTRAP_PORT
            threading.Thread(
                target=self.bootstrap,
                args=(bootstrap_host, bootstrap_port),
                daemon=True,
            ).start()

    def broadcast_application_message(self, message: str) -> None:
        """Sends an application message to all connected peers in a thread-safe manner.
        """
        # A better pattern: acquire lock, copy the list, release lock.
        # This prevents holding the lock during slow network I/O.
        with self.peers_lock:
            # We must iterate over a copy, as the original list can be modified
            # by the main network loop while we are sending.
            peers_to_send_to = list(self.iter_links())

        # Now, iterate over the safe copy without holding the lock.
        for link in peers_to_send_to:
            payload = {
                "type": json.loads(message).get("type", "unknown"),
                "data": json.loads(message).get("data", {}),
            }
            # The actual sending is still done by the specific method
            self._send_specific_application_message(link, payload)

    def _handle_application_message(
        self,
        _link: PeerLink,
        content: ApplicationData,
    ) -> None:
        try:
            message = json.loads(content.data)
            msg_type = message.get("type")
            if msg_type == "block_proposal":
                self._handle_block_proposal(message["data"])
            elif msg_type == "attestation":
                self._handle_attestation(message["data"])
            elif msg_type == "get_latest_block_request":
                self._handle_latest_block_request(_link)
            elif msg_type == "get_latest_block_response":
                self._handle_latest_block_response(message["data"])
        except Exception as exc:
            background_thread_logger.error(
                f"Error processing peer message: {exc}",
                exc_info=True,
            )

    def _get_proposer_for_slot(
        self,
        session: Session,
        slot: int,
    ) -> str | None:
        all_validators = (
            session.query(Validator).filter(Validator.is_active == True).all()
        )
        if not all_validators:
            return None

        active_sealers = []
        regions: dict[str, list] = {}
        for v in all_validators:
            if v.region not in regions:
                regions[v.region] = []
            regions[v.region].append(v)

        for region_name, validators_in_region in regions.items():

            def get_combined_score(validator):
                total_stake = validator.stake_amount + validator.rewards
                return total_stake * validator.reputation_score

            validators_in_region.sort(key=get_combined_score, reverse=True)
            sealers_for_this_region = validators_in_region[
                :MAX_SEALERS_PER_REGION
            ]
            active_sealers.extend(sealers_for_this_region)

        if not active_sealers:
            return None

        weighted_sealers = []
        for sealer in active_sealers:
            total_stake = sealer.stake_amount + sealer.rewards
            combined_score = int(
                total_stake * sealer.reputation_score * 1_000_000,
            )
            weighted_sealers.extend([sealer.public_key] * combined_score)

        if not weighted_sealers:
            return None

        seed = str(slot).encode()
        h = hashlib.sha256(seed).hexdigest()
        idx = int(h, 16) % len(weighted_sealers)
        return weighted_sealers[idx]

    def _handle_block_proposal(self, proposal_data: dict) -> None:
        if not self.is_validator:
            return

        block_data = proposal_data["block"]
        proposer_pubkey = block_data["proposer_pubkey"]

        # This database block is critical for thread safety
        with db_lock, SessionMaker() as session:
            current_slot = int(block_data["timestamp"] / SECONDS_PER_SLOT)
            expected_proposer = self._get_proposer_for_slot(
                session,
                current_slot,
            )
            if proposer_pubkey != expected_proposer:
                background_thread_logger.warning(
                    "Received block from wrong proposer.",
                )
                return

            latest_block = get_latest_block(session)
            if (
                not latest_block
                or block_data["height"] != latest_block.height + 1
            ):
                background_thread_logger.warning(
                    "Received block with invalid height.",
                )
                return

            block_hash = block_data["hash"]
            attestation = {
                "type": "attestation",
                "data": {
                    "block_hash": block_hash,
                    "voter_pubkey": self.serialized_public_key.hex(),
                },
            }
            self.broadcast_application_message(json.dumps(attestation))
            background_thread_logger.info(
                f"Attested to block {block_hash[:8]}",
            )

    def _handle_attestation(self, attestation_data: dict) -> None:
        block_hash = attestation_data["block_hash"]
        voter_pubkey = attestation_data["voter_pubkey"]

        with self.attestation_lock, db_lock, SessionMaker() as session:
            if block_hash not in self.pending_attestations:
                self.pending_attestations[block_hash] = {"votes": {}}
            voter = session.get(Validator, voter_pubkey)
            if voter and voter.is_active:
                self.pending_attestations[block_hash]["votes"][
                    voter.public_key
                ] = voter.stake_amount
                background_thread_logger.info(
                    f"Received vote for block {block_hash[:8]} from {voter_pubkey[:8]}",
                )
            else:
                return
            total_stake = sum(
                v.stake_amount
                for v in session.query(Validator)
                .filter(Validator.is_active == True)
                .all()
            )
            stake_for_block = sum(
                self.pending_attestations[block_hash]["votes"].values(),
            )
            if (
                total_stake > 0
                and (stake_for_block / total_stake) >= VOTING_THRESHOLD
            ):
                background_thread_logger.info(
                    f"Block {block_hash[:8]} has reached threshold and is FINALIZED.",
                )
                del self.pending_attestations[block_hash]

    def _send_specific_application_message(
        self, link: PeerLink, payload: dict,
    ):
        """Formats and sends an application-specific message to a single peer.
        This is the definitive, low-level implementation.
        """
        # --- START MODIFICATION ---
        # Defensive check: Ensure the link still has an active socket before using it.
        if not hasattr(link, "sock") or not link.sock:
            # This can happen in a race condition where the peer disconnected
            # just before this message was sent. We can safely ignore it.
            return

        try:
            # 1. Package the data correctly for the P2P protocol
            app_data = ApplicationData(
                content_type="application/json", data=json.dumps(payload),
            )

            # 2. Manually construct the full message header and body
            header = MessageType.APPLICATION.value.to_bytes(1, "big")
            body = app_data.model_dump_json().encode("utf-8")
            message_to_send = header + body

            # 3. Send the raw bytes DIRECTLY to the peer's socket.
            link.sock.sendall(message_to_send)

        except OSError as e:
            # This handles cases where the socket was closed between our check
            # and the sendall() call (e.g., "Broken pipe").
            background_thread_logger.warning(
                f"Could not send to {link.fmt_addr()}, socket error: {e}",
            )
            # You might want to trigger a cleanup of this peer link here.
            link.close()  # Assuming the PeerLink object has a close() method.

        except Exception as e:
            background_thread_logger.error(
                f"FATAL: Could not send application message to {link.fmt_addr()}: {e}",
                exc_info=True,
            )

    def _discovery_loop(self) -> None:
        """A slow, periodic loop for discovering, ingesting, and synthesizing new facts."""
        background_thread_logger.info("Starting autonomous discovery loop.")
        time.sleep(20)

        while True:
            background_thread_logger.info(
                "Discovery cycle started: seeking new information.",
            )
            try:
                content_list = (
                    discovery_rss.get_content_from_prioritized_feed()
                )
                if not content_list:
                    background_thread_logger.info(
                        "Discovery cycle: No new content found from feeds.",
                    )
                else:
                    with db_lock, SessionMaker() as session:
                        newly_ingested_facts = []
                        for item in content_list:
                            domain = urlparse(item["source_url"]).netloc
                            source = (
                                session.query(Source)
                                .filter(Source.domain == domain)
                                .one_or_none()
                            )
                            if not source:
                                source = Source(domain=domain)
                                session.add(source)

                            new_fact_objects = (
                                crucible.extract_facts_from_text(
                                    item["content"],
                                )
                            )
                            ingested_this_item = []
                            for fact_obj in new_fact_objects:
                                if (
                                    not session.query(Fact)
                                    .filter(Fact.content == fact_obj.content)
                                    .first()
                                ):
                                    fact_obj.sources.append(source)
                                    session.add(fact_obj)
                                    ingested_this_item.append(fact_obj)

                            if ingested_this_item:
                                session.flush()
                                newly_ingested_facts.extend(ingested_this_item)
                                background_thread_logger.info(
                                    f"Ingested {len(ingested_this_item)} new facts from {domain}.",
                                )

                        if newly_ingested_facts:
                            background_thread_logger.info(
                                f"Synthesizing {len(newly_ingested_facts)} new facts into the knowledge graph...",
                            )
                            synthesizer.link_related_facts(
                                session,
                                newly_ingested_facts,
                            )

                        session.commit()
            except Exception as exc:
                background_thread_logger.error(
                    f"Error during discovery cycle: {exc}",
                    exc_info=True,
                )

            # --- Step 4: Time-Based Stake ---
            # The status log is now GONE from here. We only award the time-based stake.
            with db_lock, SessionMaker() as session:
                if self.is_validator:
                    validator = session.get(
                        Validator,
                        self.serialized_public_key.hex(),
                    )
                    if validator:
                        validator.rewards += 5
                        background_thread_logger.info(
                            "Awarded 5 time-based stake for an hour of uptime.",
                        )
                        session.commit()

            background_thread_logger.info(
                "Discovery cycle finished. Sleeping for 1 hour.",
            )
            time.sleep(3600)

    def _background_work_loop(self) -> None:
        """A time-slot based loop for proposing and finalizing blocks."""
        background_thread_logger.info(
            "Starting Proof-of-Stake consensus cycle.",
        )
        while True:
            current_time = time.time()
            current_slot = int(current_time / SECONDS_PER_SLOT)

            proposer_pubkey = None
            with db_lock, SessionMaker() as session:
                proposer_pubkey = self._get_proposer_for_slot(
                    session,
                    current_slot,
                )

            if (
                self.is_validator
                and not self.is_syncing
                and self.serialized_public_key.hex() == proposer_pubkey
            ):
                background_thread_logger.info(
                    f"It is our turn to propose a block for slot {current_slot}.",
                )
                self._propose_block()

            next_slot_time = (current_slot + 1) * SECONDS_PER_SLOT
            sleep_duration = max(0, next_slot_time - time.time())
            time.sleep(sleep_duration)

    def _request_sync_with_peers(self):
        """Broadcasts a request to get the latest block from all known peers."""
        message = {"type": "get_latest_block_request"}
        self.broadcast_application_message(json.dumps(message))
        background_thread_logger.info(
            "Requesting synchronization with network...",
        )

    def _handle_latest_block_request(self, link: PeerLink):
        """Handles a peer's request for our latest block information."""
        with db_lock, SessionMaker() as session:
            latest_block = get_latest_block(session)
            if latest_block:
                response_payload = {
                    "type": "get_latest_block_response",
                    "data": {
                        "height": latest_block.height,
                        "hash": latest_block.hash,
                        "api_url": f"http://{self.ip_address}:{API_PORT}",
                    },
                }

                # Call our new, reliable, self-contained method
                self._send_specific_application_message(link, response_payload)

    def _handle_latest_block_response(self, response_data: dict):
        """Handles a peer's response containing their latest block info."""
        peer_height = response_data.get("height", -1)

        # --- ADD THIS BLOCK ---
        # Update our knowledge of the network's max height
        if peer_height > self.known_network_height:
            self.known_network_height = peer_height
        # --- END ADDITION ---

        if not self.is_syncing:
            return  # We are already synced.
        peer_api_url = response_data.get("api_url")

        with db_lock, SessionMaker() as session:
            my_latest_block = get_latest_block(session)
            my_height = my_latest_block.height if my_latest_block else -1

            if peer_height > my_height:
                background_thread_logger.info(
                    f"Peer is at height {peer_height}, we are at {my_height}. Starting download...",
                )
                # Use the peer's API to get the missing blocks
                try:
                    # In a real system, you'd download in batches. For here, one go is fine.
                    res = requests.get(
                        f"{peer_api_url}/get_blocks?since={my_height}",
                        timeout=30,
                    )
                    res.raise_for_status()
                    blocks_to_add = res.json().get("blocks", [])

                    for block_data in sorted(
                        blocks_to_add, key=lambda b: b["height"],
                    ):
                        # We need a function to add peer blocks. Let's assume it exists in ledger.py
                        add_block_from_peer_data(session, block_data)

                    background_thread_logger.info(
                        f"Successfully downloaded and added {len(blocks_to_add)} blocks. Checking sync status again.",
                    )
                    # Re-check sync status
                    my_new_latest_block = get_latest_block(session)
                    if (
                        my_new_latest_block
                        and my_new_latest_block.height >= peer_height
                    ):
                        self.is_syncing = False
                        background_thread_logger.info(
                            "Synchronization complete! Node is now live.",
                        )

                except (requests.RequestException, ValueError, KeyError) as e:
                    background_thread_logger.error(
                        f"Error during block download: {e}",
                    )

    def _conclude_syncing(self):
        """Periodically checks if the node has caught up to the known network height.
        If so, it transitions to a live state. Otherwise, it stays in sync mode.
        """
        if not self.is_syncing:
            return  # Already live, do nothing.

        with db_lock, SessionMaker() as session:
            my_latest_block = get_latest_block(session)
            my_height = my_latest_block.height if my_latest_block else -1

            # The crucial check:
            if my_height >= self.known_network_height:
                background_thread_logger.info(
                    f"Sync complete. Local height {my_height} matches network height {self.known_network_height}. Going live.",
                )
                self.is_syncing = False
            else:
                # If we are still behind, we are not done syncing.
                # Request another update and schedule this check to run again.
                background_thread_logger.info(
                    f"Still syncing... Local height: {my_height}, Network height: {self.known_network_height}.",
                )
                self._request_sync_with_peers()
                threading.Timer(30.0, self._conclude_syncing).start()

    def _propose_block(self) -> None:
        """Gathers facts, creates a block, marks facts as processed, and broadcasts."""
        with db_lock, SessionMaker() as session:
            facts_to_include = (
                session.query(Fact)
                .filter(Fact.status == "ingested")
                .limit(50)
                .all()
            )
            if not facts_to_include:
                #  background_thread_logger.info("No new facts to propose.")
                return

            fact_hashes = sorted([f.hash for f in facts_to_include])

            latest_block = get_latest_block(session)
            if not latest_block:
                return

            new_block = Block(
                height=latest_block.height + 1,
                previous_hash=latest_block.hash,
                fact_hashes=json.dumps(fact_hashes),
                timestamp=time.time(),
                proposer_pubkey=self.serialized_public_key.hex(),
            )
            new_block.seal_block()
            session.add(new_block)

            for fact in facts_to_include:
                fact.status = "logically_consistent"
            background_thread_logger.info(
                f"Marked {len(facts_to_include)} facts as logically_consistent.",
            )

            proposer_validator = session.get(
                Validator,
                self.serialized_public_key.hex(),
            )
            if proposer_validator:
                proposer_validator.reputation_score += 0.0000005
                background_thread_logger.info(
                    f"Awarded reputation for proposing. New score: {proposer_validator.reputation_score:.7f}",
                )

            session.commit()
            background_thread_logger.info(
                f"Proposed and added Block #{new_block.height} to local ledger.",
            )

            # --- ADD THIS FINAL BLOCK OF CODE ---
            if proposer_validator:
                background_thread_logger.info("--- NODE STATUS UPDATE ---")
                background_thread_logger.info(
                    f"  Initial Stake: {proposer_validator.stake_amount}",
                )
                background_thread_logger.info(
                    f"  Time-Based Stake: {proposer_validator.rewards}",
                )
                background_thread_logger.info(
                    f"  Reputation Score: {proposer_validator.reputation_score:.7f}",
                )
                background_thread_logger.info("--------------------------")
            # --- END OF ADDITION ---

            proposal = {
                "type": "block_proposal",
                "data": {"block": new_block.to_dict()},
            }
            self.broadcast_application_message(json.dumps(proposal))
            background_thread_logger.info(
                f"Broadcasted proposal for Block #{new_block.height}",
            )

    def start(self) -> None:
        """Start all background tasks and the main P2P loop."""
        consensus_thread = threading.Thread(
            target=self._background_work_loop,
            daemon=True,
            name="ConsensusThread",
        )
        consensus_thread.start()
        discovery_thread = threading.Thread(
            target=self._discovery_loop,
            daemon=True,
            name="DiscoveryThread",
        )
        discovery_thread.start()
        logger.info("Starting P2P network update loop...")
        while True:
            time.sleep(0.1)
            self.update()

    @classmethod
    def start_node(
        cls,
        host: str,
        port: int,
        bootstrap_peer: str | None,
    ) -> AxiomNode:
        """Create and initialize a complete AxiomNode."""
        p2p_instance = P2PBaseNode.start(ip_address=host, port=port)
        axiom_instance = cls(
            host=p2p_instance.ip_address,
            port=p2p_instance.port,
            bootstrap_peer=bootstrap_peer,
        )
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


@app.route("/submit", methods=["POST"])
def handle_submit_fact() -> Response | tuple[Response, int]:
    """Accepts a new fact from an external source and ingests it."""
    data = request.get_json()
    if not data or "content" not in data or "source" not in data:
        return jsonify(
            {"error": "Request must include 'content' and 'source' fields"},
        ), 400

    content = data["content"]
    source_domain = data["source"]

    with db_lock, SessionMaker() as session:
        # Check for duplicate content first
        existing_fact = (
            session.query(Fact).filter(Fact.content == content).first()
        )
        if existing_fact:
            return jsonify(
                {
                    "status": "duplicate",
                    "message": "This fact already exists in the ledger.",
                },
            ), 200

        # Find or create the source
        source = (
            session.query(Source)
            .filter(Source.domain == source_domain)
            .one_or_none()
        )
        if not source:
            source = Source(domain=source_domain)
            session.add(source)

        # Create the new fact with default 'ingested' status
        new_fact = Fact(content=content)
        new_fact.set_hash()
        new_fact.sources.append(source)
        session.add(new_fact)
        session.commit()

        # Optionally, you could add it to the FactIndexer here as well
        # with fact_indexer_lock:
        #     fact_indexer.add(new_fact)

        logger.info(
            f"Ingested new fact from source '{source_domain}': \"{content[:50]}...\"",
        )

    return jsonify(
        {"status": "success", "message": "Fact ingested successfully."},
    ), 201


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
                # "nonce": b.nonce, # <-- REMOVE THIS LINE
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


@app.route("/validator/stake", methods=["POST"])
def handle_stake() -> Response | tuple[Response, int]:
    """Allows a node to stake and become an active validator."""
    data = request.get_json()
    if (
        not data
        or "stake_amount" not in data
        or not isinstance(data["stake_amount"], int)
    ):
        return jsonify(
            {
                "error": "Missing or invalid 'stake_amount' (must be an integer)",
            },
        ), 400

    stake_amount = data["stake_amount"]
    if stake_amount <= 0:
        return jsonify({"error": "Stake amount must be positive"}), 400

    pubkey = node_instance.serialized_public_key.hex()
    region = node_instance.region

    with db_lock, SessionMaker() as session:
        validator = session.get(Validator, pubkey)
        if not validator:
            # NEW: Add the region when creating a new validator
            validator = Validator(
                public_key=pubkey,
                region=region,
                stake_amount=stake_amount,
                is_active=True,
            )
            session.add(validator)
            logger.info(
                f"New validator {pubkey[:10]}... from region '{region}' staked {stake_amount}.",
            )
        else:
            validator.stake_amount = stake_amount
            validator.is_active = True
            # Update region in case the node moved
            validator.region = region
            logger.info(
                f"Validator {pubkey[:10]}... updated stake to {stake_amount}.",
            )

        session.commit()
        node_instance.is_validator = True

    return jsonify(
        {
            "status": "success",
            "message": f"Node {pubkey[:10]} is now an active validator with {stake_amount} stake.",
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
    global node_instance, fact_indexer, API_PORT

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
    args = parser.parse_args()

    try:
        # 2. Create the AxiomNode instance, passing the arguments directly.
        node_instance = AxiomNode(
            host=args.host,
            port=args.p2p_port,
            bootstrap_peer=args.bootstrap_peer,
        )

        threading.Timer(5.0, node_instance._request_sync_with_peers).start()
        threading.Timer(30.0, node_instance._conclude_syncing).start()

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
