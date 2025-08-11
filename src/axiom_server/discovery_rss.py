# Axiom - discovery_rss.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.

import feedparser
import random
import logging

logger = logging.getLogger(__name__)

RSS_FEEDS = [
    "http://rss.cnn.com/rss/cnn_topstories.rss",
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "http://feeds.reuters.com/news/artsculture",
    "http://feeds.reuters.com/reuters/businessNews",
    "http://feeds.reuters.com/reuters/companyNews",
    "http://feeds.reuters.com/reuters/entertainment",
    "http://feeds.reuters.com/reuters/environment",
    "http://feeds.reuters.com/reuters/healthNews",
    "http://feeds.reuters.com/reuters/lifestyle",
    "http://feeds.reuters.com/news/wealth",
    "http://feeds.reuters.com/reuters/MostRead",
    "http://feeds.reuters.com/reuters/oddlyEnoughNews",
    "http://feeds.reuters.com/ReutersPictures",
    "http://feeds.reuters.com/reuters/peopleNews",
    "http://feeds.reuters.com/Reuters/PoliticsNews",
    "http://feeds.reuters.com/reuters/scienceNews",
    "http://feeds.reuters.com/reuters/sportsNews",
    "http://feeds.reuters.com/reuters/technologyNews",
    "http://feeds.reuters.com/reuters/topNews",
    "http://feeds.reuters.com/Reuters/domesticNews",
    "http://feeds.reuters.com/Reuters/worldNews",
    "http://feeds.reuters.com/reuters/environment",
    "https://feeds.arstechnica.com/arstechnica/index/",
    "https://www.theverge.com/rss/index.xml",
    "https://feeds.npr.org/1001/rss.xml",
]


def get_content_from_prioritized_feed(
    max_items: int = 5,
) -> list[dict[str, str]]:
    """
    Implements the "Factorial Permutation Shuffle" to select a single,
    prioritized RSS feed to explore for new content.
    """
    if not RSS_FEEDS:
        logger.warning("No RSS feeds configured.")
        return []

    shuffled_feeds = list(RSS_FEEDS)
    random.shuffle(shuffled_feeds)
    feed_url = shuffled_feeds[0]

    logger.info(
        f"Prioritized RSS feed for this cycle (post-shuffle): {feed_url}"
    )

    try:
        feed = feedparser.parse(feed_url)
        if feed.bozo:
            logger.error(f"Failed to parse malformed RSS feed: {feed_url}")
            return []

        content_list = []
        for entry in feed.entries[:max_items]:
            source_url = entry.get("link")
            content = entry.get("summary", entry.get("description", ""))
            if source_url and content:
                content_list.append(
                    {"source_url": source_url, "content": content}
                )

        logger.info(
            f"Successfully extracted {len(content_list)} items from the feed."
        )
        return content_list

    except Exception as e:
        logger.exception(
            f"An unexpected error occurred while processing RSS feed {feed_url}: {e}"
        )
        return []


def get_all_headlines_from_feeds() -> list[str]:
    """
    Fetches all headlines from ALL configured RSS feeds. This is the new,
    decentralized engine for the Zeitgeist module.
    """
    all_headlines = []
    logger.info(
        f"Fetching headlines from all {len(RSS_FEEDS)} RSS feeds for Zeitgeist analysis..."
    )
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            if not feed.bozo:
                for entry in feed.entries:
                    all_headlines.append(entry.get("title", ""))
        except Exception:
            continue
    logger.info(f"Fetched a total of {len(all_headlines)} headlines.")
    return all_headlines
