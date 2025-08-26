"""Hasher - Fact hash tools."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
from sqlalchemy import not_, or_

from axiom_server.common import NLP_MODEL
from axiom_server.ledger import (
    Block,
    Fact,
    SessionMaker,
)

# <<< CHANGE 1 HERE: Import the new advanced parser >>>
from axiom_server.nlp_utils import parse_query_advanced

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
        self.fact_id_to_vector: dict[int, np.ndarray] = {}
        self.vector_matrix: np.ndarray | None = None
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

        new_vector_row = fact_vector.reshape(1, -1)
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
            row = fact_vector.reshape(1, -1)
            if self.vector_matrix is None:
                self.vector_matrix = row
            else:
                self.vector_matrix = np.vstack([self.vector_matrix, row])
            added += 1
        if added:
            logger.info(f"Indexed {added} new facts into the live chat index.")

    def index_facts_from_db(self) -> None:
        """Read all non-disputed facts from the database and builds the index."""
        logger.info("Starting to index facts from the ledger...")

        facts_to_index = (
            self.session.query(Fact).filter(not_(Fact.disputed)).all()
        )

        if not facts_to_index:
            logger.warning("No facts found in the database to index.")
            return

        for fact in facts_to_index:
            self.fact_id_to_content[fact.id] = fact.content
            doc = NLP_MODEL(fact.content)
            self.fact_id_to_vector[fact.id] = doc.vector
            self.fact_ids.append(fact.id)

        if self.fact_ids:
            self.vector_matrix = np.vstack(
                [self.fact_id_to_vector[fid] for fid in self.fact_ids],
            )

        logger.info(
            f"Indexing complete. {len(self.fact_ids)} facts are now searchable.",
        )

    def find_closest_facts(
        self,
        query_text: str,
        top_n: int = 3,
<<<<<<< HEAD
=======
        min_similarity: float = 0.75,  # Increased threshold for better relevance
>>>>>>> ec5fd83 (Fixes)
    ) -> list[dict]:
        """Perform a HYBRID search and enriches results with blockchain data."""
        # <<< CHANGE 3 HERE: Use the new advanced parser >>>
        keywords = parse_query_advanced(query_text)
        if not keywords:
            logger.warning("Could not extract any keywords from the query.")
            return []

        logger.info(f"Extracted keywords for pre-filtering: {keywords}")

        keyword_filters = [Fact.content.ilike(f"%{key}%") for key in keywords]
        pre_filtered_facts = (
            self.session.query(Fact)
            .filter(or_(*keyword_filters))
            .filter(not_(Fact.disputed))
            .all()
        )

        if not pre_filtered_facts:
            logger.info("Pre-filtering found no facts matching the keywords.")
            return []

        candidate_ids = [fact.id for fact in pre_filtered_facts]

        try:
            candidate_indices = [
                self.fact_ids.index(fid)
                for fid in candidate_ids
                if fid in self.fact_ids
            ]
            if not candidate_indices:
                logger.warning(
                    "Pre-filtered facts are not yet in the live index.",
                )
                return []
        except ValueError:
            logger.warning(
                "Mismatch between database and live index. Index may be syncing.",
            )
            return []

        candidate_matrix = self.vector_matrix[candidate_indices, :]
        query_doc = NLP_MODEL(query_text)
        query_vector = query_doc.vector

        dot_products = np.dot(candidate_matrix, query_vector)
        norm_query = np.linalg.norm(query_vector)
        norm_matrix = np.linalg.norm(candidate_matrix, axis=1)

        if norm_query == 0 or not np.all(norm_matrix):
            return []

        similarities = dot_products / (norm_matrix * norm_query)

        # Filter by minimum similarity threshold and get top results
        high_similarity_indices = [
            i for i, sim in enumerate(similarities) if sim >= min_similarity
        ]

        if not high_similarity_indices:
            logger.info(
                f"No facts meet the minimum similarity threshold of {min_similarity}",
            )
            # Fall back to top results even if below threshold
            top_candidate_indices = np.argsort(similarities)[::-1][:top_n]
        else:
            # Sort by similarity and take top results
            top_candidate_indices = sorted(
                high_similarity_indices,
                key=lambda i: similarities[i],
                reverse=True,
            )[:top_n]

        results = []
        with SessionMaker() as session:  # Use a new session for fresh queries
            for i in top_candidate_indices:
                original_index = candidate_indices[i]
                fact_id = self.fact_ids[original_index]
                fact = next(
                    (f for f in pre_filtered_facts if f.id == fact_id),
                    None,
                )
                if not fact:
                    continue

                # --- START OF MODIFICATION ---

                # Find the block this fact was proposed in.
                # This query looks for the fact's hash within the JSON list of fact_hashes in each block.
                block_containing_fact = (
                    session.query(Block)
                    .filter(Block.fact_hashes.like(f'%"{fact.hash}"%'))
                    .first()
                )

                results.append(
                    {
                        "content": self.fact_id_to_content[fact_id],
                        "similarity": float(similarities[i]),
                        "fact_id": fact_id,
                        "disputed": fact.disputed,
                        "sources": [source.domain for source in fact.sources],
                        "source_url": fact.source_url,
                        "fact_hash": fact.hash,
                        "source_url": fact.source_url,
                        "block_height": block_containing_fact.height
                        if block_containing_fact
                        else None,
                    },
                )
                # --- END OF MODIFICATION ---

        return results
