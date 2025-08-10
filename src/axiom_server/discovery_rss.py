# Axiom - discovery_rss.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
# --- V3.1: Ethical RSS Discovery with Factorial Permutation Shuffle ---

import feedparser
import random
import logging

logger = logging.getLogger(__name__)

# This list should be expanded to at least 15 sources for maximum shuffle effectiveness.
# This list is now the new "ground truth" for sourcing, governed by the DAO.
RSS_FEEDS = [
    "http://rss.cnn.com/rss/cnn_topstories.rss",
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "https://feeds.reuters.com/reuters/topNews", # The corrected, working URL
    "https://feeds.arstechnica.com/arstechnica/index/",
    "https://www.theverge.com/rss/index.xml",
    "https://feeds.npr.org/1001/rss.xml",
]

def get_content_from_prioritized_feed(max_items=5) -> list[dict[str, str]]:
    """
    Implements the "Factorial Permutation Shuffle" to select a single,
    prioritized RSS feed to explore for new content.
    """
    if not RSS_FEEDS:
        logger.warning("No RSS feeds configured.")
        return []

    # --- The Factorial Permutation Shuffle ---
    shuffled_feeds = list(RSS_FEEDS)
    random.shuffle(shuffled_feeds)
    feed_url = shuffled_feeds[0]
    
    logger.info(f"Prioritized RSS feed for this cycle (post-shuffle): {feed_url}")

    try:
        feed = feedparser.parse(feed_url)
        if feed.bozo:
            logger.error(f"Failed to parse malformed RSS feed: {feed_url}")
            return []

        content_list = []
        for entry in feed.entries[:max_items]:
            source_url = entry.get("link")
            # The summary often provides cleaner text than a full scrape.
            content = entry.get("summary", entry.get("description", ""))
            if source_url and content:
                content_list.append({ "source_url": source_url, "content": content })
        
        logger.info(f"Successfully extracted {len(content_list)} items from the feed.")
        return content_list

    except Exception as e:
        logger.exception(f"An unexpected error occurred while processing RSS feed {feed_url}: {e}")
        return []

def get_all_headlines_from_feeds() -> list[str]:
    """
    Fetches all headlines from ALL configured RSS feeds. This is the new,
    decentralized engine for the Zeitgeist module.
    """
    all_headlines = []
    logger.info(f"Fetching headlines from all {len(RSS_FEEDS)} RSS feeds for Zeitgeist analysis...")
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            if not feed.bozo:
                for entry in feed.entries:
                    all_headlines.append(entry.get("title", ""))
        except Exception:
            # Silently ignore feeds that are down or malformed
            continue
    logger.info(f"Fetched a total of {len(all_headlines)} headlines.")
    return all_headlines