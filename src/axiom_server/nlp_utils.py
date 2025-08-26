"""NLP Utilities - Advanced local query parsing.

This module provides functions to parse natural language queries into structured
search terms using only local models (spaCy). It is designed to be a private,
secure, and cost-free alternative to external LLM APIs.

The core logic identifies a hierarchy of concepts:
1. Named Entities (e.g., "Google", "United States")
2. Noun Chunks (e.g., "the stock market", "recent tax incentives")
3. Individual Keywords (important nouns, verbs, etc.)
"""

from __future__ import annotations

from axiom_server.common import NLP_MODEL


def parse_query_advanced(query_text: str, max_terms: int = 10) -> list[str]:
    """Parse a query into a rich list of search terms using a hierarchical approach.

    This function provides a significant improvement over simple keyword extraction
    by identifying multi-word concepts and named entities first.

    Args:
        query_text: The raw user query string.
        max_terms: The maximum number of search terms to return.

    Returns:
        A de-duplicated list of the most relevant search terms, prioritized by
        specificity (Entities > Noun Chunks > Keywords).

    """
    if not query_text.strip():
        return []

    # Process the entire query once with spaCy
    doc = NLP_MODEL(query_text)

    # Use a set for automatic de-duplication of search terms
    search_terms = set()

    # --- 1. Highest Priority: Named Entities ---
    # Captures multi-word proper nouns like "San Francisco", "Apple Inc."
    for ent in doc.ents:
        # We only want entities that are likely to be useful for searching
        if ent.label_ in [
            "PERSON",
            "ORG",
            "GPE",
            "PRODUCT",
            "EVENT",
            "WORK_OF_ART",
        ]:
            search_terms.add(ent.text.lower())

    # --- 2. Medium Priority: Noun Chunks ---
    # Captures concepts like "the red car", "recent breaking news"
    for chunk in doc.noun_chunks:
        # We clean the chunk to get its "root" meaning, removing stop words
        # and determinants like "the", "a", etc.
        cleaned_chunk = " ".join(
            token.lemma_
            for token in chunk
            if not token.is_stop and not token.is_punct
        )
        if cleaned_chunk:
            search_terms.add(cleaned_chunk)

    # --- 3. Base Priority: Individual Keywords ---
    # Fallback for terms not caught in entities or chunks
    for token in doc:
        if (
            not token.is_stop
            and not token.is_punct
            and token.pos_
            in ["PROPN", "NOUN", "VERB"]  # Added VERB for action context
        ):
            search_terms.add(token.lemma_)

    # Convert set to list and limit the number of terms
    # The set automatically handles duplicates between entities, chunks, and keywords.
    final_terms = list(search_terms)

    # A simple relevance sort: longer terms are often more specific and useful
    final_terms.sort(key=len, reverse=True)

    return final_terms[:max_terms]


def extract_keywords(query_text: str, max_keywords: int = 5) -> list[str]:
    """Extract keywords for backward compatibility or basic use cases.

    For best results, use `parse_query_advanced`.
    This function returns the most important keywords (nouns and proper nouns)
    from a query.
    """
    doc = NLP_MODEL(query_text.lower())
    keywords = []
    for token in doc:
        if (
            not token.is_stop
            and not token.is_punct
            and token.pos_ in ["PROPN", "NOUN"]
        ):
            keywords.append(token.lemma_)
    # Use dict.fromkeys to keep order and uniqueness
    return list(dict.fromkeys(keywords))[:max_keywords]
