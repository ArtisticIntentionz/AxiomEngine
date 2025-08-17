# tests/test_verification_engine.py
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from axiom_server import verification_engine
from axiom_server.ledger import Fact, Source


# --- Mocking spaCy ---
# We don't want to load a real NLP model for a unit test. It's slow and unnecessary.
# We will create mock spaCy "Doc" objects that let us control the similarity score.
class MockSpacyDoc:
    """A mock spaCy Doc object for controlling similarity scores in tests."""

    def __init__(
        self,
        text: str,
        similarity_map: dict[str, float] | None = None,
    ):
        self.text = text
        self.similarity_map = similarity_map or {}

    def similarity(self, other_doc: MockSpacyDoc) -> float:
        """Return a pre-defined similarity score for the given text."""
        # This allows us to say "when comparing to doc B, return 0.95".
        return self.similarity_map.get(other_doc.text, 0.0)


class TestVerificationEngine(unittest.TestCase):
    """Tests for the Axiom Verification Engine."""

    def setUp(self):
        """Set up a mock database session and test data for each test."""
        self.mock_session = MagicMock(spec=Session)

        # Create mock Source objects
        self.source1 = Source(domain="sourceA.com")
        self.source2 = Source(domain="sourceB.com")
        self.source3 = Source(domain="sourceC.com")

    def test_find_corroborating_claims_success(self):
        """Test that find_corroborating_claims correctly identifies a similar fact from a different source."""
        # --- Arrange ---
        fact_to_verify_text = "The sky is blue"
        corroborating_fact_text = "The color of the sky is blue"
        unrelated_fact_text = "Grass is green"

        # Create mock Docs with controlled similarity
        # When comparing our target fact to the corroborating fact, the score will be 0.95
        # For all other comparisons, it will be 0.1 (the default from .get())
        mock_doc_to_verify = MockSpacyDoc(
            fact_to_verify_text,
            similarity_map={
                corroborating_fact_text: 0.95,
                unrelated_fact_text: 0.1,
            },
        )

        # Create mock Fact objects
        fact_to_verify = Fact(
            content=fact_to_verify_text,
            sources=[self.source1],
        )
        fact_to_verify.get_semantics = MagicMock(
            return_value={"doc": mock_doc_to_verify},
        )

        corroborating_fact = Fact(
            content=corroborating_fact_text,
            sources=[self.source2],
        )
        corroborating_fact.get_semantics = MagicMock(
            return_value={"doc": MockSpacyDoc(corroborating_fact_text)},
        )

        unrelated_fact = Fact(
            content=unrelated_fact_text,
            sources=[self.source3],
        )
        unrelated_fact.get_semantics = MagicMock(
            return_value={"doc": MockSpacyDoc(unrelated_fact_text)},
        )

        # Configure the mock session to return these facts
        all_facts = [fact_to_verify, corroborating_fact, unrelated_fact]
        self.mock_session.query(Fact).filter().all.return_value = [
            f for f in all_facts if f.id != fact_to_verify.id
        ]

        # --- Act ---
        results = verification_engine.find_corroborating_claims(
            fact_to_verify,
            self.mock_session,
        )

        # --- Assert ---
        assert len(results) == 1
        assert results[0]["content"] == corroborating_fact_text
        assert results[0]["source"] == "sourceB.com"
        assert results[0]["similarity"] > 0.9

    def test_find_corroborating_claims_from_same_source(self):
        """Test that a similar fact from the SAME source is NOT considered a corroboration."""
        # --- Arrange ---
        fact_to_verify_text = "The sky is blue"
        similar_fact_text = "The sky is indeed blue"

        # High similarity
        mock_doc_to_verify = MockSpacyDoc(
            fact_to_verify_text,
            similarity_map={similar_fact_text: 0.98},
        )

        fact_to_verify = Fact(
            content=fact_to_verify_text,
            sources=[self.source1],
        )
        fact_to_verify.get_semantics = MagicMock(
            return_value={"doc": mock_doc_to_verify},
        )

        # The similar fact comes from the *same source*
        similar_fact = Fact(content=similar_fact_text, sources=[self.source1])
        similar_fact.get_semantics = MagicMock(
            return_value={"doc": MockSpacyDoc(similar_fact_text)},
        )

        self.mock_session.query(Fact).filter().all.return_value = [
            similar_fact,
        ]

        # --- Act ---
        results = verification_engine.find_corroborating_claims(
            fact_to_verify,
            self.mock_session,
        )

        # --- Assert ---
        assert len(results) == 0  # Should find no corroborations

    # We use the @patch decorator to mock the `requests.head` call
    @patch("axiom_server.verification_engine.requests.head")
    def test_verify_citations(self, mock_requests_head):
        """Test that verify_citations correctly identifies and checks URLs in fact content."""
        # --- Arrange ---
        fact_content = "Check this live link http://good-url.com and this broken one http://bad-url.com."
        fact_to_verify = Fact(content=fact_content)

        # Configure the mock `requests.head` to behave how we want
        def side_effect(url, **kwargs):
            response = MagicMock()
            if url == "http://good-url.com":
                response.status_code = 200
            elif url == "http://bad-url.com":
                response.status_code = 404
            return response

        mock_requests_head.side_effect = side_effect

        # --- Act ---
        results = verification_engine.verify_citations(fact_to_verify)

        # --- Assert ---
        assert len(results) == 2

        # We use a helper to make asserting easier since dict order isn't guaranteed
        results_map = {item["url"]: item for item in results}

        assert "http://good-url.com" in results_map
        assert results_map["http://good-url.com"]["status"] == "VALID_AND_LIVE"

        assert "http://bad-url.com" in results_map
        assert results_map["http://bad-url.com"]["status"] == "BROKEN_404"


if __name__ == "__main__":
    unittest.main()
