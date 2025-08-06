# Axiom - zeitgeist_engine.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
# --- V2.2: FINAL, CORRECTED VERSION USING get_everything() ---

import os
from newsapi import NewsApiClient
from collections import Counter
import spacy
from datetime import datetime, timedelta

NEWS_API_KEY = os.environ.get("NEWS_API_KEY")
NLP_MODEL = spacy.load("en_core_web_sm")

def get_trending_topics(top_n=3):
    """
    Fetches recent articles using the get_everything endpoint to enable date filtering,
    then identifies the most frequently mentioned entities as trending topics.
    """
    if not NEWS_API_KEY:
        print("[Zeitgeist Engine] ERROR: NEWS_API_KEY environment variable not set.")
        return []
    
    print("\n--- [Zeitgeist Engine] Discovering trending topics...")
    try:
        newsapi = NewsApiClient(api_key=NEWS_API_KEY)
        
        to_date = datetime.utcnow().date()
        from_date = to_date - timedelta(days=1)
        

        # We must use the get_everything() endpoint to filter by date.
        # We will search for common, high-volume terms to get a broad sample.
        all_articles_response = newsapi.get_everything(
            q='world OR politics OR technology OR business OR science',
            language='en',
            from_param=from_date.isoformat(),
            to=to_date.isoformat(),
            sort_by='relevancy',
            page_size=100
        )


        articles = all_articles_response.get('articles', [])
        if not articles:
            print("[Zeitgeist Engine] No articles found from NewsAPI for the last 24 hours.")
            return []

        all_entities = []
        for article in articles:
            title = article.get('title', '')
            if title:
                doc = NLP_MODEL(title)
                for ent in doc.ents:
                    if ent.label_ in ['ORG', 'PERSON', 'GPE']:
                        all_entities.append(ent.text)

        if not all_entities:
            print("[Zeitgeist Engine] No significant entities found in headlines.")
            return []
        
        topic_counts = Counter(all_entities)
        most_common_topics = [topic for topic, count in topic_counts.most_common(top_n)]
        
        print(f"[Zeitgeist Engine] Top topics discovered: {most_common_topics}")
        return most_common_topics

    except Exception as e:
        print(f"[Zeitgeist Engine] ERROR: Could not fetch topics from NewsAPI. {e}")
        return []