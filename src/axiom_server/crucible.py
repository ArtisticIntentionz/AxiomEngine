"""Crucible - Semantic Analysis to extract Facts from text."""

from __future__ import annotations

# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
import logging
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from functools import cache
from typing import TYPE_CHECKING, Generic, TypeVar

# Third-party imports for HTML parsing
from bs4 import BeautifulSoup

from axiom_server.common import (
    NARRATIVE_INDICATORS,
    NLP_MODEL,
    SUBJECTIVITY_INDICATORS,
)

# Local application imports
from axiom_server.ledger import (
    Fact,
    RelationshipType,
    Semantics,
    insert_relationship_object,
    mark_fact_objects_as_disputed,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from spacy.tokens.doc import Doc
    from spacy.tokens.span import Span
    from sqlalchemy.orm import Session
    from transformers import Pipeline as NliPipeline

    from axiom_server.hasher import FactIndexer


T = TypeVar("T")

# --- Logger Setup (preserved from your original file) ---
logger = logging.getLogger("crucible")
# Avoid adding handlers multiple times if the module is reloaded
if not logger.handlers:
    stdout_handler = logging.StreamHandler(stream=sys.stdout)
    formatter = logging.Formatter(
        "[%(name)s] %(asctime)s | %(levelname)s | %(filename)s:%(lineno)s >>> %(message)s",
    )
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

# --- Pre-compiled Regex (preserved from your original file) ---
METADATA_NOISE_PATTERNS = (
    re.compile(r"^\d+\s*"),
    re.compile(
        r"^(By and\s*)?\d*[\d\s]*(min read|Heard on the Street)\s*",
        re.IGNORECASE,
    ),
    re.compile(r"^Advertisement\s*", re.IGNORECASE),
)


# --- NEW: Efficiently load and cache the NLI model ---
@cache
def get_nli_classifier() -> NliPipeline:
    """Load and returns a cached instance of the NLI pipeline.

    This prevents reloading the large model from memory on every call.
    """
    try:
        from transformers import pipeline

        logger.info(
            "Initializing Hugging Face NLI model for the first time...",
        )
        return pipeline(
            "zero-shot-classification",
            model="facebook/bart-large-mnli",
        )
    except ImportError:
        logger.error(
            "The 'transformers' and 'torch' libraries are required for contradiction detection.",
        )
        raise


class CrucibleError(Exception):
    """Crucible Error Exception."""

    __slots__ = ()


# --- Dataclasses (preserved from your original file) ---
@dataclass
class Check(Generic[T]):
    """Check dataclass."""

    run: Callable[[T], bool]
    description: str


@dataclass
class Transformation(Generic[T]):
    """Transformation dataclass."""

    run: Callable[[T], T | None]
    description: str


@dataclass
class Pipeline(Generic[T]):
    """Pipeline dataclass."""

    name: str
    steps: list[Check[T] | Transformation[T]]

    def run(self, value: T) -> T | None:
        """Run pipeline."""
        # Using a slice to prevent huge objects from filling the logs
        logger.info(f"running pipeline '{self.name}' on '%.200s'", value)
        current_value: T | None = value
        for step in self.steps:
            if current_value is None:
                logger.info(
                    f"pipeline '{self.name}' halted as value became None.",
                )
                break
            if isinstance(step, Check):
                if not step.run(current_value):
                    logger.info(
                        f"pipeline '{self.name}' stopped by check: {step.description}",
                    )
                    return None
            elif isinstance(step, Transformation):
                try:
                    current_value = step.run(current_value)
                except Exception as exc:
                    error_string = f"transformation error in '{self.name}' on step '{step.description}' ({exc})"
                    logger.exception(error_string)
                    raise CrucibleError(error_string) from exc
        logger.info(
            f"pipeline '{self.name}' finished, returning '%.200s'",
            current_value,
        )
        return current_value


# --- FIXED: Added HTML stripping as the first step ---
TEXT_SANITIZATION: Pipeline[str] = Pipeline(
    "text sanitization",
    [
        Transformation(
            lambda text: BeautifulSoup(text, "html.parser").get_text(
                separator=" ",
            ),
            "Strip HTML tags",
        ),
        Transformation(lambda text: text.lower(), "Convert text to lowercase"),
        Transformation(
            lambda text: re.sub(r"(\d{4})([A-Z])", r"\1. \2", text),
            "Fix run-on sentences",
        ),
        Transformation(
            lambda text: re.sub(r"\s+", " ", text).strip(),
            "Standardize whitespace",
        ),
    ],
)

SENTENCE_CHECKS: Pipeline[Span] = Pipeline(
    "sentence checks",
    [
        # --- NEW CHECK 1: Reject anything that still looks like code/markup ---
        Check(
            lambda sent: "<" not in sent.text and ">" not in sent.text,
            "sentence must not contain HTML-like characters",
        ),
        # --- NEW CHECK 2: Reject short, non-informative sentences ---
        Check(
            lambda sent: len(sent.text.split()) >= 7,
            "sentence minimal length (7 words)",
        ),
        Check(
            lambda sent: len(sent.text.split()) <= 100,
            "sentence maximal length (100 words)",
        ),
        # --- NEW CHECK 3: Must have at least one verb to be a statement ---
        Check(
            lambda sent: any(token.pos_ == "VERB" for token in sent),
            "sentence must contain a verb",
        ),
        Check(
            lambda sent: (
                len(sent.ents) > 0
                or any(t.pos_ in {"PROPN", "NOUN"} for t in sent)
            ),
            "sentence must contain named entities or salient nouns",
        ),
        Check(
            lambda sent: not any(
                indicator in sent.text.lower()
                for indicator in SUBJECTIVITY_INDICATORS
            ),
            "sentence is objective",
        ),
        Check(
            lambda sent: not any(
                token.lemma_.lower() in NARRATIVE_INDICATORS for token in sent
            ),
            "sentence is not a personal narrative",
        ),
    ],
)


def _get_subject_and_object(doc: Doc) -> tuple[str | None, str | None]:
    """Extract the main subject and object from a spaCy doc."""
    subject: str | None = None
    d_object: str | None = None
    for token in doc:
        if "nsubj" in token.dep_:
            subject = token.lemma_.lower()
        if (
            "dobj" in token.dep_
            or "pobj" in token.dep_
            or "attr" in token.dep_
        ):
            d_object = token.lemma_.lower()
    return subject, d_object


def semantics_check_and_set_subject_object(
    semantics: Semantics,
) -> Semantics | None:
    """Set a Semantics' subject and object fields from spaCy."""
    subject, object_ = _get_subject_and_object(semantics["doc"])
    if subject is None or object_ is None:
        return None
    semantics["subject"] = subject
    semantics["object"] = object_
    return semantics


SEMANTICS_CHECKS = Pipeline(
    "semantics checks",
    [
        Transformation(
            semantics_check_and_set_subject_object,
            "check for presence of subject and object",
        ),
    ],
)
FACT_PREANALYSIS: Pipeline[Fact] = Pipeline("Fact Preanalysis", [])


def extract_facts_from_text(text_content: str, source_url: str) -> list[Fact]:
    """Return list of Facts from text content using semantic analysis."""
    sanitized_text = TEXT_SANITIZATION.run(text_content)
    if not sanitized_text:
        logger.info(
            "text sanitizer rejected input content, returning no facts",
        )
        return []

    doc = NLP_MODEL(sanitized_text)
    facts: list[Fact] = []
    for sentence in doc.sents:
        clean_sentence_text = sentence.text.strip()
        for pattern in METADATA_NOISE_PATTERNS:
            clean_sentence_text = pattern.sub("", clean_sentence_text).strip()
        if not clean_sentence_text:
            continue

        clean_sentence_span = NLP_MODEL(clean_sentence_text)[:]
        if (
            checked_sentence := SENTENCE_CHECKS.run(clean_sentence_span)
        ) is not None:
            fact = Fact(
                content=checked_sentence.text.strip(),
                source_url=source_url,
            )

            semantics = Semantics(
                {
                    "doc": checked_sentence.as_doc(),
                    "object": "",
                    "subject": "",
                },
            )
            if (
                final_semantics := SEMANTICS_CHECKS.run(semantics)
            ) is not None:
                fact.set_semantics(final_semantics)
                if (
                    preanalyzed_fact := FACT_PREANALYSIS.run(fact)
                ) is not None:
                    facts.append(preanalyzed_fact)
    return facts


# REMOVED: The old check_contradiction is no longer needed.
# The NLI model in _infer_relationship is far more accurate.


def check_corroboration(new_fact: Fact, existing_fact: Fact) -> bool:
    """Check for corroboration between Facts."""
    # Simplified check. Can be improved with semantic similarity later.
    return bool(existing_fact.content[:50] == new_fact.content[:50])


def _extract_dates(text: str) -> list[datetime]:
    """Extract dates from text using regular expressions."""
    patterns = [
        r"\d{4}-\d{2}-\d{2}",
        r"\d{1,2}/\d{1,2}/\d{4}",
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}, \d{4}",
    ]
    found_dates = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            try:
                if "/" in match:
                    dt = datetime.strptime(match, "%m/%d/%Y")
                elif "-" in match:
                    dt = datetime.strptime(match, "%Y-%m-%d")
                else:
                    dt = datetime.strptime(match, "%B %d, %Y")
                found_dates.append(dt)
            except ValueError:
                continue
    return found_dates


