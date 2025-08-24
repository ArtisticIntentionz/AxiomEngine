# fact_reporter.py
import concurrent.futures
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Set

import requests

# --- Configuration ---
NODE_API_URL = (
    "http://127.0.0.1:8001"  # The API port of one of your running nodes
)
REPORT_FILENAME = "facts_analysis_report.txt"

# Performance tuning
BATCH_SIZE = 100  # Increased from 20
MAX_WORKERS = 4  # Parallel workers for API calls
CACHE_FILE = "fact_cache.json"  # Cache for repeated runs

# Make sure we can import server-side helpers
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")),
)
from axiom_server.common import NLP_MODEL

# --- Lightweight NLP helpers (aligned with synthesizer.py) ---


def classify_fact_type(doc):
    text = doc.text.lower()
    if any(word in text for word in ["employee", "staff", "workforce"]):
        return "company_size"
    if any(word in text for word in ["revenue", "income", "sales"]):
        return "company_revenue"
    if any(word in text for word in ["founded", "established", "since"]):
        return "founding_date"
    if any(ent.label_ == "GPE" for ent in doc.ents):
        return "location"
    return "general"


def get_main_entities(doc):
    return {
        ent.lemma_.lower()
        for ent in doc.ents
        if ent.label_ in ["PERSON", "ORG", "GPE", "EVENT"]
    }


def get_fact_doc(fact):
    """Try to reconstruct a spaCy Doc from semantics if present; else parse content."""
    semantics = fact.get("semantics")
    if semantics:
        try:
            if isinstance(semantics, str):
                semantics = json.loads(semantics)
            # Try to extract text from serialized doc payload
            doc_json = semantics.get("doc")
            if isinstance(doc_json, str):
                doc_json = json.loads(doc_json)
            text = (doc_json or {}).get("text")
            if text:
                return NLP_MODEL(text)
        except Exception:
            pass
    return NLP_MODEL(fact.get("content", ""))


def find_related_facts(fact, all_facts, min_shared_entities: int = 1):
    """Find related facts by at least N shared main entities (simple heuristic)."""
    base_doc = get_fact_doc(fact)
    base_entities = get_main_entities(base_doc)
    related = []
    if not base_entities:
        return related
    for other in all_facts:
        if other is fact or other.get("hash") == fact.get("hash"):
            continue
        other_doc = get_fact_doc(other)
        other_entities = get_main_entities(other_doc)
        if len(base_entities & other_entities) >= min_shared_entities:
            related.append(other)
    return related


def reason_for_fact(fact, related):
    if fact.get("disputed"):
        return (
            f"Contradicted by {len(related)} related fact(s) with overlapping entities."
            if related
            else "Contradicted by at least one related fact."
        )
    if fact.get("score", 0) > 0:
        return (
            f"Corroborated by {len(related)} related fact(s) with overlapping entities."
            if related
            else "Corroborated by at least one related fact."
        )
    return "No specific reason available."


def related_facts_summary(related, max_items: int = 3) -> str:
    if not related:
        return "None"
    parts = []
    for rf in related[:max_items]:
        h = rf.get("hash", "N/A")
        c = rf.get("content", "")
        snippet = c[:80] + ("..." if len(c) > 80 else "")
        parts.append(f"{h}: {snippet}")
    if len(related) > max_items:
        parts.append(f"(+{len(related) - max_items} more)")
    return " | ".join(parts)


def load_cache() -> Optional[Dict]:
    """Load cached fact data if available and recent."""
    if not os.path.exists(CACHE_FILE):
        return None

    try:
        with open(CACHE_FILE) as f:
            cache = json.load(f)

        # Check if cache is recent (less than 1 hour old)
        cache_time = cache.get("timestamp", 0)
        if time.time() - cache_time < 3600:  # 1 hour
            print(
                f"  > Using cached data from {datetime.fromtimestamp(cache_time)}",
            )
            return cache
    except Exception:
        pass
    return None


def save_cache(facts: List[Dict], fact_hashes: Set[str]):
    """Save fact data to cache for future runs."""
    try:
        cache_data = {
            "timestamp": time.time(),
            "fact_hashes": list(fact_hashes),
            "facts": facts,
        }
        with open(CACHE_FILE, "w") as f:
            json.dump(cache_data, f)
        print(f"  > Cached {len(facts)} facts for future runs")
    except Exception as e:
        print(f"  > Warning: Could not save cache: {e}")


