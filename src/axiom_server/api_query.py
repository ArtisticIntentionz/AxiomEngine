# Axiom - api_query.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
# --- V3.1: STATUS-AWARE QUERY ENGINE ---

from typing import Iterable
from sqlalchemy.orm import Session
from sqlalchemy import or_

from .ledger import Fact

# This defines the hierarchy of trust. A fact's status can only move forward.
STATUS_HIERARCHY = [
    'ingested',
    'logically_consistent',
    'corroborated',          # We'll re-introduce this as a status
    'empirically_verified'
]

def search_ledger_for_api(
    session: Session,
    search_term: str,
    min_status: str = "corroborated",
    include_disputed: bool = False
) -> Iterable[Fact]:
    """
    The new V3.1 search function. It searches the ledger for facts based
    on their position in the new, sophisticated verification lifecycle.

    Args:
        session: The active SQLAlchemy session.
        search_term: The keyword to search for in the fact content.
        min_status: The minimum verification status a fact must have to be included.
                    Defaults to 'corroborated'.
        include_disputed: Whether to include facts that are marked as disputed.
    """
    # Start with the basic search term filter.
    query = session.query(Fact).filter(Fact.content.ilike(f"%{search_term}%"))

    # Apply the new, status-based filtering logic.
    try:
        min_status_index = STATUS_HIERARCHY.index(min_status)
        # Create a list of all statuses that are considered "good enough".
        valid_statuses = STATUS_HIERARCHY[min_status_index:]
        query = query.filter(Fact.status.in_(valid_statuses))
    except ValueError:
        # If an invalid status is provided, return nothing.
        return []

    if not include_disputed:
        # The 'disputed' status can be separate from the main lifecycle.
        # This logic needs to be refined, for now we will assume a boolean flag exists.
        # In a future version, 'disputed' would be another status.
        pass # Placeholder for new disputed logic

    return query.all()