def _entities_match(fact1: Fact, fact2: Fact) -> bool:
    """Check if two facts are about the same main entity (e.g., company, person, event)."""
    sem1 = fact1.get_semantics()
    sem2 = fact2.get_semantics()
    doc1 = sem1.get("doc")
    doc2 = sem2.get("doc")
    if not doc1 or not doc2:
        return False
    # Compare main entity names (subject or first entity)
    ents1 = {
        ent.text.lower()
        for ent in doc1.ents
        if ent.label_ in {"ORG", "PERSON", "GPE", "LOC"}
    }
    ents2 = {
        ent.text.lower()
        for ent in doc2.ents
        if ent.label_ in {"ORG", "PERSON", "GPE", "LOC"}
    }
    # Require at least one strong overlap
    return bool(ents1 & ents2)


# --- Relationship inference with entity match and stricter thresholds ---
def _infer_relationship(
    fact1: Fact,
    fact2: Fact,
) -> tuple[RelationshipType, float, str] | None:
    """Analyze two facts and infer their relationship, confidence, and reason.

    Uses a powerful NLI model for logical inference.
    """
    try:
        # Only compare if entities match
        if not _entities_match(fact1, fact2):
            return None
        nli_classifier = get_nli_classifier()
        premise = fact1.content
        hypothesis = fact2.content
        result1 = nli_classifier(
            premise,
            candidate_labels=["contradiction", "entailment", "neutral"],
        )
        result2 = nli_classifier(
            hypothesis,
            candidate_labels=["contradiction", "entailment", "neutral"],
        )
        # --- Decision Logic ---
        # 1. High-Confidence Contradiction (Top Priority)
        # Require very high confidence and entity match
        if (
            result1["labels"][0] == "contradiction"
            and result1["scores"][0] > 0.98
        ) or (
            result2["labels"][0] == "contradiction"
            and result2["scores"][0] > 0.98
        ):
            confidence = max(result1["scores"][0], result2["scores"][0])
            return (
                RelationshipType.CONTRADICTION,
                confidence,
                "strong contradiction (entity match)",
            )
        # 1b. Potential Contradiction (flag, but don't dispute)
        if (
            result1["labels"][0] == "contradiction"
            and result1["scores"][0] > 0.92
        ) or (
            result2["labels"][0] == "contradiction"
            and result2["scores"][0] > 0.92
        ):
            confidence = max(result1["scores"][0], result2["scores"][0])
            return (
                RelationshipType.CONTRADICTION,
                confidence,
                "potential contradiction (borderline confidence)",
            )
        # 2. High-Confidence Corroboration (Entailment)
        if (
            result1["labels"][0] == "entailment"
            and result1["scores"][0] > 0.90
        ) or (
            result2["labels"][0] == "entailment"
            and result2["scores"][0] > 0.90
        ):
            confidence = max(result1["scores"][0], result2["scores"][0])
            return (
                RelationshipType.CORRELATION,
                confidence,
                "entailment/corroboration",
            )
        # 3. Chronology Check (if not logically related)
        dates1 = _extract_dates(fact1.content)
        dates2 = _extract_dates(fact2.content)
        if dates1 and dates2 and min(dates1) != min(dates2):
            return (
                RelationshipType.CHRONOLOGY,
                0.75,
                "chronology (different dates)",
            )
        # 4. Elaboration Check (Default for highly similar, non-conflicting facts)
        doc1 = fact1.get_semantics()["doc"]
        doc2 = fact2.get_semantics()["doc"]
        if doc1.has_vector and doc2.has_vector:
            similarity = doc1.similarity(doc2)
            if similarity > 0.85:
                return (
                    RelationshipType.ELABORATION,
                    similarity,
                    "elaboration (high similarity)",
                )
    except Exception as e:
        logger.warning(f"Could not perform NLI check due to error: {e}")
    return None


