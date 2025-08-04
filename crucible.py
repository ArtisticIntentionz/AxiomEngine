# Axiom - crucible.py
# The AI core that analyzes text to extract and verify objective facts.

import spacy
import hashlib
from ledger import insert_fact # Imports the function to save facts to the database.

# Load the spaCy English language model once when the module is loaded.
# This is efficient as it prevents reloading the model every time.
NLP_MODEL = spacy.load("en_core_web_sm")

# A set of words that often indicate an opinion, not a fact.
# This helps the AI filter out subjective statements.
OPINION_WORDS = {'believe', 'think', 'feel', 'seems', 'appears', 'argues', 'suggests', 'perhaps'}

def extract_facts_from_text(source_url, text_content):
    """
    Uses a Natural Language Processing (NLP) pipeline to analyze text
    and extract high-quality, objective factual statements.
    """
    print(f"\n--- [The Crucible] Analyzing content from {source_url[:60]}...")
    
    try:
        # Process the entire text content with the NLP model.
        doc = NLP_MODEL(text_content)
        
        facts_found_in_doc = 0
        # Iterate through each sentence detected in the document.
        for sent in doc.sents:
            # --- The Crucible's Rules of Verification ---

            # Rule 1: The sentence must have a subject and an object. A simple proxy
            # is checking for a reasonable length.
            if len(sent.text.split()) < 8 or len(sent.text.split()) > 100:
                continue
            
            # Rule 2: The sentence must contain at least one recognized "Named Entity"
            # (e.g., a person, organization, place). Facts are about things.
            if not sent.ents:
                continue
            
            # Rule 3: The sentence must NOT contain any subjective opinion words.
            if any(word in sent.text.lower() for word in OPINION_WORDS):
                continue

            # If a sentence passes all rules, it is considered a potential fact.
            fact_content = sent.text.strip().replace('\n', ' ')
            
            # Create a unique, deterministic ID for this fact by hashing its content.
            fact_id = hashlib.sha256(fact_content.encode('utf-8')).hexdigest()
            
            # Attempt to insert the fact into the ledger.
            # The ledger function will handle duplicates automatically.
            if insert_fact(fact_id, fact_content, source_url):
                facts_found_in_doc += 1

        print(f"[The Crucible] Analysis complete. Stored {facts_found_in_doc} new facts.")
    except Exception as e:
        print(f"[The Crucible] ERROR: Failed to process text. {e}")