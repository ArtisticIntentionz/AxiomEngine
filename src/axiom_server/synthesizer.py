"""Synthesizer - Compare facts."""

from __future__ import annotations

# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
import logging
import sys
from typing import TYPE_CHECKING

from axiom_server.ledger import (
    Fact,
    RelationshipType,
    insert_relationship_object,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger("synthesizer")
stdout_handler = logging.StreamHandler(stream=sys.stdout)
stdout_handler.setFormatter(
    logging.Formatter(
        "[%(name)s] %(asctime)s | %(levelname)s | %(filename)s:%(lineno)s >>> %(message)s",
    ),
)
logger.addHandler(stdout_handler)
logger.setLevel(logging.INFO)
logger.propagate = False


def link_related_facts(
    session: Session,
    new_facts_batch: list[Fact],
) -> None:
    """Compare a batch of new facts against the entire ledger to find and store relationships.

    Now a native citizen of the ORM, accepting a session object and
    operating on Fact objects directly. Leverages pre-computed
    semantics for massive performance gains.
    """
    logger.info("beginning Knowledge Graph linking...")
    if not new_facts_batch:
        logger.info("no new facts to link. Cycle complete.")
        return

    all_facts_in_ledger = session.query(Fact).all()

    links_found = 0
    for new_fact in new_facts_batch:
        new_semantics = new_fact.get_semantics()
        new_doc = new_semantics["doc"]
        new_entities = {ent.text.lower() for ent in new_doc.ents}

        for existing_fact in all_facts_in_ledger:
            if new_fact.id == existing_fact.id:
                continue

            existing_semantics = existing_fact.get_semantics()
            existing_doc = existing_semantics["doc"]
            existing_entities = {ent.text.lower() for ent in existing_doc.ents}

            shared_entities = new_entities.intersection(existing_entities)

            if shared_entities:
                relationship_score = len(shared_entities)
                insert_relationship_object(
                    session,
                    new_fact,
                    existing_fact,
                    relationship_score,
                    RelationshipType.CORRELATION,
                )
                links_found += 1

    session.commit()
    logger.info(
        f"linking complete. Found and stored {links_found} new relationships.",
    )
