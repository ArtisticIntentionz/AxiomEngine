# Axiom - test_ledger.py

import pytest
from sqlalchemy.orm import sessionmaker, Session
import time
import json

# We now import the new, complete set of V3.1 ledger components to be tested.
from axiom_server.ledger import (
    Base,
    Fact,
    Block,
    Source,
    LedgerError,
    get_latest_block,
    create_genesis_block,
)
from sqlalchemy import create_engine

# Use an in-memory database for fast, isolated tests.
engine = create_engine("sqlite:///:memory:")
SessionLocal = sessionmaker(bind=engine)


@pytest.fixture
def db_session() -> Session:
    """Provides a clean, isolated database session for each test function."""
    Base.metadata.create_all(engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


# These new tests verify the core security and integrity of our new architecture.
def test_genesis_block_creation(db_session: Session):
    """Tests that the very first block is created correctly."""
    create_genesis_block(db_session)
    genesis = get_latest_block(db_session)
    assert genesis is not None, "Genesis block should be created"
    assert genesis.height == 0, "Genesis block height should be 0"
    assert genesis.previous_hash == "0", (
        "Genesis block's previous_hash should be '0'"
    )
    assert genesis.hash.startswith("00"), (
        "Genesis block should be sealed with default difficulty"
    )


def test_add_new_block_to_chain(db_session: Session):
    """Tests that a new block is correctly chained to the previous one."""
    create_genesis_block(db_session)
    genesis = get_latest_block(db_session)
    assert genesis is not None

    fact_hashes = json.dumps(["hash1", "hash2"])
    new_block = Block(
        height=genesis.height + 1,
        previous_hash=genesis.hash,
        fact_hashes=fact_hashes,
        timestamp=time.time(),
    )
    new_block.seal_block(difficulty=3)

    db_session.add(new_block)
    db_session.commit()

    latest = get_latest_block(db_session)
    assert latest is not None, "New block should be added to the chain"
    assert latest.height == 1, "New block height should be 1"
    assert latest.previous_hash == genesis.hash, (
        "New block should chain to genesis hash"
    )
    assert latest.hash.startswith("000"), (
        "New block should be sealed with specified difficulty"
    )


def test_fact_ingestion_default_status(db_session: Session):
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


def test_update_fact_status(db_session: Session):
    """Tests that a fact's status can be correctly updated through its lifecycle."""
    source = Source(domain="example.com")
    fact = Fact(content="Lifecycle test", sources=[source])
    db_session.add(fact)
    db_session.commit()

    fact.status = "logically_consistent"
    db_session.commit()

    retrieved_fact = db_session.get(Fact, fact.id)
    assert retrieved_fact is not None
    assert retrieved_fact.status == "logically_consistent", (
        "Status should update to 'logically_consistent'"
    )

    fact.status = "empirically_verified"
    db_session.commit()

    retrieved_fact = db_session.get(Fact, fact.id)
    assert retrieved_fact is not None
    assert retrieved_fact.status == "empirically_verified", (
        "Status should update to 'empirically_verified'"
    )
