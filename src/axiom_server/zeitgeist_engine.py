"""Zeitgeist Engine - Get trending topics from the news."""

from __future__ import annotations

# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
import logging
import sys
from collections import Counter

# --- NEW: Import the langdetect library and our crucible's intelligence ---
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


def get_trending_topics(top_n: int = 1) -> list[str]:
    """Fetch recent news headlines, filter for high-quality English content,
    and return the most frequently mentioned entities.
    """
    logger.info("Discovering high-quality, English trending topics...")
    all_headlines = discovery_rss.get_all_headlines_from_feeds()

    if not all_headlines:
        logger.warning("No headlines found from RSS feeds to analyze.")
        return []

    all_entities = []

    for title in all_headlines:
        if not title:
            continue

        # --- ENHANCEMENT 1: Language Check ---
        # We only want to analyze English headlines.
        try:
            if detect(title) != "en":
                logger.debug(
                    f"Skipping non-English headline: '{title[:50]}...'",
                )
                continue
        except LangDetectException:
            # This happens if the text is too short or ambiguous. Skip it.
            logger.debug(
                f"Could not determine language for: '{title[:50]}...'",
            )
            continue

        # --- ENHANCEMENT 2: Quality Check ---
        # We reuse the crucible's intelligence to filter out "bad" headlines.
        # We create a spaCy object to pass to the pipeline.
        doc = NLP_MODEL(title)

        # The pipeline will return None if any check fails.
        checked_span = SENTENCE_CHECKS.run(doc[:])

        if not checked_span:
            # The log message for why it failed is already printed by the pipeline.
            continue

        # --- If both checks pass, extract entities ---
        for ent in checked_span.ents:
            if ent.label_ in ["ORG", "PERSON", "GPE"]:
                all_entities.append(ent.text)

    if not all_entities:
        logger.warning(
            "No significant entities found in high-quality English headlines.",
        )
        return []

    topic_counts = Counter(all_entities)
    most_common = [topic for topic, count in topic_counts.most_common(top_n)]

    logger.info(f"Top high-quality topics discovered: {most_common}")
    return most_common
