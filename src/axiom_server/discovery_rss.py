"""Discovery RSS - Find news from RSS."""

from __future__ import annotations

# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
import logging
import random
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)  # <-- NEW IMPORT
from typing import Final

import feedparser

logger = logging.getLogger(__name__)

# Your curated and verified list of RSS feeds.
RSS_FEEDS: Final[tuple[str, ...]] = (
    # Major Global News
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "https://feeds.bbci.co.uk/news/rss.xml",
    # # "https://www.reutersagency.com/feed/?best-topics=world-news&post_type=best",
    # "https://web.archive.org/web/20120506093420/https://twitter.com/statuses/user_timeline/2467791.rss",
    "https://www.theguardian.com/world/rss",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://www.lemonde.fr/rss/une.xml",
    "https://www.npr.org/rss/rss.php?id=1001",
    "https://rss.dw.com/rdf/rss-en-all",
    "https://foreignpolicy.com/feed/",
    # --- Other Major Global Sources (for diverse perspectives) ---
    "https://www.aljazeera.com/xml/rss/all.xml",  # Al Jazeera - All
    # # "https://www.cbc.ca/rss/world",                        # CBC (Canada) - World News
    "https://www.abc.net.au/news/feed/51120/rss.xml",  # ABC (Australia) - Top Stories
    "https://www.spiegel.de/international/index.rss",  # Der Spiegel (Germany) - International
    "https://www.lemonde.fr/rss/une.xml",  # Le Monde (France) - English Edition
    "https://www.japantimes.co.jp/feed",  # The Japan Times
    "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",  # The Times of India
    # US Focused
    "https://apnews.my.id/feed",
    "https://www.latimes.com/index.rss",
    "https://chicago.suntimes.com/feed/",
    "https://api.axios.com/feed/",
    # "https://www.politico.com/rss/politicopicks.xml",
    "https://thehill.com/rss/syndicator/19110",
    "https://www.cbsnews.com/latest/rss/main",
    "https://feeds.nbcnews.com/nbcnews/public/news",
    # Technology & Science
    "https://www.wired.com/feed/rss",
    "https://www.technologyreview.com/feed/",
    "https://spectrum.ieee.org/rss/fulltext",
    "https://www.scientificamerican.com/platform/syndication/rss/",
    "https://www.nature.com/nature.rss",
    "https://science.sciencemag.org/rss/current.xml",
    "https://www.nasa.gov/rss/dyn/breaking_news.rss",
    "https://www.technologyreview.com/feed/",
    "https://arstechnica.com/feed/",
    "https://techcrunch.com/feed/",
    # Business & Finance
    # # "https://www.economist.com/feeds/latest/full.xml",
    "https://www.ft.com/rss/home/international",
    "https://www.ft.com/rss/home",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "https://feeds.a.dj.com/rss/RSSWorldNews.xml",
    # Investigative & Specialized
    "https://www.propublica.org/feeds/propublica/main",
    # # "https://feeds.revealnews.org/revealnews",
    "https://www.themarshallproject.org/rss/recent",
    "https://www.politifact.com/rss/all/",
    "https://www.icij.org/feed/",
    # # "https://www.transparency.org/news/feed",
    # # "https://www.cfr.org/rss/current",
    "https://www.bellingcat.com/feed/",
    # Health & Environment
    "https://www.statnews.com/feed/",
    "https://www.sciencedaily.com/rss/all.xml",
    # # "https://www.nih.gov/news-events/news-releases/rss",
    # # "https://www.who.int/rss-feeds/news-english",
    "https://www.nationalgeographic.cz/rss/vse.xml",
    "https://insideclimatenews.org/feed/",
    # Additional Trusted Sources
    "https://rss.csmonitor.com/feeds/all",
    "https://www.pbs.org/newshour/feeds/rss/headlines",
    "https://www.afp.com/rss.xml",
    "https://time.com/feed",
    # 1 Trusted rss Source from each of the 50 US States
    # Alabama
    "https://www.al.com/arc/outboundfeeds/rss/?outputType=xml",
    # Alaska
    # "https://www.adiario.mx/feed/",
    # Arizona
    # # "https://www.azcentral.com/rss/",
    # Arkansas
    # # "https://www.arkansasonline.com/feed/",
    # California
    "https://www.latimes.com/index.rss",
    # Colorado
    "https://www.denverpost.com/feed/",
    # Connecticut
    # # "https://www.ctinsider.com/rss/",
    # Delaware
    # # "https://www.delawareonline.com/rss/",
    # Florida
    # # "https://www.miamiherald.com/latest-news/rss/",
    # Georgia
    # # "https://www.ajc.com/rss/",
    # Hawaii
    "https://www.staradvertiser.com/feed/",
    # Idaho
    # # "https://www.idahostatesman.com/latest-news/rss/",
    # Illinois
    "https://www.chicagotribune.com/rss",
    "https://www.chicagotribune.com/rss.xml",
    # Indiana
    # # "https://www.indystar.com/rss/",
    # Iowa
    # # "https://www.desmoinesregister.com/rss/",
    # Kansas
    # # "https://www.kansas.com/latest-news/rss/",
    # Kentucky
    # # "https://www.courier-journal.com/rss/",
    # Louisiana
    "http://www.nola.com/news/podcasts/?f=rss&t=article&c=&l=50&s=start_time&sd=desc",
    # Maine
    "https://www.pressherald.com/feed/",
    # Maryland
    "https://www.baltimoresun.com/feed/",
    # Massachusetts
    # # "https://www.bostonglobe.com/rss/",
    # Michigan
    # # "https://www.freep.com/rss/",
    # Minnesota
    "https://www.startribune.com/rss/",
    # Mississippi
    # # "https://www.clarionledger.com/rss/",
    # Missouri
    "http://www.stltoday.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc&k%5B%5D=%23topstory",
    # Montana
    "https://billingsgazette.com/feeds",
    # Nebraska
    # "http://omaha.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc&k%5B%5D=%23topstory",
    # Nevada
    # "https://www.youtube.com/feeds/videos.xml?channel_id=UCo30hbSt6D9z2ObnR4Goo0A",
    # New Hampshire
    # # "https://www.unionleader.com/rss",
    # New Jersey
    "https://www.nj.com/arc/outboundfeeds/rss/?outputType=xml",
    # New Mexico
    "http://www.abqjournal.com/search/?f=rss&t=article&c=news&l=50&s=start_time&sd=desc",
    # New York
    "https://www.nytimes.com/svc/collections/v1/publish/www.nytimes.com/section/nyregion/rss.xml",
    # North Carolina
    # # "https://www.newsobserver.com/latest-news/rss/",
    # North Dakota
    "http://bismarcktribune.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc&k%5B%5D=%23topstory",
    # Ohio
    # # "https://www.dispatch.com/arc/outboundfeeds/rss/",
    # Oklahoma
    # # "https://www.oklahoman.com/feed/",
    # Oregon
    "https://www.oregonlive.com/arc/outboundfeeds/rss/",
    # Pennsylvania
    # # "https://www.inquirer.com/arc/outboundfeeds/rss/",
    # Rhode Island
    # # "https://www.providencejournal.com/arc/outboundfeeds/rss/",
    # South Carolina
    "https://www.postandcourier.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc&k%5B%5D=%23topstory",
    # South Dakota
    "http://rapidcityjournal.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc&k%5B%5D=%23topstory",
    # Tennessee
    # # "https://www.tennessean.com/rss/",
    # Texas
    # # "https://www.dallasnews.com/feed/",
    # Utah
    "https://www.sltrib.com/arc/outboundfeeds/rss/?outputType=xml",
    # Vermont
    "https://vtdigger.org/feed/",
    # Virginia
    "http://richmond.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc&k%5B%5D=%23topstory",
    # Washington
    "https://www.seattletimes.com/feed/",
    # West Virginia
    "http://www.wvgazettemail.com/search/?f=rss&t=article&c=news&l=50&s=start_time&sd=desc",
    # Wisconsin
    # # "https://www.jsonline.com/rss/",
    # Wyoming
    "http://trib.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc&k%5B%5D=%23topstory",
)


