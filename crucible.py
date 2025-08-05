# Axiom - crucible.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
# --- UPGRADED WITH CONTRADICTION DETECTION ---

import spacy
import hashlib
import re
import sqlite3
from datetime import datetime
from ledger import get_all_facts_for_analysis, mark_facts_as_disputed

DB_NAME = "axiom_ledger.db"
NLP_MODEL = spacy.load("en_core_web_sm")
OPINION_WORDS = {'believe', 'think', 'feel', 'seems', 'appears', 'argues', 'suggests', 'perhaps'}

def _get_subject_and_object(doc):
    """A helper function to extract the main subject and object from a spaCy doc."""
    subject = None
    d_object = None
    for token in doc:
        # Find the nominal subject
        if "nsubj" in token.dep_:
            subject = token.lemma_.lower()
        # Find the direct object, object of a preposition, or attribute
        if "dobj" in token.dep_ or "pobj" in token.dep_ or "attr" in token.dep_:
            d_object = token.lemma_.lower()
    return subject, d_object

def _check_for_contradiction(new_fact_doc, all_existing_facts):
    """
    Analyzes a new fact against all existing facts to find a direct contradiction.
    Returns the contradictory fact if found, otherwise None.
    This is a simplified NLP approach and a key area for future improvement.
    """
    new_subject, new_object = _get_subject_and_object(new_fact_doc)
    
    # We need a subject and an object to detect a contradiction.
    if not new_subject or not new_object:
        return None

    for existing_fact in all_existing_facts:
        # Don't compare against facts that are already disputed.
        if existing_fact['status'] == 'disputed':
            continue
        
        existing_fact_doc = NLP_MODEL(existing_fact['fact_content'])
        existing_subject, existing_object = _get_subject_and_object(existing_fact_doc)
        
        # The core contradiction rule:
        # If the subject is the same, but the object/attribute is different,
        # it's a potential contradiction.
        if new_subject == existing_subject and new_object != existing_object:
            # Check for negative polarity (e.g., "is" vs. "is not")
            new_is_negated = any(tok.dep_ == 'neg' for tok in new_fact_doc)
            existing_is_negated = any(tok.dep_ == 'neg' for tok in existing_fact_doc)
            
            if new_is_negated != existing_is_negated:
                 # e.g., "Earth is flat" vs. "Earth is not flat"
                 return existing_fact
            elif not new_is_negated and not existing_is_negated:
                 # e.g., "The capital is Paris" vs. "The capital is Lyon"
                 return existing_fact
            
    return None

def extract_facts_from_text(source_url, text_content):
    """
    The main Crucible pipeline, now with a new three-step process for analyzing facts.
    1. Check for Contradiction
    2. Check for Corroboration
    3. Insert as New
    """
    print(f"\n--- [The Crucible] Analyzing content from {source_url[:60]}...")
    
    try:
        source_domain_match = re.search(r'https?://(?:www\.)?([^/]+)', source_url)
        if not source_domain_match:
            print("[The Crucible] ERROR: Could not parse domain from source URL.")
            return
        source_domain = source_domain_match.group(1)

        # Get all facts from the ledger ONCE per document for efficient comparison.
        all_facts_in_ledger = get_all_facts_for_analysis()
        
        doc = NLP_MODEL(text_content)
        
        for sent in doc.sents:
            # --- Rule-based Filtering (Unchanged) ---
            if len(sent.text.split()) < 8 or len(sent.text.split()) > 100: continue
            if not sent.ents: continue
            if any(word in sent.text.lower() for word in OPINION_WORDS): continue
            
            fact_content = sent.text.strip().replace('\n', ' ')
            new_fact_doc = NLP_MODEL(fact_content) # Process once for analysis
            
            # --- Step 1: Check for Contradictions FIRST ---
            contradictory_fact = _check_for_contradiction(new_fact_doc, all_facts_in_ledger)
            if contradictory_fact:
                new_fact_id = hashlib.sha256(fact_content.encode('utf-8')).hexdigest()
                mark_facts_as_disputed(contradictory_fact['fact_id'], new_fact_id, fact_content, source_url)
                continue # A contradiction was found and handled. Move to the next sentence.

            # --- Step 2: If no contradiction, check for Corroboration ---
            similar_fact_found = False
            for existing_fact in all_facts_in_ledger:
                try:
                    existing_domain = re.search(r'https?://(?:www\.)?([^/]+)', existing_fact['source_url']).group(1)
                    if source_domain.lower() == existing_domain.lower(): continue
                except AttributeError: continue
                
                # Using a simplified similarity check. This is a key area for future improvement.
                if fact_content[:60] == existing_fact['fact_content'][:60]:
                    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
                    new_score = existing_fact['trust_score'] + 1
                    # Safely handle potentially NULL corroborating_sources
                    existing_sources = existing_fact.get('corroborating_sources') or existing_fact['source_url']
                    new_sources = existing_sources + "," + source_url
                    cursor.execute("UPDATE facts SET trust_score = ?, status = 'trusted', corroborating_sources = ? WHERE fact_id = ?",
                                   (new_score, new_sources, existing_fact['fact_id']))
                    conn.commit(); conn.close()
                    print(f"  [Ledger] SUCCESS: Corroborated existing fact. New trust score: {new_score}")
                    similar_fact_found = True
                    break # Stop searching once a corroboration is found.
            
            if similar_fact_found:
                continue # The fact was a corroboration. Move to the next sentence.

            # --- Step 3: If no contradiction and no corroboration, insert as a new, uncorroborated fact ---
            fact_id = hashlib.sha256(fact_content.encode('utf-8')).hexdigest()
            conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
            timestamp = datetime.now(datetime.UTC).isoformat()
            try:
                cursor.execute("INSERT INTO facts (fact_id, fact_content, source_url, ingest_timestamp_utc, trust_score, status) VALUES (?, ?, ?, ?, 1, 'uncorroborated')",
                               (fact_id, fact_content, source_url, timestamp))
                conn.commit()
                print(f"  [Ledger] SUCCESS: New uncorroborated fact recorded.")
            except sqlite3.IntegrityError:
                pass # This specific fact_id already exists, so we do nothing.
            finally:
                conn.close()

    except Exception as e:
        print(f"[The Crucible] ERROR: Failed to process text. {e}")
