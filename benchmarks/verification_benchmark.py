"""Axiom V4.1 Benchmark: Semantic Verification Performance."""

import random
import sys
import time
from typing import Any

import requests

# --- Configuration: Point this to your running testnet ---
SEALER_NODE_URL = "http://122.0.0.1:5000"
LISTENER_NODE_URL = (
    "http://127.0.0.1:6000"  # Assumes you are running Listener A
)


def run_benchmark() -> None:
    """Execute the full benchmark protocol."""
    print("--- Axiom V4.1 Verification Benchmark ---")
    print("Ensuring network is ready...")

    # --- Step 1: Get a "Fact to Verify" from the network ---
    try:
        response = requests.get(
            f"{SEALER_NODE_URL}/get_blocks?since=0",
            timeout=10,
        )
        response.raise_for_status()
        blocks = response.json().get("blocks", [])
        if not blocks:
            print(
                "\nERROR: No blocks found on the Sealer node. "
                "Please let the network run and find facts first.",
            )
            sys.exit(1)

        latest_block = blocks[-1]
        fact_hashes: list[str] = latest_block.get("fact_hashes", [])
        if not fact_hashes:
            print(
                "\nERROR: Latest block has no facts. "
                "Please let the network run and find facts first.",
            )
            sys.exit(1)

        # S311: We are using random for non-cryptographic selection, which is safe.
        fact_hash_to_verify = random.choice(fact_hashes)  # noqa: S311
        block_height_to_verify = latest_block["height"]

        print("  -> Network is ready. Test target selected:")
        print(f"     Fact Hash:  {fact_hash_to_verify}")
        print(f"     Block Height: {block_height_to_verify}")

    except requests.RequestException as e:
        print(
            f"\nFATAL ERROR: Could not connect to the Sealer Node at {SEALER_NODE_URL}.",
        )
        print(f"Please ensure your testnet is running. Details: {e}")
        sys.exit(1)

    print("\n--- BENCHMARK 1: The 'Old Way' (Full Node Query) ---")
    start_time = time.perf_counter()

    response = requests.post(
        f"{SEALER_NODE_URL}/get_facts_by_hash",
        json={"fact_hashes": [fact_hash_to_verify]},
        timeout=10,
    )
    fact_data: dict[str, Any] = response.json()

    end_time = time.perf_counter()
    is_verified_old_way = len(fact_data.get("facts", [])) > 0

    print(f"  -> Verification Result: {is_verified_old_way}")
    print(f"  -> Time Elapsed: {(end_time - start_time) * 1000:.2f} ms")
    print(
        "  -> Security Model: Requires running a full node and trusting your own hardware.",
    )

    print("\n--- BENCHMARK 2: The 'New Way' (V4 Listener Verification) ---")
    start_time = time.perf_counter()

    response = requests.get(
        f"{LISTENER_NODE_URL}/verify_fact_by_hash",
        params={
            "fact_hash": fact_hash_to_verify,
            "block_height": block_height_to_verify,
        },
        timeout=10,
    )
    verification_data: dict[str, Any] = response.json()

    end_time = time.perf_counter()
    is_verified_new_way = verification_data.get("verified", False)

    print(f"  -> Verification Result: {is_verified_new_way}")
    print(f"  -> Time Elapsed: {(end_time - start_time) * 1000:.2f} ms")
    print(
        "  -> Security Model: Trustless. Cryptographically verified against a lightweight header.",
    )


if __name__ == "__main__":
    run_benchmark()
