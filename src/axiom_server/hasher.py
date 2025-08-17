"""Hasher - Fact hash tools."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
from sqlalchemy import or_

from axiom_server.common import NLP_MODEL  # We are using the LARGE model here!
from axiom_server.ledger import Fact

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# Use the same logger as other parts of the application for consistency
logger = logging.getLogger("axiom-node.hasher")


def _extract_keywords(query_text: str, max_keywords: int = 5) -> list[str]:
    """Return the most important keywords (nouns and proper nouns) from a query."""
    # Process the query with our powerful NLP model
    doc = NLP_MODEL(query_text.lower())

    keywords = []
    # We prioritize proper nouns (like "Trump", "SpaceX") and regular nouns.
    # We ignore stopwords (like "the", "a", "for") and punctuation.
    for token in doc:
        if (
            not token.is_stop
            and not token.is_punct
            and token.pos_ in ["PROPN", "NOUN"]
        ):
            keywords.append(token.lemma_)  # Use the base form of the word

    # Return the most important (first occurring) keywords up to the max limit
    return keywords[:max_keywords]


class FactIndexer:
    """A simple class to hold our indexed data."""

    def __init__(self, session: Session) -> None:
        """Initialize the indexer with a database session."""
        self.session = session  # This session will be used for pre-filtering
        # A dictionary to map a unique fact ID to its text content.
        self.fact_id_to_content: dict[int, str] = {}
        # A dictionary to map that same fact ID to its numerical vector.
        self.fact_id_to_vector = {}
        self.vector_matrix = None
        # A list to keep track of the order of fact IDs corresponding to the matrix rows.
        self.fact_ids: list[int] = []

    def add_fact(self, fact: Fact):
        """Adds a single, new fact to the live index in memory."""
        # This is a convenience method that calls the more efficient batch method.
        self.add_facts([fact])

    def add_facts(self, facts_to_add: list[Fact]):
        """Adds a list of new Fact objects to the live in-memory search index
        efficiently in a single batch operation.

        Args:
            facts_to_add: A list of SQLAlchemy Fact objects to be indexed.

        """
        if not facts_to_add:
            return

        # Filter out any facts that might already be in the index
        new_facts = [
            fact for fact in facts_to_add if fact.id not in self.fact_ids
        ]
        if not new_facts:
            logger.info("All provided facts are already indexed. Skipping.")
            return

        # --- Batch process all new facts ---
        new_contents = [fact.content for fact in new_facts]
        new_ids = [fact.id for fact in new_facts]

        # Use the NLP model to get all vectors in one go. This is very efficient.
        # We need to process each content string with the NLP model individually to get its vector.
        new_vectors = [NLP_MODEL(content).vector for content in new_contents]

        # --- Update the in-memory stores ---
        for i, fact in enumerate(new_facts):
            self.fact_id_to_content[fact.id] = new_contents[i]
            self.fact_id_to_vector[fact.id] = new_vectors[i]
            self.fact_ids.append(fact.id)

        # --- Update the NumPy matrix for fast searching ---
        # Stack all the new vectors into a single matrix.
        new_vectors_matrix = np.vstack(new_vectors)

        if self.vector_matrix is None:
            # If this is the first batch, the matrix is just these new vectors.
            self.vector_matrix = new_vectors_matrix
        else:
            # Otherwise, stack the new matrix onto the existing one.
            self.vector_matrix = np.vstack(
                [self.vector_matrix, new_vectors_matrix],
            )

        logger.info(
            f"Successfully added {len(new_facts)} new facts to the search index.",
        )

    def index_facts_from_db(self) -> None:
        """Read all non-disputed facts from the database and builds the index."""
        logger.info("Starting to index facts from the ledger...")
        facts_to_index = (
            self.session.query(Fact).filter(Fact.disputed == False).all()  # noqa: E712
        )
        if not facts_to_index:
            logger.warning("No facts found in the database to index.")
            return

        # We can now reuse our efficient batch-processing method!
        self.add_facts(facts_to_index)

        logger.info(
            f"Initial indexing complete. {len(self.fact_ids)} facts are now searchable.",
        )

    def find_closest_facts(
        self,
        query_text: str,
        top_n: int = 3,
    ) -> list[dict]:
        """Perform a HYBRID search.

        1. Extracts keywords from the query.
        2. Pre-filters the database for facts containing those keywords.
        3. Performs a vector similarity search ONLY on the pre-filtered results.
        """
        # --- Step 1: Extract Keywords ---
        keywords = _extract_keywords(query_text)
        if not keywords:
            logger.warning("Could not extract any keywords from the query.")
            return []  # If no keywords, we can't search.

        logger.info(f"Extracted keywords for pre-filtering: {keywords}")

        # --- Step 2: Pre-filter the Database for Keywords ---

        # Build a query that looks for facts containing ANY of the keywords.
        # This is a fast, indexed text search in the database.
        keyword_filters = [Fact.content.ilike(f"%{key}%") for key in keywords]

        # We only want to search through facts that are not disputed.
        pre_filtered_facts = (
            self.session.query(Fact)
            .filter(or_(*keyword_filters))
            .filter(Fact.disputed == False)  # noqa: E712
            .all()
        )

        if not pre_filtered_facts:
            logger.info("Pre-filtering found no facts matching the keywords.")
            return []

        candidate_ids = [fact.id for fact in pre_filtered_facts]

        # We need to find the positions (indices) of these candidate facts
        # in our main, full vector_matrix.
        try:
            candidate_indices = [
                self.fact_ids.index(fid) for fid in candidate_ids
            ]
        except ValueError:
            # This can happen if a fact is in the DB but not yet in the in-memory index.
            # For robustness, we'll just log it and proceed with what we have.
            logger.warning(
                "Some pre-filtered facts were not found in the live index. The index may be syncing.",
            )
            # Filter out the missing IDs
            valid_candidate_ids = [
                fid for fid in candidate_ids if fid in self.fact_ids
            ]
            if not valid_candidate_ids:
                return []
            candidate_indices = [
                self.fact_ids.index(fid) for fid in valid_candidate_ids
            ]

        except ValueError:
            logger.warning(
                "A race condition occurred where a fact was un-indexed during a search. Returning no results.",
            )
            return []

        if self.vector_matrix is None or len(candidate_indices) == 0:
            return []

        # Create a smaller matrix with only the vectors of our candidate facts.
        candidate_matrix = self.vector_matrix[candidate_indices, :]

        # --- Step 3 & 4: Vectorize Query and Compare ---
        query_doc = NLP_MODEL(query_text)
        query_vector = query_doc.vector

        dot_products = np.dot(candidate_matrix, query_vector)
        norm_query = np.linalg.norm(query_vector)
        norm_matrix = np.linalg.norm(candidate_matrix, axis=1)

        if norm_query == 0 or not np.all(norm_matrix):
            return []

        similarities = dot_products / (norm_matrix * norm_query)

        top_candidate_indices = np.argsort(similarities)[::-1][:top_n]

        # --- Final Step: Prepare and Return Results ---
        results = []
        for i in top_candidate_indices:
            original_index = candidate_indices[i]
            fact_id = self.fact_ids[original_index]

            results.append(
                {
                    "content": self.fact_id_to_content[fact_id],
                    "similarity": float(similarities[i]),
                    "fact_id": fact_id,
                },
            )

        return results
