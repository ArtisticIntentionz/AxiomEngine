# Axiom - crucible.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
# --- V2.5: UNIFIED VERSION WITH COMMUNITY REFACTOR AND ROBUST SANITIZATION ---

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import sys
import hashlib
import re
from typing import TYPE_CHECKING, Generic, TypeVar

from spacy.tokens.doc import Doc
from spacy.tokens.span import Span
from sqlalchemy.orm import Session

from axiom_server.ledger import (
    Fact,
    add_fact_object_corroboration,
    get_all_facts_for_analysis,
    insert_relationship_object,
    mark_fact_objects_as_disputed,
    mark_facts_as_disputed,
    insert_uncorroborated_fact,
    Semantics,
)
from axiom_server.common import NLP_MODEL, SUBJECTIVITY_INDICATORS

if TYPE_CHECKING:
    from collections.abc import Callable


T = TypeVar("T")

# Community Change: Professional logging setup.
logger = logging.getLogger("crucible")
stdout_handler = logging.StreamHandler(stream=sys.stdout)
stdout_handler.setFormatter(
    logging.Formatter(
        "[%(name)s] %(asctime)s | %(levelname)s | %(filename)s:%(lineno)s >>> %(message)s"
    )
)
logger.addHandler(stdout_handler)
logger.setLevel(logging.INFO)
logger.propagate = False

# --- OUR UPGRADE: A more robust list of noise patterns to be removed. ---
METADATA_NOISE_PATTERNS = (
    re.compile(r"^\d+\s*"),
    re.compile(
        r"^(By and\s*)?\d*[\d\s]*(min read|Heard on the Street)\s*",
        re.IGNORECASE,
    ),
    re.compile(r"^Advertisement\s*", re.IGNORECASE),
)


class CrucibleError(BaseException):
    __slots__ = ()


@dataclass
class Check(Generic[T]):
    run: Callable[[T], bool]
    description: str


@dataclass
class Transformation(Generic[T]):
    run: Callable[[T], T | None]
    description: str


@dataclass
class Pipeline(Generic[T]):
    name: str
    steps: list[Check[T] | Transformation[T]]

    def run(self, value: T) -> T | None:
        logger.info(f"running pipeline '{self.name}' on '{value}'")

        current_value: T | None = value

        for step in self.steps:
            if isinstance(step, Check):
                if not step.run(value):
                    logger.info(
                        f"pipeline stopped after check: {step.description}"
                    )
                    return None

            if isinstance(step, Transformation):
                try:
                    assert current_value is not None
                    current_value = step.run(current_value)

                except Exception as e:
                    logger.exception(
                        f"transformation error '{step.description}' ({e})"
                    )
                    raise CrucibleError(
                        f"transformation error '{step.description}' ({e})"
                    )

                if current_value is None:
                    logger.info(
                        f"pipeline stopped after transformation '{step.description}'"
                    )
                    break

        logger.info(f"pipeline is done and returning '{current_value}'")
        return current_value


TEXT_SANITIZATION: Pipeline[str] = Pipeline(
    "text sanitization",
    [
        Transformation(lambda text: text.lower(), "Convert text to lowercase"),
        Transformation(
            lambda text: re.sub(r"^\d+[\d\s]*min read\s*", "", text),
            "Remove read times and comment counts (e.g., '42 2 min read ')",
        ),
        Transformation(
            lambda text: (
                text.lstrip("advertisement ")
                if text.startswith("advertisement ")
                else text
            ),
            "Remove 'Advertisement' from the start of a sentence (case-insensitive)",
        ),
        Transformation(
            lambda text: re.sub(r"(\d{4})([A-Z])", r"\1. \2", text),
            "Fix run-on sentences common in topic pages",
        ),
        Transformation(
            lambda text: re.sub(r"\s+", " ", text).strip(),
            "Standardize all whitespace to single spaces",
        ),
    ],
)