def get_content_from_prioritized_feed(
    max_items: int = 5,
) -> list[dict[str, str]]:
    """Select and processes a single, valid RSS feed.

    This function is resilient: it shuffles the feeds and tries them one by
    one until it finds a valid one to process, preventing a single broken
    feed from stopping a fact-finding cycle.
    """
    shuffled_feeds = list(RSS_FEEDS)
    random.shuffle(shuffled_feeds)

    if not shuffled_feeds:
        logger.warning("No RSS feeds configured.")
        return []

    for feed_url in shuffled_feeds:
        logger.info(f"Attempting to process feed: {feed_url}")
        try:
            feed = feedparser.parse(feed_url)
            if feed.bozo:
                logger.warning(
                    f"Feed is malformed, skipping: {feed_url}. Reason: {feed.bozo_exception}",
                )
                continue

            content_list = []
            for entry in feed.entries[:max_items]:
                source_url = entry.get("link")
                content = entry.get("summary", entry.get("description", ""))
                if source_url and content:
                    content_list.append(
                        {"source_url": source_url, "content": content},
                    )

            if content_list:
                logger.info(
                    f"Successfully extracted {len(content_list)} items from {feed_url}.",
                )
                return content_list
            logger.info(
                f"Feed {feed_url} was valid but contained no new items. Trying next.",
            )

        except Exception as exc:
            logger.warning(
                f"An unexpected error occurred for feed {feed_url}. Skipping. Error: {exc}",
            )
            continue

    logger.error(
        "Failed to retrieve content from ANY of the configured RSS feeds.",
    )
    return []


