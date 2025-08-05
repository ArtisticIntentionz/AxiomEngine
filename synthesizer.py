# Axiom - synthesizer.py
# The V2 Knowledge Graph engine.

import spacy
from ledger import get_all_facts_for_analysis, insert_relationship

NLP_MODEL = spacy.load("en_core_web_sm")

def link_related_facts(new_facts_batch):
    """
    Compares a batch of new facts against the entire ledger to find and store relationships.
    """
    print("\n--- [The Synthesizer] Beginning Knowledge Graph linking...")
    if not new_facts_batch:
        print("[The Synthesizer] No new facts to link. Cycle complete.")
        return

    all_facts_in_ledger = get_all_facts_for_analysis()
    
    links_found = 0
    for new_fact in new_facts_batch:
        new_doc = NLP_MODEL(new_fact['fact_content'])
        new_entities = {ent.text.lower() for ent in new_doc.ents}

        for existing_fact in all_facts_in_ledger:
            if new_fact['fact_id'] == existing_fact['fact_id']:
                continue

            existing_doc = NLP_MODEL(existing_fact['fact_content'])
            existing_entities = {ent.text.lower() for ent in existing_doc.ents}

            # Find the number of entities that are shared between the two facts.
            shared_entities = new_entities.intersection(existing_entities)
            
            # The core relationship rule:
            if len(shared_entities) > 0:
                # Our "score" is simply the number of shared entities.
                # A higher score means a stronger contextual link.
                relationship_score = len(shared_entities)
                insert_relationship(new_fact['fact_id'], existing_fact['fact_id'], relationship_score)
                links_found += 1

    print(f"[The Synthesizer] Linking complete. Found and stored {links_found} new relationships.")