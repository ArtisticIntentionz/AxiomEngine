# Axiom - ledger.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
# --- V3.1: FINAL, UNIFIED BLOCKCHAIN ORM LEDGER ---

from __future__ import annotations

import sys
import logging
import hashlib
import datetime
import json
import time
from typing import cast

from spacy.tokens.doc import Doc
from sqlalchemy import (
    create_engine, Engine, ForeignKey, String, Integer, 
    Boolean, Text, Float
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, relationship, 
    sessionmaker, Session
)
from pydantic import BaseModel

from .common import NLP_MODEL

from typing_extensions import Self, NotRequired, TypedDict


logger = logging.getLogger("ledger")

stdout_handler = logging.StreamHandler(stream=sys.stdout)
stdout_handler.setFormatter(
    logging.Formatter(
        "[%(name)s] %(asctime)s | %(levelname)s | %(filename)s:%(lineno)s >>> %(message)s"
    )
)
logger.addHandler(stdout_handler)
logger.setLevel(logging.INFO)
logger.propagate = False

DB_NAME = "axiom_ledger.db"
ENGINE = create_engine(f"sqlite:///{DB_NAME}")
SessionMaker = sessionmaker(bind=ENGINE)

class LedgerError(BaseException): __slots__ = ()
class Base(DeclarativeBase): __slots__ = ()

