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
        """Add a single, new fact to the live index in memory."""
        # This is a convenience method that calls the more efficient batch method.
        self.add_facts([fact])

    def add_facts(self, facts_to_add: list[Fact]):
        """Add a list of new Fact objects to the live in-memory search index efficiently in a single batch operation.

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
        # new_ids = [fact.id for fact in new_facts]

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
        """Perform a HYBRID search with a full semantic fallback.

        1. Extracts keywords from the query.
        2. Pre-filters the database for facts containing those keywords.
        3. Performs a vector similarity search ONLY on the pre-filtered results.
        4. If pre-filtering yields no results, it falls back to a full
        vector search against the entire index.
        """
        if self.vector_matrix is None or len(self.fact_ids) == 0:
            logger.warning("Fact index is not available. Cannot perform search.")
            return []

        # --- Step 1: Extract Keywords ---
        keywords = _extract_keywords(query_text)
        pre_filtered_facts = []

        if keywords:
            logger.info(f"Extracted keywords for pre-filtering: {keywords}")
            # --- Step 2: Pre-filter the Database for Keywords ---
            keyword_filters = [Fact.content.ilike(f"%{key}%") for key in keywords]
            pre_filtered_facts = (
                self.session.query(Fact)
                .filter(or_(*keyword_filters))
                .filter(Fact.disputed == False)
                .all()
            )

        # --- NEW: FALLBACK LOGIC ---
        if not pre_filtered_facts:
            logger.warning(
                "Keyword pre-filter found no candidates. Falling back to full semantic search."
            )
            # If the fast filter fails, we search against everything.
            candidate_indices = list(range(len(self.fact_ids)))
            candidate_matrix = self.vector_matrix
        else:
            logger.info(f"Pre-filtering found {len(pre_filtered_facts)} candidate facts.")
            # If the fast filter succeeds, we limit our search to the candidates.
            candidate_ids = {fact.id for fact in pre_filtered_facts}
            # Find the indices in our master list that correspond to the candidate IDs
            candidate_indices = [
                i for i, fact_id in enumerate(self.fact_ids) if fact_id in candidate_ids
            ]
            if not candidate_indices:
                return [] # No valid candidates found in the live index
            candidate_matrix = self.vector_matrix[candidate_indices, :]

        # --- Step 3 & 4: Vectorize Query and Compare (this part is mostly unchanged) ---
        query_doc = NLP_MODEL(query_text)
        query_vector = query_doc.vector.reshape(1, -1) # Ensure query_vector is 2D

        # Using cosine_similarity is more stable and standard than manual calculation
        from sklearn.metrics.pairwise import cosine_similarity
        similarities = cosine_similarity(query_vector, candidate_matrix)[0]

        # Get the top N indices from the candidates
        top_candidate_indices = np.argsort(similarities)[-top_n:][::-1]

        # --- Final Step: Prepare and Return Results ---
        results = []
        for i in top_candidate_indices:
            # If the candidate index is out of bounds for similarities, skip
            if i >= len(similarities):
                continue

            similarity_score = similarities[i]

            # Only return results above a certain confidence threshold
            if similarity_score < 0.3:  # Tune this threshold as needed
                continue

            original_index = candidate_indices[i]
            fact_id = self.fact_ids[original_index]

            results.append(
                {
                    "content": self.fact_id_to_content[fact_id],
                    "similarity": float(similarity_score),
                    "fact_id": fact_id,
                },
            )

        return results
