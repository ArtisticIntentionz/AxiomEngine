"""Synthesizer - Compare facts."""

from __future__ import annotations

# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
import logging
import re  # Add this import for regular expressions
import sys
from collections import defaultdict
from typing import TYPE_CHECKING

from axiom_server.ledger import (
    Fact,
    RelationshipType,
    insert_relationship_object,
    mark_fact_objects_as_disputed,
)

if TYPE_CHECKING:
    from spacy.tokens import Doc
    from sqlalchemy.orm import Session


# Helper function to find all numbers (digits, decimals, percentages) in a text
def find_numbers(text: str) -> list[float]:
    """Extract all integer and floating-point numbers from a string."""
    # This regex finds integers, decimals, and numbers with commas.
    # It will not handle currency symbols, so it's a good starting point.
    return [
        float(num.replace(",", ""))
        for num in re.findall(r"-?\d[\d,]*\.?\d*", text)
    ]


# --- Numeric tolerance helper ---
def numbers_are_close(
    a: float,
    b: float,
    rel_tol: float = 0.05,
    abs_tol: float = 2.0,
) -> bool:
    """Return True if numbers are close enough to not be considered a contradiction."""
    if a == 0 or b == 0:
        return abs(a - b) <= abs_tol
    return abs(a - b) <= abs_tol or abs(a - b) / max(abs(a), abs(b)) <= rel_tol


# --- Fact type classifier (very simple heuristic) ---
def classify_fact_type(doc: Doc) -> str:
    """Classify fact type for more precise comparison (e.g., company size, location, founding date)."""
    # This is a simple heuristic; can be expanded
    text = doc.text.lower()
    if any(word in text for word in ["employee", "staff", "workforce"]):
        return "company_size"
    if any(word in text for word in ["revenue", "income", "sales"]):
        return "company_revenue"
    if any(word in text for word in ["founded", "established", "since"]):
        return "founding_date"
    if any(ent.label_ == "GPE" for ent in doc.ents):
        return "location"
    return "general"


# --- Entity extraction helper ---
def get_main_entities(doc: Doc) -> set[str]:
    """Return set of main entities (ORG, PERSON, GPE, EVENT) in lowercase."""
    return {
        ent.lemma_.lower()
        for ent in doc.ents
        if ent.label_ in ["PERSON", "ORG", "GPE", "EVENT"]
    }


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

SIMILARITY_THRESHOLD = 0.85


def get_numeric_entities(doc: Doc) -> dict[str, float]:
    """Find numbers in a document and attempt to identify the noun they describe.

    Return a dictionary mapping the noun's lemma to the number.
    Example: "110mph wind" -> {"wind": 110.0}
    """
    numeric_entities = {}
    for ent in doc.ents:
        if ent.label_ in ["CARDINAL", "QUANTITY", "PERCENT", "MONEY"]:
            try:
                # Find the noun this number is attached to (its "head")
                head = ent.root.head
                if head.pos_ == "NOUN":
                    # Use the lemma for consistency (e.g., "miles" -> "mile")
                    numeric_entities[head.lemma_] = float(
                        ent.text.replace(",", ""),
                    )
            except (ValueError, AttributeError):
                continue
    return numeric_entities


