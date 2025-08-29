"""Ledger - Fact Database Logic."""

# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.

from __future__ import annotations

import enum
import hashlib
import json
import logging
import sys
import time
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel
from spacy.tokens.doc import Doc
from sqlalchemy import (
    Boolean,
    DateTime,
    Engine,
    Enum,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)
from typing_extensions import Self, TypedDict

from axiom_server import merkle
from axiom_server.common import NLP_MODEL

logger = logging.getLogger("ledger")

stdout_handler = logging.StreamHandler(stream=sys.stdout)
stdout_handler.setFormatter(
    logging.Formatter(
        "[%(name)s] %(asctime)s | %(levelname)s | %(filename)s:%(lineno)s >>> %(message)s",
    ),
)
logger.addHandler(stdout_handler)
logger.setLevel(logging.INFO)
logger.propagate = False

DB_NAME = "axiom_ledger.db"
ENGINE = create_engine(f"sqlite:///{DB_NAME}")
SessionMaker = sessionmaker(bind=ENGINE)


class LedgerError(Exception):
    """Ledger Error."""

    __slots__ = ()


class Base(DeclarativeBase):
    """DeclarativeBase subclass."""

    __slots__ = ()


class FactStatus(str, enum.Enum):
    """Defines the sophisticated verification lifecycle for a Fact."""

    INGESTED = "ingested"
    PROPOSED = "proposed"  # --- FIX: ADDED MISSING STATUS ---
    LOGICALLY_CONSISTENT = "logically_consistent"
    CORROBORATED = "corroborated"
    EMPIRICALLY_VERIFIED = "empirically_verified"


class RelationshipType(str, enum.Enum):
    """Defines the nature of the link between two facts."""

    CORRELATION = "correlation"
    CONTRADICTION = "contradiction"
    CAUSATION = "causation"
    CHRONOLOGY = "chronology"
    ELABORATION = "elaboration"


