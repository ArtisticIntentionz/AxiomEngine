"""Discovery RSS - Find news from RSS."""

from __future__ import annotations

# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
import logging
import random
from typing import Final

import feedparser

logger = logging.getLogger(__name__)

RSS_FEEDS: Final = (
    # --- DAO Governed Sources ---
    "http://rss.cnn.com/rss/cnn_topstories.rss",
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "https://feeds.reuters.com/reuters/topNews",  # Top News from Reuters
    "https://feeds.reuters.com/Reuters/worldNews",  # World News from Reuters
    "https://apnews.com/hub/ap-top-news/rss",  # Associated Press Top News
    "https://feeds.npr.org/1001/rss.xml",  # NPR News
    "https://feeds.washingtonpost.com/rss/world",  # The Washington Post
    "https://feeds.a.dj.com/rss/RSSWorldNews.xml",  # The Wall Street Journal
    "https://www.aljazeera.com/xml/rss/all.xml",  # Al Jazeera
    "https://www.propublica.org/feeds/propublica/main",  # ProPublica
    "http://feeds.revealnews.org/revealnews",  # The Center for Investigative Reporting
    "https://www.themarshallproject.org/rss.xml",  # The Marshall Project
    "https://www.politifact.com/rss/all/",  # PolitiFact
    "https://feeds.arstechnica.com/arstechnica/index/",  # Ars Technica
    "https://www.theverge.com/rss/index.xml",  # The Verge
    "https://www.technologyreview.com/feed/",  # MIT Technology Review
    "https://www.wired.com/feed/rss",  # Wired
    "https://spectrum.ieee.org/rss/full-text",  # IEEE Spectrum
    "https://www.economist.com/feeds/latest/full.xml",  # The Economist
    "https://www.reddit.com/r/worldnews/.rss",  # Reddit World News
)


def get_content_from_prioritized_feed(
    max_items: int = 5,
) -> list[dict[str, str]]:
    """Select a prioritized RSS feed to explore for new content."""
    shuffled_feeds = list(RSS_FEEDS)
    random.shuffle(shuffled_feeds)

    if not shuffled_feeds:
        logger.warning("No RSS feeds configured.")
        return []

    feed_url = shuffled_feeds[0]

    logger.info(
        f"Prioritized RSS feed for this cycle (post-shuffle): {feed_url}",
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
                    {"source_url": source_url, "content": content},
                )

        logger.info(
            f"Successfully extracted {len(content_list)} items from the feed.",
        )
        return content_list

    except Exception as exc:
        logger.exception(
            f"An unexpected error occurred while processing RSS feed {feed_url}: {exc}",
        )
        return []


def get_all_headlines_from_feeds() -> list[str]:
    """Fetch all headlines from ALL configured RSS feeds."""
    all_headlines = []
    logger.info(
        f"Fetching headlines from all {len(RSS_FEEDS)} RSS feeds for Zeitgeist analysis...",
    )
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            if not feed.bozo:
                for entry in feed.entries:
                    all_headlines.append(entry.get("title", ""))
        except Exception as exc:
            logger.exception(exc)
            continue
    logger.info(f"Fetched a total of {len(all_headlines)} headlines.")
    return all_headlines
