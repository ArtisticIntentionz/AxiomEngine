# In AxiomEngine/src/axiom_server/hasher.py

import logging

import numpy as np
from sqlalchemy.orm import Session

from axiom_server.common import NLP_MODEL  # We are using the LARGE model here!
from axiom_server.ledger import Fact

# Use the same logger as other parts of the application for consistency
logger = logging.getLogger("axiom-node.hasher")


def _extract_keywords(query_text: str, max_keywords: int = 5) -> list[str]:
    """Extracts the most important keywords (nouns and proper nouns) from a query.
    """
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


# A simple class to hold our indexed data.
class FactIndexer:
    def __init__(self, session: Session):
        """Initializes the indexer with a database session."""
        self.session = session  # This session will be used for pre-filtering
        # A dictionary to map a unique fact ID to its text content.
        self.fact_id_to_content = {}
        # A dictionary to map that same fact ID to its numerical vector.
        self.fact_id_to_vector = {}
        # A list to hold all the vectors for fast searching.
        self.vector_matrix = None
        # A list to keep track of the order of fact IDs corresponding to the matrix rows.
        self.fact_ids = []

    def add_fact(self, fact: Fact):
        """Adds a single, new fact to the live index in memory."""
        if fact.id in self.fact_ids:
            logger.info(f"Fact {fact.id} is already indexed. Skipping.")
            return

        # 1. Get the fact's vector
        doc = NLP_MODEL(fact.content)
        fact_vector = doc.vector

        # 2. Update our dictionaries and lists
        self.fact_id_to_content[fact.id] = fact.content
        self.fact_id_to_vector[fact.id] = fact_vector
        self.fact_ids.append(fact.id)

        # 3. Add the new vector to our NumPy matrix
        # Reshape the vector to be a row (1, 300) instead of a flat array (300,)
        new_vector_row = fact_vector.reshape(1, -1)

        if self.vector_matrix is None:
            # If this is the first fact, the matrix is just this one row.
            self.vector_matrix = new_vector_row
        else:
            # Otherwise, stack the new row onto the existing matrix.
            self.vector_matrix = np.vstack(
                [self.vector_matrix, new_vector_row],
            )

        logger.info(
            f"Successfully added Fact ID {fact.id} to the live chat index.",
        )

    def index_facts_from_db(self):
        """Reads all non-disputed facts from the database and builds the index."""
        logger.info("Starting to index facts from the ledger...")

        # Query the database for all proven, non-disputed facts.
        facts_to_index = (
            self.session.query(Fact).filter(Fact.disputed == False).all()
        )

        if not facts_to_index:
            logger.warning("No facts found in the database to index.")
            return

        for fact in facts_to_index:
            # Store the fact's text content.
            self.fact_id_to_content[fact.id] = fact.content

            # Create a vector for the fact's content using the large spaCy model.
            # The .vector attribute provides the semantic representation of the text.
            doc = NLP_MODEL(fact.content)
            self.fact_id_to_vector[fact.id] = doc.vector

            # Keep track of the fact ID.
            self.fact_ids.append(fact.id)

        # For efficient searching, we stack all the individual vectors into one big
        # NumPy matrix (like a spreadsheet of numbers).
        if self.fact_ids:
            self.vector_matrix = np.vstack(
                [self.fact_id_to_vector[fid] for fid in self.fact_ids],
            )

        logger.info(
            f"Indexing complete. {len(self.fact_ids)} facts are now searchable.",
        )

    def find_closest_facts(
        self, query_text: str, top_n: int = 3,
    ) -> list[dict]:
        """Performs a HYBRID search:
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
        from sqlalchemy import or_

        # Build a query that looks for facts containing ANY of the keywords.
        # This is a fast, indexed text search in the database.
        keyword_filters = [Fact.content.ilike(f"%{key}%") for key in keywords]

        # We only want to search through facts that are not disputed.
        pre_filtered_facts = (
            self.session.query(Fact)
            .filter(or_(*keyword_filters))
            .filter(Fact.disputed == False)
            .all()
        )

        if not pre_filtered_facts:
            logger.info("Pre-filtering found no facts matching the keywords.")
            return []

        # Create a temporary, smaller index from only the relevant facts.
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

        # Create a smaller matrix with only the vectors of our candidate facts.
        candidate_matrix = self.vector_matrix[candidate_indices, :]

        # --- Step 3 & 4: Vectorize Query and Compare ---
        query_doc = NLP_MODEL(query_text)
        query_vector = query_doc.vector

        # Perform the fast vector math, but ONLY on the small candidate_matrix.
        dot_products = np.dot(candidate_matrix, query_vector)
        norm_query = np.linalg.norm(query_vector)
        norm_matrix = np.linalg.norm(candidate_matrix, axis=1)

        if norm_query == 0 or not np.all(norm_matrix):
            return []

        similarities = dot_products / (norm_matrix * norm_query)

        # The indices of the top N scores are relative to our small candidate list.
        top_candidate_indices = np.argsort(similarities)[::-1][:top_n]

        # --- Final Step: Prepare and Return Results ---
        results = []
        for i in top_candidate_indices:
            # Get the original index from our candidate list
            original_index = candidate_indices[i]
            # Use that to find the original fact ID
            fact_id = self.fact_ids[original_index]

            results.append(
                {
                    "content": self.fact_id_to_content[fact_id],
                    "similarity": float(similarities[i]),
                    "fact_id": fact_id,
                },
            )

        return results