@dataclass
class CrucibleFactAdder:
    """Processes a new fact against the existing knowledge base efficiently."""

    session: Session
    fact_indexer: FactIndexer

    def add(self, fact: Fact) -> None:
        """Add and process a fact against the database and update the search index."""
        # Use a sub-pipeline for post-ingestion processing
        processing_pipeline = Pipeline(
            "Crucible Fact Processing",
            [
                Transformation(
                    self._process_relationships,
                    "Find and store relationships",
                ),
            ],
        )

        processed_fact = processing_pipeline.run(fact)

        if processed_fact:
            # If processing was successful and the fact wasn't disputed and removed, add it to the index.
            self.fact_indexer.add_fact(processed_fact)
            logger.info(
                f"Fact {processed_fact.id} successfully processed and added to search index.",
            )

        self.session.commit()

    def _process_relationships(self, new_fact: Fact) -> Fact | None:
        """Find and process all interactions for a new fact."""
        new_doc = new_fact.get_semantics().get("doc")
        if not new_doc:
            return new_fact
        new_entities = {
            ent.text.lower() for ent in new_doc.ents if len(ent.text) > 2
        }
        if not new_entities:
            return new_fact
        query = self.session.query(Fact).filter(
            Fact.id != new_fact.id,
            Fact.disputed == False,  # noqa: E712
        )
        from sqlalchemy import or_

        entity_filters = [
            Fact.content.ilike(f"%{entity}%") for entity in new_entities
        ]
        potentially_related_facts = query.filter(or_(*entity_filters)).all()
        logger.info(
            f"Found {len(potentially_related_facts)} potentially related facts for Fact ID {new_fact.id}.",
        )
        for existing_fact in potentially_related_facts:
            inference = _infer_relationship(new_fact, existing_fact)
            if not inference:
                continue
            relationship_type, score, reason = inference
            if relationship_type == RelationshipType.CONTRADICTION:
                if score > 0.98:
                    logger.info(
                        f"Contradiction found (strong, entity match) between new fact {new_fact.id} and existing fact {existing_fact.id}: {reason}",
                    )
                    mark_fact_objects_as_disputed(
                        self.session,
                        existing_fact,
                        new_fact,
                    )
                    return None  # Signal that this fact should not be indexed
                logger.info(
                    f"Potential contradiction (not disputed) between new fact {new_fact.id} and existing fact {existing_fact.id}: {reason}",
                )
                # Optionally, flag for review or log for future analysis
                continue
            if relationship_type == RelationshipType.CORRELATION:
                logger.info(
                    f"Corroboration found between new fact {new_fact.id} and existing fact {existing_fact.id}",
                )
                score_increase = int(score * 5)
                new_fact.score += score_increase
                existing_fact.score += score_increase
                insert_relationship_object(
                    self.session,
                    new_fact,
                    existing_fact,
                    score_increase,
                    relationship_type,
                )
            else:
                insert_relationship_object(
                    self.session,
                    new_fact,
                    existing_fact,
                    int(score * 5),
                    relationship_type,
                )
        return new_fact