class Block(Base):
    """Block table."""

    __tablename__ = "blockchain"
    height: Mapped[int] = mapped_column(Integer, primary_key=True)
    hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    previous_hash: Mapped[str] = mapped_column(String, nullable=False)
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    fact_hashes: Mapped[str] = mapped_column(Text, nullable=False)
    merkle_root: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="",
    )
    proposer_pubkey: Mapped[str] = mapped_column(
        String,
        ForeignKey("validators.public_key"),
        nullable=True,
    )
    proposer: Mapped[Validator] = relationship("Validator")

    def calculate_hash(self) -> str:
        """Return hash from this block."""
        # Parse fact hashes and ensure they're sorted consistently
        fact_hashes_list = json.loads(self.fact_hashes)
        if isinstance(fact_hashes_list, list):
            fact_hashes_as_strings = sorted(fact_hashes_list)
        else:
            fact_hashes_as_strings = []

        block_string = json.dumps(
            {
                "height": self.height,
                "previous_hash": self.previous_hash,
                "timestamp": self.timestamp,
                "merkle_root": self.merkle_root,
                "proposer_pubkey": self.proposer_pubkey,
                "fact_hashes": fact_hashes_as_strings,
            },
            sort_keys=True,
        ).encode()
        return hashlib.sha256(block_string).hexdigest()

    def seal_block(self) -> None:
        """Calculate the Merkle Root and finalize the block's hash."""
        fact_hashes_list = json.loads(self.fact_hashes)
        if fact_hashes_list:
            merkle_tree = merkle.MerkleTree(fact_hashes_list)
            self.merkle_root = merkle_tree.root.hex()
        else:
            self.merkle_root = hashlib.sha256(b"").hexdigest()

        self.hash = self.calculate_hash()
        logger.info(f"Block content finalized! Hash: {self.hash}")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary for P2P broadcasting."""
        return {
            "height": self.height,
            "hash": self.hash,
            "previous_hash": self.previous_hash,
            "merkle_root": self.merkle_root,
            "timestamp": self.timestamp,
            "proposer_pubkey": self.proposer_pubkey,
            "fact_hashes": json.loads(
                self.fact_hashes,
            ),  # --- FIX: Include fact hashes for validation ---
        }


class SerializedSemantics(BaseModel):
    """Serialized semantics."""

    doc: str
    subject: str
    object: str


class Semantics(TypedDict):
    """Semantics dictionary."""

    doc: Doc
    subject: str
    object: str


def semantics_from_serialized(serialized: SerializedSemantics) -> Semantics:
    """Return Semantics dictionary from serialized semantics."""
    return Semantics(
        {
            "doc": Doc(NLP_MODEL.vocab).from_json(json.loads(serialized.doc)),
            "subject": serialized.subject,
            "object": serialized.object,
        },
    )


class Fact(Base):
    """A single, objective statement extracted from a source."""

    __tablename__ = "facts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content: Mapped[str] = mapped_column(String, default="", nullable=False)
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[FactStatus] = mapped_column(
        Enum(FactStatus),
        default=FactStatus.INGESTED,
        nullable=False,
    )
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    disputed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    hash: Mapped[str] = mapped_column(
        String,
        default="",
        nullable=False,
        index=True,
    )
    last_checked: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    semantics: Mapped[str] = mapped_column(
        String,
        default="{}",
        nullable=False,
    )

    vector_data: Mapped[FactVector] = relationship(
        back_populates="fact",
        cascade="all, delete-orphan",
    )
    sources: Mapped[list[Source]] = relationship(
        "Source",
        secondary="fact_source_link",
        back_populates="facts",
    )
    links: Mapped[list[FactLink]] = relationship(
        "FactLink",
        primaryjoin="or_(Fact.id == FactLink.fact1_id, Fact.id == FactLink.fact2_id)",
        viewonly=True,
    )

    def __init__(self, **kwargs: Any) -> None:
        """Initialize a new Fact instance and set its hash."""
        super().__init__(**kwargs)
        if self.content:
            self.set_hash()

    @property
    def corroborated(self) -> bool:
        """Return True if the fact has a positive corroboration score."""
        return self.score > 0

    def has_source(self, domain: str) -> bool:
        """Check if the fact is attributed to a source from a specific domain."""
        return any(source.domain == domain for source in self.sources)

    def set_hash(self) -> str:
        """Calculate and set the SHA256 hash of the fact's content."""
        self.hash = hashlib.sha256(self.content.encode("utf-8")).hexdigest()
        return self.hash

    def get_serialized_semantics(self) -> SerializedSemantics:
        """Return the stored semantics as a serialized Pydantic model."""
        try:
            if not self.semantics or self.semantics == "{}" or self.semantics == "null":
                # Return default semantics if none exist
                return SerializedSemantics(
                    doc="{}",
                    subject="",
                    object=""
                )
            return SerializedSemantics.model_validate_json(self.semantics)
        except Exception as e:
            # If validation fails, return default semantics
            logger.warning(f"Failed to validate semantics for fact {self.id}: {e}")
            return SerializedSemantics(
                doc="{}",
                subject="",
                object=""
            )

    def get_semantics(self) -> Semantics:
        """Return the rich, deserialized Semantics object, including the spaCy Doc."""
        serializable = self.get_serialized_semantics()
        return semantics_from_serialized(serializable)

    def set_semantics(self, semantics: Semantics) -> None:
        """Serialize and store the rich Semantics object as a JSON string."""
        self.semantics = json.dumps(
            {
                "doc": json.dumps(semantics["doc"].to_json()),
                "subject": semantics["subject"],
                "object": semantics["object"],
            },
        )


class FactVector(Base):
    """Stores the pre-computed NLP vector for a fact for fast semantic search."""

    __tablename__ = "fact_vectors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fact_id: Mapped[int] = mapped_column(ForeignKey("facts.id"), unique=True)
    vector: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    fact: Mapped[Fact] = relationship(back_populates="vector_data")


