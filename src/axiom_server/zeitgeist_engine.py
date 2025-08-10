# Axiom - zeitgeist_engine.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
# --- V3.1: DECENTRALIZED RSS-BASED DISCOVERY ---

import logging
from collections import Counter
from .common import NLP_MODEL

# We now import our new, ethical RSS discovery module.
from . import discovery_rss

# Setup professional logging
logger = logging.getLogger(__name__)

def get_trending_topics(top_n=1):
    """
    The new V3.1 Zeitgeist engine. It discovers trending topics by analyzing
    the headlines from all configured RSS feeds. 100% free and decentralized.
    It no longer uses any external, paid APIs.
    """
    logger.info("Discovering trending topics via V3 RSS analysis...")
    
    # 1. Get all headlines from our new RSS module.
    all_headlines = discovery_rss.get_all_headlines_from_feeds()
    if not all_headlines:
        logger.warning("No headlines found from RSS feeds to analyze.")
        return []

    # 2. Use the NLP model to extract named entities from the headlines.
    all_entities = []
    for title in all_headlines:
        if title:
            doc = NLP_MODEL(title)
            for ent in doc.ents:
                if ent.label_ in ['ORG', 'PERSON', 'GPE']:
                    all_entities.append(ent.text)

    if not all_entities:
        logger.warning("No significant entities found in RSS headlines.")
        return []
    
    # 3. Count the most frequent entities to find the "trending topic."
    topic_counts = Counter(all_entities)
    most_common = [topic for topic, count in topic_counts.most_common(top_n)]
    
    logger.info(f"Top topics discovered: {most_common}")
    return most_common