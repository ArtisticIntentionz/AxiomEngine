# fact_reporter_db.py - Direct database access version for maximum speed
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from typing import Dict, List

# Make sure we can import server-side helpers
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")),
)

# Direct database imports
from axiom_server.common import NLP_MODEL
from axiom_server.ledger import Fact, SessionMaker

REPORT_FILENAME = "facts_analysis_report_db.txt"

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
    semantics = (
        fact.get("semantics") if isinstance(fact, dict) else fact.semantics
    )
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
    content = (
        fact.get("content", "")
        if isinstance(fact, dict)
        else (fact.content or "")
    )
    return NLP_MODEL(content)


def find_related_facts(fact, all_facts, min_shared_entities: int = 1):
    """Find related facts by at least N shared main entities (simple heuristic)."""
    base_doc = get_fact_doc(fact)
    base_entities = get_main_entities(base_doc)
    related = []
    if not base_entities:
        return related
    for other in all_facts:
        fact_hash = (
            fact.get("hash", "") if isinstance(fact, dict) else fact.hash
        )
        other_hash = (
            other.get("hash", "") if isinstance(other, dict) else other.hash
        )
        if other is fact or other_hash == fact_hash:
            continue
        other_doc = get_fact_doc(other)
        other_entities = get_main_entities(other_doc)
        if len(base_entities & other_entities) >= min_shared_entities:
            related.append(other)
    return related


def reason_for_fact(fact, related):
    disputed = (
        fact.get("disputed") if isinstance(fact, dict) else fact.disputed
    )
    score = fact.get("score", 0) if isinstance(fact, dict) else fact.score

    if disputed:
        return (
            f"Contradicted by {len(related)} related fact(s) with overlapping entities."
            if related
            else "Contradicted by at least one related fact."
        )
    if score > 0:
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
        h = rf.get("hash", "") if isinstance(rf, dict) else rf.hash
        c = (
            rf.get("content", "")
            if isinstance(rf, dict)
            else (rf.content or "")
        )
        snippet = c[:80] + ("..." if len(c) > 80 else "")
        parts.append(f"{h}: {snippet}")
    if len(related) > max_items:
        parts.append(f"(+{len(related) - max_items} more)")
    return " | ".join(parts)


def get_facts_from_database() -> List[Dict]:
    """Direct database access for maximum speed."""
    print("Step 1: Loading facts directly from database...")
    start_time = time.time()

    with SessionMaker() as session:
        # Get all facts with their sources
        facts = session.query(Fact).all()

        # Convert to dict format for compatibility
        facts_data = []
        for fact in facts:
            fact_dict = {
                "hash": fact.hash,
                "content": fact.content,
                "score": fact.score,
                "disputed": fact.disputed,
                "semantics": fact.semantics,
                "sources": [source.domain for source in fact.sources]
                if fact.sources
                else [],
            }
            facts_data.append(fact_dict)

    elapsed = time.time() - start_time
    print(
        f"  > Loaded {len(facts_data)} facts from database in {elapsed:.1f}s",
    )
    return facts_data


def generate_report_optimized(facts: list[dict]):
    """Optimized report generation with progress tracking."""
    if not facts:
        print("\nNo facts to analyze. Report will not be generated.")
        return

    print(f"\nStep 2: Generating report '{REPORT_FILENAME}'...")
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
        f.write(f"Total Facts Analyzed: {len(facts)}\n")
        f.write("Method: Direct Database Access\n\n")

        # --- Summary Section ---
        f.write("----------------------------------------\n")
        f.write("Summary of Relationships\n")
        f.write("----------------------------------------\n")
        f.writelines(f"{rel_type.title()}: {count}\n" for rel_type, count in relationship_counts.items())
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

    try:
        all_facts = get_facts_from_database()
        generate_report_optimized(all_facts)
    except Exception as e:
        print(f"Error accessing database: {e}")
        print(
            "Make sure you're running this from the same environment as the Axiom node",
        )
        print("and that the database file is accessible.")
        return

    total_time = time.time() - start_time
    print(f"\nTotal execution time: {total_time:.1f}s")


if __name__ == "__main__":
    main()
