"""API Query - Find facts from database."""

from __future__ import annotations

# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
# --- UPGRADED TO HANDLE DISPUTED FACTS ---
from typing import TYPE_CHECKING, Final

from axiom_server.ledger import Fact

if TYPE_CHECKING:
    from collections.abc import Iterable

    from sqlalchemy.orm import Session

DB_NAME: Final = "axiom_ledger.db"


def search_ledger_for_api(
    session: Session,
    search_term: str,
    include_uncorroborated: bool = False,
    include_disputed: bool = False,
) -> Iterable[Fact]:
    """Search the ledger for facts containing the search term.

    - By default, ONLY returns 'trusted' facts.
    - By default, ALWAYS excludes 'disputed' facts.
    """
    query = session.query(Fact).filter(Fact.content.ilike(f"%{search_term}%"))

    if include_uncorroborated:
        query = query.filter(Fact.score >= 0)

    else:
        query = query.filter(Fact.score > 0)

    if not include_disputed:
        query = query.filter(Fact.disputed == False)  # noqa: E712

    return query.all()
