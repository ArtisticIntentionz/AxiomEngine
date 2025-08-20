# Axiom - verification_engine.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
"""The experimental V4 Verification Engine for Axiom nodes."""

import re
from typing import Any

import requests
from sqlalchemy.orm import Session

from axiom_server.ledger import Fact


# --- The "Simple, Smart, Genius" Corroboration Engine ---
def find_corroborating_claims(
    fact_to_verify: Fact,
    session: Session,
) -> list[dict[str, Any]]:
    """Perform a semantic similarity search across the ledger.

    This function finds facts that corroborate the given fact. This is the
    heart of the V4 "Corroboration Engine."

    Args:
        fact_to_verify: The Fact object to be verified.
        session: The SQLAlchemy session to use for database queries.

    Returns:
        A list of dictionaries, each representing a corroborating fact.

    """
    corroborations = []

    # This is your "deep dive": get the "brain" of our target fact.
    target_semantics = fact_to_verify.get_semantics()
    target_doc = target_semantics["doc"]

    # Get all other facts from the ledger to compare against.
    all_other_facts = (
        session.query(Fact).filter(Fact.id != fact_to_verify.id).all()
    )

    for other_fact in all_other_facts:
        other_doc = other_fact.get_semantics()["doc"]

        # Use spaCy's powerful, built-in vector similarity comparison.
        # This is a number from 0.0 (completely different) to 1.0 (identical).
        similarity_score = target_doc.similarity(other_doc)

        # We define "corroboration" as high semantic similarity from a different source.
        if similarity_score > 0.90 and not other_fact.has_source(
            fact_to_verify.sources[0].domain,
        ):
            corroborations.append(
                {
                    "fact_id": other_fact.id,
                    "content": other_fact.content,
                    "similarity": round(similarity_score, 4),
                    "source": other_fact.sources[0].domain,
                },
            )

    return corroborations


# --- The "Simple, Smart, Genius" Citation Engine ---
def verify_citations(fact_to_verify: Fact) -> list[dict[str, str]]:
    """Find and verify all hyperlinks within a fact's content.

    This is the first step towards the V5 "Citation Engine" for primary
    source verification.

    Args:
        fact_to_verify: The Fact object to be analyzed.

    Returns:
        A list of dictionaries, each representing a found citation and its status.

    """
    citations = []

    # Use a simple regex to find all URLs in the fact's text.
    urls_found = re.findall(
        r"https?://(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,6}(?:/[^\s]*)?",
        fact_to_verify.content,
    )

    if not urls_found:
        return []

    for url in set(
        urls_found,
    ):  # Use set() to avoid checking the same URL twice
        try:
            # We use a HEAD request with a timeout to be a "Good Neighbor".
            # We only care if the page exists, we don't need to download it.
            response = requests.head(url, timeout=5, allow_redirects=True)
            if response.status_code == 200:
                status = "VALID_AND_LIVE"
            else:
                status = f"BROKEN_{response.status_code}"
        except requests.RequestException:
            status = "UNREACHABLE"

        citations.append({"url": url, "status": status})

    return citations
