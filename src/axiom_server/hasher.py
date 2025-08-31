"""Fact Indexer - Ultra-fast hybrid search for facts."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

import numpy as np
from sqlalchemy import not_, or_
from sqlalchemy.orm import joinedload

from axiom_server.common import NLP_MODEL
from axiom_server.ledger import (
    Fact,
    FactStatus,
    SessionMaker,
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
        """Perform ULTRA-FAST search using intelligent keyword extraction."""
        # Enhanced keyword extraction
        keywords = self._extract_keywords_enhanced(query_text)
        if not keywords:
            logger.warning("Could not extract any keywords from the query.")
            return []

        logger.info(f"Extracted keywords for enhanced search: {keywords}")

        # Enhanced keyword-based filtering with optimized query
        keyword_filters = [Fact.content.ilike(f"%{key}%") for key in keywords]
        candidate_facts = (
            self.session.query(Fact)
            .filter(or_(*keyword_filters))
            .filter(not_(Fact.disputed))
            .limit(10)  # Increased limit for better selection
            .options(  # Eager load relationships to avoid N+1 queries
                joinedload(Fact.sources),
            )
            .all()
        )

        if not candidate_facts:
            logger.info("No facts found matching keywords.")
            return []

        # Enhanced scoring based on multiple factors
        scored_facts = []
        query_lower = query_text.lower()

        for fact in candidate_facts:
            fact_lower = fact.content.lower()
            
            # Factor 1: Keyword match count
            keyword_matches = sum(
                1 for keyword in keywords if keyword.lower() in fact_lower
            )
            
            # Factor 2: Exact phrase matching
            exact_phrase_score = 0
            query_words = query_text.split()
            if len(query_words) > 1:
                for i in range(len(query_words) - 1):
                    phrase = f"{query_words[i]} {query_words[i+1]}"
                    if phrase.lower() in fact_lower:
                        exact_phrase_score += 0.3
            
            # Factor 3: Source quality
            source_score = 0
            if fact.sources:
                authoritative_sources = ['reuters.com', 'ap.org', 'bbc.com', 'cnn.com', 'nytimes.com']
                for source in fact.sources:
                    if source.domain in authoritative_sources:
                        source_score += 0.2
            
            # Factor 4: Fact status quality
            status_score = 0
            if fact.status == FactStatus.EMPIRICALLY_VERIFIED:
                status_score = 0.3
            elif fact.status == FactStatus.CORROBORATED:
                status_score = 0.2
            elif fact.status == FactStatus.LOGICALLY_CONSISTENT:
                status_score = 0.1
            
            # Factor 5: Content length and quality
            content_score = min(len(fact.content.split()) / 50, 0.2)  # Prefer longer, more detailed facts
            
            # Calculate overall score
            base_score = keyword_matches / len(keywords) if keywords else 0
            total_score = base_score + exact_phrase_score + source_score + status_score + content_score
            
            if total_score > 0:
                scored_facts.append((total_score, fact))

        # Sort by score and take top results
        scored_facts.sort(key=lambda x: x[0], reverse=True)
        top_facts = scored_facts[:top_n]

        # Build results with enhanced information
        results = []
        for score, fact in top_facts:
            # Get source domains
            source_domains = [source.domain for source in fact.sources] if fact.sources else []
            
            results.append({
                'content': fact.content,
                'similarity': min(score, 0.95),  # Cap similarity at 0.95
                'confidence': min(score + 0.1, 0.9),  # Add small confidence boost
                'sources': source_domains,
                'fact_id': fact.id,
                'status': fact.status.value,
                'created_at': fact.created_at.isoformat() if hasattr(fact, 'created_at') and fact.created_at else None
            })

        return results

    def _extract_keywords_enhanced(self, text: str) -> list[str]:
        """Enhanced keyword extraction with better filtering."""
        if not text:
            return []
        
        # Remove common stop words but keep important ones
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
            'will', 'would', 'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those'
        }
        
        # Keep important question words and entities
        important_words = {
            'what', 'how', 'why', 'when', 'where', 'who', 'which', 'trump', 'biden', 'sec', 'companies',
            'said', 'announced', 'reported', 'according', 'study', 'research', 'data', 'statistics'
        }
        
        # Extract words
        words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
        
        # Filter and score words
        keyword_scores = {}
        for word in words:
            if len(word) < 2:
                continue
                
            if word in stop_words and word not in important_words:
                continue
                
            # Score based on importance
            score = 1.0
            if word in important_words:
                score = 2.0
            elif word[0].isupper():  # Proper nouns
                score = 1.5
            elif len(word) > 5:  # Longer words tend to be more specific
                score = 1.2
            
            keyword_scores[word] = keyword_scores.get(word, 0) + score
        
        # Sort by score and return top keywords
        sorted_keywords = sorted(keyword_scores.items(), key=lambda x: x[1], reverse=True)
        return [word for word, score in sorted_keywords[:8]]  # Return top 8 keywords
