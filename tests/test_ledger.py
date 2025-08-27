# Axiom - test_ledger.py

import json
import time
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from axiom_server.ledger import (
    Base,
    Block,
    Fact,
    FactStatus,
    Source,
    create_genesis_block,
    get_latest_block,
)

# Use an in-memory database for fast, isolated tests.
engine = create_engine("sqlite:///:memory:")
SessionLocal = sessionmaker(bind=engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Return a clean, isolated database session."""
    Base.metadata.create_all(engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


# --- UPDATED TEST FOR PROOF-OF-STAKE ---
def test_genesis_block_creation(db_session: Session) -> None:
    """Tests that the very first block is created correctly."""
    create_genesis_block(db_session)
    genesis = get_latest_block(db_session)
    assert genesis is not None, "Genesis block should be created"
    assert genesis.height == 0, "Genesis block height should be 0"
    assert genesis.previous_hash == "0", (
        "Genesis block's previous_hash should be '0'"
    )
    # A PoS block's hash just needs to be a valid 64-character hex string.
    assert len(genesis.hash) == 64
    assert all(c in "0123456789abcdef" for c in genesis.hash)


# --- UPDATED TEST FOR PROOF-OF-STAKE ---
def test_add_new_block_to_chain(db_session: Session) -> None:
    """Tests that a new block is correctly chained to the previous one."""
    create_genesis_block(db_session)
    genesis = get_latest_block(db_session)
    assert genesis is not None

    fact_hashes = json.dumps(
        [
            "1dfa9132b143d22538cb38522338604791552554756b107c14a5a8126e8436e8",
            "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
        ],
    )
    new_block = Block(
        height=genesis.height + 1,
        previous_hash=genesis.hash,
        fact_hashes=fact_hashes,
        timestamp=time.time(),
        # Add a dummy proposer, as this is now part of the block's identity
        proposer_pubkey="test_proposer_key",
    )
    # The new seal_block function has no arguments.
    new_block.seal_block()

    db_session.add(new_block)
    db_session.commit()

    latest = get_latest_block(db_session)
    assert latest is not None, "New block should be added to the chain"
    assert latest.height == 1, "New block height should be 1"
    assert latest.previous_hash == genesis.hash, (
        "New block should chain to genesis hash"
    )
    # A PoS block's hash just needs to be a valid 64-character hex string.
    assert len(latest.hash) == 64
    assert all(c in "0123456789abcdef" for c in latest.hash)


# --- THIS TEST IS ALREADY CORRECT AND REMAINS UNCHANGED ---
def test_fact_ingestion_default_status(db_session: Session) -> None:
    """Tests that a new fact is created with the correct default 'ingested' status."""
    source = Source(domain="example.com")
    db_session.add(source)
    db_session.commit()

    fact = Fact(content="Test fact", sources=[source])
    db_session.add(fact)
    db_session.commit()

    retrieved_fact = db_session.get(Fact, fact.id)
    assert retrieved_fact is not None, (
        "Fact should be retrievable from the database"
    )
    assert retrieved_fact.status == "ingested", (
        "A new fact's default status must be 'ingested'"
    )


# --- THIS TEST IS ALREADY CORRECT AND REMAINS UNCHANGED ---
def test_update_fact_status(db_session: Session) -> None:
    """Tests that a fact's status can be correctly updated through its lifecycle."""
    source = Source(domain="example.com")
    fact = Fact(content="Lifecycle test", sources=[source])
    db_session.add(fact)
    db_session.commit()

    fact.status = FactStatus.LOGICALLY_CONSISTENT
    db_session.commit()

    retrieved_fact = db_session.get(Fact, fact.id)
    assert retrieved_fact is not None
    assert retrieved_fact.status == "logically_consistent", (
        "Status should update to 'logically_consistent'"
    )

    fact.status = FactStatus.EMPIRICALLY_VERIFIED
    db_session.commit()

    retrieved_fact = db_session.get(Fact, fact.id)
    assert retrieved_fact is not None
    assert retrieved_fact.status == "empirically_verified", (
        "Status should update to 'empirically_verified'"
    )
