# fact_reporter.py
from datetime import datetime

import requests

# --- Configuration ---
NODE_API_URL = (
    "http://127.0.0.1:8001"  # The API port of one of your running nodes
)
REPORT_FILENAME = "facts_analysis_report.txt"


def get_all_fact_hashes() -> set[str]:
    """Queries the node for all blocks and extracts all unique fact hashes."""
    print("Step 1: Fetching all blocks from the blockchain...")
    try:
        response = requests.get(
            f"{NODE_API_URL}/get_blocks?since=-1",
            timeout=10,
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


def get_facts_details(fact_hashes: set[str]) -> list[dict]:
    """Queries the node for the full content of fact hashes, fetching in batches."""
    if not fact_hashes:
        return []

    print(
        f"\nStep 2: Fetching full details for {len(fact_hashes)} fact hashes in batches...",
    )
    all_facts = []
    hash_list = list(fact_hashes)
    BATCH_SIZE = 20

    for i in range(0, len(hash_list), BATCH_SIZE):
        batch = hash_list[i : i + BATCH_SIZE]
        print(
            f"  > Fetching batch {i // BATCH_SIZE + 1} ({len(batch)} hashes)...",
        )
        try:
            payload = {"fact_hashes": batch}
            # We increase the timeout slightly for larger requests
            response = requests.post(
                f"{NODE_API_URL}/get_facts_by_hash",
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            facts_data = response.json()
            all_facts.extend(facts_data.get("facts", []))
        except requests.RequestException as e:
            print(
                "  [ERROR] Could not fetch fact details batch from the Axiom node.",
            )
            print(f"  Details: {e}")
            # Continue to next batch, maybe this one will work
            continue

    print(
        f"  > Successfully retrieved details for {len(all_facts)} total facts.",
    )
    return all_facts


def generate_report(facts: list[dict]):
    """Analyzes the list of facts and writes a human-readable report to a file."""
    if not facts:
        print("\nNo facts to analyze. Report will not be generated.")
        return

    print(f"\nStep 3: Generating report '{REPORT_FILENAME}'...")

    # Categorize facts
    ingested_facts = []
    corroborated_facts = []
    disputed_facts = []

    for fact in facts:
        if fact.get("disputed"):
            disputed_facts.append(fact)
        elif fact.get("score", 0) > 0:
            corroborated_facts.append(fact)
        else:
            ingested_facts.append(fact)

    with open(REPORT_FILENAME, "w", encoding="utf-8") as f:
        f.write("========================================\n")
        f.write("      AxiomEngine Fact Analysis Report\n")
        f.write("========================================\n")
        f.write(f"Generated on: {datetime.now().isoformat()}\n")
        f.write(f"Total Facts Analyzed: {len(facts)}\n\n")

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
        f.write("\n")

    print(f"  > Report successfully written to {REPORT_FILENAME}")


def main():
    """Main function to run the fact extraction and reporting process."""
    all_hashes = get_all_fact_hashes()
    if all_hashes:
        all_facts = get_facts_details(all_hashes)
        generate_report(all_facts)


if __name__ == "__main__":
    main()
