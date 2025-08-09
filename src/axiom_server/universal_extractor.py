# Axiom - universal_extractor.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
# --- V2.5: UNIFIED VERSION WITH COMMUNITY REFACTOR ---

import os
import sys
import logging
import requests
from serpapi import GoogleSearch # This requires 'google-search-results' to be installed
import trafilatura
from urllib.parse import urlparse

# --- Professional logging setup (Corrected) ---
logger = logging.getLogger(__name__) # Use __name__ for automatic, correct logger naming.
stdout_handler = logging.StreamHandler(stream=sys.stdout)
stdout_handler.setFormatter(
    logging.Formatter(
        "[%(name)s] %(asctime)s | %(levelname)s | %(filename)s:%(lineno)s >>> %(message)s"
    )
)

logger.addHandler(stdout_handler)
logger.setLevel(logging.INFO)
logger.propagate = False

SERPAPI_API_KEY = os.environ.get("SERPAPI_API_KEY")
SCRAPER_API_KEY = os.environ.get("SCRAPER_API_KEY")

TRUSTED_DOMAINS = [
    "wikipedia.org",
    "reuters.com",
    "apnews.com",
    "bbc.com",
    "nytimes.com",
    "wsj.com",
    "britannica.com",
    ".gov",
    ".edu",
    "forbes.com",
    "nature.com",
    "techcrunch.com",
    "theverge.com",
    "arstechnica.com",
    ".org",
]


def is_trusted_domain(url):
    """A secure helper function to validate a URL's domain."""
    try:
        netloc = urlparse(url).netloc
        if not netloc:
            return False
        domain_without_www = netloc.lower().replace("www.", "")
        for trusted_suffix in TRUSTED_DOMAINS:
            if domain_without_www.endswith(trusted_suffix.lower()):
                return True
        return False
    except Exception:
        return False


def find_and_extract(topic, max_sources=3) -> list[dict[str, str]]:
    """
        returns {"source_url": url, "content": main_text}
    """
    logger.info(f"seeking sources for '{topic}' using SerpApi...")

    if not SERPAPI_API_KEY or not SCRAPER_API_KEY:
        logger.error("API keys not set.")
        return []

    search_query = f'"{topic}" news facts information'

    search_params = {
        "api_key": SERPAPI_API_KEY,
        "engine": "google",
        "q": search_query,
        "num": 20,
    }
    try:
        search_results = GoogleSearch(search_params)
        results_dict = search_results.get_dict()
        organic_results = results_dict.get("organic_results", [])
        all_urls = [res["link"] for res in organic_results]

        trusted_urls = [url for url in all_urls if is_trusted_domain(url)]

        if not trusted_urls:
            logger.info(f"no trusted sources found for '{topic}'.")
            return []
    except Exception as e:
        logger.exception(f"SerpApi search failed. {e}")
        return []

    logger.info(
        f"found {len(trusted_urls)} potential trusted sources. Fetching content via ScraperAPI..."
    )
    extracted_content = []
    for url in trusted_urls[:max_sources]:
        try:
            logger.info(f"fetching: {url}")
            scraper_api_url = (
                f"http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url={url}"
            )
            response = requests.get(scraper_api_url, timeout=60)
            response.raise_for_status()
            downloaded_html = response.text

            if downloaded_html:
                main_text = trafilatura.extract(downloaded_html)
                if main_text:
                    logger.info("extraction successful.")
                    extracted_content.append({"source_url": url, "content": main_text})
        except requests.exceptions.RequestException as e:
            logger.exception(f"fetch failed for {url}. Error: {e}")
            continue

    return extracted_content
