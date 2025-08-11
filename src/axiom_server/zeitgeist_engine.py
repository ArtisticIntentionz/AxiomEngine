# Axiom - zeitgeist_engine.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.

import logging
from collections import Counter
from axiom_server import discovery_rss
from axiom_server.common import NLP_MODEL

logger = logging.getLogger("zeitgeist")


def get_trending_topics(top_n: int = 1) -> list[str]:
    """
    The new V3.1 Zeitgeist engine. It discovers trending topics by analyzing
    the headlines from all configured RSS feeds. 100% free and decentralized.
    """
    logger.info("Discovering trending topics via V3 RSS analysis...")
    all_headlines = discovery_rss.get_all_headlines_from_feeds()

    if not all_headlines:
        logger.warning("No headlines found from RSS feeds to analyze.")
        return []

    all_entities = []

    for title in all_headlines:
        if title:
            doc = NLP_MODEL(title)
            for ent in doc.ents:
                if ent.label_ in ["ORG", "PERSON", "GPE"]:
                    all_entities.append(ent.text)
    if not all_entities:
        logger.warning("No significant entities found in RSS headlines.")
        return []

    topic_counts = Counter(all_entities)
    most_common = [topic for topic, count in topic_counts.most_common(top_n)]

    logger.info(f"Top topics discovered: {most_common}")
    return most_common