SENTENCE_CHECKS: Pipeline[Span] = Pipeline(
    "sentence sanitization",
    [
        Check(
            lambda sent: len(sent.text.split()) >= 8, "sentence minimal length"
        ),
        Check(
            lambda sent: len(sent.text.split()) <= 100,
            "sentence maximal length",
        ),
        Check(
            lambda sent: len(sent.ents) > 0, "sentence must contain entities"
        ),
        Check(
            lambda sent: any(
                indicator in sent.text.lower()
                for indicator in SUBJECTIVITY_INDICATORS
            ),
            "sentence contains subjective wording",
        ),
    ],
)


def has_subject_and_object(fact: Fact) -> bool:
    subject, object_ = _get_subject_and_object(fact.get_semantics()["doc"])
    return subject is not None and object_ is not None


def set_subject_and_object(fact: Fact) -> Fact:
    semantics = fact.get_semantics()
    subject, object_ = _get_subject_and_object(semantics["doc"])
    assert subject is not None
    assert object_ is not None
    semantics["subject"] = subject
    semantics["object"] = object_
    fact.set_semantics(semantics)
    return fact


FACT_PREANALYSIS: Pipeline[Fact] = Pipeline(
    "Fact Preanalysis",
    [ ],
)


def _get_subject_and_object(doc: Doc) -> tuple[str | None, str | None]:
    """A helper function to extract the main subject and object from a spaCy doc."""
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


def semantics_check_and_set_subject_object(semantics: Semantics) -> Semantics|None:
    subject, object_ = _get_subject_and_object(semantics["doc"])
    if subject is None or object_ is None: return None
    semantics["subject"] = subject
    semantics["object"] = object_
    return semantics

SEMANTICS_CHECKS = Pipeline(
    "semantics checks",
    [
        Transformation(
            semantics_check_and_set_subject_object,
            "check for presence of subject and object"
        )
    ]
)


def extract_facts_from_text(text_content: str) -> list[Fact]:
    """
    The main V2.2 Crucible pipeline. It now sanitizes text before analysis.
    It outputs Facts that are not added to the database and not linked to any source.
    It only has pre computed semantics, and went through the FACT_PREANALYSIS pipeline.
    """
    facts: list[Fact] = []
    sanitized_text = TEXT_SANITIZATION.run(text_content)

    if sanitized_text is None:
        logger.info(
            f"text sanitizer rejected input content, returning no facts"
        )
        return []

    doc = NLP_MODEL(sanitized_text)

    fact: Fact | None
    sentence: Span | None

    for sentence in doc.sents:
        if (sentence := SENTENCE_CHECKS.run(sentence)) is not None:
            fact = Fact(content=sentence.text.strip())
            semantics = Semantics(
                { "doc": sentence.as_doc(), "object": "", "subject": "" }
            )

            if (semantics := SEMANTICS_CHECKS.run(semantics)) is not None:
                fact.set_semantics(semantics)

                if (fact := FACT_PREANALYSIS.run(fact)) is not None:
                    facts.append(fact)

    return facts


def check_contradiction(
    existing_fact: Fact,
    existing_semantics: Semantics,
    existing_doc: Doc,
    existing_subject: str,
    existing_object: str,
    new_fact: Fact,
    new_semantics: Semantics,
    new_doc: Doc,
    new_subject: str,
    new_object: str,
) -> bool:
    if new_subject == existing_subject and new_object != existing_object:
        new_is_negated = any(tok.dep_ == "neg" for tok in new_doc)
        existing_is_negated = any(tok.dep_ == "neg" for tok in existing_doc)
        return new_is_negated != existing_is_negated or (
            not new_is_negated and not existing_is_negated
        )

    return False


def check_corroboration(
    existing_fact: Fact,
    existing_semantics: Semantics,
    existing_doc: Doc,
    existing_subject: str,
    existing_object: str,
    new_fact: Fact,
    new_semantics: Semantics,
    new_doc: Doc,
    new_subject: str,
    new_object: str,
) -> bool:
    return bool(existing_fact.content[:50] == new_fact.content[:50])


