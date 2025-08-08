# Axiom - crucible.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
# --- V2.5: UNIFIED VERSION WITH COMMUNITY REFACTOR AND ROBUST SANITIZATION ---

from dataclasses import dataclass, field
import logging
import sys
import hashlib
import re
from typing import Callable

from spacy.ml import Doc, Span
from sqlalchemy.orm import Session
from axiom_server.ledger import (
    Fact,
    add_fact_object_corroboration,
    get_all_facts_for_analysis,
    insert_relationship_object,
    mark_fact_objects_as_disputed,
    mark_facts_as_disputed,
    insert_uncorroborated_fact,
)
from axiom_server.common import NLP_MODEL, SUBJECTIVITY_INDICATORS

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

# --- OUR UPGRADE: A more robust list of noise patterns to be removed. ---
METADATA_NOISE_PATTERNS = [
    re.compile(r'^\d+\s*'),
    re.compile(r'^(By and\s*)?\d*[\d\s]*(min read|Heard on the Street)\s*', re.IGNORECASE),
    re.compile(r'^Advertisement\s*', re.IGNORECASE)
]

class CrucibleError(BaseException): ...


@dataclass
class Check[T]:
    run: Callable[[T,], bool]
    description: str


@dataclass
class Transformation[T]:
    run: Callable[[T,], T | None]
    description: str


@dataclass
class Pipeline[T]:
    name: str
    steps: list[Check[T]|Transformation[T]]

    def run(self, value: T) -> T | None:
        logger.info(f"running pipeline {self.name} on '{value}'")

        current_value: T | None = value

        for step in self.steps:
            if isinstance(step, Check):
                if not step.run(value):
                    logger.info(f"pipeline stopped after check: {step.description}")
                    return None
                
            if isinstance(step, Transformation):
                try:
                    current_value = step.run(current_value)

                except Exception as e:
                    logger.exception(
                        f"transformation error '{step.description}' ({e})"
                    )
                    raise CrucibleError(
                        f"transformation error '{step.description}' ({e})"
                    )

                if current_value is None:
                    logger.info(f"pipeline stopped after transformation '{step.description}'")
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
        Check(lambda sent: len(sent.text.split()) >= 8, "sentence minimal length"),
        Check(lambda sent: len(sent.text.split()) <= 100, "sentence maximal length"),
        Check(lambda sent: len(sent.ents) > 0, "sentence must contain entities"),
        Check(
            lambda sent: any(
                indicator in sent.text.lower() for indicator in SUBJECTIVITY_INDICATORS
            ),
            "sentence contains subjective wording",
        ),
    ],
)


def has_subject_and_object(fact: Fact) -> bool:
    subject, object = _get_subject_and_object(Fact.get_doc(fact.get_semantics()))
    return subject is not None and object is not None

def set_subject_and_object(fact: Fact) -> Fact|None:
    semantics = fact.get_semantics()
    subject, object = _get_subject_and_object(Fact.get_doc(semantics))
    assert subject is not None and object is not None
    semantics["subject"] = subject
    semantics["object"] = object
    fact.set_semantics(semantics)
    return fact


FACT_PREANALYSIS: Pipeline[Fact] = Pipeline(
    "Fact Preanalysis",
    [
        Check(has_subject_and_object, "the fact must have a subject and object"),
        Transformation(set_subject_and_object, "precomputing the subject and object")
    ],
)


def _get_subject_and_object(doc: Doc) -> tuple[str | None, str | None]:
    """A helper function to extract the main subject and object from a spaCy doc."""
    subject = None
    d_object = None

    for token in doc:
        if "nsubj" in token.dep_:
            subject = token.lemma_.lower()

        if "dobj" in token.dep_ or "pobj" in token.dep_ or "attr" in token.dep_:
            d_object = token.lemma_.lower()

    return subject, d_object


def extract_facts_from_text(text_content: str) -> list[Fact]:
    """
    The main V2.2 Crucible pipeline. It now sanitizes text before analysis.
    It outputs Facts that are not added to the database and not linked to any source.
    It only has pre computed semantics, and went through the FACT_PREANALYSIS pipeline.
    """
    facts: list[Fact] = []
    sanitized_text = TEXT_SANITIZATION.run(text_content)

    if sanitized_text is None:
        logger.info(f"text sanitizer rejected input content, returning no facts")
        return [ ]

    doc = NLP_MODEL(sanitized_text)

    for sentence in doc.sents:
        if (sentence := SENTENCE_CHECKS.run(sentence)) is not None:
            fact = Fact(content=sentence.text.strip())
            semantics = { }
            Fact.set_doc(semantics, sentence.as_doc())
            fact.set_semantics(semantics)

            if (fact := FACT_PREANALYSIS.run(fact)) is not None:
                facts.append(fact)

    return facts


