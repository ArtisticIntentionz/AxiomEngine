"""API Query - Find facts from database."""

from __future__ import annotations

# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
from typing import TYPE_CHECKING, Final

from axiom_server.ledger import Fact

if TYPE_CHECKING:
    from collections.abc import Iterable

    from sqlalchemy.orm import Session

STATUS_HIERARCHY: Final = (
    "ingested",
    "logically_consistent",
    "corroborated",
    "empirically_verified",
)

DB_NAME: Final = "axiom_ledger.db"


def search_ledger_for_api(
    session: Session,
    search_term: str,
    min_status: str = "corroborated",
    include_disputed: bool = False,
) -> Iterable[Fact]:
    """Search the ledger for facts containing the search term.

    Args:
        session: The active SQLAlchemy session.
        search_term: The keyword to search for in the fact content.
        min_status: The minimum verification status a fact must have to be included.
                    Defaults to 'corroborated' for safety.
        include_disputed: Whether to include facts that are marked as disputed.

    """
    query = session.query(Fact).filter(Fact.content.ilike(f"%{search_term}%"))

    try:
        min_status_index = STATUS_HIERARCHY.index(min_status)
        valid_statuses = STATUS_HIERARCHY[min_status_index:]
        query = query.filter(Fact.status.in_(valid_statuses))
    except ValueError:
        return []

    if not include_disputed:
        query = query.filter(Fact.disputed.is_(False))

    return query.all()
