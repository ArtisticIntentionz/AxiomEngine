"""API Query - Find facts from database using semantic search."""

from __future__ import annotations

# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
from typing import TYPE_CHECKING

# --- ADDITION: New imports for math and NLP ---
import numpy as np
from scipy.spatial.distance import cosine

from axiom_server.common import NLP_MODEL
from axiom_server.crucible import TEXT_SANITIZATION
from axiom_server.ledger import Fact, FactStatus, FactVector

if TYPE_CHECKING:
    from collections.abc import Iterable

    from sqlalchemy.orm import Session


# --- keyword search is no longer the primary method ---
def keyword_search_ledger(
    session: Session,
    search_term: str,
    include_disputed: bool = False,
) -> Iterable[Fact]:
    """Search the ledger for facts containing the search term."""
    query = session.query(Fact).filter(Fact.content.ilike(f"%{search_term}%"))

    if not include_disputed:
        query = query.filter(Fact.disputed.is_(False))

    return query.all()


def semantic_search_ledger(
    session: Session,
    search_term: str,
    min_status: str = "corroborated",  # We are now correctly accepting this!
    top_n: int = 5,
    similarity_threshold: float = 0.65,  # Our new, tuned threshold
) -> list[Fact]:
    """Perform a semantic vector search and filter by fact status."""
    if not search_term.strip():
        return []

    sanitized_term = TEXT_SANITIZATION.run(search_term)
    if not sanitized_term:
        return []

    query_vector = NLP_MODEL(sanitized_term).vector
    all_fact_vectors = session.query(FactVector).all()
    if not all_fact_vectors:
        return []

    scored_facts = []
    for fact_vector in all_fact_vectors:
        db_vector = np.frombuffer(fact_vector.vector, dtype=np.float32)
        if query_vector.shape != db_vector.shape:
            continue

        similarity = 1 - cosine(query_vector, db_vector)
        if similarity > similarity_threshold:
            scored_facts.append((similarity, fact_vector.fact))

    scored_facts.sort(key=lambda x: x[0], reverse=True)
    top_facts = [fact for _, fact in scored_facts[:top_n]]

    try:
        # This is the original, brilliant hierarchy from the main branch
        status_hierarchy = (
            "ingested",
            "logically_consistent",
            "corroborated",
            "empirically_verified",
        )
        min_status_index = status_hierarchy.index(min_status.lower())
        valid_statuses = {
            s.value
            for s in FactStatus
            if status_hierarchy.index(s.value) >= min_status_index
        }

        # Filter the top semantic results by our desired quality level
        return [fact for fact in top_facts if fact.status in valid_statuses]
    except (ValueError, IndexError):
        return []  # Return empty if an invalid status is requested
