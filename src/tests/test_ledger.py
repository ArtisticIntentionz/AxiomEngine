# Axiom - test_ledger.py
# --- V3.1: BLOCKCHAIN AND LIFECYCLE TEST SUITE ---

import pytest
from sqlalchemy.orm import sessionmaker
import time
import json

# Import the new, complete set of V3.1 ledger components
from axiom_server.ledger import (
    Base, Fact, FactLink, Source, Block,
    LedgerError, initialize_database,
    get_latest_block, create_genesis_block
)
from sqlalchemy import create_engine

# Use an in-memory database for fast, isolated tests.
engine = create_engine("sqlite:///:memory:")
SessionLocal = sessionmaker(bind=engine)

# --- Test Fixture: A Clean Database for Every Test ---
@pytest.fixture
def db_session():
    """Provides a clean, isolated database session for each test function."""
    Base.metadata.create_all(engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)

# --- V3.1 Blockchain Tests ---
def test_genesis_block_creation(db_session):
    """Tests that the very first block is created correctly."""
    create_genesis_block(db_session)
    genesis = get_latest_block(db_session)
    assert genesis is not None
    assert genesis.height == 0
    assert genesis.previous_hash == "0"
    assert genesis.hash.startswith("00") # Default difficulty

def test_add_new_block_to_chain(db_session):
    """Tests that a new block is correctly chained to the previous one."""
    create_genesis_block(db_session)
    genesis = get_latest_block(db_session)
    
    fact_hashes = json.dumps(["hash1", "hash2"])
    new_block = Block(
        height=genesis.height + 1,
        previous_hash=genesis.hash,
        fact_hashes=fact_hashes,
        timestamp=time.time()
    )
    new_block.seal_block(difficulty=3)
    
    db_session.add(new_block)
    db_session.commit()
    
    latest = get_latest_block(db_session)
    assert latest is not None
    assert latest.height == 1
    assert latest.previous_hash == genesis.hash
    assert latest.hash.startswith("000")

# --- V3.1 Fact Lifecycle Tests ---
def test_fact_ingestion(db_session):
    """Tests that a new fact is created with the 'ingested' status."""
    source = Source(domain="example.com")
    db_session.add(source)
    db_session.commit()

    fact = Fact(content="Test fact", sources=[source])
    # The default status should be 'ingested' upon creation
    assert fact.status == 'ingested'
    
    db_session.add(fact)
    db_session.commit()
    
    retrieved_fact = db_session.get(Fact, fact.id)
    assert retrieved_fact is not None
    assert retrieved_fact.status == 'ingested'

def test_update_fact_status(db_session):
    """Tests that a fact's status can be correctly updated through its lifecycle."""
    source = Source(domain="example.com")
    fact = Fact(content="Lifecycle test", sources=[source])
    db_session.add(fact)
    db_session.commit()

    # In a real system, other modules would call this. We simulate it here.
    fact.status = 'logically_consistent'
    db_session.commit()
    
    retrieved_fact = db_session.get(Fact, fact.id)
    assert retrieved_fact.status == 'logically_consistent'

    fact.status = 'empirically_verified'
    db_session.commit()

    retrieved_fact = db_session.get(Fact, fact.id)
    assert retrieved_fact.status == 'empirically_verified'

# --- The test suite can be expanded with more V3.1 specific tests ---