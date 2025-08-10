# Axiom - p2p.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
# --- V3.1: BLOCKCHAIN-AWARE SYNCHRONIZATION PROTOCOL ---

import logging
import sys
import requests
import json
from sqlalchemy.orm import Session

# Import the new V3.1 ledger components
from axiom_server.ledger import Block, Fact, FactModel, Source, get_latest_block

# --- Professional Logging Setup (from contributor) ---
logger = logging.getLogger("p2p")
stdout_handler = logging.StreamHandler(stream=sys.stdout)
stdout_handler.setFormatter(
    logging.Formatter(
        "[%(name)s] %(asctime)s | %(levelname)s | %(filename)s:%(lineno)s >>> %(message)s"
    )
)
logger.addHandler(stdout_handler)
logger.setLevel(logging.INFO)
logger.propagate = False

def sync_with_peer(node_instance, peer_url: str, session: Session) -> tuple[str, int]:
    """
    The V3.1 P2P sync protocol. It synchronizes and validates the entire blockchain,
    then fetches any missing facts contained within the new blocks.
    """
    logger.info(f"Attempting to sync blockchain with peer: {peer_url}")
    try:
        # Step 1: Get the peer's chain height using our new API endpoint.
        response = requests.get(f"{peer_url}/get_chain_height", timeout=10)
        response.raise_for_status()
        peer_height = response.json().get('height', -1)

        local_latest_block = get_latest_block(session)
        local_height = local_latest_block.height if local_latest_block else -1

        if peer_height <= local_height:
            logger.info(f"Local blockchain is up-to-date with {peer_url}.")
            return "SUCCESS_UP_TO_DATE", 0

        # Step 2: Download the missing blocks from the peer.
        logger.info(f"Local chain ({local_height}) is behind peer ({peer_height}). Downloading blocks...")
        response = requests.get(f"{peer_url}/get_blocks?since={local_height}", timeout=30)
        response.raise_for_status()
        blocks_data: list[dict] = response.json().get('blocks', [])

        if not blocks_data:
            logger.warning(f"Peer {peer_url} reported a longer chain but sent no blocks.")
            return "SYNC_ERROR", 0

        # Step 3: Validate and add the new blocks to our local chain.
        current_valid_block = local_latest_block
        all_missing_fact_hashes: set[str] = set()

        for block_data in blocks_data:
            new_block = Block(
                height=block_data['height'],
                previous_hash=block_data['previous_hash'],
                fact_hashes=json.dumps(block_data['fact_hashes']),
                timestamp=block_data['timestamp'],
            )
            new_block.nonce = block_data['nonce']

            # THE CORE CONSENSUS RULE: Validate the cryptographic chain.
            if new_block.calculate_hash() != block_data['hash']:
                logger.error(f"VALIDATION FAILED! Peer {peer_url} provided a block with an invalid hash.")
                return "SYNC_ERROR", 0
            if new_block.previous_hash != current_valid_block.hash:
                logger.error(f"VALIDATION FAILED! Peer {peer_url} provided a broken chain.")
                return "SYNC_ERROR", 0

            session.add(new_block)
            current_valid_block = new_block
            
            # While we're here, collect all the fact hashes we'll need to download.
            for fact_hash in block_data['fact_hashes']:
                all_missing_fact_hashes.add(fact_hash)
        
        # Step 4: Download the actual fact data for all facts in the new blocks.
        local_fact_hashes: set[str] = {fact.hash for fact in session.query(Fact).all()}
        fact_hashes_to_request = list(all_missing_fact_hashes - local_fact_hashes)

        if fact_hashes_to_request:
            logger.info(f"Requesting data for {len(fact_hashes_to_request)} new facts from peer...")
            response = requests.post(f"{peer_url}/get_facts_by_hash", json={"fact_hashes": fact_hashes_to_request}, timeout=30)
            response.raise_for_status()
            
            new_facts_json = response.json().get("facts", "[]")
            new_facts_data = json.loads(new_facts_json)

            for fact_data in new_facts_data:
                model = FactModel(**fact_data)
                fact = Fact.from_model(model)
                session.add(fact)
                for domain in model.sources:
                    source = session.query(Source).filter(Source.domain == domain).one_or_none() or Source(domain=domain)
                    fact.sources.append(source)

        session.commit()
        logger.info(f"Successfully synced and validated {len(blocks_data)} new blocks from {peer_url}.")
        return "SUCCESS_NEW_BLOCKS", len(blocks_data)

    except requests.exceptions.RequestException as e:
        logger.exception(f"Connection failed during sync with {peer_url}. Error: {e}")
        return "CONNECTION_FAILED", 0
    except Exception as e:
        logger.exception(f"Unexpected error during sync with {peer_url}. Error: {e}")
        return "SYNC_ERROR", 0