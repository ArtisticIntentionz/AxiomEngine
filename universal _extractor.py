# Axiom - universal_extractor.py
# Finds authoritative web sources for a topic and extracts clean, main content.

from googlesearch import search
import trafilatura

# A curated list of domains the system trusts for high-quality information.
# This helps filter out blogs, social media, and low-quality content.
TRUSTED_DOMAINS = [
    'wikipedia.org', 'reuters.com', 'apnews.com', 'bbc.com', 'nytimes.com',
    'wsj.com', 'britannica.com', '.gov', '.edu', 'forbes.com', 'nature.com'
]

def find_and_extract(topic, max_sources=3):
    """
    Performs a web search for a topic, filters for trusted domains,
    and extracts the primary text content from the top results.
    Returns a list of dictionaries, each containing a source URL and its content.
    """
    print(f"\n--- [Pathfinder] Seeking sources for '{topic}'...")
    # Formulate a search query designed to find factual, historical information.
    query = f'"{topic}" official information history facts filetype:html'
    
    try:
        # Perform the search and filter the results.
        all_urls = search(query, num=10, stop=10, pause=1.0)
        urls = [url for url in all_urls if any(domain in url for domain in TRUSTED_DOMAINS)]
        
        if not urls:
            print(f"[Pathfinder] No trusted sources found for '{topic}'.")
            return []

        print(f"[Universal Extractor] Found {len(urls)} potential sources. Extracting content...")
        
        extracted_content = []
        # Process the top N sources.
        for url in urls[:max_sources]:
            print(f"  -> Extracting from: {url}")
            # trafilatura downloads the page and intelligently extracts only the main article body.
            downloaded = trafilatura.fetch_url(url)
            main_text = trafilatura.extract(downloaded, include_comments=False, include_tables=False, include_images=False)
            
            if main_text:
                extracted_content.append({'source_url': url, 'content': main_text})
        
        return extracted_content
    except Exception as e:
        # Handle potential search or network errors.
        print(f"[Pathfinder/Extractor] ERROR: An exception occurred. {e}")
        return []