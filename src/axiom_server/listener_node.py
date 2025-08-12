# Axiom - listener_node.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
"""The entry point for a lightweight Axiom Listener Node."""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from typing import Any

import requests
from flask import Flask, Response, jsonify, request

from axiom_server import merkle
from axiom_server.lite_ledger import BlockHeader, LiteLedger, SessionMaker

# --- Listener-Specific Configuration ---
logger = logging.getLogger("axiom-listener")
stdout_handler = logging.StreamHandler(stream=sys.stdout)
formatter = logging.Formatter(
    "[%(name)s] %(asctime)s | %(levelname)s | %(filename)s:%(lineno)s >>> %(message)s",
)
stdout_handler.setFormatter(formatter)
logger.addHandler(stdout_handler)
logger.setLevel(logging.INFO)
logger.propagate = False


class ListenerNode:
    """A lightweight Axiom node for verifying facts, not creating them."""

    def __init__(self, sealer_url: str):
        """Initialize the Listener Node.

        Args:
            sealer_url: The URL of the trusted Sealer node to sync with.

        """
        self.sealer_url = sealer_url
        self.lite_ledger = LiteLedger()
        logger.info(
            f"Listener initialized. Trusting Sealer at: {self.sealer_url}",
        )

    def _background_sync(self) -> None:
        """Run the main loop for syncing headers from a Sealer node."""
        while True:
            try:
                logger.info("Starting header sync cycle...")
                latest_header = self.lite_ledger.get_latest_header()
                since_height = latest_header.height if latest_header else -1

                # 1. Ask the Sealer for all new blocks since our last sync.
                sealer_endpoint = (
                    f"{self.sealer_url}/get_blocks?since={since_height}"
                )
                response = requests.get(sealer_endpoint, timeout=10)
                response.raise_for_status()
                new_blocks: list[dict[str, Any]] = response.json().get(
                    "blocks",
                    [],
                )

                if not new_blocks:
                    logger.info("Ledger is up-to-date. No new headers found.")
                else:
                    logger.info(
                        f"Found {len(new_blocks)} new block(s) to sync.",
                    )
                    for block_data in new_blocks:
                        # 2. Add each new header to our local Lite Ledger.
                        # The add_header function automatically validates chain integrity.
                        self.lite_ledger.add_header(block_data)

                logger.info("Header sync cycle finished.")

            except requests.RequestException as e:
                logger.warning(f"Could not connect to Sealer for sync: {e}")
            except Exception as e:
                logger.exception(f"An error occurred during header sync: {e}")

            # Wait for the next sync cycle.
            time.sleep(300)  # Sync every 5 minutes.

    def start_background_tasks(self) -> None:
        """Create a thread to run the header sync in the background."""
        background_thread = threading.Thread(
            target=self._background_sync,
            daemon=True,
        )
        background_thread.start()


# --- Flask API for the Listener Node ---
app = Flask(__name__)
listener_instance: ListenerNode


@app.route("/verify_fact_by_hash", methods=["GET"])
def handle_verify_fact() -> Response | tuple[Response, int]:
    """Verify a fact's inclusion in the ledger using a Merkle Proof."""
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

    # 1. Check our local, trusted Lite Ledger for the block header.
    with SessionMaker() as session:
        header = (
            session.query(BlockHeader)
            .filter(BlockHeader.height == block_height)
            .one_or_none()
        )

    # --- THE FIX: A more robust check for stale headers ---
    if not header:
        return jsonify(
            {
                "verified": False,
                "reason": f"Block height {block_height} not found in local Lite Ledger. The Listener may be syncing. Please try again in a moment.",
            },
        ), 200  # Return 200 OK, as this is a state, not an error.

    trusted_merkle_root = header.merkle_root

    # 2. Ask the Sealer for the proof.
    try:
        sealer_endpoint = f"{listener_instance.sealer_url}/get_merkle_proof?fact_hash={fact_hash}&block_height={block_height}"
        response = requests.get(sealer_endpoint, timeout=10)
        response.raise_for_status()
        proof_data = response.json()
    except requests.RequestException as e:
        return jsonify({"error": f"Failed to get proof from Sealer: {e}"}), 502

    # 3. Security validation:
    # First, verify the Sealer isn't lying about the Merkle Root for this block.
    if proof_data.get("merkle_root") != trusted_merkle_root:
        return jsonify(
            {
                "verified": False,
                "reason": "Merkle Root mismatch! Sealer provided an invalid proof.",
            },
        ), 200

    # Second, use our own Merkle toolkit to verify the proof is mathematically valid.
    is_valid = merkle.MerkleTree.verify_proof(
        proof=proof_data.get("proof", []),
        leaf_data=fact_hash,
        root=bytes.fromhex(trusted_merkle_root),
    )

    if is_valid:
        return jsonify(
            {
                "verified": True,
                "message": "Fact is confirmed to be in the ledger.",
            },
        ), 200
    return jsonify(
        {"verified": False, "reason": "Merkle proof verification failed."},
    ), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    sealer_url = os.environ.get("SEALER_URL")
    if not sealer_url:
        logger.error(
            "FATAL: SEALER_URL environment variable is not set. Cannot start Listener.",
        )
        sys.exit(1)

    listener_instance = ListenerNode(sealer_url=sealer_url)
    listener_instance.start_background_tasks()
    app.run(host="127.0.0.1", port=port, debug=False)
