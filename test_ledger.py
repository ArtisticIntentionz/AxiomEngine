
import pytest
from sqlalchemy.orm import sessionmaker
from src.axiom_server.ledger import (
    Base,
    Fact,
    FactLink,
    Source,
    add_fact_corroboration,
    insert_uncorroborated_fact,
    LedgerError,
    mark_facts_as_disputed,
    insert_relationship,
)
from sqlalchemy import create_engine

engine = create_engine("sqlite:///:memory:")
SessionLocal = sessionmaker(bind=engine)


def test_insert_uncorroborated_fact_success():
    Base.metadata.create_all(engine)
    session = SessionLocal()
    # Add a source first
    source = Source(domain="example.com")
    session.add(source)
    session.commit()
    # Insert fact
    insert_uncorroborated_fact(session, "Test fact content", source.id)
    session.commit()
    # Check that the fact was added
    fact = session.query(Fact).filter_by(content="Test fact content").first()
    assert fact is not None
    assert fact.score == 0
    assert len(fact.sources) == 1
    assert fact.sources[0].domain == "example.com"
    assert fact.hash is not None and len(fact.hash) == 64
    session.close()
    Base.metadata.drop_all(engine)


def test_insert_uncorroborated_fact_source_not_found():
    Base.metadata.create_all(engine)
    session = SessionLocal()
    # Try to insert a fact with a non-existent source
    with pytest.raises(LedgerError):
        insert_uncorroborated_fact(session, "Another fact", 999)
    session.close()
    Base.metadata.drop_all(engine)


def test_mark_facts_as_disputed_success():
    Base.metadata.create_all(engine)
    session = SessionLocal()
    # Add a source
    source = Source(domain="dispute.com")
    session.add(source)
    session.commit()
    # Add two facts
    fact1 = Fact(content="Fact 1", score=1, sources=[source])
    fact2 = Fact(content="Fact 2", score=2, sources=[source])
    session.add_all([fact1, fact2])
    session.commit()
    # Mark as disputed
    mark_facts_as_disputed(session, fact1.id, fact2.id)
    session.commit()
    # Reload facts
    f1 = session.get(Fact, fact1.id)
    f2 = session.get(Fact, fact2.id)
    assert f1 is not None
    assert f2 is not None
    assert f1.disputed is True
    assert f2.disputed is True
    # Check that a FactLink with score -1 exists
    link = (
        session.query(FactLink)
        .filter_by(fact1_id=f1.id, fact2_id=f2.id, score=-1)
        .first()
    )
    assert link is not None
    session.close()
    Base.metadata.drop_all(engine)


def test_mark_facts_as_disputed_fact_not_found():
    Base.metadata.create_all(engine)
    session = SessionLocal()
    # Add a source and one fact
    source = Source(domain="dispute.com")
    session.add(source)
    session.commit()
    fact = Fact(content="Only fact", score=1, sources=[source])
    session.add(fact)
    session.commit()
    # Try to dispute with a non-existent fact
    with pytest.raises(LedgerError):
        mark_facts_as_disputed(session, fact.id, 9999)
    with pytest.raises(LedgerError):
        mark_facts_as_disputed(session, 9999, fact.id)
    session.close()
    Base.metadata.drop_all(engine)


def test_insert_relationship_success():
    Base.metadata.create_all(engine)
    session = SessionLocal()
    # Add a source
    source = Source(domain="rel.com")
    session.add(source)
    session.commit()
    # Add two facts
    fact1 = Fact(content="Rel Fact 1", score=1, sources=[source])
    fact2 = Fact(content="Rel Fact 2", score=2, sources=[source])
    session.add_all([fact1, fact2])
    session.commit()
    # Insert relationship
    insert_relationship(session, fact1.id, fact2.id, 5)
    session.commit()
    # Check that a FactLink with correct score exists
    link = (
        session.query(FactLink)
        .filter_by(fact1_id=fact1.id, fact2_id=fact2.id, score=5)
        .first()
    )
    assert link is not None
    session.close()
    Base.metadata.drop_all(engine)


def test_insert_relationship_fact_not_found():
    Base.metadata.create_all(engine)
    session = SessionLocal()
    # Add a source and one fact
    source = Source(domain="rel.com")
    session.add(source)
    session.commit()
    fact = Fact(content="Only rel fact", score=1, sources=[source])
    session.add(fact)
    session.commit()
    # Try to relate with a non-existent fact
    with pytest.raises(LedgerError):
        insert_relationship(session, fact.id, 9999, 1)
    with pytest.raises(LedgerError):
        insert_relationship(session, 9999, fact.id, 1)
    session.close()
    Base.metadata.drop_all(engine)


def test_add_fact_corroboration_success():
    Base.metadata.create_all(engine)
    session = SessionLocal()
    # Add two sources
    source1 = Source(domain="corroborate1.com")
    source2 = Source(domain="corroborate2.com")
    session.add_all([source1, source2])
    session.commit()
    # Add a fact with one source
    fact = Fact(content="Corroborate fact", score=1, sources=[source1])
    session.add(fact)
    session.commit()
    # Corroborate with a new source
    add_fact_corroboration(session, fact.id, source2.id)
    session.commit()
    updated_fact = session.get(Fact, fact.id)
    assert updated_fact is not None
    assert updated_fact.score == 2
    assert any(s.domain == "corroborate2.com" for s in updated_fact.sources)
    session.close()
    Base.metadata.drop_all(engine)


def test_add_fact_corroboration_duplicate_source():
    Base.metadata.create_all(engine)
    session = SessionLocal()
    # Add a source
    source = Source(domain="dupe.com")
    session.add(source)
    session.commit()
    # Add a fact with that source
    fact = Fact(content="Dupe fact", score=0, sources=[source])
    session.add(fact)
    session.commit()
    # Corroborate with the same source again
    add_fact_corroboration(session, fact.id, source.id)
    session.commit()
    updated_fact = session.get(Fact, fact.id)
    # Score should not increment, source should not be duplicated
    assert updated_fact is not None
    assert updated_fact.score == 0
    assert len([s for s in updated_fact.sources if s.domain == "dupe.com"]) == 1
    session.close()
    Base.metadata.drop_all(engine)


def test_add_fact_corroboration_fact_or_source_not_found():
    Base.metadata.create_all(engine)
    session = SessionLocal()
    # Add a source and a fact
    source = Source(domain="missing.com")
    session.add(source)
    session.commit()
    fact = Fact(content="Missing fact", score=0, sources=[source])
    session.add(fact)
    session.commit()
    # Non-existent fact
    with pytest.raises(LedgerError):
        add_fact_corroboration(session, 9999, source.id)
    # Non-existent source
    with pytest.raises(LedgerError):
        add_fact_corroboration(session, fact.id, 9999)
    session.close()
    Base.metadata.drop_all(engine)
