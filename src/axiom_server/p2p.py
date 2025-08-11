"""P2P - Peer to peer fact sharing."""

from __future__ import annotations

# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
import json
import logging
import sys
from typing import TYPE_CHECKING, Any

import requests

from axiom_server.ledger import (
    Block,
    Fact,
    SerializedFact,
    Source,
    get_latest_block,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from axiom_server.node import AxiomNode


logger = logging.getLogger("p2p")
stdout_handler = logging.StreamHandler(stream=sys.stdout)
stdout_handler.setFormatter(
    logging.Formatter(
        "[%(name)s] %(asctime)s | %(levelname)s | %(filename)s:%(lineno)s >>> %(message)s",
    ),
)
logger.addHandler(stdout_handler)
logger.setLevel(logging.INFO)
logger.propagate = False


def sync_with_peer(
    node_instance: AxiomNode,
    peer_url: str,
    session: Session,
) -> tuple[str, int]:
    """Synchronize the local ledger with a peer's ledger.

    The V3.1 P2P sync protocol. It synchronizes and validates the entire blockchain,
    then fetches any missing facts contained within the new blocks.
    Returns a status string and the number of new blocks received.
    """
    logger.info(f"Attempting to sync blockchain with peer: {peer_url}")
    try:
        response = requests.get(f"{peer_url}/get_chain_height", timeout=10)
        response.raise_for_status()
        peer_height = response.json().get("height", -1)

        local_latest_block = get_latest_block(session)
        local_height = local_latest_block.height if local_latest_block else -1

        if peer_height <= local_height:
            logger.info(f"Local blockchain is up-to-date with {peer_url}.")
            return "SUCCESS_UP_TO_DATE", 0

        logger.info(
            f"Local chain ({local_height}) is behind peer ({peer_height}). Downloading blocks...",
        )
        response = requests.get(
            f"{peer_url}/get_blocks?since={local_height}",
            timeout=30,
        )
        response.raise_for_status()
        blocks_data: list[dict[str, Any]] = response.json().get("blocks", [])

        if not blocks_data:
            logger.warning(
                f"Peer {peer_url} reported a longer chain but sent no blocks.",
            )
            return "SYNC_ERROR", 0

        current_valid_block = local_latest_block
        all_missing_fact_hashes: set[str] = set()

        for block_data in blocks_data:
            new_block = Block(
                height=block_data["height"],
                previous_hash=block_data["previous_hash"],
                fact_hashes=json.dumps(block_data["fact_hashes"]),
                timestamp=block_data["timestamp"],
                nonce=block_data["nonce"],
            )

            if new_block.calculate_hash() != block_data["hash"]:
                logger.error(
                    f"VALIDATION FAILED! Peer {peer_url} provided a block with an invalid hash.",
                )
                return "SYNC_ERROR", 0

            if (
                current_valid_block
                and new_block.previous_hash != current_valid_block.hash
            ):
                logger.error(
                    f"VALIDATION FAILED! Peer {peer_url} provided a broken chain.",
                )
                return "SYNC_ERROR", 0

            session.add(new_block)
            current_valid_block = new_block
            all_missing_fact_hashes.update(block_data["fact_hashes"])

        local_fact_hashes: set[str] = {
            fact.hash for fact in session.query(Fact).with_entities(Fact.hash)
        }
        fact_hashes_to_request = list(
            all_missing_fact_hashes - local_fact_hashes,
        )

        if fact_hashes_to_request:
            logger.info(
                f"Requesting data for {len(fact_hashes_to_request)} new facts from peer...",
            )

            response = requests.post(
                f"{peer_url}/get_facts_by_hash",
                json={"fact_hashes": fact_hashes_to_request},
                timeout=30,
            )
            response.raise_for_status()

            new_facts_data = response.json().get("facts", [])

            for fact_data in new_facts_data:
                model = SerializedFact(**fact_data)
                fact = Fact.from_model(model)
                session.add(fact)
                for domain in model.sources:
                    source = session.query(Source).filter(
                        Source.domain == domain,
                    ).one_or_none() or Source(domain=domain)
                    if source not in fact.sources:
                        fact.sources.append(source)

        session.commit()
        logger.info(
            f"Successfully synced and validated {len(blocks_data)} new blocks from {peer_url}.",
        )
        return "SUCCESS_NEW_BLOCKS", len(blocks_data)

    except requests.exceptions.RequestException as e:
        logger.warning(
            f"Connection failed during sync with {peer_url}. Error: {e}",
        )
        return "CONNECTION_FAILED", 0
    except Exception as e:
        logger.exception(
            f"Unexpected error during sync with {peer_url}. Error: {e}",
        )
        return "SYNC_ERROR", 0
