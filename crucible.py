# Axiom - crucible.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
# --- Corrected Function Call & Restored Return Value ---

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
    # Simple Opinion Verbs
    'believe', 'think', 'feel', 'seems', 'appears', 'argues', 'suggests', 
    'contends', 'opines', 'speculates',

    # Judgmental Adverbs & Qualifiers
    'especially', 'notably', 'remarkably', 'surprisingly', 'unfortunately',
    'clearly', 'obviously', 'reportedly', 'allegedly', 'routinely', 'likely',
    'apparently', 'essentially', 'largely',

    # Metaphorical / Idiomatic Phrases
    'wedded to', 'new heights', 'war on facts', 'playbook', 'art of',

    # Words that imply a conclusion
    'therefore', 'consequently', 'thus', 'hence', 'conclusion',

    # V2.1: Judgmental Words
    'untrue', 'false', 'incorrect', 'correctly', 'rightly', 'wrongly',
    'inappropriate', 'disparage', 'sycophants', 'unwelcome', 'flatly'
}

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
    
    if not new_subject or not new_object:
        return None

    for existing_fact in all_existing_facts:
        if existing_fact['status'] == 'disputed':
            continue
        
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
    The main V2 Crucible pipeline. It analyzes text, handles contradictions/corroborations,
    and returns a list of any newly created facts for the Synthesizer.
    """
    print(f"\n--- [The Crucible] Analyzing content from {source_url[:60]}...")
    newly_created_facts = [] # This will be our return value
    
    try:
        source_domain_match = re.search(r'https?://(?:www\.)?([^/]+)', source_url)
        if not source_domain_match:
            return newly_created_facts # Return empty list on failure
        source_domain = source_domain_match.group(1)

        all_facts_in_ledger = get_all_facts_for_analysis()
        doc = NLP_MODEL(text_content)
        
        for sent in doc.sents:
            if len(sent.text.split()) < 8 or len(sent.text.split()) > 100: continue
            if not sent.ents: continue
            if any(indicator in sent.text.lower() for indicator in SUBJECTIVITY_INDICATORS): continue
            
            fact_content = sent.text.strip().replace('\n', ' ')
            new_fact_doc = NLP_MODEL(fact_content)
            
            # Step 1: Check for Contradictions
            contradictory_fact = _check_for_contradiction(new_fact_doc, all_facts_in_ledger)
            if contradictory_fact:
                new_fact_id = hashlib.sha256(fact_content.encode('utf-8')).hexdigest()
                mark_facts_as_disputed(contradictory_fact['fact_id'], new_fact_id, fact_content, source_url)
                continue

            # Step 2: Check for Corroboration
            # --- THIS IS THE FIX ---
            # We now call the function with only the two required arguments.
            similar_fact = find_similar_fact_from_different_domain(fact_content, source_domain, all_facts_in_ledger)
            if similar_fact:
                update_fact_corroboration(similar_fact['fact_id'], source_url)
                continue

            # Step 3: Insert as a new, uncorroborated fact
            fact_id = hashlib.sha256(fact_content.encode('utf-8')).hexdigest()
            new_fact_data = insert_uncorroborated_fact(fact_id, fact_content, source_url)
            if new_fact_data:
                newly_created_facts.append(new_fact_data)

    except Exception as e:
        print(f"[The Crucible] ERROR: Failed to process text. {e}")
    
    print(f"[The Crucible] Analysis complete. Created {len(newly_created_facts)} new facts.")
    return newly_created_facts