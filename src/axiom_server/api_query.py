"""API Query - Find facts from database using scalable hybrid search."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from scipy.spatial.distance import cosine
from sqlalchemy import not_, or_

from axiom_server.common import NLP_MODEL
from axiom_server.crucible import TEXT_SANITIZATION
from axiom_server.ledger import Fact, FactStatus
from axiom_server.nlp_utils import parse_query_advanced

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# The old keyword_search_ledger is now obsolete and can be removed.


def semantic_search_ledger(
    session: Session,
    search_term: str,
    min_status: str = "corroborated",
    top_n: int = 10,
    similarity_threshold: float = 0.45,
) -> list[Fact]:
    """Perform a scalable, hybrid semantic search on the database.

    1. Pre-filters facts using keywords for performance.
    2. Ranks the filtered candidates by vector similarity.
    3. Filters the final results by status and threshold.
    """
    if not search_term.strip():
        return []

    sanitized_term = TEXT_SANITIZATION.run(search_term)
    if not sanitized_term:
        return []

    # --- Step 1: Hybrid Search Pre-filtering ---
    keywords = parse_query_advanced(sanitized_term)
    if not keywords:
        return []

    keyword_filters = [Fact.content.ilike(f"%{key}%") for key in keywords]

    # Build the base query to find candidate facts
    candidate_query = (
        session.query(Fact)
        .join(Fact.vector_data)  # Ensure we only get facts that have a vector
        .filter(or_(*keyword_filters))
        .filter(not_(Fact.disputed))
    )

    # Pre-fetch candidate facts and their vectors from the database in one efficient query
    candidate_facts = candidate_query.all()
    if not candidate_facts:
        return []

    # --- Step 2: Vector Similarity Ranking ---
    query_vector = NLP_MODEL(sanitized_term).vector
    scored_facts = []

    for fact in candidate_facts:
        # The fact's vector is already loaded due to the join and relationship
        db_vector = np.frombuffer(fact.vector_data.vector, dtype=np.float32)

        if query_vector.shape != db_vector.shape:
            continue

        # Calculate similarity and store if it meets the threshold
        similarity = 1 - cosine(query_vector, db_vector)
        if similarity > similarity_threshold:
            scored_facts.append((similarity, fact))

    # Sort the candidates by similarity score
    scored_facts.sort(key=lambda x: x[0], reverse=True)

    # --- Step 3: Final Filtering by Status and top_n ---

    # Get the top N facts after similarity ranking
    top_ranked_facts = [fact for _, fact in scored_facts[:top_n]]

    try:
        status_hierarchy = (
            "ingested",
            "proposed",
            "corroborated",
            "empirically_verified",
        )
        min_status_index = status_hierarchy.index(min_status.lower())

        # Get all valid statuses from the enum that are at or above the minimum required level
        valid_statuses = {
            s
            for i, s_name in enumerate(status_hierarchy)
            if i >= min_status_index
            for s in FactStatus
            if s.value == s_name
        }

        # Filter the top N ranked facts by our desired quality level
        return [
            fact for fact in top_ranked_facts if fact.status in valid_statuses
        ]

    except (ValueError, IndexError):
        return []  # Return empty if an invalid status is requested