def get_all_fact_hashes() -> set[str]:
    """Queries the node for all blocks and extracts all unique fact hashes."""
    print("Step 1: Fetching all blocks from the blockchain...")
    try:
        response = requests.get(
            f"{NODE_API_URL}/get_blocks?since=-1",
            timeout=120,
        )
        response.raise_for_status()
        blocks_data = response.json()
    except requests.RequestException as e:
        print(
            f"  [ERROR] Could not connect to the Axiom node at {NODE_API_URL}. Is it running?",
        )
        print(f"  Details: {e}")
        return set()

    all_hashes = set()
    for block in blocks_data.get("blocks", []):
        for fact_hash in block.get("fact_hashes", []):
            if fact_hash:  # Ensure we don't add empty strings
                all_hashes.add(fact_hash)

    print(
        f"  > Found {len(all_hashes)} unique fact hashes across {len(blocks_data.get('blocks', []))} blocks.",
    )
    return all_hashes


def fetch_batch_parallel(batch: List[str]) -> List[Dict]:
    """Fetch a batch of facts in parallel."""
    try:
        payload = {"fact_hashes": batch}
        response = requests.post(
            f"{NODE_API_URL}/get_facts_by_hash",
            json=payload,
            timeout=180,
        )
        response.raise_for_status()
        facts_data = response.json()
        return facts_data.get("facts", [])
    except requests.RequestException as e:
        print(f"  [ERROR] Batch failed: {e}")
        return []


def get_facts_details_optimized(fact_hashes: set[str]) -> list[dict]:
    """Optimized fact fetching with parallel processing and caching."""
    if not fact_hashes:
        return []

    # Try to load from cache first
    cache = load_cache()
    if cache and set(cache.get("fact_hashes", [])) == fact_hashes:
        print(f"  > Using cached data for {len(cache['facts'])} facts")
        return cache["facts"]

    print(
        f"\nStep 2: Fetching full details for {len(fact_hashes)} fact hashes in parallel batches...",
    )

    all_facts = []
    hash_list = list(fact_hashes)
    total_batches = (len(hash_list) + BATCH_SIZE - 1) // BATCH_SIZE

    start_time = time.time()

    # Process batches in parallel
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=MAX_WORKERS,
    ) as executor:
        # Create batches
        batches = [
            hash_list[i : i + BATCH_SIZE]
            for i in range(0, len(hash_list), BATCH_SIZE)
        ]

        # Submit all batches
        future_to_batch = {
            executor.submit(fetch_batch_parallel, batch): i + 1
            for i, batch in enumerate(batches)
        }

        # Collect results as they complete
        for future in concurrent.futures.as_completed(future_to_batch):
            batch_num = future_to_batch[future]
            try:
                batch_facts = future.result()
                all_facts.extend(batch_facts)
                elapsed = time.time() - start_time
                print(
                    f"  > Completed batch {batch_num}/{total_batches} ({len(batch_facts)} facts) - {elapsed:.1f}s elapsed",
                )
            except Exception as e:
                print(f"  > Batch {batch_num} failed: {e}")

    elapsed = time.time() - start_time
    print(
        f"  > Successfully retrieved details for {len(all_facts)} total facts in {elapsed:.1f}s",
    )

    # Save to cache for future runs
    save_cache(all_facts, fact_hashes)

    return all_facts


