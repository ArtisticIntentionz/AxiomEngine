# Axiom - crucible.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
# --- V2.2: ADDED TEXT SANITIZATION PRE-PROCESSOR ---

import spacy
import hashlib
import re
from ledger import (
    get_all_facts_for_analysis, 
    mark_facts_as_disputed,
    find_similar_fact_from_different_domain,
    update_fact_corroboration,
    insert_uncorroborated_fact
)

NLP_MODEL = spacy.load("en_core_web_sm")
SUBJECTIVITY_INDICATORS = {
    'believe', 'think', 'feel', 'seems', 'appears', 'argues', 'suggests', 
    'contends', 'opines', 'speculates', 'especially', 'notably', 'remarkably', 
    'surprisingly', 'unfortunately', 'clearly', 'obviously', 'reportedly', 
    'allegedly', 'routinely', 'likely', 'apparently', 'essentially', 'largely',
    'wedded to', 'new heights', 'war on facts', 'playbook', 'art of',
    'therefore', 'consequently', 'thus', 'hence', 'conclusion',
    'untrue', 'false', 'incorrect', 'correctly', 'rightly', 'wrongly',
    'inappropriate', 'disparage', 'sycophants', 'unwelcome', 'flatly'
}

def _sanitize_and_preprocess_text(text):
    """
    A new helper function to clean up extracted text before NLP analysis.
    Fixes run-on sentences common in topic pages and summaries.
    """
    # This regex looks for a year (e.g., 2024) followed by a capital letter,
    # which often indicates the start of a new headline without a period.
    # It inserts a period between them.
    text = re.sub(r'(\d{4})([A-Z])', r'\1. \2', text)
    # Replace multiple newlines with a single space for better sentence splitting.
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def _get_subject_and_object(doc):
    """A helper function to extract the main subject and object from a spaCy doc."""
    subject = None
    d_object = None
    for token in doc:
        if "nsubj" in token.dep_:
            subject = token.lemma_.lower()
        if "dobj" in token.dep_ or "pobj" in token.dep_ or "attr" in token.dep_:
            d_object = token.lemma_.lower()
    return subject, d_object

def _check_for_contradiction(new_fact_doc, all_existing_facts):
    """Analyzes a new fact against all existing facts to find a direct contradiction."""
    new_subject, new_object = _get_subject_and_object(new_fact_doc)
    if not new_subject or not new_object: return None
    for existing_fact in all_existing_facts:
        if existing_fact['status'] == 'disputed': continue
        existing_fact_doc = NLP_MODEL(existing_fact['fact_content'])
        existing_subject, existing_object = _get_subject_and_object(existing_fact_doc)
        if new_subject == existing_subject and new_object != existing_object:
            new_is_negated = any(tok.dep_ == 'neg' for tok in new_fact_doc)
            existing_is_negated = any(tok.dep_ == 'neg' for tok in existing_fact_doc)
            if new_is_negated != existing_is_negated or (not new_is_negated and not existing_is_negated):
                 return existing_fact
    return None

def extract_facts_from_text(source_url, text_content):
    """
    The main V2.2 Crucible pipeline. It now sanitizes text before analysis.
    """
    print(f"\n--- [The Crucible] Analyzing content from {source_url[:60]}...")
    newly_created_facts = []
    try:
        source_domain_match = re.search(r'https?://(?:www\.)?([^/]+)', source_url)
        if not source_domain_match: return newly_created_facts
        source_domain = source_domain_match.group(1)

        # Step 1: Sanitize the text
        sanitized_text = _sanitize_and_preprocess_text(text_content)
        
        all_facts_in_ledger = get_all_facts_for_analysis()
        doc = NLP_MODEL(sanitized_text)
        
        for sent in doc.sents:
            if len(sent.text.split()) < 8 or len(sent.text.split()) > 100: continue
            if not sent.ents: continue
            if any(indicator in sent.text.lower() for indicator in SUBJECTIVITY_INDICATORS): continue
            
            fact_content = sent.text.strip()
            new_fact_doc = NLP_MODEL(fact_content)
            
            # Step 2: Check for Contradictions
            contradictory_fact = _check_for_contradiction(new_fact_doc, all_facts_in_ledger)
            if contradictory_fact:
                new_fact_id = hashlib.sha256(fact_content.encode('utf-8')).hexdigest()
                mark_facts_as_disputed(contradictory_fact['fact_id'], new_fact_id, fact_content, source_url)
                continue

            # Step 3: Check for Corroboration
            # We now correctly pass all_facts_in_ledger to the function.
            similar_fact = find_similar_fact_from_different_domain(fact_content, source_domain, all_facts_in_ledger)
            if similar_fact:
                update_fact_corroboration(similar_fact['fact_id'], source_url)
                continue

            # Step 4: Insert as a new, uncorroborated fact
            fact_id = hashlib.sha256(fact_content.encode('utf-8')).hexdigest()
            new_fact_data = insert_uncorroborated_fact(fact_id, fact_content, source_url)
            if new_fact_data:
                newly_created_facts.append(new_fact_data)

    except Exception as e:
        print(f"[The Crucible] ERROR: Failed to process text. {e}")
    
    print(f"[The Crucible] Analysis complete. Created {len(newly_created_facts)} new facts.")
    return newly_created_facts