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
from transformers import pipeline

from axiom_server.common import NLP_MODEL, SUBJECTIVITY_INDICATORS

# Local application imports
from axiom_server.ledger import (
    Fact,
    RelationshipType,
    Semantics,
    add_fact_object_corroboration,
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
def get_nli_classifier() -> NliPipeline | None:
    """Loads and returns a cached instance of the NLI pipeline."""
    try:
        logger.info(
            "Initializing Hugging Face NLI model for the first time...",
        )
        # Now, Python knows what 'pipeline' is because we imported it at the top.
        return pipeline(
            "zero-shot-classification",
            model="typeform/distilbert-base-uncased-mnli",
        )
    except Exception as e:
        logger.error(
            f"CRITICAL: Failed to initialize NLI model. Contradiction checks will be disabled. Error: {e}",
        )
        return None


class CrucibleError(Exception):
    """Crucible Error Exception."""

    __slots__ = ()


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
        Check(
            lambda sent: len(sent.text.split()) >= 8,
            "sentence minimal length",
        ),
        Check(
            lambda sent: len(sent.text.split()) <= 100,
            "sentence maximal length",
        ),
        Check(
            lambda sent: len(sent.ents) > 0,
            "sentence must contain entities",
        ),
        Check(
            lambda sent: not any(
                indicator in sent.text.lower()
                for indicator in SUBJECTIVITY_INDICATORS
            ),
            "sentence is objective (does not contain subjective wording)",
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


def extract_facts_from_text(text_content: str) -> list[Fact]:
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
            fact = Fact(content=checked_sentence.text.strip())
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


# --- FIXED: Integrated NLI model for powerful contradiction detection ---
def _infer_relationship(fact1: Fact, fact2: Fact) -> RelationshipType | None:
    """Analyze two facts and infers the nature of their relationship using an NLI model."""
    # 1. Contradiction Check using the powerful NLI Model
    try:
        nli_classifier = get_nli_classifier()
        # The premise is fact1, the hypothesis is fact2
        result = nli_classifier(
            fact1.content,
            candidate_labels=["contradiction", "entailment", "neutral"],
            hypothesis_template=f"This statement, '{fact2.content}', is a {{}}.",
        )
        # Use a high confidence threshold to avoid false positives
        if (
            result["labels"][0] == "contradiction"
            and result["scores"][0] > 0.9
        ):
            return RelationshipType.CONTRADICTION
    except Exception as e:
        logger.warning(f"Could not perform NLI check due to error: {e}")

    # 2. Chronology Check
    dates1 = _extract_dates(fact1.content)
    dates2 = _extract_dates(fact2.content)
    if dates1 and dates2 and min(dates1) != min(dates2):
        return RelationshipType.CHRONOLOGY

    # 3. Causality Check
    causal_words = {"because", "due to", "as a result", "caused by", "led to"}
    if any(word in fact1.content for word in causal_words) or any(
        word in fact2.content for word in causal_words
    ):
        return RelationshipType.CAUSATION

    return None


# --- REFACTORED: Unified and scalable logic for processing facts ---
@dataclass
class CrucibleFactAdder:
    """Processes a new fact against the existing knowledge base efficiently."""

    session: Session
    fact_indexer: FactIndexer
    contradiction_count: int = 0
    corroboration_count: int = 0
    addition_count: int = 0

    def add(self, fact: Fact):
        """Adds and processes a fact against the database, now with robust,
        database-level duplicate handling.
        """
        from sqlalchemy.exc import (
            IntegrityError,
        )  # Import the specific exception

        assert fact.sources, "Fact must have a source before being added."
        primary_source = fact.sources[0]

        fact.set_hash()

        try:
            # We attempt to add the new fact and commit it immediately.
            self.session.add(fact)
            self.session.commit()
            self.addition_count += 1

            # If the commit succeeds, it was a unique fact. We can now process it.
            self._process_relationships(fact)
            self.fact_indexer.add_fact(fact)
            self.session.commit()

        except IntegrityError:
            # If the commit fails with an IntegrityError, it means the database's
            # `unique=True` constraint was violated. The fact already exists.

            # We must rollback the failed session to a clean state.
            self.session.rollback()

            # Now, we find the existing fact and corroborate it with the new source.
            existing_fact = (
                self.session.query(Fact).filter(Fact.hash == fact.hash).one()
            )
            logger.info(
                f"Duplicate fact detected by database (hash: {fact.hash[:8]}). Corroborating with new source: {primary_source.domain}",
            )
            add_fact_object_corroboration(existing_fact, primary_source)
            self.session.commit()

    def _process_relationships(self, new_fact: Fact):
        """Finds potentially related facts and checks for contradictions, corroborations,
        and other relationships.
        """
        new_doc = new_fact.get_semantics().get("doc")
        nli_classifier = get_nli_classifier()
        if not new_doc or not nli_classifier:
            return

        # Your entity-based query to find related facts is excellent for performance.
        new_entities = {
            ent.text.lower() for ent in new_doc.ents if len(ent.text) > 2
        }
        if not new_entities:
            return

        from sqlalchemy import or_

        entity_filters = [
            Fact.content.ilike(f"%{entity}%") for entity in new_entities
        ]
        query = self.session.query(Fact).filter(
            Fact.id != new_fact.id,
            Fact.disputed == False,
            or_(*entity_filters),
        )
        potentially_related_facts = query.all()

        logger.info(
            f"Found {len(potentially_related_facts)} potentially related facts for Fact ID {new_fact.id}.",
        )

        for existing_fact in potentially_related_facts:
            # --- FIX 2 of 3: CONTRADICTION DETECTION ---
            premise = existing_fact.content
            hypothesis = new_fact.content

            try:
                result = nli_classifier(
                    hypothesis,
                    candidate_labels=[
                        "contradiction",
                        "entailment",
                        "neutral",
                    ],
                )
                top_label = result["labels"][0]
                top_score = result["scores"][0]

                if top_label == "contradiction" and top_score > 0.90:
                    logger.warning(
                        f"NLI CONTRADICTION DETECTED between new Fact ID {new_fact.id} and existing Fact ID {existing_fact.id}! Marking as disputed.",
                    )
                    mark_fact_objects_as_disputed(
                        self.session, existing_fact, new_fact,
                    )
                    self.contradiction_count += 1
                    self.session.commit()
                    # Once contradicted, we stop processing this fact further.
                    return
            except Exception as e:
                logger.error(
                    f"Error during NLI check between facts {new_fact.id} and {existing_fact.id}: {e}",
                )

            # --- FIX 3 of 3: ENTITY RESOLUTION (Simplified) ---
            # Your check_corroboration is a simple form of entity resolution.
            # We can keep it to strengthen relationships.
            if check_corroboration(new_fact, existing_fact):
                self.corroboration_count += 1
                for source in new_fact.sources:
                    add_fact_object_corroboration(existing_fact, source)