def generate_report_optimized(facts: list[dict]):
    """Optimized report generation with progress tracking."""
    if not facts:
        print("\nNo facts to analyze. Report will not be generated.")
        return

    print(f"\nStep 3: Generating report '{REPORT_FILENAME}'...")
    start_time = time.time()

    # Categorize and summarize relationships
    ingested_facts = []
    corroborated_facts = []
    disputed_facts = []
    potential_contradictions = []
    relationship_counts = defaultdict(int)

    print("  > Categorizing facts...")
    for i, fact in enumerate(facts):
        if i % 100 == 0:
            print(f"    Processed {i}/{len(facts)} facts...")

        if fact.get("disputed"):
            disputed_facts.append(fact)
            relationship_counts["contradiction"] += 1
        elif fact.get("score", 0) > 0:
            corroborated_facts.append(fact)
            relationship_counts["corroboration"] += 1
        else:
            ingested_facts.append(fact)

    print("  > Computing related facts...")
    # Pre-compute related facts for all facts (simple entity-overlap heuristic)
    related_map: dict[str, list[dict]] = {}
    for i, f in enumerate(facts):
        if i % 50 == 0:
            print(f"    Computing relationships for {i}/{len(facts)} facts...")
        related_map[f.get("hash", "")] = find_related_facts(f, facts)

    # --- Write the report ---
    print("  > Writing report to file...")
    with open(REPORT_FILENAME, "w", encoding="utf-8") as f:
        f.write("========================================\n")
        f.write("      AxiomEngine Fact Analysis Report\n")
        f.write("========================================\n")
        f.write(f"Generated on: {datetime.now().isoformat()}\n")
        f.write(f"Total Facts Analyzed: {len(facts)}\n\n")

        # --- Summary Section ---
        f.write("----------------------------------------\n")
        f.write("Summary of Relationships\n")
        f.write("----------------------------------------\n")
        f.writelines(
            f"{rel_type.title()}: {count}\n"
            for rel_type, count in relationship_counts.items()
        )
        f.write("\n")

        # --- Disputed Facts Section ---
        f.write("----------------------------------------\n")
        f.write(f"Disputed Facts ({len(disputed_facts)})\n")
        f.write("----------------------------------------\n")
        if not disputed_facts:
            f.write("No disputed facts found in the ledger.\n")
        else:
            for i, fact in enumerate(disputed_facts, 1):
                f.write(f"\n{i}. Fact Hash: {fact.get('hash', 'N/A')}\n")
                f.write(f"   Content: {fact.get('content', 'N/A')}\n")
                f.write(f"   Sources: {', '.join(fact.get('sources', []))}\n")
                related = related_map.get(fact.get("hash", ""), [])
                f.write(f"   Reason: {reason_for_fact(fact, related)}\n")
                f.write(
                    f"   Related Fact(s): {related_facts_summary(related)}\n",
                )
        f.write("\n")

        # --- Potential Contradictions Section ---
        f.write("----------------------------------------\n")
        f.write(
            f"Potential Contradictions ({len(potential_contradictions)})\n",
        )
        f.write("----------------------------------------\n")
        if not potential_contradictions:
            f.write("No potential contradictions flagged.\n")
        else:
            for i, fact in enumerate(potential_contradictions, 1):
                f.write(f"\n{i}. Fact Hash: {fact.get('hash', 'N/A')}\n")
                f.write(f"   Content: {fact.get('content', 'N/A')}\n")
                f.write(f"   Sources: {', '.join(fact.get('sources', []))}\n")
                related = related_map.get(fact.get("hash", ""), [])
                f.write(f"   Reason: {reason_for_fact(fact, related)}\n")
                f.write(
                    f"   Related Fact(s): {related_facts_summary(related)}\n",
                )
        f.write("\n")

        # --- Corroborated Facts Section ---
        f.write("----------------------------------------\n")
        f.write(f"Corroborated Facts ({len(corroborated_facts)})\n")
        f.write("----------------------------------------\n")
        if not corroborated_facts:
            f.write(
                "No corroborated facts found. These are facts with a score > 0.\n",
            )
        else:
            for i, fact in enumerate(corroborated_facts, 1):
                f.write(f"\n{i}. Fact Hash: {fact.get('hash', 'N/A')}\n")
                f.write(f"   Score: {fact.get('score', 0)}\n")
                f.write(f"   Content: {fact.get('content', 'N/A')}\n")
                f.write(f"   Sources: {', '.join(fact.get('sources', []))}\n")
                related = related_map.get(fact.get("hash", ""), [])
                f.write(f"   Reason: {reason_for_fact(fact, related)}\n")
                f.write(
                    f"   Related Fact(s): {related_facts_summary(related)}\n",
                )
        f.write("\n")

        # --- Ingested Facts Section ---
        f.write("----------------------------------------\n")
        f.write(f"Ingested & Awaiting Corroboration ({len(ingested_facts)})\n")
        f.write("----------------------------------------\n")
        if not ingested_facts:
            f.write("No facts are currently in the 'ingested' state.\n")
        else:
            for i, fact in enumerate(ingested_facts, 1):
                f.write(f"\n{i}. Fact Hash: {fact.get('hash', 'N/A')}\n")
                f.write(f"   Content: {fact.get('content', 'N/A')}\n")
                f.write(f"   Sources: {', '.join(fact.get('sources', []))}\n")
                doc = get_fact_doc(fact)
                fact_type = classify_fact_type(doc)
                main_entities = get_main_entities(doc)
                f.write(f"   Fact Type: {fact_type}\n")
                f.write(
                    f"   Main Entities: {', '.join(main_entities) if main_entities else 'None'}\n",
                )
        f.write("\n")

    elapsed = time.time() - start_time
    print(
        f"  > Report successfully written to {REPORT_FILENAME} in {elapsed:.1f}s",
    )


def main():
    """Main function to run the fact extraction and reporting process."""
    start_time = time.time()

    all_hashes = get_all_fact_hashes()
    if all_hashes:
        all_facts = get_facts_details_optimized(all_hashes)
        generate_report_optimized(all_facts)

    total_time = time.time() - start_time
    print(f"\nTotal execution time: {total_time:.1f}s")


if __name__ == "__main__":
    main()