# --- Improved contradiction check with tolerance, fact type, and explainability ---
def check_for_contradiction(doc1: Doc, doc2: Doc) -> tuple[bool, bool, str]:
    """Analyze two highly similar documents to find specific, high-confidence contradictions.

    Return (is_contradiction: bool, is_potential: bool, reason: str).
    """
    contradiction_score = 0
    reasons = []
    # --- 1. Conflicting Numerical Data (with tolerance) ---
    numeric_entities1 = get_numeric_entities(doc1)
    numeric_entities2 = get_numeric_entities(doc2)
    shared_subjects = set(numeric_entities1.keys()).intersection(
        set(numeric_entities2.keys()),
    )
    for subject in shared_subjects:
        n1 = numeric_entities1[subject]
        n2 = numeric_entities2[subject]
        if not numbers_are_close(n1, n2):
            reasons.append(
                f"Conflicting numbers for subject '{subject}': {n1} vs {n2}",
            )
            contradiction_score += 3
    # --- 2. Conflicting Dates/Times for the Same Event (improved) ---
    verbs1 = {token.lemma_.lower() for token in doc1 if token.pos_ == "VERB"}
    verbs2 = {token.lemma_.lower() for token in doc2 if token.pos_ == "VERB"}
    if verbs1.intersection(verbs2):
        dates1 = {ent.text for ent in doc1.ents if ent.label_ == "DATE"}
        dates2 = {ent.text for ent in doc2.ents if ent.label_ == "DATE"}
        # Only flag as contradiction if dates overlap or are meant to be the same
        if dates1 and dates2:
            # If both mention a year and the years are different, that's a contradiction
            years1 = {d for d in dates1 if any(c.isdigit() for c in d)}
            years2 = {d for d in dates2 if any(c.isdigit() for c in d)}
            if years1 and years2 and not years1.intersection(years2):
                reasons.append(
                    f"Different years for similar events: {years1} vs {years2}",
                )
                contradiction_score += 2
    # --- 3. Negation Detection (More Precise) ---
    shared_verbs = verbs1.intersection(verbs2)
    for verb in shared_verbs:
        negated_in_1 = any(
            tok.dep_ == "neg" and tok.head.lemma_.lower() == verb
            for tok in doc1
        )
        negated_in_2 = any(
            tok.dep_ == "neg" and tok.head.lemma_.lower() == verb
            for tok in doc2
        )
        if negated_in_1 != negated_in_2:
            reasons.append(f"Negation of shared verb '{verb}'.")
            contradiction_score += 1
    # --- 4. Fact type awareness ---
    type1 = classify_fact_type(doc1)
    type2 = classify_fact_type(doc2)
    if type1 != type2:
        reasons.append(f"Fact types differ: {type1} vs {type2}")
        # Don't count as contradiction, but log for explainability
    # --- Final Decision ---
    if contradiction_score >= 3:
        return True, False, "; ".join(reasons)
    if contradiction_score == 2:
        return False, True, "; ".join(reasons)
    return False, False, "; ".join(reasons)


