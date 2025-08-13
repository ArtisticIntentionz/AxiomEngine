# maintain_feeds.py (Version 1.0 - The Unified Toolchain)
"""
A single, powerful script to maintain the Axiom Engine's RSS feed list.

This script will automatically:
1.  Create a backup of your existing discovery_rss.py file.
2.  Read and parse the RSS_FEEDS tuple from the source file.
3.  Verify all feeds, sorting them into 'good' and 'bad' lists.
4.  For bad feeds, it uses a multi-strategy approach (knowledge base, scraping,
    and an intelligent web search with relevance checking) to find replacements.
5.  It then REWRITES the discovery_rss.py file:
    - Replaces broken URLs with their verified replacements.
    - Comments out any URLs for which no replacement could be found.
6.  Provides a final summary report of the actions taken.

Dependencies:
pip install ddgs beautifulsoup4 requests feedparser lxml
"""
import os
import re
import sys
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Set, Dict, Tuple
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup
from ddgs import DDGS

# --- This allows us to import directly from the axiom_server directory ---
sys.path.insert(0, os.path.join(os.getcwd(), "src"))
SOURCE_FILE_PATH = os.path.join("src", "axiom_server", "discovery_rss.py")
BACKUP_FILE_PATH = f"{SOURCE_FILE_PATH}.bak"


# --- KNOWLEDGE BASE of manual fixes ---
KNOWN_REPLACEMENTS: Dict[str, str] = {
    "www.washingtonpost.com"     : "https://feeds.washingtonpost.com/rss/world",
    "www.wsj.com"                : "https://feeds.a.dj.com/rss/RSSWorldNews.xml",
    "www.axios.com"              : "https://api.axios.com/feed/",
    "www.pbs.org/newshour"       : "https://www.pbs.org/newshour/feeds/rss/headlines",
    "www.politico.com"           : "https://www.politico.com/rss/politicopicks.xml",
    "www.dw.com"                 : "https://rss.dw.com/rdf/rss-en-all",
    "www.ft.com"                 : "https://www.ft.com/rss/world",
    "www.latimes.com"            : "https://www.latimes.com/business/rss2.0.xml#nt=0000016c-0bf3-d57d-afed-2fff84fd0000-1col-7030col1",
    "www.csmonitor.com"          : "https://rss.csmonitor.com/feeds/all",
    "www.bostonglobe.com"        : "https://www.bostonglobe.com/world/",
    "www.chicagotribune.com"     : "https://www.chicagotribune.com/arcio/rss/category/news/",
}

HEADERS = {'User-Agent': 'Axiom-Feed-Maintainer/1.0'}