class SerializedFact(BaseModel):
    """Serialized Fact table entry."""

    content: str
    score: int
    disputed: bool
    hash: str
    last_checked: str
    semantics: SerializedSemantics
    sources: list[str]

    @classmethod
    def from_fact(cls, fact: Fact) -> Self:
        """Return SerializedFact from Fact."""
        data_for_model: dict[str, Any] = {
            "content": fact.content,
            "score": fact.score,
            "disputed": fact.disputed,
            "hash": fact.hash,
            "last_checked": fact.last_checked.isoformat(),
            "semantics": fact.get_serialized_semantics(),
            "sources": [source.domain for source in fact.sources],
        }
        return cls(**data_for_model)


class Source(Base):
    """Source table entry."""

    __tablename__ = "source"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    domain: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    source_type: Mapped[str] = mapped_column(
        String,
        default="secondary",
        nullable=False,
    )
    credibility_score: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        nullable=False,
    )

    facts: Mapped[list[Fact]] = relationship(
        "Fact",
        secondary="fact_source_link",
        back_populates="sources",
    )


class FactSourceLink(Base):
    """Fact Source Link table entry."""

    __tablename__ = "fact_source_link"
    fact_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("facts.id"),
        primary_key=True,
    )
    source_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("source.id"),
        primary_key=True,
    )


class FactLink(Base):
    """Fact Link table entry."""

    __tablename__ = "fact_link"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    relationship_type: Mapped[RelationshipType] = mapped_column(
        Enum(RelationshipType),
        default=RelationshipType.CORRELATION,
        nullable=False,
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    fact1_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("facts.id"),
        nullable=False,
    )
    fact1: Mapped[Fact] = relationship("Fact", foreign_keys=[fact1_id])
    fact2_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("facts.id"),
        nullable=False,
    )
    fact2: Mapped[Fact] = relationship("Fact", foreign_keys=[fact2_id])


class Validator(Base):
    """Represents a node that has staked collateral to participate in consensus."""

    __tablename__ = "validators"
    public_key: Mapped[str] = mapped_column(String, primary_key=True)
    region: Mapped[str] = mapped_column(String, nullable=False)
    stake_amount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    reputation_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
    )
    rewards: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


def initialize_database(engine: Engine) -> None:
    """Ensure the database file and ALL required tables exist."""
    Base.metadata.create_all(engine)
    logger.info("initialized database")


def get_latest_block(session: Session) -> Block | None:
    """Return latest block from session if it exists."""
    return session.query(Block).order_by(Block.height.desc()).first()


def create_genesis_block(session: Session) -> None:
    """Create initial block."""
    if get_latest_block(session):
        return
    genesis = Block(
        height=0,
        previous_hash="0",
        fact_hashes=json.dumps([]),
        timestamp=time.time(),
        proposer_pubkey=None,  # Genesis has no proposer
    )
    genesis.seal_block()
    session.add(genesis)
    session.commit()
    logger.info("Genesis Block created and sealed.")


def add_block_from_peer_data(
    session: Session,
    block_data: dict[str, Any],
) -> Block:
    """Validate and add a new block received from a peer."""
    latest_local_block = get_latest_block(session)
    if not latest_local_block:
        raise LedgerError("Cannot add peer block: Local ledger has no blocks.")

    expected_height = latest_local_block.height + 1
    if block_data["height"] != expected_height:
        raise ValueError(
            f"Block height mismatch. Expected {expected_height}, got {block_data['height']}.",
        )

    if block_data["previous_hash"] != latest_local_block.hash:
        raise ValueError(
            "Block integrity error: Peer block's previous_hash does not match local head.",
        )

    new_block = Block(
        height=block_data["height"],
        previous_hash=block_data["previous_hash"],
        merkle_root=block_data["merkle_root"],
        timestamp=block_data["timestamp"],
        proposer_pubkey=block_data.get("proposer_pubkey"),
        fact_hashes=json.dumps(block_data.get("fact_hashes", [])),
    )
    # The hash must be recalculated locally to verify integrity, not trusted from the peer.
    new_block.hash = new_block.calculate_hash()

    if new_block.hash != block_data["hash"]:
        raise ValueError(
            f"Block hash mismatch. Peer sent {block_data['hash']}, we calculated {new_block.hash}.",
        )

    session.add(new_block)
    # We don't commit here; the calling function in node.py is responsible for the commit.
    logger.info(f"Validated and staged block #{new_block.height} from peer.")
    return new_block