def check_contradiction(
    existing_fact: Fact, existing_semantics: dict, existing_doc: Doc, existing_subject: str, existing_object: str,
    new_fact: Fact, new_semantics: dict, new_doc: Doc, new_subject: str, new_object: str
) -> bool:
    if new_subject == existing_subject and new_object != existing_object:
        new_is_negated = any(tok.dep_ == "neg" for tok in new_doc)
        existing_is_negated = any(tok.dep_ == "neg" for tok in existing_doc)
        return new_is_negated != existing_is_negated or (not new_is_negated and not existing_is_negated)
    
    return False


def check_corroboration(
    existing_fact: Fact, existing_semantics: dict, existing_doc: Doc, existing_subject: str, existing_object: str,
    new_fact: Fact, new_semantics: dict, new_doc: Doc, new_subject: str, new_object: str
) -> bool:
    return existing_fact.content[:50] == new_fact.content[:50]


@dataclass
class CrucibleFactAdder:
    session: Session
    contradiction_count: int = 0 # count of facts contradicted
    corroboration_count: int = 0 # count of facts corroborated
    addition_count: int = 0
    existing_facts: list[Fact] = field(default_factory=lambda : [ ])

    def add(self, fact: Fact):
        """
            fact is assumed to already exist in the database
        """
        assert fact.id is not None

        pipeline = Pipeline(
            "Crucible Fact Addition",
            [
                Transformation(self._set_hash, "Computing"),
                Transformation(self._contradiction_check, "Contradiction Check"),
                Transformation(self._corroborate_against_existing_facts, "Corroboration against existing facts"),
                Transformation(self._detect_relationships, "Relationship strength detection")
            ]
        )

        self._load_all_facts()
        pipeline.run(fact)
        self.session.commit()

    def _load_all_facts(self):
        self.existing_facts = self.session.query(Fact).all()

    def _set_hash(self, fact: Fact) -> Fact|None:
        fact.set_hash()
        return fact

    def _contradiction_check(self, fact: Fact) -> Fact|None:
        """ check with all existing facts if it contradicts with any, changing database accordingly """
        new_semantics = fact.get_semantics()
        new_subject, new_object = new_semantics["subject"], new_semantics["object"]
        new_doc = Fact.get_doc(new_semantics)

        for existing_fact in self.existing_facts:
            if existing_fact == fact:
                continue

            if existing_fact.disputed:
                continue

            existing_semantics = existing_fact.get_semantics()
            existing_subject, existing_object = existing_semantics["subject"], existing_semantics["object"]
            existing_doc = Fact.get_doc(existing_semantics)

            if check_contradiction(
                existing_fact, existing_semantics, existing_doc,
                existing_subject, existing_object,
                fact, new_semantics, new_doc,
                new_subject, new_object
            ):
                mark_fact_objects_as_disputed(self.session, existing_fact, fact)
                self.session.commit()
                self.contradiction_count += 1
                logger.info(f"Contradiction found between '{fact.id=}' and '{existing_fact.id=}'")

        return fact

    def _corroborate_against_existing_facts(self, fact: Fact) -> Fact|None:
        new_semantics = fact.get_semantics()
        new_subject, new_object = new_semantics["subject"], new_semantics["object"]
        new_doc = Fact.get_doc(new_semantics)

        for existing_fact in self.existing_facts:
            if existing_fact == fact:
                continue

            existing_semantics = existing_fact.get_semantics()
            existing_subject, existing_object = existing_semantics["subject"], existing_semantics["object"]
            existing_doc = Fact.get_doc(existing_semantics)

            if check_corroboration(
                existing_fact, existing_semantics, existing_doc,
                existing_subject, existing_object,
                fact, new_semantics, new_doc,
                new_subject, new_object
            ):
                for source in fact.sources:
                    add_fact_object_corroboration(existing_fact, source)

        return fact
    
    def _detect_relationships(self, fact: Fact) -> Fact|None:
        new_semantics = fact.get_semantics()
        new_doc = Fact.get_doc(new_semantics)
        new_entities = { ent.text.lower() for ent in new_doc.ents }

        for existing_fact in self.existing_facts:
            if existing_fact == fact:
                continue

            existing_semantics = existing_fact.get_semantics()
            existing_doc = Fact.get_doc(existing_semantics)
            existing_entities = { ent.text.lower() for ent in existing_doc.ents }

            score = len(new_entities & existing_entities)

            if score > 0:
                insert_relationship_object(self.session, fact, existing_fact, score)

        return fact
