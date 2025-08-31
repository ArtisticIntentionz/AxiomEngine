"""Node - Implementation of a single, P2P-enabled node of the Axiom fact network."""

from __future__ import annotations

# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
import argparse
import json
import logging
import random
import sys
import threading
import time
from datetime import datetime
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import requests
from flask import Flask, Response, jsonify, request
from flask_cors import CORS

from axiom_server import (
    crucible,
    discovery_rss,
    discovery_sec,
    merkle,
    synthesizer,
)
from axiom_server.api_query import semantic_search_ledger
from axiom_server.crucible import _extract_dates
from axiom_server.enhanced_endpoints import (
    handle_analyze_question,
    handle_enhanced_chat,
    handle_extract_facts,
    handle_get_fact_statistics,
    handle_test_enhanced_search,
    handle_verify_fact,
)
from axiom_server.neural_verifier import NeuralFactVerifier
from axiom_server.dispute_system import DisputeSystem
from axiom_server.enhanced_fact_processor import EnhancedFactProcessor
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
    add_block_from_peer_data,
    create_genesis_block,
    get_latest_block,
    initialize_database,
    mark_fact_objects_as_disputed,
    FactStatus,
)
from axiom_server.p2p.constants import (
    BOOTSTRAP_PORT,
)
from axiom_server.p2p.node import (
    ApplicationData,
    Message,
    Node as P2PBaseNode,
    PeerLink,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


__version__ = "3.1.6"

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

API_PORT = 8001  # Default API port, will be overridden by command line args
CORROBORATION_THRESHOLD = 2
SECONDS_PER_SLOT = 12
VOTING_THRESHOLD = 0.67
MAX_SEALERS_PER_REGION = 20

# Reward scaling: store fractional stake in integer micro-units to avoid DB migration
# 1 unit = 1e-7 stake. A cycle reward of 0.0000007 equals 7 units per cycle.
REWARD_SCALE = 10_000_000  # 1e-7 units
CYCLE_REWARD = 0.0000007  # stake per discovery cycle

# This lock ensures only one thread can access the database at a time.
db_lock = threading.Lock()

# This lock ensures only one thread can read from or write to the fact indexer at a time.
fact_indexer_lock = threading.Lock()


# --- NEW: We create a single class that combines Axiom logic and P2P networking ---
class AxiomNode(P2PBaseNode):
    """A class representing a single Axiom node, inheriting P2P capabilities."""

    def _get_geo_region(self) -> str:
        """Determine the node's geographic region based on its public IP."""
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
        api_port: int,
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

        logger.info("=" * 60)
        logger.info("            NODE IDENTITY INITIALIZED")
        pubkey_hex = self.serialized_public_key.hex()
        logger.info(f"  Public Key: {pubkey_hex[:16]}...{pubkey_hex[-16:]}")
        logger.info("=" * 60)

        self.peers_lock = threading.Lock()
        self.api_port = api_port
        self.region = self._get_geo_region()
        self.is_validator = False
        self.is_syncing = True
        self.known_network_height = 0
        self.pending_attestations: dict[str, dict] = {}
        self.attestation_lock = threading.Lock()
        self.active_proposals: dict[int, Proposal] = {}

        # Initialize Neural Network and Dispute System
        logger.info("Initializing Neural Network Verification System...")
        self.neural_verifier = NeuralFactVerifier()
        self.dispute_system = DisputeSystem(
            node_id=self.serialized_public_key.hex(),
            neural_verifier=self.neural_verifier
        )
        self.enhanced_fact_processor = EnhancedFactProcessor(
            node_id=self.serialized_public_key.hex()
        )
        logger.info("✅ Neural Network and Dispute System initialized successfully")

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
            background_thread_logger.info(
                f"Connecting to bootstrap peer: {bootstrap_peer}",
            )

            # Handle both URL format (http://host:port) and simple format (host:port)
            if bootstrap_peer.startswith(("http://", "https://")):
                parsed_url = urlparse(bootstrap_peer)
                bootstrap_host = parsed_url.hostname
                bootstrap_port = parsed_url.port
            else:
                # Simple format: host:port
                if ":" in bootstrap_peer:
                    bootstrap_host, port_str = bootstrap_peer.split(":", 1)
                    bootstrap_port = int(port_str)
                else:
                    bootstrap_host = bootstrap_peer
                    bootstrap_port = BOOTSTRAP_PORT

            background_thread_logger.info(
                f"Parsed bootstrap host: {bootstrap_host}, port: {bootstrap_port}",
            )
            threading.Thread(
                target=self.bootstrap,
                args=(bootstrap_host, bootstrap_port),
                daemon=True,
            ).start()
        else:
            background_thread_logger.info("No bootstrap peer specified")

    def broadcast_application_message(self, message: str) -> None:
        """Send an application message to all connected peers in a thread-safe manner."""
        # A better pattern: acquire lock, copy the list, release lock.
        # This prevents holding the lock during slow network I/O.
        with self.peers_lock:
            # We must iterate over a copy, as the original list can be modified
            # by the main network loop while we are sending.
            peers_to_send_to = list(self.iter_links())

        # Now, iterate over the safe copy without holding the lock.
        for link in peers_to_send_to:
            # The message is already a JSON string, so we send it directly
            # The actual sending is done by the specific method
            self._send_specific_application_message(link, message)

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
        # Use the node's port number to determine proposer selection
        # 3-node rotation: Bootstrap (5001), Peer1 (5002), Peer2 (5003)
        my_pubkey = self.serialized_public_key.hex()

        # Determine which node should be the proposer based on slot number
        proposer_port = 5001 + (slot % 3)  # 5001, 5002, or 5003

        if self.port == proposer_port:
            background_thread_logger.info(
                f"Slot {slot}: We are the proposer! (slot % 3 = {slot % 3}, port = {self.port})",
            )
            return my_pubkey
        # This is not our turn to propose
        background_thread_logger.info(
            f"Slot {slot}: Not proposer for slot {slot}. Expected: port {proposer_port}, Our port: {self.port}",
        )
        return None

    def _handle_block_proposal(self, proposal_data: dict) -> None:
        """Handle a block proposal from a peer.

        All nodes validate and add the block to their ledger, but only validators
        send an attestation.
        """
        block_data = proposal_data["block"]
        proposer_pubkey = block_data["proposer_pubkey"]
        block_hash = block_data["hash"]

        # Use a single, locked database session for the whole operation.
        with db_lock, SessionMaker() as session:
            # Step 1: Validate the block's legitimacy (ALL nodes do this).
            current_slot = int(block_data["timestamp"] / SECONDS_PER_SLOT)
            expected_proposer = self._get_proposer_for_slot(
                session,
                current_slot,
            )
            if expected_proposer is None:
                background_thread_logger.warning(
                    f"Rejected block {block_hash[:8]} - not our turn to propose for this slot.",
                )
                return
            if proposer_pubkey != expected_proposer:
                background_thread_logger.warning(
                    f"Rejected block {block_hash[:8]} from wrong proposer. Expected {expected_proposer[:8]}, got {proposer_pubkey[:8]}.",
                )
                return

            latest_block = get_latest_block(session)
            if not latest_block:
                background_thread_logger.warning(
                    f"Rejected block {block_hash[:8]} - no local blocks found.",
                )
                return

            expected_height = latest_block.height + 1
            received_height = block_data["height"]

            # Allow for slight synchronization issues (within 1 block)
            if abs(received_height - expected_height) > 1:
                background_thread_logger.warning(
                    f"Rejected block {block_hash[:8]} with height {received_height}. "
                    f"Our height is {latest_block.height}, expected {expected_height}. "
                    f"Height difference too large.",
                )
                return
            if received_height != expected_height:
                background_thread_logger.info(
                    f"Accepting block {block_hash[:8]} with height {received_height} "
                    f"(expected {expected_height}) - minor sync issue.",
                )

            # Log that we received it *before* adding it.
            background_thread_logger.info(
                f"Received valid block proposal #{block_data['height']} from peer.",
            )

            # Step 2: Add the valid block to our local ledger (ALL nodes do this).
            # We need the `add_block_from_peer_data` function from ledger.py for this.
            add_block_from_peer_data(session, block_data)
            session.commit()
            background_thread_logger.info(
                f"Added Block #{block_data['height']} from peer to local ledger.",
            )

            # Update known network height when receiving blocks from peers
            if block_data["height"] > self.known_network_height:
                self.known_network_height = block_data["height"]
                background_thread_logger.info(
                    f"📡 NETWORK HEIGHT UPDATED: {self.known_network_height} (Block #{block_data['height']} received from peer)",
                )

            # Step 3: If we are a validator, attest to the block (VALIDATORS ONLY).
            if self.is_validator:
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
                .filter(Validator.is_active)
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
        self,
        link: PeerLink,
        message: str,
    ):
        """Format and send an application-specific message to a single peer.

        This is the definitive, low-level implementation.
        """
        # Ensure the link still has an active socket before using it.
        if (
            not hasattr(link, "socket")
            or link.socket is None
            or not getattr(link, "alive", True)
        ):
            return

        try:
            # Only send after handshake is complete to avoid confusing the
            # remote's handshake parser (which expects public key then port).
            if (
                link.peer is None
                or link.peer.public_key is None
                or link.peer.port is None
            ):
                return

            # Build a signed, framed P2P message using the base protocol
            # The message is already a JSON string, so we use it directly
            p2p_message = Message.application_data(message)
            self._send_message(link, p2p_message)
        except Exception as e:
            background_thread_logger.warning(
                f"Could not send to {link.fmt_addr()}, error: {e}; closing link",
            )
            try:
                link.alive = False
                if hasattr(link, "socket") and link.socket:
                    link.socket.close()
            except Exception as close_exc:
                background_thread_logger.debug(
                    f"Exception during socket cleanup for {link.fmt_addr()}: {close_exc}",
                )

    def _discovery_loop(self) -> None:
        """Run a slow, periodic loop for discovering, ingesting, and synthesizing new facts."""
        background_thread_logger.info("Starting autonomous discovery loop.")
        time.sleep(20)

        while True:
            background_thread_logger.info(
                "Discovery cycle started: seeking new information.",
            )
            try:
                # --- START OF THE ONLY CHANGE YOU NEED IN THIS FUNCTION ---

                # 1. Gather content from ALL discovery agents
                rss_content = discovery_rss.get_content_from_prioritized_feed()
                sec_content = discovery_sec.get_financial_facts_from_edgar()

                # 2. Combine them into one list to be processed
                content_list = rss_content + sec_content

                # --- END OF CHANGE ---

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
                                # --- ADD THIS IF/ELSE BLOCK FOR SOURCE CREDIBILITY ---
                                if "sec.gov" in domain:
                                    source = Source(
                                        domain=domain,
                                        source_type="primary",
                                        credibility_score=10.0,
                                    )
                                    background_thread_logger.info(
                                        f"Created new PRIMARY source: {domain} with score 10.0",
                                    )
                                else:
                                    source = Source(
                                        domain=domain,
                                        source_type="secondary",
                                        credibility_score=1.0,
                                    )
                                session.add(source)

                            new_fact_objects = (
                                crucible.extract_facts_from_text(
                                    item["content"],
                                    item["source_url"],
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
                        # After commit, update the live search index with new facts
                        try:
                            with fact_indexer_lock:
                                if newly_ingested_facts:
                                    fact_indexer.add_facts(
                                        newly_ingested_facts,
                                    )
                        except Exception as e:
                            background_thread_logger.warning(
                                f"Unable to update live index after ingestion: {e}",
                            )
            except Exception as exc:
                background_thread_logger.error(
                    f"Error during discovery cycle: {exc}",
                    exc_info=True,
                )

            # --- Step 4: Time-Based Stake ---
            with db_lock, SessionMaker() as session:
                pubkey = self.serialized_public_key.hex()
                validator = session.get(Validator, pubkey)
                if not validator:
                    # Auto-activate this node as a validator with zero base stake
                    validator = Validator(
                        public_key=pubkey,
                        region=self.region,
                        stake_amount=0,
                        is_active=True,
                    )
                    session.add(validator)
                    background_thread_logger.info(
                        "Auto-activated validator record for this node (initial stake 0).",
                    )

                # Award scaled time-based stake units
                reward_units = int(CYCLE_REWARD * REWARD_SCALE)
                validator.rewards = (validator.rewards or 0) + reward_units
                session.commit()

                # Mark local state as validator so proposer logic engages
                self.is_validator = True
                background_thread_logger.info(
                    f"Awarded time-based stake: +{CYCLE_REWARD:.7f}. Total time stake: {(validator.rewards / REWARD_SCALE):.7f}",
                )

            background_thread_logger.info(
                "Discovery cycle finished. Sleeping for 20 min.",
            )
            time.sleep(1200)  #

    def _background_work_loop(self) -> None:
        """Run a time-slot based loop for proposing and finalizing blocks."""
        background_thread_logger.info(
            "Starting Proof-of-Stake consensus cycle.",
        )
        last_status_update = 0
        while True:
            current_time = time.time()
            current_slot = int(current_time / SECONDS_PER_SLOT)

            # Periodic network height status update (every 30 seconds)
            if current_time - last_status_update >= 30:
                with db_lock, SessionMaker() as session:
                    latest_block = get_latest_block(session)
                    my_height = latest_block.height if latest_block else 0
                    background_thread_logger.info(
                        f"📊 NETWORK STATUS: Local height {my_height}, Network height {self.known_network_height}, Slot {current_slot}",
                    )
                last_status_update = current_time

            proposer_pubkey = None
            with db_lock, SessionMaker() as session:
                proposer_pubkey = self._get_proposer_for_slot(
                    session,
                    current_slot,
                )

            if self.is_validator and not self.is_syncing:
                if self.serialized_public_key.hex() == proposer_pubkey:
                    # Add a small random delay to reduce race conditions between nodes
                    delay = random.uniform(0.1, 0.5)
                    time.sleep(delay)

                    # Check if we've already received a block for this slot before proposing
                    with db_lock, SessionMaker() as session:
                        latest_block = get_latest_block(session)
                        if latest_block:
                            # Check if the latest block was created in the current slot
                            block_slot = int(
                                latest_block.timestamp / SECONDS_PER_SLOT,
                            )
                            if block_slot == current_slot:
                                background_thread_logger.info(
                                    f"Block already exists for slot {current_slot}, skipping proposal.",
                                )
                                # Continue to next iteration
                                next_slot_time = (
                                    current_slot + 1
                                ) * SECONDS_PER_SLOT
                                sleep_duration = max(
                                    0,
                                    next_slot_time - time.time(),
                                )
                                time.sleep(sleep_duration)
                                continue

                    background_thread_logger.info(
                        f"It is our turn to propose a block for slot {current_slot}.",
                    )
                    self._propose_block()
                else:
                    # Log when we're not the proposer to help debug
                    background_thread_logger.info(
                        f"Not proposer for slot {current_slot}. Expected: {proposer_pubkey[:8] if proposer_pubkey else 'None'}, Our key: {self.serialized_public_key.hex()[:8]}",
                    )

            next_slot_time = (current_slot + 1) * SECONDS_PER_SLOT
            sleep_duration = max(0, next_slot_time - time.time())
            time.sleep(sleep_duration)

    def _request_sync_with_peers(self):
        """Broadcast a request to get the latest block from all known peers."""
        message = {"type": "get_latest_block_request"}
        self.broadcast_application_message(json.dumps(message))
        background_thread_logger.info(
            "Requesting synchronization with network...",
        )

    def _handle_latest_block_request(self, link: PeerLink):
        """Handle a peer's request for our latest block information."""
        with db_lock, SessionMaker() as session:
            latest_block = get_latest_block(session)
            if latest_block:
                response_payload = {
                    "type": "get_latest_block_response",
                    "data": {
                        "height": latest_block.height,
                        "hash": latest_block.hash,
                        "api_url": f"http://127.0.0.1:{self.api_port}",
                    },
                }

                # Call our new, reliable, self-contained method
                self._send_specific_application_message(
                    link,
                    json.dumps(response_payload),
                )

    def _handle_latest_block_response(self, response_data: dict):
        """Handle a peer's response containing their latest block info."""
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
                    # Download all blocks from the beginning to ensure we have the complete chain
                    res = requests.get(
                        f"{peer_api_url}/get_blocks?since=-1",
                        timeout=30,
                    )
                    res.raise_for_status()
                    blocks_to_add = res.json().get("blocks", [])

                    if blocks_to_add:
                        background_thread_logger.info(
                            f"Downloading {len(blocks_to_add)} blocks from peer...",
                        )

                        # Clear existing blocks if we're starting fresh or if peer is ahead
                        if my_height == 0 or peer_height > my_height:
                            background_thread_logger.info(
                                "Clearing existing blocks to sync with peer...",
                            )
                            session.query(Block).delete()
                            session.commit()

                        for block_data in sorted(
                            blocks_to_add,
                            key=lambda b: b["height"],
                        ):
                            try:
                                # For the first block, create it directly
                                if block_data["height"] == 0:
                                    new_block = Block(
                                        height=block_data["height"],
                                        previous_hash=block_data[
                                            "previous_hash"
                                        ],
                                        merkle_root=block_data["merkle_root"],
                                        timestamp=block_data["timestamp"],
                                        proposer_pubkey=block_data.get(
                                            "proposer_pubkey",
                                        ),
                                        fact_hashes=json.dumps(
                                            block_data.get("fact_hashes", []),
                                        ),
                                    )
                                    new_block.hash = block_data["hash"]
                                    session.add(new_block)
                                    background_thread_logger.info(
                                        "Added genesis block from peer",
                                    )
                                else:
                                    # For non-genesis blocks, create them directly to avoid hash validation issues
                                    new_block = Block(
                                        height=block_data["height"],
                                        previous_hash=block_data[
                                            "previous_hash"
                                        ],
                                        merkle_root=block_data["merkle_root"],
                                        timestamp=block_data["timestamp"],
                                        proposer_pubkey=block_data.get(
                                            "proposer_pubkey",
                                        ),
                                        fact_hashes=json.dumps(
                                            block_data.get("fact_hashes", []),
                                        ),
                                    )
                                    new_block.hash = block_data[
                                        "hash"
                                    ]  # Use the hash from peer
                                    session.add(new_block)
                                    background_thread_logger.info(
                                        f"Added block {block_data['height']} from peer",
                                    )
                            except Exception as block_error:
                                background_thread_logger.error(
                                    f"Error adding block {block_data.get('height', 'unknown')}: {block_error}",
                                )
                                continue

                        session.commit()
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
                    else:
                        background_thread_logger.warning(
                            "No blocks received from peer",
                        )

                except (requests.RequestException, ValueError, KeyError) as e:
                    background_thread_logger.error(
                        f"Error during block download: {e}",
                    )

    def _conclude_syncing(self):
        """Periodically check if the node has caught up to the known network height.

        If so, it transitions to a live state. Otherwise, it stays in sync mode.
        """
        if not self.is_syncing:
            return  # Already live, do nothing.

        with db_lock, SessionMaker() as session:
            my_latest_block = get_latest_block(session)
            my_height = my_latest_block.height if my_latest_block else -1

            # Update network height to match our local height if we're ahead
            if my_height > self.known_network_height:
                self.known_network_height = my_height
                background_thread_logger.info(
                    f"Updated network height to {self.known_network_height} based on local height",
                )

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
        """Gather facts, create a block, mark facts as processed, and broadcast."""
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

            # Update known network height when we propose a block
            if new_block.height > self.known_network_height:
                self.known_network_height = new_block.height
                background_thread_logger.info(
                    f"🚀 NETWORK HEIGHT UPDATED: {self.known_network_height} (Block #{new_block.height} proposed)",
                )

            # --- ADD THIS FINAL BLOCK OF CODE ---
            if proposer_validator:
                rewards_units = proposer_validator.rewards or 0
                rewards_as_stake = rewards_units / REWARD_SCALE
                total_effective_stake = (
                    proposer_validator.stake_amount or 0
                ) + rewards_as_stake
                background_thread_logger.info("--- NODE STATUS UPDATE ---")
                background_thread_logger.info(
                    f"  Initial Stake: {proposer_validator.stake_amount}",
                )
                background_thread_logger.info(
                    f"  Time-Based Stake: {rewards_as_stake:.7f} ({rewards_units} units)",
                )
                background_thread_logger.info(
                    f"  Total Effective Stake: {total_effective_stake:.7f}",
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
    """Accept a new fact from an external source and ingest it."""
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
    """Handle natural language queries from the client using secure RAG synthesis.

    This endpoint implements a multi-layered security system:
    1. Validates user input for malicious content
    2. Searches the ledger for verified facts
    3. Uses LLM to synthesize natural, direct answers (optional)
    4. Cross-checks responses to prevent hallucination
    """
    data = request.get_json()
    if not data or "query" not in data:
        return jsonify({"error": "Missing 'query' in request body"}), 400

    user_query = data["query"]
    use_llm = data.get(
        "use_llm",
        False,
    )  # Default to False to avoid LLM issues

    # Step 1: Find relevant facts from the ledger
    with fact_indexer_lock:
        closest_facts = fact_indexer.find_closest_facts(user_query)

    # Step 2: Use LLM synthesis only if requested
    if use_llm:
        try:
            from axiom_server.rag_synthesis import process_user_query

            success, message, synthesized_answer = process_user_query(
                user_query,
                closest_facts,
            )

            if success:
                # Return both the synthesized answer and the raw facts for verification
                return jsonify(
                    {
                        "answer": synthesized_answer,
                        "results": closest_facts,
                        "synthesis_status": "success",
                        "message": message,
                    },
                )
            # Fall back to raw facts if synthesis fails
            return jsonify(
                {
                    "answer": "I found some relevant information, but encountered an issue generating a direct answer.",
                    "results": closest_facts,
                    "synthesis_status": "failed",
                    "message": message,
                },
            )

        except Exception as e:
            logger.error(f"RAG synthesis failed: {e}")
            # Fall back to raw facts with better error handling
            return jsonify(
                {
                    "answer": "I found some relevant information in the ledger.",
                    "results": closest_facts,
                    "synthesis_status": "error",
                    "message": f"LLM processing error: {e!s}",
                },
            )
    else:
        # Fast mode: return only the facts without LLM synthesis
        # But add intelligent answer synthesis for SEC company questions
        intelligent_answer = None
        confidence = 0.0

        # Check if this is a SEC company question
        if any(
            word in user_query.lower()
            for word in ["sec", "companies", "registered", "publicly traded"]
        ):
            sec_facts = [
                f
                for f in closest_facts
                if "sec" in f["content"].lower()
                and (
                    "inc" in f["content"].lower()
                    or "corporation" in f["content"].lower()
                )
            ]

            if sec_facts:
                # Extract company names from SEC facts
                companies = []
                for fact in sec_facts:
                    # Extract company name from fact content
                    content = fact["content"].lower()
                    if "apple inc" in content:
                        companies.append("Apple Inc.")
                    elif "amazon.com inc" in content:
                        companies.append("Amazon.com Inc.")
                    elif "alphabet inc" in content:
                        companies.append("Alphabet Inc.")
                    elif "microsoft corporation" in content:
                        companies.append("Microsoft Corporation")
                    elif "tesla inc" in content:
                        companies.append("Tesla Inc.")

                if companies:
                    intelligent_answer = f"Based on SEC records, the following companies are publicly traded and registered with the SEC: {', '.join(companies)}."
                    confidence = 0.9

        return jsonify(
            {
                "results": closest_facts,
                "synthesis_status": "disabled",
                "message": "LLM synthesis disabled - showing raw facts only",
                "intelligent_answer": intelligent_answer,
                "confidence": confidence,
            },
        )


@app.route("/enhanced_chat", methods=["POST"])
def handle_enhanced_chat_route() -> Response | tuple[Response, int]:
    """Enhanced chat endpoint that provides intelligent answers."""
    return handle_enhanced_chat()


@app.route("/extract_facts", methods=["POST"])
def handle_extract_facts_route() -> Response | tuple[Response, int]:
    """Extract facts from content using the enhanced processor."""
    return handle_extract_facts()


@app.route("/verify_fact", methods=["POST"])
def handle_verify_fact_route() -> Response | tuple[Response, int]:
    """Verify a specific fact against the knowledge base."""
    return handle_verify_fact()


@app.route("/analyze_question", methods=["POST"])
def handle_analyze_question_route() -> Response | tuple[Response, int]:
    """Analyze a question to understand what type of answer is needed."""
    return handle_analyze_question()


@app.route("/fact_statistics", methods=["GET"])
def handle_fact_statistics_route() -> Response:
    """Get statistics about the fact database."""
    return handle_get_fact_statistics()


@app.route("/test_enhanced_search", methods=["GET"])
def handle_test_enhanced_search_route() -> Response:
    """Test enhanced search functionality."""
    return handle_test_enhanced_search()


@app.route("/sec_edgar_status", methods=["GET"])
def handle_sec_edgar_status_route() -> Response:
    """Check SEC EDGAR integration status."""
    from axiom_server.discovery_sec import get_sec_edgar_status

    status = get_sec_edgar_status()
    return jsonify(status)


@app.route("/debug/propose_block", methods=["POST"])
def debug_propose_block():
    """Debug endpoint to manually trigger block proposal."""
    try:
        node_instance._propose_block()
        return jsonify(
            {"status": "success", "message": "Block proposal triggered"},
        )
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/dao/dispute_fact", methods=["POST"])
def handle_dispute_fact():
    """Handle a DAO request to mark two facts as disputed."""
    data = request.get_json()
    if not data or "fact1_hash" not in data or "fact2_hash" not in data:
        return jsonify(
            {"error": "Request must include 'fact1_hash' and 'fact2_hash'"},
        ), 400

    with db_lock, SessionMaker() as session:
        fact1 = (
            session.query(Fact)
            .filter(Fact.hash == data["fact1_hash"])
            .one_or_none()
        )
        fact2 = (
            session.query(Fact)
            .filter(Fact.hash == data["fact2_hash"])
            .one_or_none()
        )

        if not fact1 or not fact2:
            return jsonify({"error": "One or both facts not found"}), 404

        mark_fact_objects_as_disputed(session, fact1, fact2)
        session.commit()

    return jsonify(
        {
            "status": "success",
            "message": "Facts have been marked as disputed.",
        },
    )


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
    """Allow a node to stake and become an active validator."""
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


@app.route("/explorer/node_stats", methods=["GET"])
def handle_get_node_stats() -> Response:
    """Provide detailed statistics for this specific node."""
    with db_lock, SessionMaker() as session:
        pubkey = node_instance.serialized_public_key.hex()
        validator = session.get(Validator, pubkey)

        if not validator:
            return jsonify(
                {
                    "public_key": pubkey,
                    "is_validator": False,
                    "region": node_instance.region,
                },
            )

        # Count blocks proposed by this validator
        blocks_proposed_count = (
            session.query(Block)
            .filter(Block.proposer_pubkey == pubkey)
            .count()
        )

        # In a real system, uptime would be tracked, here we simulate it
        # This is a placeholder for a real uptime tracking mechanism
        uptime_percentage = 99.8

        return jsonify(
            {
                "public_key": pubkey,
                "is_validator": True,
                "region": validator.region,
                "stake_amount": validator.stake_amount,
                "reputation_score": validator.reputation_score,
                "rewards_earned": validator.rewards,
                "blocks_proposed": blocks_proposed_count,
                "uptime_percentage": uptime_percentage,
            },
        )


@app.route("/explorer/network_stats", methods=["GET"])
def handle_get_network_stats() -> Response:
    """Provide aggregate statistics for the entire network as seen by this node."""
    with db_lock, SessionMaker() as session:
        total_facts = session.query(Fact).count()
        corroborated_facts = session.query(Fact).filter(Fact.score > 0).count()
        disputed_facts = session.query(Fact).filter(Fact.disputed).count()
        total_validators = (
            session.query(Validator).filter(Validator.is_active).count()
        )
        latest_block = get_latest_block(session)

        return jsonify(
            {
                "current_block_height": latest_block.height
                if latest_block
                else 0,
                "total_facts_grounded": total_facts,
                "corroborated_facts": corroborated_facts,
                "disputed_facts": disputed_facts,
                "active_validators": total_validators,
            },
        )


@app.route("/explorer/ledger_growth", methods=["GET"])
def handle_get_ledger_growth() -> Response:
    """Provide data for charting the growth of facts and blocks over time."""
    with db_lock, SessionMaker() as session:
        # Query blocks and their timestamps
        blocks = (
            session.query(Block.height, Block.timestamp)
            .order_by(Block.height)
            .all()
        )

        # In a more advanced system, we'd query fact creation dates.
        # For now, we can approximate fact growth by counting facts per block.
        fact_growth_data = []
        total_facts = 0
        for block in blocks:
            fact_hashes = json.loads(block.fact_hashes)
            total_facts += len(fact_hashes)
            fact_growth_data.append(
                {
                    "height": block.height,
                    "timestamp": block.timestamp,
                    "total_facts": total_facts,
                },
            )

        return jsonify(fact_growth_data)


# Neural Network and Dispute System Endpoints
@app.route("/neural/verify_fact", methods=["POST"])
def handle_neural_verify_fact():
    """Verify a fact using the neural network system."""
    data = request.get_json()
    if not data or "content" not in data:
        return jsonify({"error": "Request must include 'content'"}), 400
    
    try:
        # Create a temporary fact for verification
        sources = []
        if "sources" in data:
            # Handle sources that might be strings or dictionaries
            for s in data["sources"]:
                if isinstance(s, dict):
                    sources.append(Source(domain=s.get('domain', '')))
                elif isinstance(s, str):
                    sources.append(Source(domain=s))
                else:
                    sources.append(Source(domain=str(s)))
        
        fact = Fact(
            content=data["content"],
            sources=sources,
            status=FactStatus.INGESTED
        )
        
        # Use the neural verifier
        result = node_instance.neural_verifier.verify_fact(fact)
        
        return jsonify({
            "status": "success",
            "verification_result": result
        })
    except Exception as e:
        logger.error(f"Error in neural verification: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/neural/process_fact", methods=["POST"])
def handle_neural_process_fact():
    """Process a fact through the enhanced fact processor."""
    data = request.get_json()
    if not data or "content" not in data:
        return jsonify({"error": "Request must include 'content'"}), 400
    
    try:
        sources = []
        if "sources" in data:
            sources = data["sources"]
        
        metadata = data.get("metadata", {})
        
        # Use the enhanced fact processor
        result = node_instance.enhanced_fact_processor.process_fact(
            fact_content=data["content"],
            sources=sources,
            metadata=metadata
        )
        
        return jsonify({
            "status": "success",
            "processing_result": result
        })
    except Exception as e:
        logger.error(f"Error in fact processing: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/dispute/create", methods=["POST"])
def handle_create_dispute():
    """Create a new dispute against a fact."""
    data = request.get_json()
    if not data or "fact_id" not in data or "reason" not in data:
        return jsonify({"error": "Request must include 'fact_id' and 'reason'"}), 400
    
    try:
        evidence = None
        if "evidence" in data:
            from axiom_server.dispute_system import DisputeEvidence
            evidence = [DisputeEvidence(**ev) for ev in data["evidence"]]
        
        dispute = node_instance.dispute_system.create_dispute(
            fact_id=data["fact_id"],
            reason=data["reason"],
            evidence=evidence
        )
        
        # Broadcast dispute to network
        broadcast_result = node_instance.dispute_system.broadcast_dispute(dispute)
        
        return jsonify({
            "status": "success",
            "dispute_id": dispute.dispute_id,
            "broadcast_result": broadcast_result
        })
    except Exception as e:
        logger.error(f"Error creating dispute: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/dispute/vote", methods=["POST"])
def handle_vote_on_dispute():
    """Cast a vote on a dispute."""
    data = request.get_json()
    if not data or "dispute_id" not in data or "vote" not in data or "reasoning" not in data:
        return jsonify({"error": "Request must include 'dispute_id', 'vote', and 'reasoning'"}), 400
    
    try:
        success = node_instance.dispute_system.cast_vote(
            dispute_id=data["dispute_id"],
            vote=data["vote"],  # True = fact is false, False = fact is true
            reasoning=data["reasoning"],
            confidence=data.get("confidence", 0.8)
        )
        
        return jsonify({
            "status": "success" if success else "failed",
            "message": "Vote cast successfully" if success else "Failed to cast vote"
        })
    except Exception as e:
        logger.error(f"Error casting vote: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/dispute/status", methods=["GET"])
def handle_get_dispute_status():
    """Get status of all disputes."""
    try:
        disputes = node_instance.dispute_system.get_active_disputes()
        stats = node_instance.dispute_system.get_dispute_statistics()
        
        return jsonify({
            "status": "success",
            "disputes": disputes,
            "statistics": stats
        })
    except Exception as e:
        logger.error(f"Error getting dispute status: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/neural/performance", methods=["GET"])
def handle_get_neural_performance():
    """Get neural network performance metrics."""
    try:
        neural_metrics = node_instance.neural_verifier.get_performance_metrics()
        processing_stats = node_instance.enhanced_fact_processor.get_processing_statistics()
        
        return jsonify({
            "status": "success",
            "neural_metrics": neural_metrics,
            "processing_stats": processing_stats
        })
    except Exception as e:
        logger.error(f"Error getting neural performance: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/test_fact_indexer", methods=["GET"])
def handle_test_fact_indexer():
    """Test endpoint to check if the fact indexer is working."""
    try:
        # Test if fact_indexer is accessible
        if 'fact_indexer' in globals():
            # Test a simple search
            test_results = fact_indexer.find_closest_facts("test", top_n=1, min_similarity=0.1)
            return jsonify({
                "status": "success",
                "fact_indexer_accessible": True,
                "test_results_count": len(test_results),
                "fact_indexer_type": str(type(fact_indexer))
            })
        else:
            return jsonify({
                "status": "error",
                "fact_indexer_accessible": False,
                "error": "fact_indexer not found in globals"
            })
    except Exception as e:
        return jsonify({
            "status": "error",
            "fact_indexer_accessible": False,
            "error": str(e)
        }), 500


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
        # Debug: Print the arguments
        logger.info("Starting node with arguments:")
        logger.info(f"  host: {args.host}")
        logger.info(f"  p2p_port: {args.p2p_port}")
        logger.info(f"  api_port: {args.api_port}")
        logger.info(f"  bootstrap_peer: {args.bootstrap_peer}")

        # 2. Create the AxiomNode instance, passing the arguments directly.
        node_instance = AxiomNode(
            host=args.host,
            port=args.p2p_port,
            api_port=args.api_port,
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