def get_all_facts_for_analysis(session: Session) -> list[Fact]:
    """Return list of all facts."""
    return session.query(Fact).all()


def add_fact_corroboration(
    session: Session,
    fact_id: int,
    source_id: int,
) -> None:
    """Increment a fact's trust score and add the source to it."""
    fact = session.get(Fact, fact_id)
    source = session.get(Source, source_id)
    if fact is None:
        raise LedgerError(f"fact not found: {fact_id=}")
    if source is None:
        raise LedgerError(f"source not found: {source_id=}")
    add_fact_object_corroboration(fact, source)


def add_fact_object_corroboration(fact: Fact, source: Source) -> None:
    """Increment a fact's trust score and add the source to it."""
    if source not in fact.sources:
        fact.sources.append(source)
        fact.score += 1
        logger.info(
            f"corroborated existing fact {fact.id} {fact.score=} with source {source.id}",
        )


def insert_uncorroborated_fact(
    session: Session,
    content: str,
    source_id: int,
) -> None:
    """Insert a fact for the first time. The source must exist."""
    source = session.get(Source, source_id)
    if source is None:
        raise LedgerError(f"source not found: {source_id=}")
    fact = Fact(content=content, score=0, sources=[source])
    fact.set_hash()
    session.add(fact)
    logger.info(f"inserted uncorroborated fact {fact.id=}")


def insert_relationship(
    session: Session,
    fact_id_1: int,
    fact_id_2: int,
    score: int,
    relationship_type: RelationshipType = RelationshipType.CORRELATION,
) -> None:
    """Insert a relationship between two facts into the knowledge graph."""
    fact1 = session.get(Fact, fact_id_1)
    fact2 = session.get(Fact, fact_id_2)
    if fact1 is None:
        raise LedgerError(f"fact(s) not found: {fact_id_1=}")
    if fact2 is None:
        raise LedgerError(f"fact(s) not found: {fact_id_2=}")
    insert_relationship_object(session, fact1, fact2, score, relationship_type)


def insert_relationship_object(
    session: Session,
    fact1: Fact,
    fact2: Fact,
    score: int,
    relationship_type: RelationshipType,
) -> None:
    """Insert fact relationship given Fact objects."""
    link = FactLink(
        score=score,
        fact1=fact1,
        fact2=fact2,
        relationship_type=relationship_type,
    )
    session.add(link)
    logger.info(
        f"inserted {relationship_type.value} relationship between {fact1.id=} and {fact2.id=} with {score=}",
    )


def mark_facts_as_disputed(
    session: Session,
    original_facts_id: int,
    new_facts_id: int,
) -> None:
    """Mark two facts as disputed and links them together."""
    original_facts = session.get(Fact, original_facts_id)
    new_facts = session.get(Fact, new_facts_id)
    if original_facts is None:
        raise LedgerError(f"fact not found: {original_facts_id=}")
    if new_facts is None:
        raise LedgerError(f"fact not found: {new_facts_id=}")
    mark_fact_objects_as_disputed(session, original_facts, new_facts)


def mark_fact_objects_as_disputed(
    session: Session,
    original_fact: Fact,
    new_fact: Fact,
) -> None:
    """Mark two Fact objects as disputed and link them."""
    original_fact.disputed = True
    new_fact.disputed = True
    link = FactLink(
        score=-1,
        fact1=original_fact,
        fact2=new_fact,
        relationship_type=RelationshipType.CONTRADICTION,
    )
    session.add(link)
    logger.info(
        f"marked facts as disputed: {original_fact.id=}, {new_fact.id=}",
    )


class Votes(TypedDict):
    """Votes dictionary."""

    choice: str
    weight: float


class Proposal(TypedDict):
    """Proposal dictionary."""

    text: str
    proposer: str
    votes: dict[str, Votes]
