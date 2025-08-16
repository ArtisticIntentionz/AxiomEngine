"""Ledger - Fact Database Logic."""

from __future__ import annotations

# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
import datetime
import enum
import hashlib
import json
import logging
import sys
import time
from typing import Any

from pydantic import BaseModel
from spacy.tokens.doc import Doc
from sqlalchemy import (
    Boolean,
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
    LOGICALLY_CONSISTENT = "logically_consistent"
    CORROBORATED = "corroborated"
    EMPIRICALLY_VERIFIED = "empirically_verified"


class RelationshipType(str, enum.Enum):
    """Defines the nature of the link between two facts."""

    CORRELATION = "correlation"  # The facts are about the same topic.
    CONTRADICTION = "contradiction"  # The facts state opposing information.
    CAUSATION = "causation"  # One fact is a likely cause of the other.
    CHRONOLOGY = "chronology"  # One fact chronologically follows another.
    ELABORATION = "elaboration"


class Block(Base):
    """Block table."""

    __tablename__ = "blockchain"
    height: Mapped[int] = mapped_column(Integer, primary_key=True)
    hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    previous_hash: Mapped[str] = mapped_column(String, nullable=False)
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    nonce: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fact_hashes: Mapped[str] = mapped_column(Text, nullable=False)

    merkle_root: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="",
    )

    def __init__(self, **kwargs: Any) -> None:
        """Initialize Block."""
        super().__init__(**kwargs)
        self.nonce = self.nonce or 0

    def calculate_hash(self) -> str:
        """Return hash from this block."""
        block_string = json.dumps(
            {
                "height": self.height,
                "previous_hash": self.previous_hash,
                "fact_hashes": sorted(json.loads(self.fact_hashes)),
                "timestamp": self.timestamp,
                "nonce": self.nonce,
                "merkle_root": self.merkle_root,
            },
            sort_keys=True,
        ).encode()
        return hashlib.sha256(block_string).hexdigest()

    def seal_block(self, difficulty: int) -> None:
        """Calculate the Merkle Root and then seal the block via Proof of Work."""
        fact_hashes_list = json.loads(self.fact_hashes)
        if fact_hashes_list:
            merkle_tree = merkle.MerkleTree(fact_hashes_list)
            self.merkle_root = merkle_tree.root.hex()
        else:
            self.merkle_root = hashlib.sha256(b"").hexdigest()

        self.hash = self.calculate_hash()
        target = "0" * difficulty
        while not self.hash.startswith(target):
            self.nonce += 1
            self.hash = self.calculate_hash()
        logger.info(f"Block sealed! Hash: {self.hash}")

    def to_dict(self) -> dict[str, Any]:
        """Serializes the Block object to a dictionary for P2P broadcasting."""
        return {
            "height": self.height,
            "hash": self.hash,
            "previous_hash": self.previous_hash,
            "merkle_root": self.merkle_root,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
            "fact_hashes": self.fact_hashes,
        }
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """
        Creates a Block object from a dictionary, typically from P2P data.
        This is the inverse of the to_dict() method.
        """
        # We use .get() for safety to avoid KeyErrors if a field is missing.
        return cls(
            height=data.get("height"),
            hash=data.get("hash"),
            previous_hash=data.get("previous_hash"),
            merkle_root=data.get("merkle_root"),
            timestamp=data.get("timestamp"),
            nonce=data.get("nonce", 0),
            # fact_hashes is not part of the header, so we default it.
            fact_hashes=data.get("fact_hashes", "[]"),
        )


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

    vector_data: Mapped[FactVector] = relationship(
        back_populates="fact",
        cascade="all, delete-orphan",
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content: Mapped[str] = mapped_column(String, default="", nullable=False)
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
    hash: Mapped[str] = mapped_column(String, default="", nullable=False)
    last_checked: Mapped[str] = mapped_column(
        String,
        default=lambda: datetime.datetime.now(
            datetime.timezone.utc,
        ).isoformat(),
        nullable=False,
    )
    semantics: Mapped[str] = mapped_column(
        String,
        default="{}",
        nullable=False,
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

    @classmethod
    def from_model(cls, model: SerializedFact) -> Self:
        """Return new Fact from serialized fact."""
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
        """Return if score is positive."""
        return self.score > 0

    def has_source(self, domain: str) -> bool:
        """Return if any source uses given domain."""
        return any(source.domain == domain for source in self.sources)

    def set_hash(self) -> str:
        """Set self.hash."""
        self.hash = hashlib.sha256(self.content.encode("utf-8")).hexdigest()
        return self.hash

    def get_serialized_semantics(self) -> SerializedSemantics:
        """Return serialized semantics."""
        return SerializedSemantics.model_validate_json(self.semantics)

    def get_semantics(self) -> Semantics:
        """Return Semantics dictionary."""
        serializable = self.get_serialized_semantics()
        return semantics_from_serialized(serializable)

    def set_semantics(self, semantics: Semantics) -> None:
        """Serialize semantics for database storage."""
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
    """Source table entry."""

    __tablename__ = "source"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    domain: Mapped[str] = mapped_column(String, nullable=False)
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
    )
    genesis.seal_block(difficulty=2)
    session.add(genesis)
    session.commit()
    logger.info("Genesis Block created and sealed.")


# --- NEW FUNCTION FOR P2P SYNCHRONIZATION ---
def add_block_from_peer_data(
    session: Session,
    block_data: dict[str, Any],
) -> Block | None: # --- FIX: The return type is now optional.
    """Validates and adds a new block received from a peer.

    This is the core of blockchain synchronization. It ensures that a node
    only accepts blocks that correctly extend its own version of the chain.

    Args:
        session: The active SQLAlchemy database session.
        block_data: A dictionary containing the block header data from a peer.

    Returns:
        The newly added Block object on success, or None on failure.

    """
    latest_local_block = get_latest_block(session)
    if not latest_local_block:
        logger.error("Cannot add peer block: Local ledger has no blocks.")
        return None

    try:
        # 1. CRITICAL VALIDATION: Is the new block the very next one in the sequence?
        expected_height = latest_local_block.height + 1
        if block_data["height"] != expected_height:
            logger.error(
                f"Block height mismatch. Expected {expected_height}, "
                f"but peer sent {block_data['height']}. Node may be out of sync.",
            )
            return None

        # 2. CRITICAL VALIDATION: Does the new block correctly chain to our latest block?
        if block_data["previous_hash"] != latest_local_block.hash:
            logger.error(
                f"Block integrity error: Peer block's previous_hash "
                f"({block_data['previous_hash']}) does not match local head "
                f"({latest_local_block.hash}). A fork may have occurred.",
            )
            return None

        # 3. If validation passes, create the Block object from the peer data.
        # We now use the Block.from_dict method to ensure consistency.
        new_block = Block.from_dict(block_data)

        # 4. Optional but Recommended: Re-verify the block's hash.
        # This prevents peers from sending blocks with invalid proof-of-work.
        if new_block.hash != new_block.calculate_hash():
            logger.error("Invalid hash for received block. Discarding.")
            return None

        session.add(new_block)
        session.commit()
        logger.info(
            f"Added new block #{new_block.height} from peer to local ledger.",
        )
        
        # --- FIX: Return the newly created block object on success.
        return new_block

    except (KeyError, TypeError, ValueError) as e:
        logger.error(f"Error processing peer block data: {e}. Discarding block.")
        session.rollback()
        return None

def get_all_facts_for_analysis(session: Session) -> list[Fact]:
    """Return list of all facts."""
    return session.query(Fact).all()


def add_fact_corroboration(
    session: Session,
    fact_id: int,
    source_id: int,
) -> None:
    """Increment a fact's trust score and add the source to it. Both must already exist."""
    fact = session.get(Fact, fact_id)
    source = session.get(Source, source_id)
    if fact is None:
        raise LedgerError(f"fact not found: {fact_id=}")
    if source is None:
        raise LedgerError(f"source not found: {source_id=}")
    add_fact_object_corroboration(fact, source)


def add_fact_object_corroboration(fact: Fact, source: Source) -> None:
    """Increment a fact's trust score and add the source to it. Does nothing if the source already exists."""
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
    """Insert a relationship between two facts into the knowledge graph. Both facts must exist."""
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

def get_chain_as_dicts(session: Session) -> list[dict]:
    """
    Queries the database for all blocks, orders them by height, and serializes
    them into a list of dictionaries for network transport.
    """
    logger.info("Exporting full blockchain from database for peer...")
    all_blocks = session.query(Block).order_by(Block.height.asc()).all()
    # This uses the to_dict() method you already have on your Block objects.
    return [block.to_dict() for block in all_blocks]


def replace_chain(session: Session, new_chain_dicts: list[dict]) -> bool:
    """
    Performs a full validation of a received blockchain and, if it is valid
    and longer than the current chain, atomically replaces the local chain.
    This is the heart of the synchronization process.
    """
    logger.info("Attempting to replace local chain with received chain...")
    current_blocks = session.query(Block).order_by(Block.height.asc()).all()

    # 1. Validation: The new chain must be longer to be considered.
    if len(new_chain_dicts) <= len(current_blocks):
        logger.warning("Received chain is not longer than the current one. Aborting sync.")
        return False

    try:
        # 2. Cryptographic Validation: Reconstruct the blocks using the new from_dict
        #    classmethod and verify the entire chain's integrity by checking the
        #    `previous_hash` links.
        temp_blocks = [Block.from_dict(b) for b in new_chain_dicts]
        for i in range(1, len(temp_blocks)):
            # Ensure the current block's previous_hash matches the actual hash of the previous block.
            if temp_blocks[i].previous_hash != temp_blocks[i-1].calculate_hash():
                logger.error(
                    f"Chain validation failed: Invalid hash link at block index {temp_blocks[i].height}."
                )
                return False
        logger.info("Validation of received chain was successful.")

        # 3. Atomic Replacement: Perform the delete and insert operations within a
        #    single transaction to prevent database corruption on failure.
        logger.info(f"Deleting {len(current_blocks)} old blocks from the database.")
        for block in current_blocks:
            session.delete(block)

        logger.info(f"Inserting {len(temp_blocks)} new blocks into the database.")
        session.add_all(temp_blocks)

        session.commit()
        logger.info("Blockchain successfully synced and replaced in the database!")
        return True

    except Exception as e:
        logger.error(f"A critical error occurred during chain replacement: {e}")
        # IMPORTANT: Roll back any partial changes if an error occurs.
        session.rollback()
        return False