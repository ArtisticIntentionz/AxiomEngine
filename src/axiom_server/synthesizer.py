# Axiom - synthesizer.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
# --- V3.1: ORM-NATIVE KNOWLEDGE GRAPH ENGINE ---

import logging
import sys
from sqlalchemy.orm import Session

# Import the new, advanced ORM classes and functions
from axiom_server.ledger import Fact, insert_relationship_object

# --- Professional Logging Setup (from contributor) ---
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


def link_related_facts(session: Session, new_facts_batch: list[Fact]):
    """
    The new V3.1 Synthesizer. It is now a native citizen of the ORM,
    accepting a session object and operating on Fact objects directly.
    It leverages pre-computed semantics for massive performance gains.
    """
    logger.info("beginning Knowledge Graph linking...")
    if not new_facts_batch:
        logger.info("no new facts to link. Cycle complete.")
        return

    # 1. Get all facts using the correct, efficient ORM query.
    all_facts_in_ledger = session.query(Fact).all()
    
    links_found = 0
    for new_fact in new_facts_batch:
        # 2. HUGE PERFORMANCE WIN: Use the pre-computed spaCy doc.
        # We no longer re-run the slow NLP model here.
        new_semantics = new_fact.get_semantics()
        new_doc = Fact.get_doc(new_semantics)
        new_entities = {ent.text.lower() for ent in new_doc.ents}

        for existing_fact in all_facts_in_ledger:
            if new_fact.id == existing_fact.id:
                continue

            existing_semantics = existing_fact.get_semantics()
            existing_doc = Fact.get_doc(existing_semantics)
            existing_entities = {ent.text.lower() for ent in existing_doc.ents}

            # 3. Find shared entities to determine relationship strength.
            shared_entities = new_entities.intersection(existing_entities)
            
            if len(shared_entities) > 0:
                relationship_score = len(shared_entities)
                # 4. Use the correct, ORM-native function to insert the link.
                insert_relationship_object(session, new_fact, existing_fact, relationship_score)
                links_found += 1

    session.commit() # Commit all new relationships at the end of the process.
    logger.info(f"linking complete. Found and stored {links_found} new relationships.")