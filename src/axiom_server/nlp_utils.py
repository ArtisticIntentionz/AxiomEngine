from axiom_server.common import NLP_MODEL

def extract_keywords(query_text: str, max_keywords: int = 5) -> list[str]:
    """Return the most important keywords (nouns and proper nouns) from a query."""
    doc = NLP_MODEL(query_text.lower())
    keywords = []
    for token in doc:
        if not token.is_stop and not token.is_punct and token.pos_ in ["PROPN", "NOUN"]:
            keywords.append(token.lemma_)
    return list(dict.fromkeys(keywords))[:max_keywords] # Use dict.fromkeys to keep order and uniqueness