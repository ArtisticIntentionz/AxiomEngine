# In AxiomEngine/src/axiom_server/hasher.py

import logging

import numpy as np
from sqlalchemy.orm import Session

from axiom_server.common import NLP_MODEL  # We are using the LARGE model here!
from axiom_server.ledger import Fact

# Use the same logger as other parts of the application for consistency
logger = logging.getLogger("axiom-node.hasher")


# A simple class to hold our indexed data.
class FactIndexer:
    def __init__(self):
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

    def index_facts_from_db(self, session: Session):
        """Reads all non-disputed facts from the database and builds the index.
        """
        logger.info("Starting to index facts from the ledger...")

        # Query the database for all proven, non-disputed facts.
        facts_to_index = (
            session.query(Fact).filter(Fact.disputed == False).all()
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
        """Takes a user's question, finds the most similar facts from the index.
        """
        if self.vector_matrix is None or len(self.fact_ids) == 0:
            logger.warning("Attempted to search, but the fact index is empty.")
            return []  # Return empty if the index is not built yet.

        # 1. Convert the user's query text into a vector.
        query_doc = NLP_MODEL(query_text)
        query_vector = query_doc.vector

        # 2. Calculate the "cosine similarity" between the query vector and ALL
        #    of the fact vectors in our matrix. This is a fast math operation.
        #    The result is a score from -1 to 1 for each fact. Higher is better.
        dot_products = np.dot(self.vector_matrix, query_vector)
        norm_query = np.linalg.norm(query_vector)
        norm_matrix = np.linalg.norm(self.vector_matrix, axis=1)

        # Handle potential division by zero if query or facts have no vector
        if norm_query == 0 or not np.all(norm_matrix):
            return []

        similarities = dot_products / (norm_matrix * norm_query)

        # 3. Find the indices of the top N highest scores.
        #    `np.argsort` gives the indices from lowest to highest, so we reverse it.
        top_indices = np.argsort(similarities)[::-1][:top_n]

        # 4. Prepare the results to be sent back.
        results = []
        for i in top_indices:
            fact_id = self.fact_ids[i]
            results.append(
                {
                    "content": self.fact_id_to_content[fact_id],
                    "similarity": float(similarities[i]),
                    "fact_id": fact_id,
                },
            )

        return results
