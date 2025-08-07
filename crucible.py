# Axiom - crucible.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
# --- V2.5: UNIFIED VERSION WITH COMMUNITY REFACTOR AND ROBUST SANITIZATION ---

import logging
import sys
import hashlib
import re
from ledger import (
    get_all_facts_for_analysis,
    mark_facts_as_disputed,
    find_similar_fact_from_different_domain,
    update_fact_corroboration,
    insert_uncorroborated_fact,
)

# Community Change: NLP_MODEL and SUBJECTIVITY_INDICATORS are now imported from a central file.
from common import NLP_MODEL, SUBJECTIVITY_INDICATORS

# Community Change: Professional logging setup.
logger = logging.getLogger("crucible")
stdout_handler = logging.StreamHandler(stream=sys.stdout)
stdout_handler.setFormatter(
    logging.Formatter(
        "[%(name)s] %(asctime)s | %(levelname)s | %(filename)s:%(lineno)s >>> %(message)s"
    )
)
logger.addHandler(stdout_handler)
logger.setLevel(logging.INFO)

# --- OUR UPGRADE: A more robust list of noise patterns to be removed. ---
METADATA_NOISE_PATTERNS = [
    re.compile(r'^\d+\s*'),
    re.compile(r'^(By and\s*)?\d*[\d\s]*(min read|Heard on the Street)\s*', re.IGNORECASE),
    re.compile(r'^Advertisement\s*', re.IGNORECASE)
]

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
        if existing_fact["status"] == "disputed":
            continue
        existing_fact_doc = NLP_MODEL(existing_fact["fact_content"])
        existing_subject, existing_object = _get_subject_and_object(existing_fact_doc)
        if new_subject == existing_subject and new_object != existing_object:
            new_is_negated = any(tok.dep_ == "neg" for tok in new_fact_doc)
            existing_is_negated = any(tok.dep_ == "neg" for tok in existing_fact_doc)
            if new_is_negated != existing_is_negated or (
                not new_is_negated and not existing_is_negated
            ):
                return existing_fact
    return None

def extract_facts_from_text(source_url, text_content):
    """
    The main V2.5 Crucible pipeline. Now with professional logging and robust, per-sentence sanitization.
    """
    logger.info(f"analyzing content from {source_url[:60]}...")
    newly_created_facts = []
    try:
        source_domain_match = re.search(r"https?://(?:www\.)?([^/]+)", source_url)
        if not source_domain_match:
            return newly_created_facts
        source_domain = source_domain_match.group(1)

        # We do a basic, global text clean first for run-on sentences and whitespace.
        preprocessed_text = re.sub(r"(\d{4})([A-Z])", r"\1. \2", text_content)
        preprocessed_text = re.sub(r"\s+", " ", preprocessed_text).strip()

        all_facts_in_ledger = get_all_facts_for_analysis()
        doc = NLP_MODEL(preprocessed_text)

        for sent in doc.sents:
            fact_content = sent.text.strip()

            # --- OUR UPGRADE: We now loop through our noise patterns and clean EACH sentence. ---
            for pattern in METADATA_NOISE_PATTERNS:
                fact_content = pattern.sub('', fact_content).strip()

            # Now, perform our standard checks on the FULLY CLEANED sentence
            if len(fact_content.split()) < 8 or len(fact_content.split()) > 100:
                continue
            if not fact_content or not NLP_MODEL(fact_content).ents:
                continue
            if any(indicator in fact_content.lower() for indicator in SUBJECTIVITY_INDICATORS):
                continue

            new_fact_doc = NLP_MODEL(fact_content)
            
            contradictory_fact = _check_for_contradiction(new_fact_doc, all_facts_in_ledger)
            if contradictory_fact:
                new_fact_id = hashlib.sha256(fact_content.encode("utf-8")).hexdigest()
                mark_facts_as_disputed(contradictory_fact["fact_id"], new_fact_id, fact_content, source_url)
                continue

            similar_fact = find_similar_fact_from_different_domain(fact_content, source_domain, all_facts_in_ledger)
            if similar_fact:
                update_fact_corroboration(similar_fact["fact_id"], source_url)
                continue

            fact_id = hashlib.sha256(fact_content.encode("utf-8")).hexdigest()
            new_fact_data = insert_uncorroborated_fact(fact_id, fact_content, source_url)
            if new_fact_data:
                newly_created_facts.append(new_fact_data)

    except Exception as e:
        logger.exception(f"failed to process text: {e}")

    logger.info(f"analysis complete. Created {len(newly_created_facts)} new facts.")
    return newly_created_facts