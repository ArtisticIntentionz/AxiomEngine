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
from urllib.parse import urlparse

import feedparser

logger = logging.getLogger(__name__)

BLACKLISTED_DOMAINS: Final[set[str]] = {
    "www.fodors.com",  # Travel blog/forum
    "www.lotterypost.com",  # Lottery results/forum
    "www.nomadicmatt.com",  # Travel blog
    "georgerrmartin.com",  # Author's personal blog
    "freakonomics.com",  # Opinion/narrative content
    "consequence.net",  # Music/entertainment news
    "pitchfork.com",  # Music reviews
    "www.brooklynvegan.com",  # Music blog
    "www.rollingstone.com",  # Entertainment/culture magazine
    "www.billboard.com",  # Music charts/news
    "www.spin.com",  # Music magazine
    "www.stereogum.com",  # Music blog
    "adventure.com",  # Travel/adventure stories
    "matadornetwork.com",  # Travel stories
    "www.roadsandkingdoms.com",  # Travel stories
    "www.smithsonianmag.com",  # Often contains long-form narrative stories
    "www.atlasobscura.com",  # Often narrative/story-based
}

# Your curated and verified list of RSS feeds.
RSS_FEEDS: Final[tuple[str, ...]] = (
    "https://api.quantamagazine.org/feed/",
    "http://bismarcktribune.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc&k%5B%5D=%23topstory",
    "http://channels.feeddigest.com/rss/29291.xml",
    "http://feeds.feedburner.com/Incatrailinfo",
    "http://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
    "http://omaha.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc&k%5B%5D=%23topstory",
    "http://rapidcityjournal.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc&k%5B%5D=%23topstory",
    "http://richmond.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc&k%5B%5D=%23topstory",
    "http://trib.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc&k%5B%5D=%23topstory",
    "http://www.abqjournal.com/search/?f=rss&t=article&c=news&l=50&s=start_time&sd=desc",
    "http://www.indianadg.net/feed/",
    "http://www.stltoday.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc&k%5B%5D=%23topstory",
    "http://www.unionleader.com/search/?f=rss&t=article&c=weather&l=50&s=start_time&sd=desc",
    "http://www.wvgazettemail.com/search/?f=rss&t=article&c=news&l=50&s=start_time&sd=desc",
    "http://www.wyopress.org/search/?f=rss&t=article&c=&l=50&s=start_time&sd=desc",
    "https://adventure.com/feed/",
    "https://api.axios.com/feed/",
    "https://apnews.my.id/feed",
    "https://arstechnica.com/feed/",
    "https://arstechnica.com/science/feed/",
    "https://billingsgazette.com/feeds",
    "https://billingsgazette.com/search/?f=rss&t=article&c=news&l=50",
    "https://bsky.app/profile/did:plc:465tbrqfeduj3lhludc6nbog/rss",
    "https://bsky.app/profile/did:plc:pzt2hepn3ta77cjehoyec6xn/rss",
    "https://carnegieendowment.org/rss/solr/feed",
    "https://chicago.suntimes.com/feed/",
    "https://consequence.net/feed/",
    "https://discourse.32bit.cafe/t/useful-rss-feeds/723.rss",
    "https://elpais.com/rss/elpais/inenglish.xml",
    "https://www.esa.int/rssfeed/ESA_in_English",
    "https://feedly.com/new-features/feed.xml",
    "https://feeds.a.dj.com/rss/RSSWorldNews.xml",
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://feeds.nbcnews.com/nbcnews/public/news",
    "https://flipboard.com/@IdahoStatesman.rss",
    "https://blogs.plos.org/feed/",
    "https://foreignpolicy.com/feed/",
    "https://freakonomics.com/feed/",
    "https://georgerrmartin.com/notablog/feed/",
    "https://insideclimatenews.org/feed/",
    "https://kuumbareport.com/feed/",
    "https://lerpr.com/blog/feed/",
    "https://lifehacker.com/rss",
    "https://matadornetwork.com/feed/",
    "https://milwaukeenns.org/feed/",
    "https://newsloth.com/blog/rss.xml",
    "https://omaha.com/search/?f=rss&t=article&c=news&l=50",
    "https://pitchfork.com/feed/feed-news/rss",
    "https://pulitzercenter.org/rss.xml",
    "https://reliefweb.int/rss.xml",
    "https://richmond.com/search/?f=rss&t=article&c=news&l=50",
    "https://rss.csmonitor.com/feeds/all",
    "https://rss.dw.com/rdf/rss-en-all",
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "https://phys.org/rss-feed/",
    "https://science.sciencemag.org/rss/current.xml",
    "https://spectrum.ieee.org/rss/fulltext",
    "https://techcrunch.com/feed/",
    "https://www.thelancet.com/rssfeed/lancet_current.xml",
    "https://www.nih.gov/news-events/news-releases.xml",
    "https://www.newscientist.com/feed/home/",
    "https://www.cell.com/rss/current.xml",
    "https://thehill.com/rss/syndicator/19110",
    "https://time.com/feed",
    "https://time.com/feed/",
    "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
    "https://ukradiofeeds.co.uk/feed/",
    "https://urlscan.io/blog/feed.xml",
    "https://vtdigger.org/feed/",
    "https://web.archive.org/web/20110523060846/http://www.dispatch.com/live/static/crt/2_rss_localnews.xml",
    "https://web.archive.org/web/20120506093420/https://twitter.com/statuses/user_timeline/2467791.rss",
    "https://www.abc.net.au/news/feed/51120/rss.xml",
    "https://www.adiario.mx/feed/",
    "https://www.adn.com/arc/outboundfeeds/rss/",
    "https://www.afp.com/rss.xml",
    "https://www.al.com/arc/outboundfeeds/rss/?outputType=xml",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://www.arkansasonline.com/rss/headlines/",
    "https://www.asahi.com/rss/asahi/newsheadlines.rdf",
    "https://www.atlasobscura.com/feeds/latest",
    "https://www.baltimoresun.com/feed/",
    "https://www.baltimoresun.com/rss/",
    "https://www.basementmedicine.org/feed/",
    "https://www.bellingcat.com/feed/",
    "https://www.billboard.com/feed/",
    "https://www.boston.com/feed/",
    "https://www.brooklynvegan.com/feed/",
    "https://www.buenosairesherald.com/rss",
    "https://www.cbsnews.com/latest/rss/main",
    "https://www.chicagotribune.com/rss",
    "https://www.chicagotribune.com/rss.xml",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "https://www.cntraveler.com/feed/rss",
    "https://www.courant.com/feed/",
    "https://www.cphpost.dk/feed/",
    "https://www.cra-recycle.org/feed/",
    "https://www.dallasnewscorporation.com/feed/",
    "https://www.noaa.gov/news.xml",
    "https://www.dawn.com/feeds/world",
    "https://www.denverpost.com/feed/",
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://www.euractiv.com/feed/",
    "https://www.euronews.com/rss?format=mrss&level=vertical&name=world",
    "https://www.fodors.com/community/external.php?type=RSS2",
    "https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml",
    "https://www.ft.com/rss/markets",
    "https://www.france24.com/en/rss",
    "https://www.ft.com/rss/home",
    "https://www.ft.com/rss/home/international",
    "https://www.icij.org/feed/",
    "https://www.iiss.org/rss",
    "https://www.independent.co.uk/news/world/rss",
    "https://www.inforum.com/topics/engagements.rss",
    "http://feeds.marketwatch.com/marketwatch/topstories/",
    "https://www.inoreader.com/blog/feed",
    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=&company=&dateb=&owner=only&start=0&count=40&output=atom",
    "https://www.latimes.com/index.rss",
    "https://www.latimes.com/world-nation/rss2.0.xml",
    "https://www.lotterypost.com/rss/topic/144197",
    "https://www.lowyinstitute.org/publications/rss.xml",
    "https://www.musicbusinessworldwide.com/feed",
    "https://www.nasa.gov/rss/dyn/breaking_news.rss",
    "https://www.nasa.gov/rss/dyn/lg_image_of_the_day.rss",
    "https://www.nature.com/nature.rss",
    "https://www.nj.com/arc/outboundfeeds/rss/?outputType=xml",
    "https://www.cnbc.com/id/10000664/device/rss/rss.html",
    "https://www.nomadicmatt.com/travel-blog/feed/",
    "https://www.npr.org/rss/rss.php?id=1001",
    "https://www.npr.org/rss/rss.php?id=1004",
    "https://www.npr.org/rss/rss.php?id=1039",
    "https://www.nytimes.com/svc/collections/v1/publish/www.nytimes.com/section/nyregion/rss.xml",
    "https://www.oregonlive.com/arc/outboundfeeds/rss/",
    "https://www.pbs.org/newshour/feeds/rss/headlines",
    "https://www.politico.eu/feed/",
    "https://www.politifact.com/rss/all/",
    "https://www.postandcourier.com/search/?f=rss&t=article&c=news&l=50",
    "https://www.postandcourier.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc&k%5B%5D=%23topstory",
    "https://www.pressherald.com/feed/",
    "https://www.pri.org/programs/the-world/feed",
    "https://www.propublica.org/feeds/propublica/main",
    "https://www.reviewjournal.com/feed/",
    "https://www.rfi.fr/en/rss",
    "https://www.roadsandkingdoms.com/feed",
    "https://www.rollingstone.com/feed/",
    "https://www.runnerspace.com/rss.php?t=e&id=42",
    "https://www.sciencedaily.com/rss/all.xml",
    "https://www.scientificamerican.com/platform/syndication/rss/",
    "https://www.scmp.com/rss/91/feed",
    "https://www.seattletimes.com/feed/",
    "https://www.sltrib.com/arc/outboundfeeds/rss/?outputType=xml",
    "https://www.smh.com.au/rss/world.xml",
    "https://www.smithsonianmag.com/rss/travel/",
    "https://www.spiegel.de/international/index.rss",
    "https://www.spin.com/feed/",
    "https://www.staradvertiser.com/feed/",
    "https://www.startribune.com/rss/",
    "https://www.statnews.com/feed/",
    "https://www.stereogum.com/category/news/feed/",
    "https://www.stltoday.com/search/?f=rss&t=article&c=news&l=50",
    "https://www.straitstimes.com/news/world/rss.xml",
    "https://www.stripes.com/rss.xml",
    "https://www.tampabay.com/arc/outboundfeeds/rss/category/news/?outputType=xml",
    "https://www.technologyreview.com/feed/",
    "https://www.theadvocate.com/search/?f=rss&t=article&c=news&l=50",
    "https://www.theage.com.au/rss/world.xml",
    "https://www.theatlantic.com/feed/channel/news/",
    "https://www.theguardian.com/world/rss",
    "https://www.thehindu.com/news/international/feeder/default.rss",
    "https://www.thelocal.de/feed",
    "https://www.themarshallproject.org/rss/recent",
    "https://www.thenewhumanitarian.org/rss.xml",
    "https://www.theridirectory.com/rssfeed.php",
    "https://www.travelling-greece.com/feed/",
    "https://www.un.org/press/en/feed",
    "https://www.unionleader.com/search/?f=rss&t=article&c=news&l=50",
    "https://www.voanews.com/api/",
    "https://www.wired.com/feed/rss",
    "https://www.wvgazettemail.com/search/?f=rss&t=article&c=news&l=50",
    "https://www.youtube.com/feeds/videos.xml?channel_id=UCW39zufHfsuGgpLviKh297Q",
    "https://www.youtube.com/feeds/videos.xml?channel_id=UCo30hbSt6D9z2ObnR4Goo0A",
)


def get_content_from_prioritized_feed(
    max_items: int = 5,
) -> list[dict[str, str]]:
    """Select and processes a single, valid RSS feed to find new content."""
    shuffled_feeds = list(RSS_FEEDS)
    random.shuffle(shuffled_feeds)

    if not shuffled_feeds:
        logger.warning("No RSS feeds configured.")
        return []

    for feed_url in shuffled_feeds:
        # --- NEW: Check against the blacklist before processing ---
        try:
            domain = urlparse(feed_url).netloc
            if domain in BLACKLISTED_DOMAINS:
                logger.debug(f"Skipping blacklisted feed: {feed_url}")
                continue
        except Exception as e:
            logger.warning(
                f"Could not parse URL '{feed_url}' for domain check. Skipping. Error: {e}",
            )
            continue
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

    Uses a thread pool to dramatically speed up the process.
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
