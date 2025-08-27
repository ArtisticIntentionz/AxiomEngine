"""Zeitgeist Engine - Get trending topics and their context from the news."""

from __future__ import annotations

# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
import logging
import sys
from collections import Counter, defaultdict

from langdetect import LangDetectException, detect

from axiom_server import discovery_rss
from axiom_server.common import NLP_MODEL
from axiom_server.crucible import SENTENCE_CHECKS

logger = logging.getLogger(__name__)

# --- Logger setup (no changes) ---
stdout_handler = logging.StreamHandler(stream=sys.stdout)
stdout_handler.setFormatter(
    logging.Formatter(
        "[%(name)s] %(asctime)s | %(levelname)s | %(filename)s:%(lineno)s >>> %(message)s",
    ),
)
logger.addHandler(stdout_handler)
logger.setLevel(logging.INFO)
logger.propagate = False


def normalize_and_count_topics(
    entities: list[str],
    similarity_threshold: float = 0.90,
) -> Counter[str]:
    """Normalize a list of entities by grouping semantically similar ones, then return a Counter with the aggregated counts."""
    if not entities:
        return Counter()

    # The corrected line:
    unique_entities = sorted(set(entities))
    entity_docs = {name: NLP_MODEL(name) for name in unique_entities}

    merged_topics = {}
    topic_map = {}

    for i, name1 in enumerate(unique_entities):
        if name1 in topic_map:
            continue
        canonical_name = name1
        merged_topics[canonical_name] = [canonical_name]
        topic_map[canonical_name] = canonical_name
        doc1 = entity_docs[name1]
        if not doc1.has_vector:
            continue
        for name2 in unique_entities[i + 1 :]:
            if name2 in topic_map:
                continue
            doc2 = entity_docs[name2]
            if not doc2.has_vector:
                continue
            if doc1.similarity(doc2) > similarity_threshold:
                merged_topics[canonical_name].append(name2)
                topic_map[name2] = canonical_name

    final_counts: Counter[str] = Counter()
    for entity in entities:
        canonical_form = topic_map.get(entity, entity)
        final_counts[canonical_form] += 1

    return final_counts


def get_trending_topics(top_n: int = 5) -> dict[str, Any]:
    """Fetch recent news headlines, analyze them for context, and return a dictionary of the top trending topics with their associated terms."""
    logger.info("Discovering trending topics with context...")
    all_headlines = discovery_rss.get_all_headlines_from_feeds()

    if not all_headlines:
        logger.warning("No headlines found from RSS feeds to analyze.")
        return {}

    # --- NEW DATA STRUCTURE: To hold topics and their context ---
    # Example: topic_context['ukraine']['verbs'].append('attack')
    #          topic_context['ukraine']['entities'].append('russia')
    topic_context: dict[str, Any] = defaultdict(
        lambda: {"verbs": [], "entities": []},
    )
    all_primary_entities = []

    for title in all_headlines:
        if not title:
            continue

        try:
            if detect(title) != "en":
                continue
        except LangDetectException:
            continue

        doc = NLP_MODEL(title)
        checked_span = SENTENCE_CHECKS.run(doc[:])

        if not checked_span:
            continue

        # --- CONTEXT GATHERING LOGIC ---

        # 1. Identify all entities and verbs in the headline
        headline_entities = []
        for ent in checked_span.ents:
            if ent.label_ in ["ORG", "PERSON", "GPE", "EVENT", "PRODUCT"]:
                headline_entities.append(ent.lemma_.lower())

        headline_verbs = [
            token.lemma_.lower()
            for token in checked_span
            if token.pos_ == "VERB" and not token.is_stop
        ]

        # 2. Add to the context dictionary
        # Each entity in the headline becomes a key, and all other terms become its context.
        for primary_entity in headline_entities:
            all_primary_entities.append(
                primary_entity,
            )  # For overall trend counting

            # Associate verbs with this entity
            topic_context[primary_entity]["verbs"].extend(headline_verbs)

            # Associate other co-occurring entities
            for other_entity in headline_entities:
                if primary_entity != other_entity:
                    topic_context[primary_entity]["entities"].append(
                        other_entity,
                    )

    if not all_primary_entities:
        logger.warning(
            "No significant entities found in high-quality headlines.",
        )
        return {}

    # --- POST-PROCESSING AND RANKING ---

    # 1. Get the top N trending topics after normalization
    normalized_topic_counts = normalize_and_count_topics(all_primary_entities)
    top_topics = [
        topic for topic, count in normalized_topic_counts.most_common(top_n)
    ]

    # 2. Build the final, structured result
    zeitgeist_report = {}
    for topic in top_topics:
        # Get the most common associated terms for this topic
        associated_verbs = [
            verb
            for verb, count in Counter(
                topic_context[topic]["verbs"],
            ).most_common(5)
        ]
        associated_entities = [
            entity
            for entity, count in Counter(
                topic_context[topic]["entities"],
            ).most_common(5)
        ]

        zeitgeist_report[topic] = {
            "count": normalized_topic_counts[topic],
            "associated_verbs": associated_verbs,
            "associated_entities": associated_entities,
        }

    logger.info(f"Top trending topics discovered: {zeitgeist_report}")
    return zeitgeist_report