@dataclass
class CrucibleFactAdder:
    session: Session
    # count of facts contradicted
    contradiction_count: int = 0
    # count of facts corroborated
    corroboration_count: int = 0
    addition_count: int = 0
    existing_facts: list[Fact] = field(default_factory=lambda: [])

    def add(self, fact: Fact) -> None:
        """fact is assumed to already exist in the database"""
        assert fact.id is not None

        pipeline = Pipeline(
            "Crucible Fact Addition",
            [
                Transformation(self._set_hash, "Computing"),
                Transformation(
                    self._contradiction_check, "Contradiction Check"
                ),
                Transformation(
                    self._corroborate_against_existing_facts,
                    "Corroboration against existing facts",
                ),
                Transformation(
                    self._detect_relationships,
                    "Relationship strength detection",
                ),
            ],
        )

        self._load_all_facts()
        pipeline.run(fact)
        self.session.commit()

    def _load_all_facts(self) -> None:
        self.existing_facts = self.session.query(Fact).all()

    def _set_hash(self, fact: Fact) -> Fact:
        fact.set_hash()
        return fact

    def _contradiction_check(self, fact: Fact) -> Fact:
        """check with all existing facts if it contradicts with any, changing database accordingly"""
        new_semantics = fact.get_semantics()
        new_subject, new_object = (
            new_semantics["subject"],
            new_semantics["object"],
        )
        new_doc = new_semantics["doc"]

        for existing_fact in self.existing_facts:
            if existing_fact == fact:
                continue

            if existing_fact.disputed:
                continue

            existing_semantics = existing_fact.get_semantics()
            existing_subject, existing_object = (
                existing_semantics["subject"],
                existing_semantics["object"],
            )
            existing_doc = existing_semantics["doc"]

            if check_contradiction(
                existing_fact,
                existing_semantics,
                existing_doc,
                existing_subject,
                existing_object,
                fact,
                new_semantics,
                new_doc,
                new_subject,
                new_object,
            ):
                mark_fact_objects_as_disputed(
                    self.session, existing_fact, fact
                )
                self.session.commit()
                self.contradiction_count += 1
                logger.info(
                    f"Contradiction found between '{fact.id=}' and '{existing_fact.id=}'"
                )

        return fact

    def _corroborate_against_existing_facts(self, fact: Fact) -> Fact:
        new_semantics = fact.get_semantics()
        new_subject, new_object = (
            new_semantics["subject"],
            new_semantics["object"],
        )
        new_doc = new_semantics["doc"]

        for existing_fact in self.existing_facts:
            if existing_fact == fact:
                continue

            existing_semantics = existing_fact.get_semantics()
            existing_subject, existing_object = (
                existing_semantics["subject"],
                existing_semantics["object"],
            )
            existing_doc = existing_semantics["doc"]

            if check_corroboration(
                existing_fact,
                existing_semantics,
                existing_doc,
                existing_subject,
                existing_object,
                fact,
                new_semantics,
                new_doc,
                new_subject,
                new_object,
            ):
                for source in fact.sources:
                    add_fact_object_corroboration(existing_fact, source)

        return fact

    def _detect_relationships(self, fact: Fact) -> Fact:
        new_semantics = fact.get_semantics()
        new_doc = new_semantics["doc"]
        new_entities = {ent.text.lower() for ent in new_doc.ents}

        for existing_fact in self.existing_facts:
            if existing_fact == fact:
                continue

            existing_semantics = existing_fact.get_semantics()
            existing_doc = existing_semantics["doc"]
            existing_entities = {ent.text.lower() for ent in existing_doc.ents}

            score = len(new_entities & existing_entities)

            if score > 0:
                insert_relationship_object(
                    self.session, fact, existing_fact, score
                )

        return fact
