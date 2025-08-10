# Axiom - p2p.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
# --- V2.1: HARDENED SYNC LOGIC ---

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

import requests

from axiom_server.ledger import (
    Fact,
    SerializedFact,
    SessionMaker,
    Source,
)

if TYPE_CHECKING:
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
) -> tuple[str, list[Fact]]:
    """Synchronizes the local ledger with a peer's ledger.
    This version correctly handles database integrity errors during sync.
    """
    logging.info(f"attempting to sync with peer: {peer_url}")

    try:
        with SessionMaker() as session:
            # Step 1: Get the peer's list of all fact hashes
            response = requests.get(f"{peer_url}/get_fact_hashes", timeout=10)
            response.raise_for_status()
            peer_fact_hashes: set[str] = set(
                response.json().get("fact_hashes", []),
            )

            # Step 2: Get the local list of all fact hashes
            local_fact_hashes: set[str] = set(
                fact.hash for fact in session.query(Fact).all()
            )

            # Step 3: Determine which facts are missing locally
            missing_fact_hashes: list[str] = list(
                peer_fact_hashes - local_fact_hashes,
            )

            if not missing_fact_hashes:
                logging.info(f"ledger is already up-to-date with {peer_url}.")
                return "SUCCESS_UP_TO_DATE", []

            # Step 4: Request the full data for only the missing facts
            logging.info(
                f"found {len(missing_fact_hashes)} new facts to download from {peer_url}.",
            )

            response = requests.post(
                f"{peer_url}/get_facts_by_hash",
                json={"fact_hashes": missing_fact_hashes},
                timeout=30,
            )

            response.raise_for_status()

            new_fact_models: list[SerializedFact] = [
                SerializedFact(**fact_data)
                for fact_data in response.json().get("facts", [])
            ]

            # Step 5: Insert the new facts into the local ledger
            facts_added_count: int = 0
            new_facts: list[Fact] = []

            for model in new_fact_models:
                fact = Fact.from_model(model)
                session.add(fact)

                for domain in model.sources:
                    if (
                        source := session.query(Source)
                        .filter(Source.domain == domain)
                        .one_or_none()
                    ) is not None:
                        fact.sources.append(source)

                    else:
                        source = Source(domain=domain)
                        session.add(source)
                        fact.sources.append(source)

            session.commit()

            if facts_added_count > 0:
                return "SUCCESS_NEW_FACTS", new_facts

            return "SUCCESS_UP_TO_DATE", []

    except requests.exceptions.RequestException as e:
        logging.exception(
            f"FAILED to connect or communicate with peer {peer_url}. Error: {e}",
        )
        return "CONNECTION_FAILED", []
    except Exception as e:
        logging.exception(
            f"an unexpected error occurred during sync with {peer_url}. Error: {e}",
        )
        return "SYNC_ERROR", []
