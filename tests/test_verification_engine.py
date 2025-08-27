# tests/test_verification_engine.py
from __future__ import annotations

# No longer need unittest
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from axiom_server.ledger import Fact, Source
from axiom_server.verification_engine import (
    find_corroborating_claims,
    verify_citations,
)


class MockFact(Fact):
    """Mock Fact class for testing that allows method assignment."""

    def __init__(self, content: str, sources: list[Source]) -> None:
        super().__init__(content=content, sources=sources)
        self._get_semantics_mock: dict[str, Any] | None = None

    def get_semantics(self) -> Semantics:
        if self._get_semantics_mock:
            return self._get_semantics_mock  # type: ignore[return-value]
        return super().get_semantics()

    def set_get_semantics_mock(self, mock_value: dict[str, Any]) -> None:
        self._get_semantics_mock = mock_value


# We will use pytest fixtures instead of the unittest.TestCase class structure.


# --- Mocking spaCy (no changes needed here) ---
class MockSpacyDoc:
    """A mock spaCy Doc object that supports symmetrical similarity for tests."""

    def __init__(
        self,
        text: str,
        similarity_map: dict[str, float] | None = None,
    ):
        self.text = text
        self.similarity_map = similarity_map or {}

    def similarity(self, other_doc: MockSpacyDoc) -> float:
        """Return a pre-defined similarity score, checking in both directions."""
        if other_doc.text in self.similarity_map:
            return self.similarity_map[other_doc.text]
        if self.text in other_doc.similarity_map:
            return other_doc.similarity_map[self.text]
        return 0.0


# --- Pytest Fixture for Mocks ---
@pytest.fixture
def mock_session() -> MagicMock:
    """Provide a fresh MagicMock for the database session for each test."""
    return MagicMock(spec=Session)


# --- Tests are now regular functions, not methods of a class ---


def test_find_corroborating_claims_success(mock_session: MagicMock) -> None:
    """Test that a similar fact from a DIFFERENT source is correctly identified."""
    # --- Arrange ---
    fact_to_verify_text = "The sky is blue"
    corroborating_fact_text = "The color of the sky is blue"
    unrelated_fact_text = "Grass is green"

    mock_doc_to_verify = MockSpacyDoc(
        fact_to_verify_text,
        similarity_map={corroborating_fact_text: 0.95},
    )
    mock_doc_corroborating = MockSpacyDoc(corroborating_fact_text)
    mock_doc_unrelated = MockSpacyDoc(unrelated_fact_text)

    source1 = Source(domain="sourceA.com")
    source2 = Source(domain="sourceB.com")

    fact_to_verify = MockFact(content=fact_to_verify_text, sources=[source1])
    fact_to_verify.set_get_semantics_mock({"doc": mock_doc_to_verify})

    corroborating_fact = MockFact(
        content=corroborating_fact_text,
        sources=[source2],
    )
    corroborating_fact.set_get_semantics_mock({"doc": mock_doc_corroborating})

    unrelated_fact = MockFact(content=unrelated_fact_text, sources=[source2])
    unrelated_fact.set_get_semantics_mock({"doc": mock_doc_unrelated})

    # Configure the mock session to return our test facts
    mock_session.query(Fact).filter().all.return_value = [
        corroborating_fact,
        unrelated_fact,
    ]

    # --- Act ---
    results = find_corroborating_claims(fact_to_verify, mock_session)

    # --- Assert (using modern pytest style) ---
    assert len(results) == 1
    assert results[0]["content"] == corroborating_fact_text
    assert results[0]["source"] == "sourceB.com"
    assert results[0]["similarity"] > 0.9


def test_find_corroborating_claims_from_same_source(
    mock_session: MagicMock,
) -> None:
    """Test that a similar fact from the SAME source is ignored."""
    # --- Arrange ---
    fact_to_verify_text = "The Earth is round"
    similar_fact_text = "The Earth is an oblate spheroid"

    mock_doc_to_verify = MockSpacyDoc(
        fact_to_verify_text,
        similarity_map={similar_fact_text: 0.98},
    )

    source1 = Source(domain="sourceA.com")

    fact_to_verify = MockFact(content=fact_to_verify_text, sources=[source1])
    fact_to_verify.set_get_semantics_mock({"doc": mock_doc_to_verify})

    # Note: this fact has the SAME source as the fact_to_verify
    similar_fact = MockFact(content=similar_fact_text, sources=[source1])
    similar_fact.set_get_semantics_mock(
        {"doc": MockSpacyDoc(similar_fact_text)},
    )

    mock_session.query(Fact).filter().all.return_value = [similar_fact]

    # --- Act ---
    results = find_corroborating_claims(fact_to_verify, mock_session)

    # --- Assert (using modern pytest style) ---
    assert len(results) == 0


@patch("axiom_server.verification_engine.requests.head")
def test_verify_citations(mock_requests_head: MagicMock) -> None:
    """Test that verify_citations correctly identifies and checks URLs."""
    # --- Arrange ---
    fact_content = "Check this live link http://good-url.com and a broken one http://bad-url.com."
    fact_to_verify = Fact(content=fact_content)

    def side_effect(url: str, **kwargs: Any) -> MagicMock:
        response = MagicMock()
        if url == "http://good-url.com":
            response.status_code = 200
        elif url == "http://bad-url.com":
            response.status_code = 404
        else:
            response.status_code = 500
        return response

    mock_requests_head.side_effect = side_effect

    # --- Act ---
    results = verify_citations(fact_to_verify)

    # --- Assert (using modern pytest style) ---
    assert len(results) == 2
    results_map = {item["url"]: item for item in results}

    assert "http://good-url.com" in results_map
    assert results_map["http://good-url.com"]["status"] == "VALID_AND_LIVE"

    assert "http://bad-url.com" in results_map
    assert results_map["http://bad-url.com"]["status"] == "BROKEN_404"


# We no longer need the if __name__ == "__main__": block