# --- Main linking function with entity pre-filter and explainability ---
def link_related_facts(
    session: Session,
    new_facts_batch: list[Fact],
) -> None:
    """Analyze new facts to find correlations or disputes with existing ones.

    Iterate through a batch of new facts and compare them against all existing
    facts in the database. To optimize, first build an in-memory index that maps
    entities to the facts they appear in, ensuring comparisons only happen between
    facts that share at least one entity.

    For each potential pair, perform two main checks in order of priority:
    1.  **Contradiction:** Identify high-confidence contradictions. If found,
        mark both facts as disputed.
    2.  **Correlation:** If not a contradiction, calculate a correlation score
        based on semantic similarity, shared entities, and shared nouns. If the
        score exceeds a threshold, create a "CORRELATION" relationship and
        increase the scores of both facts.

    Args:
        session: The database session for querying and persisting changes.
        new_facts_batch: A list of new Fact objects to process and link.

    Side Effects:
        - Creates new `Relationship` objects in the database for correlated facts.
        - Updates the `score` attribute on correlated `Fact` objects.
        - Modifies the status of `Fact` objects to 'disputed' if a
          contradiction is found.

    """
    logger.info("beginning Knowledge Graph linking...")
    if not new_facts_batch:
        logger.info("no new facts to link. Cycle complete.")
        return
    # --- Build entity index for performance ---
    all_facts_in_ledger = session.query(Fact).all()
    entity_to_facts = defaultdict(list)
    for fact in all_facts_in_ledger:
        try:
            semantics = fact.get_semantics()
            if semantics and "doc" in semantics and semantics["doc"]:
                doc = semantics["doc"]
                for ent in get_main_entities(doc):
                    entity_to_facts[ent].append(fact)
        except Exception as e:
            logger.warning(f"Skipping fact {fact.id} due to semantics error: {e}")
            continue
    links_found = 0
    disputes_found = 0
    for new_fact in new_facts_batch:
        try:
            new_semantics = new_fact.get_semantics()
            if not new_semantics or "doc" not in new_semantics or not new_semantics["doc"]:
                logger.warning(f"Skipping new fact {new_fact.id} - no valid semantics")
                continue
            new_doc = new_semantics["doc"]
            new_entities = get_main_entities(new_doc)
            if not new_entities:
                continue
        except Exception as e:
            logger.warning(f"Skipping new fact {new_fact.id} due to semantics error: {e}")
            continue
        # Only compare to facts sharing at least one main entity
        compared_facts = set()
        for ent in new_entities:
            for existing_fact in entity_to_facts.get(ent, []):
                if (
                    existing_fact.id == new_fact.id
                    or (new_fact.id, existing_fact.id) in compared_facts
                ):
                    continue
                compared_facts.add((new_fact.id, existing_fact.id))
                existing_semantics = existing_fact.get_semantics()
                existing_doc = existing_semantics["doc"]
                if not new_doc.has_vector or not existing_doc.has_vector:
                    continue
                # Priority 1: Check for a high-confidence contradiction.
                is_contradiction, is_potential, reason = (
                    check_for_contradiction(
                        new_doc,
                        existing_doc,
                    )
                )
                if is_contradiction:
                    logger.info(f"CONFIRMED CONTRADICTION: {reason}")
                    mark_fact_objects_as_disputed(
                        session,
                        new_fact,
                        existing_fact,
                    )
                    disputes_found += 1
                    continue
                if is_potential:
                    logger.info(f"POTENTIAL CONTRADICTION: {reason}")
                    # Optionally, store as a soft-flag in a review table or log
                    continue
                # Priority 2: If not a dispute, check for correlation using a multi-factor score.
                correlation_score = 0
                similarity = new_doc.similarity(existing_doc)
                if similarity > 0.80:
                    correlation_score += 1
                if similarity > 0.90:
                    correlation_score += 1
                existing_entities = get_main_entities(existing_doc)
                shared_entities_count = len(
                    new_entities.intersection(existing_entities),
                )
                if shared_entities_count > 0:
                    correlation_score += shared_entities_count * 2
                new_nouns = {
                    token.lemma_.lower()
                    for token in new_doc
                    if token.pos_ == "NOUN" and not token.is_stop
                }
                existing_nouns = {
                    token.lemma_.lower()
                    for token in existing_doc
                    if token.pos_ == "NOUN" and not token.is_stop
                }
                shared_nouns_count = len(
                    new_nouns.intersection(existing_nouns),
                )
                if shared_nouns_count > 2:
                    correlation_score += 1
                correlation_threshold = 3
                if correlation_score >= correlation_threshold:
                    if existing_fact.sources:
                        source_credibility_weight = max(
                            s.credibility_score for s in existing_fact.sources
                        )
                    else:
                        source_credibility_weight = 1.0
                    final_weighted_score = correlation_score * int(
                        source_credibility_weight,
                    )
                    logger.info(
                        f"Correlation found. Base score: {correlation_score}, Source Weight: {source_credibility_weight}, Final Score: {final_weighted_score} | Reason: shared entities: {new_entities.intersection(existing_entities)}, shared nouns: {shared_nouns_count}, similarity: {similarity:.2f}",
                    )
                    new_fact.score += final_weighted_score
                    existing_fact.score += final_weighted_score
                    insert_relationship_object(
                        session,
                        new_fact,
                        existing_fact,
                        final_weighted_score,
                        RelationshipType.CORRELATION,
                    )
                    links_found += 1
    logger.info(
        f"linking complete. Found {links_found} new correlations and {disputes_found} new disputes.",
    )
