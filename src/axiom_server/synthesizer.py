# Axiom - synthesizer.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
# --- V2.5: UNIFIED VERSION WITH COMMUNITY REFACTOR ---

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING, TypedDict

from axiom_server.ledger import get_all_facts_for_analysis, insert_relationship
from axiom_server.common import NLP_MODEL

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


logger = logging.getLogger("synthesizer")
stdout_handler = logging.StreamHandler(stream=sys.stdout)
stdout_handler.setFormatter(
    logging.Formatter(
        "[%(name)s] %(asctime)s | %(levelname)s | %(filename)s:%(lineno)s >>> %(message)s"
    )
)
logger.addHandler(stdout_handler)
logger.setLevel(logging.INFO)
logger.propagate = False


class Fact(TypedDict):
    fact_id: int
    fact_content: str


def link_related_facts(
    session: Session,
    new_facts_batch: list[Fact],
) -> None:
    """
    Compares a batch of new facts against the entire ledger to find and store relationships.
    """
    logger.info("beginning Knowledge Graph linking...")
    if not new_facts_batch:
        logger.info("no new facts to link. Cycle complete.")
        return

    all_facts_in_ledger = get_all_facts_for_analysis(session)

    links_found = 0
    for new_fact in new_facts_batch:
        new_doc = NLP_MODEL(new_fact['fact_content'])
        new_entities = {ent.text.lower() for ent in new_doc.ents}

        for existing_fact in all_facts_in_ledger:
            if new_fact['fact_id'] == existing_fact['fact_id']:
                continue

            existing_doc = NLP_MODEL(existing_fact['fact_content'])
            existing_entities = {ent.text.lower() for ent in existing_doc.ents}

            shared_entities = new_entities.intersection(existing_entities)

            if shared_entities:
                relationship_score = len(shared_entities)
                insert_relationship(
                    session,
                    new_fact['fact_id'],
                    existing_fact['fact_id'],
                    score=relationship_score,
                )
                links_found += 1

    logger.info(f"linking complete. Found and stored {links_found} new relationships.")