# --- NEW HELPER FUNCTION for concurrent fetching ---
def _fetch_one_feed_headlines(feed_url: str) -> list[str]:
    """Worker function to fetch and parse a single RSS feed.

    Designed to be called concurrently. Returns a list of headlines.
    """
    try:
        feed = feedparser.parse(feed_url)

        if feed.bozo:
            # Silently ignore malformed feeds in concurrent mode to avoid log spam.
            return []

        headlines = []
        for entry in feed.entries:
            headline = entry.get("title", "")
            if headline:
                headlines.append(headline)
        return headlines

    except Exception:
        # If any other error occurs (e.g., network timeout), silently fail for this feed.
        return []


# --- main function to be concurrent ---
def get_all_headlines_from_feeds() -> list[str]:
    """Fetch all headlines concurrently from all configured RSS feeds.

    using a thread pool to dramatically speed up the process.
    """
    # Use a set to automatically handle any duplicate URLs in the RSS_FEEDS list
    unique_feed_urls = set(RSS_FEEDS)
    all_headlines: list[str] = []

    logger.info(
        f"Fetching headlines concurrently from {len(unique_feed_urls)} unique RSS feeds...",
    )

    # Use a ThreadPoolExecutor to run up to 16 requests at the same time.
    with ThreadPoolExecutor(max_workers=16) as executor:
        # Create a dictionary mapping future tasks to their URLs
        future_to_url = {
            executor.submit(_fetch_one_feed_headlines, url): url
            for url in unique_feed_urls
        }

        # Process the results as they complete
        for future in as_completed(future_to_url):
            try:
                headlines_from_one_feed = future.result()
                all_headlines.extend(headlines_from_one_feed)
            except Exception as exc:
                url = future_to_url[future]
                logger.warning(
                    f"Concurrent fetch for {url} generated an exception: {exc}",
                )

    logger.info(
        f"Fetched a total of {len(all_headlines)} headlines concurrently.",
    )
    return all_headlines
