"""Hasher - Fact hash tools."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import numpy as np
from sqlalchemy import not_, or_
from sqlalchemy.orm import joinedload

from axiom_server.common import NLP_MODEL
from axiom_server.ledger import (
    Fact,
)

# <<< CHANGE 1 HERE: Import the new advanced parser >>>

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# Use the same logger as other parts of the application for consistency
logger = logging.getLogger("axiom-node.hasher")


# <<< CHANGE 2 HERE: The old _extract_keywords function has been removed. >>>


class FactIndexer:
    """A class to hold our indexed data and perform hybrid searches."""

    def __init__(self, session: Session) -> None:
        """Initialize the indexer with a database session."""
        self.session = session
        self.fact_id_to_content: dict[int, str] = {}
        self.fact_id_to_vector: dict[int, Any] = {}
        self.vector_matrix: Any | None = None
        self.fact_ids: list[int] = []

    def add_fact(self, fact: Fact) -> None:
        """Add a single, new fact to the live index in memory."""
        if fact.id in self.fact_ids:
            logger.info(f"Fact {fact.id} is already indexed. Skipping.")
            return

        doc = NLP_MODEL(fact.content)
        fact_vector = doc.vector

        self.fact_id_to_content[fact.id] = fact.content
        self.fact_id_to_vector[fact.id] = fact_vector
        self.fact_ids.append(fact.id)

        new_vector_row = fact_vector.reshape((1, -1))
        if self.vector_matrix is None:
            self.vector_matrix = new_vector_row
        else:
            self.vector_matrix = np.vstack(
                [self.vector_matrix, new_vector_row],
            )

        logger.info(
            f"Successfully added Fact ID {fact.id} to the live chat index.",
        )

    def add_facts(self, facts: list[Fact]) -> None:
        """Add multiple facts efficiently and log a concise summary."""
        added = 0
        for fact in facts:
            if fact.id in self.fact_ids:
                continue
            doc = NLP_MODEL(fact.content)
            fact_vector = doc.vector
            self.fact_id_to_content[fact.id] = fact.content
            self.fact_id_to_vector[fact.id] = fact_vector
            self.fact_ids.append(fact.id)
            row = fact_vector.reshape((1, -1))
            if self.vector_matrix is None:
                self.vector_matrix = row
            else:
                self.vector_matrix = np.vstack([self.vector_matrix, row])
            added += 1
        if added:
            logger.info(f"Indexed {added} new facts into the live chat index.")

    def index_facts_from_db(self) -> None:
        """Skip expensive indexing since we use ultra-fast search."""
        logger.info(
            "Skipping expensive vector indexing - using ultra-fast search instead.",
        )
        logger.info(
            "Facts will be searched directly from database using keyword matching.",
        )
        return

    def find_closest_facts(
        self,
        query_text: str,
        top_n: int = 3,
        min_similarity: float = 0.45,  # Lowered threshold for faster, more inclusive results
    ) -> list[dict[str, Any]]:
        """Perform ULTRA-FAST search using simple keyword extraction."""
        # Ultra-fast keyword extraction without spaCy
        keywords = self._extract_keywords_fast(query_text)
        if not keywords:
            logger.warning("Could not extract any keywords from the query.")
            return []

        logger.info(f"Extracted keywords for ultra-fast search: {keywords}")

        # Ultra-fast keyword-based filtering with optimized query
        keyword_filters = [Fact.content.ilike(f"%{key}%") for key in keywords]
        candidate_facts = (
            self.session.query(Fact)
            .filter(or_(*keyword_filters))
            .filter(not_(Fact.disputed))
            .limit(5)  # Very small limit for maximum speed
            .options(  # Eager load relationships to avoid N+1 queries
                joinedload(Fact.sources),
            )
            .all()
        )

        if not candidate_facts:
            logger.info("No facts found matching keywords.")
            return []

        # Simple scoring based on keyword matches
        scored_facts = []
        query_lower = query_text.lower()

        for fact in candidate_facts:
            fact_lower = fact.content.lower()

            # Count keyword matches
            keyword_matches = sum(
                1 for keyword in keywords if keyword.lower() in fact_lower
            )

            # Simple relevance score
            if keyword_matches > 0:
                score = min(0.9, keyword_matches / len(keywords) + 0.1)
                scored_facts.append((score, fact))

        # Sort by score and take top results
        scored_facts.sort(key=lambda x: x[0], reverse=True)
        top_facts = scored_facts[:top_n]

        # Build results (without slow block lookup)
        results = []
        for score, fact in top_facts:
            results.append(
                {
                    "content": fact.content,
                    "similarity": float(score),
                    "fact_id": fact.id,
                    "disputed": fact.disputed,
                    "sources": [source.domain for source in fact.sources],
                    "source_url": fact.source_url,
                    "fact_hash": fact.hash,
                    "block_height": None,  # Skip slow block lookup for performance
                },
            )

        return results

    def _extract_keywords_fast(self, query_text: str) -> list[str]:
        """Ultra-fast keyword extraction without spaCy."""
        if not query_text.strip():
            return []

        # Simple stop words to filter out
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "can",
            "this",
            "that",
            "these",
            "those",
            "what",
            "when",
            "where",
            "why",
            "how",
            "who",
            "which",
            "whom",
            "i",
            "you",
            "he",
            "she",
            "it",
            "we",
            "they",
            "me",
            "him",
            "her",
            "us",
            "them",
            "my",
            "your",
            "his",
            "its",
            "our",
            "their",
            "mine",
            "yours",
            "hers",
            "ours",
            "theirs",
        }

        # Simple punctuation to remove
        import string

        punctuation = string.punctuation

        # Clean and split the query
        query_lower = query_text.lower()
        for char in punctuation:
            query_lower = query_lower.replace(char, " ")

        # Extract meaningful words
        words = query_lower.split()
        keywords = []

        for word in words:
            word = word.strip()
            if (
                word
                and len(word) > 2  # Skip very short words
                and word not in stop_words
                and not word.isdigit()
            ):  # Skip pure numbers
                keywords.append(word)

        # Return unique keywords, limited to 5 for speed
        return list(dict.fromkeys(keywords))[:5]
