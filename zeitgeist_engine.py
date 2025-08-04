# Axiom - zeitgeist_engine.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.

# --- NEW: Import the 'os' library to access environment variables ---
import os
from newsapi import NewsApiClient
from collections import Counter
import re

# --- SECURE CONFIGURATION ---
# The script now reads the API key from an environment variable named 'NEWS_API_KEY'.
# The .get() method is used to safely retrieve it. If the variable is not set,
# it will return None, and the program will handle it gracefully.
API_KEY = os.environ.get("NEWS_API_KEY")
# --------------------------

def get_trending_topics(top_n=5):
    """
    Connects to the News API and analyzes headlines to find the most
    frequently mentioned topics (proper nouns).
    Returns a list of the top N topics.
    """
    # --- NEW: Add a check to ensure the API key exists ---
    if not API_KEY:
        print("[Zeitgeist Engine] ERROR: NEWS_API_KEY environment variable not set. Cannot proceed.")
        return []
    # ------------------------------------------------------
    
    print("\n--- [Zeitgeist Engine] Discovering trending topics...")
    try:
        newsapi = NewsApiClient(api_key=API_KEY)
        top_headlines = newsapi.get_top_headlines(
            sources='bbc-news,reuters,associated-press,the-wall-street-journal',
            language='en'
        )
        all_headlines = " ".join([article['title'] for article in top_headlines['articles']])
        potential_topics = re.findall(r'\b[A-Z][a-z]{2,}\b', all_headlines)
        topic_counts = Counter(potential_topics)
        
        if not topic_counts:
            print("[Zeitgeist Engine] No topics found in current headlines.")
            return []

        trending = [topic for topic, count in topic_counts.most_common(top_n)]
        print(f"[Zeitgeist Engine] Top topics discovered: {trending}")
        return trending

    except Exception as e:
        # The error message now points to a potentially invalid key, not just a missing one.
        print(f"[Zeitgeist Engine] ERROR: Could not fetch topics. Is your API Key valid? Details: {e}")
        return []
