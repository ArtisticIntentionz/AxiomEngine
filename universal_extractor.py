# Axiom - universal_extractor.py
# --- FINAL, CORRECTED VERSION USING SERPAPI FOR SEARCH AND SCRAPERAPI FOR FETCHING ---

import os
import requests
from serpapi import GoogleSearch
import trafilatura

# Get API keys from environment variables
SERPAPI_API_KEY = os.environ.get("SERPAPI_API_KEY")
SCRAPER_API_KEY = os.environ.get("SCRAPER_API_KEY") # <-- NEW KEY

TRUSTED_DOMAINS = [
    'wikipedia.org', 'reuters.com', 'apnews.com', 'bbc.com', 'nytimes.com',
    'wsj.com', 'britannica.com', '.gov', '.edu', 'forbes.com', 'nature.com'
]

def find_and_extract(topic, max_sources=1):
    print(f"\n--- [Pathfinder] Seeking sources for '{topic}' using SerpApi...")
    
    if not SERPAPI_API_KEY or not SCRAPER_API_KEY:
        print("[Pathfinder/Extractor] ERROR: SERPAPI_API_KEY or SCRAPER_API_KEY environment variable not set.")
        return []

    # Step 1: Use SerpApi to find the URLs
    search_params = {
        "api_key": SERPAPI_API_KEY, "engine": "google",
        "q": f'"{topic}" official information history facts filetype:html', "num": 20
    }
    try:
        search = GoogleSearch(search_params)
        results = search.get_dict()
        organic_results = results.get("organic_results", [])
        all_urls = [res['link'] for res in organic_results]
        trusted_urls = [url for url in all_urls if any(domain in url for domain in TRUSTED_DOMAINS)]
        
        if not trusted_urls:
            print(f"[Pathfinder] No trusted sources found for '{topic}'.")
            return []
    except Exception as e:
        print(f"[Pathfinder] ERROR: SerpApi search failed. {e}")
        return []

    # Step 2: Use ScraperAPI to reliably download the HTML content
    print(f"[Universal Extractor] Found {len(trusted_urls)} potential trusted sources. Fetching content via ScraperAPI...")
    extracted_content = []
    for url in trusted_urls[:max_sources]:
        try:
            print(f"  -> Fetching: {url}")
            scraper_api_url = f'http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url={url}'
            
            response = requests.get(scraper_api_url, timeout=60) # Increased timeout for scraper
            response.raise_for_status() # Will raise an error for 4xx/5xx responses
            
            downloaded_html = response.text
            
            if downloaded_html:
                main_text = trafilatura.extract(downloaded_html)
                if main_text:
                    print("  -> Extraction successful.")
                    extracted_content.append({'source_url': url, 'content': main_text})
                else:
                    print("  -> Extraction failed. Page was downloaded, but no main article content was found.")
            else:
                print("  -> Fetch failed. ScraperAPI returned empty content.")

        except requests.exceptions.RequestException as e:
            print(f"  -> Fetch failed for {url}. Error: {e}")
            continue # Move to the next URL

    return extracted_content