class Block(Base):
    __tablename__ = "blockchain"
    height: Mapped[int] = mapped_column(Integer, primary_key=True)
    hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    previous_hash: Mapped[str] = mapped_column(String, nullable=False)
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    nonce: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fact_hashes: Mapped[str] = mapped_column(Text, nullable=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.nonce = self.nonce or 0

    def calculate_hash(self) -> str:
        block_string = json.dumps({
            "height": self.height, "previous_hash": self.previous_hash,
            "fact_hashes": sorted(json.loads(self.fact_hashes)),
            "timestamp": self.timestamp, "nonce": self.nonce
        }, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def seal_block(self, difficulty: int) -> None:
        self.hash = self.calculate_hash()
        target = '0' * difficulty
        while not self.hash.startswith(target):
            self.nonce += 1
            self.hash = self.calculate_hash()
        logger.info(f"Block sealed! Hash: {self.hash}")

class SerializedSemantics(BaseModel):
    doc: str
    subject: str
    object: str

class Semantics(TypedDict):
    doc: Doc
    subject: str
    object: str

def semantics_from_serialized(serialized: SerializedSemantics) -> Semantics:
    """Correctly deserializes the semantics from the database."""
    return Semantics(
        {

            # We now correctly parse the JSON string of the doc object.
            "doc": Doc(NLP_MODEL.vocab).from_json(
                json.loads(serialized.doc)
            ),
            "subject": serialized.subject,
            "object": serialized.object,
        }
    )

class Fact(Base):
    __tablename__ = "fact"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content: Mapped[str] = mapped_column(String, default="", nullable=False)
    status: Mapped[str] = mapped_column(String, default="ingested", nullable=False)
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    disputed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    hash: Mapped[str] = mapped_column(String, default="", nullable=False)
    last_checked: Mapped[str] = mapped_column(String, default=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(), nullable=False)
    semantics: Mapped[str] = mapped_column(String, default="{}", nullable=False)
    sources: Mapped[list[Source]] = relationship("Source", secondary="fact_source_link", back_populates="facts")
    links: Mapped[list["FactLink"]] = relationship("FactLink", primaryjoin="or_(Fact.id == FactLink.fact1_id, Fact.id == FactLink.fact2_id)", viewonly=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.status = self.status or "ingested"

    @classmethod
    def from_model(cls, model: SerializedFact) -> Self:
        return cls(
            content=model.content,
            score=model.score,
            disputed=model.disputed,
            hash=model.hash,
            last_checked=model.last_checked,
            semantics=model.semantics.model_dump_json(),
        )

    @property
    def corroborated(self) -> bool:
        return self.score > 0

    def has_source(self, domain: str) -> bool:
        return any(source.domain == domain for source in self.sources)

    def set_hash(self) -> None:
        self.hash = hashlib.sha256(self.content.encode("utf-8")).hexdigest()

    def get_serialized_semantics(self) -> SerializedSemantics:
        return SerializedSemantics.model_validate_json(self.semantics)

    def get_semantics(self) -> Semantics:
        serializable = self.get_serialized_semantics()
        return semantics_from_serialized(serializable)

    def set_semantics(self, semantics: Semantics) -> None:
        """Correctly serializes the semantics for database storage."""
        # We now correctly convert the doc object to a JSON *string*
        # before storing it in the main semantics dictionary.
        self.semantics = json.dumps({
            "doc": json.dumps(semantics["doc"].to_json()),
            "subject": semantics["subject"],
            "object": semantics["object"],
        })

class SerializedFact(BaseModel):
    content: str
    score: int
    disputed: bool
    hash: str
    last_checked: str
    semantics: SerializedSemantics
    sources: list[str]

    @classmethod
    def from_fact(cls, fact: Fact) -> Self:
        return cls(
            content=fact.content,
            score=fact.score,
            disputed=fact.disputed,
            hash=fact.hash,
            last_checked=fact.last_checked,
            semantics=fact.get_serialized_semantics(),
            sources=[source.domain for source in fact.sources],
        )

class Source(Base):
    __tablename__ = "source"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    domain: Mapped[str] = mapped_column(String, nullable=False)
    facts: Mapped[list["Fact"]] = relationship("Fact", secondary="fact_source_link", back_populates="sources")

class FactSourceLink(Base):
    __tablename__ = "fact_source_link"
    fact_id: Mapped[int] = mapped_column(Integer, ForeignKey("fact.id"), primary_key=True)
    source_id: Mapped[int] = mapped_column(Integer, ForeignKey("source.id"), primary_key=True)

class FactLink(Base):
    __tablename__ = "fact_link"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    fact1_id: Mapped[int] = mapped_column(Integer, ForeignKey("fact.id"), nullable=False)
    fact1: Mapped["Fact"] = relationship("Fact", foreign_keys=[fact1_id])
    fact2_id: Mapped[int] = mapped_column(Integer, ForeignKey("fact.id"), nullable=False)
    fact2: Mapped["Fact"] = relationship("Fact", foreign_keys=[fact2_id])

def initialize_database(engine: Engine) -> None:
    Base.metadata.create_all(engine)
    logger.info("initialized database")

def get_latest_block(session: Session) -> Block | None:
    return session.query(Block).order_by(Block.height.desc()).first()

def create_genesis_block(session: Session) -> None:
    if get_latest_block(session): return
    genesis = Block(height=0, previous_hash="0", fact_hashes=json.dumps([]), timestamp=time.time())
    genesis.seal_block(difficulty=2)
    session.add(genesis)
    session.commit()
    logger.info("Genesis Block created and sealed.")

def get_all_facts_for_analysis(session: Session) -> list[Fact]:
    return session.query(Fact).all()

def add_fact_corroboration(session: Session, fact_id: int, source_id: int) -> None:
    fact = session.get(Fact, fact_id)
    source = session.get(Source, source_id)
    if fact is None: raise LedgerError(f"fact not found: {fact_id=}")
    if source is None: raise LedgerError(f"source not found: {source_id=}")
    add_fact_object_corroboration(fact, source)

def add_fact_object_corroboration(fact: Fact, source: Source) -> None:
    if source not in fact.sources:
        fact.sources.append(source)
        fact.score += 1
        logger.info(f"corroborated existing fact {fact.id} {fact.score=} with source {source.id}")

def insert_uncorroborated_fact(session: Session, content: str, source_id: int) -> None:
    source = session.get(Source, source_id)
    if source is None: raise LedgerError(f"source not found: {source_id=}")
    fact = Fact(content=content, score=0, sources=[source])
    fact.set_hash()
    session.add(fact)
    logger.info(f"inserted uncorroborated fact {fact.id=}")

def insert_relationship(session: Session, fact_id_1: int, fact_id_2: int, score: int) -> None:
    fact1 = session.get(Fact, fact_id_1)
    fact2 = session.get(Fact, fact_id_2)
    if fact1 is None: raise LedgerError(f"fact(s) not found: {fact_id_1=}")
    if fact2 is None: raise LedgerError(f"fact(s) not found: {fact_id_2=}")
    insert_relationship_object(session, fact1, fact2, score)

def insert_relationship_object(session: Session, fact1: Fact, fact2: Fact, score: int) -> None:
    link = FactLink(score=score, fact1=fact1, fact2=fact2)
    session.add(link)
    logger.info(f"inserted relationship between {fact1.id=} and {fact2.id=} with {score=}")

def mark_facts_as_disputed(session: Session, original_fact_id: int, new_fact_id: int) -> None:
    original_fact = session.get(Fact, original_fact_id)
    new_fact = session.get(Fact, new_fact_id)
    if original_fact is None: raise LedgerError(f"fact not found: {original_fact_id=}")
    if new_fact is None: raise LedgerError(f"fact not found: {new_fact_id=}")
    mark_fact_objects_as_disputed(session, original_fact, new_fact)

def mark_fact_objects_as_disputed(session: Session, original_fact: Fact, new_fact: Fact) -> None:
    original_fact.disputed = True
    new_fact.disputed = True
    link = FactLink(score=-1, fact1=original_fact, fact2=new_fact)
    session.add(link)
    logger.info(f"marked facts as disputed: {original_fact.id=}, {new_fact.id=}")

class Votes(TypedDict):
    choice: str
    weight: float

class Proposal(TypedDict):
    text: str
    proposer: str
    votes: dict[str, Votes]