def _verify_url(url: str) -> Tuple[bool, str | None]:
    """Checks a URL and returns its status and title if valid."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        feed = feedparser.parse(r.content)
        if not feed.bozo and feed.entries:
            return True, feed.feed.get("title")
    except Exception:
        pass
    return False, None

def _find_single_replacement(bad_url: str, original_site_title: str) -> List[str]:
    """Worker function to find a replacement for one bad URL with relevance checking."""
    # Strategy 0: Knowledge Base
    for key, replacement in KNOWN_REPLACEMENTS.items():
        if key in bad_url:
            is_valid, _ = _verify_url(replacement)
            if is_valid: return [replacement]
    
    verified_replacements = set()
    try:
        # Strategies 1 & 2: Homepage scraping and guessing
        parsed_uri = urlparse(bad_url)
        base_url = f"{parsed_uri.scheme}://{parsed_uri.netloc}"
        r = requests.get(base_url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.content, "lxml") # Use the better parser
        for link in soup.find_all("link", {"rel": "alternate", "type": "application/rss+xml"}):
            url = urljoin(base_url, link.get("href"))
            is_valid, title = _verify_url(url)
            # Relevance Check: Does the new feed title seem related to the original?
            if is_valid and original_site_title.lower() in title.lower():
                verified_replacements.add(url)
    except Exception: pass

    if verified_replacements: return list(verified_replacements)

    # Strategy 3: Web Search
    try:
        query = f'"{original_site_title}" official RSS feed'
        with DDGS() as ddgs:
            for result in ddgs.text(query, max_results=3):
                try:
                    page_req = requests.get(result['href'], headers=HEADERS, timeout=10)
                    page_soup = BeautifulSoup(page_req.content, "lxml")
                    for link in page_soup.find_all("link", {"rel": "alternate", "type": "application/rss+xml"}):
                        feed_url = urljoin(result['href'], link.get("href"))
                        is_valid, title = _verify_url(feed_url)
                        if is_valid and original_site_title.lower() in title.lower():
                            verified_replacements.add(feed_url)
                except Exception: continue
    except Exception: pass
    
    return list(verified_replacements)

def read_and_parse_source_file() -> Tuple[List[str], List[str]]:
    """Reads the source file and extracts URLs using regex."""
    if not os.path.exists(SOURCE_FILE_PATH):
        print(f"❌ ERROR: Source file not found at {SOURCE_FILE_PATH}")
        sys.exit(1)
        
    with open(SOURCE_FILE_PATH, 'r') as f:
        lines = f.readlines()
    
    urls = []
    for line in lines:
        match = re.search(r'"(https?://[^"]+)"', line)
        if match:
            urls.append(match.group(1))
    return urls, lines

def main():
    """Runs the full verification, repair, and file update pipeline."""
    all_urls, original_lines = read_and_parse_source_file()
    unique_urls = sorted(list(set(all_urls)))
    print(f"--- Starting Maintenance for {len(unique_urls)} Unique Feeds ---\n")

    # --- Phase 1: Verification ---
    print("--- Phase 1: Verifying all current feeds... ---")
    good_feeds: Set[str] = set()
    bad_feeds_map: Dict[str, str] = {} # {url: site_title}
    
    with ThreadPoolExecutor(max_workers=16) as executor:
        future_to_url = {executor.submit(_verify_url, url): url for url in unique_urls}
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            is_valid, title = future.result()
            if is_valid:
                good_feeds.add(url)
            else:
                # Try to get a site title for better searching later
                domain = urlparse(url).netloc.replace('www.', '').split('.')[0].capitalize()
                bad_feeds_map[url] = domain
    
    bad_feeds = list(bad_feeds_map.keys())
    print(f"\n--- Phase 1 Complete: {len(good_feeds)} Good, {len(bad_feeds)} Bad ---\n")
    if not bad_feeds:
        print("✅ All feeds are healthy! No maintenance needed.")
        return

    # --- Phase 2: Repair ---
    print(f"--- Phase 2: Attempting to find replacements for {len(bad_feeds)} bad feeds... ---")
    replacement_map: Dict[str, str] = {}
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_url = {executor.submit(_find_single_replacement, url, bad_feeds_map[url]): url for url in bad_feeds}
        for future in as_completed(future_to_url):
            original_url = future_to_url[future]
            replacements = future.result()
            if replacements:
                replacement_map[original_url] = replacements[0] # Use the first good one
    
    # --- Step 3: Rewrite the Source File ---
    print("\n--- Phase 3: Updating the source file... ---")
    
    new_lines = []
    for line in original_lines:
        match = re.search(r'"(https?://[^"]+)"', line)
        if not match:
            new_lines.append(line)
            continue
            
        url = match.group(1)
        if url in good_feeds:
            new_lines.append(line)
        elif url in replacement_map:
            # Replace the old URL with the new one, keeping surrounding quotes and commas
            new_line = line.replace(url, replacement_map[url])
            new_lines.append(new_line)
            print(f"  [🔧 REPAIRED] Replaced {url} with {replacement_map[url]}")
        else:
            # Comment out the line if no replacement was found
            new_lines.append(f"# {line.lstrip()}")
            print(f"  [DISABLE] Commented out {url}")

    # Create a backup and write the new file
    try:
        shutil.copy(SOURCE_FILE_PATH, BACKUP_FILE_PATH)
        print(f"\n✅ Backup of original file created at: {BACKUP_FILE_PATH}")
        with open(SOURCE_FILE_PATH, 'w') as f:
            f.writelines(new_lines)
        print(f"✅ Successfully updated {SOURCE_FILE_PATH}!")
    except Exception as e:
        print(f"❌ FATAL ERROR: Could not write to source file. Error: {e}")
        print(f"Your original file is safe. A backup was attempted at {BACKUP_FILE_PATH}")


if __name__ == "__main__":
    main()