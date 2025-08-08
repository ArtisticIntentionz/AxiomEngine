# Axiom - ledger.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
# --- UNIFIED V2 VERSION WITH ALL REQUIRED FUNCTIONS ---

from __future__ import annotations
import sys
import logging
import hashlib
import datetime
import json
from typing import cast

from spacy.ml import Doc
from sqlalchemy import Engine, ForeignKey, String, Integer, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from common import NLP_MODEL

logger = logging.getLogger("ledger")

stdout_handler = logging.StreamHandler(stream=sys.stdout)
stdout_handler.setFormatter(
    logging.Formatter(
        "[%(name)s] %(asctime)s | %(levelname)s | %(filename)s:%(lineno)s >>> %(message)s"
    )
)

logger.addHandler(stdout_handler)
logger.setLevel(logging.INFO)

DB_NAME = "axiom_ledger.db"
ENGINE = create_engine(f"sqlite:///{DB_NAME}")


class LedgerError(BaseException): ...


class Base(DeclarativeBase): ...


class Fact(Base):
    __tablename__ = "fact"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content: Mapped[str] = mapped_column(String, default="", nullable=False)
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    disputed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    hash: Mapped[str] = mapped_column(String, default="", nullable=False)
    last_checked: Mapped[str] = mapped_column(
        String, default=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(), nullable=False
    )
    semantics: Mapped[str] = mapped_column(String, default="{}", nullable=False) # holds JSON string
    """
        {
            "doc": str,
            "subject": str,
            "object": str,
        }
    """

    sources: Mapped[list[Source]] = relationship(
        "Source", secondary="fact_source_link", back_populates="facts"
    )
    links: Mapped[list["FactLink"]] = relationship(
        "FactLink",
        primaryjoin="or_(Fact.id == FactLink.fact1_id, Fact.id == FactLink.fact2_id)",
        viewonly=True,
    )

    @property
    def corroborated(self) -> bool:
        return cast(bool, self.score > 0)

    def has_source(self, domain: str) -> bool:
        return any(source.domain == domain for source in self.sources)

    def set_hash(self):
        self.hash = hashlib.sha256(self.content.encode("utf-8")).hexdigest()

    def get_semantics(self) -> dict:
        return json.loads(self.semantics)
    
    def set_semantics(self, semantics: dict):
        self.semantics = json.dumps(semantics)

    @staticmethod
    def get_doc(semantics: dict) -> Doc:
        return Doc(NLP_MODEL.vocab).from_json(semantics["doc"])
    
    @staticmethod
    def set_doc(semantics: dict, doc: Doc):
        semantics["doc"] = doc.to_json()


class Source(Base):
    __tablename__ = "source"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    domain: Mapped[str] = mapped_column(String, nullable=False)

    facts: Mapped[list["Fact"]] = relationship(
        "Fact", secondary="fact_source_link", back_populates="sources"
    )


class FactSourceLink(Base):
    __tablename__ = "fact_source_link"

    fact_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("fact.id"), primary_key=True
    )
    source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("source.id"), primary_key=True
    )


class FactLink(Base):
    __tablename__ = "fact_link"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    score: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # >0 strong bond, -1 contradicting

    fact1_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("fact.id"), nullable=False
    )
    fact1: Mapped["Fact"] = relationship("Fact", foreign_keys=[fact1_id])

    fact2_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("fact.id"), nullable=False
    )
    fact2: Mapped["Fact"] = relationship("Fact", foreign_keys=[fact2_id])


def initialize_database(engine: Engine):
    """
    Ensures the database file and ALL required tables ('facts', 'fact_relationships') exist.
    """
    Base.metadata.create_all(engine)
    logger.info("initialized database")


def get_all_facts_for_analysis(session: Session) -> list[Fact]:
    """Retrieves all facts."""
    return session.query(Fact).all()


def add_fact_corroboration(session: Session, fact_id: int, source_id: int):
    """Increments a fact's trust score and add the source to it. Both must already exist"""

    fact = session.get(Fact, fact_id)
    source = session.get(Source, source_id)

    if fact is None:
        logger.error(f"fact not found: {fact_id=}")
        raise LedgerError(f"fact not found: {fact_id=}")

    if source is None:
        logger.error(f"source not found: {source_id=}")
        raise LedgerError(f"source not found: {source_id=}")

    add_fact_object_corroboration(fact, source)

def add_fact_object_corroboration(fact: Fact, source: Source):
    """ Increments a fact's trust score and add the source to it. Does nothing if the source already exists. """
    if source not in fact.sources:
        fact.sources.append(source)
        fact.score += 1
        logger.info(f"corroborated existing fact {fact.id} {fact.score=} with source {source.id}")


def insert_uncorroborated_fact(session: Session, content: str, source_id: int):
    """Inserts a fact for the first time. The source must exist."""

    source = session.get(Source, source_id)

    if source is None:
        logger.error(f"source not found: {source_id=}")
        raise LedgerError(f"source not found: {source_id=}")

    fact = Fact(content=content, score=0, sources=[source])
    fact.set_hash()
    session.add(fact)
    logger.info(f"inserted uncorroborated fact {fact.id=}")


def insert_relationship(session: Session, fact_id_1: int, fact_id_2: int, score: int):
    """Inserts a relationship between two facts into the knowledge graph. Both facts must exist."""

    fact1 = session.get(Fact, fact_id_1)
    fact2 = session.get(Fact, fact_id_2)

    if fact1 is None:
        logger.error(f"fact not found: {fact_id_1=}")
        raise LedgerError(f"fact(s) not found: {fact_id_1=}")

    if fact2 is None:
        logger.error(f"fact not found: {fact_id_2=}")
        raise LedgerError(f"fact(s) not found: {fact_id_2=}")

    link = FactLink(
        score=score,
        fact1=fact1,
        fact2=fact2,
    )
    session.add(link)
    logger.info(
        f"inserted relationship between {fact_id_1=} and {fact_id_2=} with {score=}"
    )


def mark_facts_as_disputed(session: Session, original_fact_id: int, new_fact_id: int):
    """
    Marks two facts as disputed and links them together.
    """

    original_fact = session.get(Fact, original_fact_id)
    new_fact = session.get(Fact, new_fact_id)

    if original_fact is None:
        logger.error(f"fact not found: {original_fact_id=}")
        raise LedgerError(f"fact not found: {original_fact_id=}")

    if new_fact is None:
        logger.error(f"fact not found: {new_fact_id=}")
        raise LedgerError(f"fact not found: {new_fact_id=}")

    mark_fact_objects_as_disputed(session, original_fact, new_fact)

def mark_fact_objects_as_disputed(session: Session, original_fact: Fact, new_fact: Fact):
    original_fact.disputed = True
    new_fact.disputed = True
    link = FactLink(
        score=-1,
        fact1=original_fact,
        fact2=new_fact,
    )
    session.add(link)
    logger.info(
        f"marked facts as disputed: {original_fact.id=}, {new_fact.id=}"
    )
