# Axiom - crucible.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License.
# See the LICENSE file for details.

import spacy
import hashlib
import re
# --- UPDATED LEDGER IMPORTS ---
from ledger import insert_uncorroborated_fact, find_similar_fact_from_different_domain, update_fact_corroboration

NLP_MODEL = spacy.load("en_core_web_sm")
OPINION_WORDS = {'believe', 'think', 'feel', 'seems', 'appears', 'argues', 'suggests', 'perhaps'}

def extract_facts_from_text(source_url, text_content):
    """
    Uses an NLP pipeline to analyze text and applies the Corroboration Rule
    before saving facts to the ledger.
    """
    print(f"\n--- [The Crucible] Analyzing content from {source_url[:60]}...")
    
    try:
        # Extract the domain from the source URL for comparison.
        source_domain_match = re.search(r'https?://(?:www\.)?([^/]+)', source_url)
        if not source_domain_match:
            print("[The Crucible] ERROR: Could not parse domain from source URL.")
            return
        source_domain = source_domain_match.group(1)

        doc = NLP_MODEL(text_content)
        
        facts_processed = 0
        for sent in doc.sents:
            # --- Verification Rules (Unchanged) ---
            if len(sent.text.split()) < 8 or len(sent.text.split()) > 100:
                continue
            if not sent.ents:
                continue
            if any(word in sent.text.lower() for word in OPINION_WORDS):
                continue
            
            # --- New Corroboration Logic ---
            fact_content = sent.text.strip().replace('\n', ' ')
            
            # Check if a similar fact from a DIFFERENT domain already exists.
            similar_fact = find_similar_fact_from_different_domain(fact_content, source_domain)
            
            if similar_fact:
                # If it exists, we don't insert a new one. We update the existing one.
                update_fact_corroboration(similar_fact['fact_id'], source_url)
            else:
                # If no similar fact exists, we insert this as a new, uncorroborated fact.
                fact_id = hashlib.sha256(fact_content.encode('utf-8')).hexdigest()
                insert_uncorroborated_fact(fact_id, fact_content, source_url)
            
            facts_processed += 1

        print(f"[The Crucible] Analysis complete. Processed {facts_processed} potential facts.")
    except Exception as e:
        print(f"[The Crucible] ERROR: Failed to process text. {e}")