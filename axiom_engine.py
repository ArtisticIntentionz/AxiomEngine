# Axiom - axiom_engine.py
# The main orchestrator for the Autonomous Scrubber Engine (ASE).

import zeitgeist_engine
import universal_extractor
import crucible
from ledger import initialize_database

def run_axiom_engine():
    """
    Executes one full cycle of the Axiom learning process.
    """
    print("====== [AXIOM ENGINE STARTING FULL CYCLE] ======")
    
    # Step 0: Ensure the database is ready for use.
    initialize_database()
    print("[Engine] Database initialized.")
    
    # Step 1: Discover what is important in the world right now.
    # We'll start by processing the top 3 trending topics.
    topics = zeitgeist_engine.get_trending_topics(top_n=3)
    
    if not topics:
        print("[Engine] Halting cycle: No topics were discovered.")
        return

    # Step 2 & 3: For each discovered topic, find sources, extract content,
    # and distill it into verifiable facts in The Crucible.
    for topic in topics:
        # Find and extract content from up to 2 top-tier sources per topic.
        content_list = universal_extractor.find_and_extract(topic, max_sources=2)
        
        # Analyze each piece of retrieved content to find and store facts.
        for item in content_list:
            crucible.extract_facts_from_text(item['source_url'], item['content'])
    
    print("\n====== [AXIOM ENGINE CYCLE COMPLETE] ======")

if __name__ == "__main__":
    # This block allows us to run the engine directly from the command line.
    run_axiom_engine()