# Axiom - merkle.py
# Copyright (C) 2025 The Axiom Contributors
# This program is licensed under the Peer Production License (PPL).
# See the LICENSE file for full details.
"""A Merkle Tree engine for generating cryptographic proofs."""

from __future__ import annotations

import hashlib


def _hash_pair(left: bytes, right: bytes) -> bytes:
    """Combine and hash two byte strings using SHA-256."""
    # --- Ensure consistent ordering for hashing ---
    if left < right:
        return hashlib.sha256(left + right).digest()
    return hashlib.sha256(right + left).digest()


class MerkleTree:
    """A cryptographic tool for creating verifiable proofs of inclusion."""

    def __init__(self, data: list[str]) -> None:
        """Initialize the MerkleTree from a list of hex strings."""
        if not data:
            raise ValueError("Cannot create a Merkle Tree with no data.")

        # --- The data is ALREADY hashes. Do NOT re-hash them. ---
        sorted_data = sorted(data)
        self.leaves: list[bytes] = [bytes.fromhex(d) for d in sorted_data]

        if len(self.leaves) % 2 == 1:
            self.leaves.append(self.leaves[-1])

        self.levels: list[list[bytes]] = [self.leaves]
        while len(self.levels[-1]) > 1:
            self._build_next_level()

        self.root: bytes = self.levels[-1][0]

    def _build_next_level(self) -> None:
        """Take the last level of the tree and build the next level up."""
        last_level = self.levels[-1]
        next_level: list[bytes] = []
        for i in range(0, len(last_level), 2):
            left = last_level[i]
            right = last_level[i + 1]
            next_level.append(_hash_pair(left, right))

        if len(next_level) % 2 == 1 and len(next_level) > 1:
            next_level.append(next_level[-1])

        self.levels.append(next_level)

    def get_proof(self, index: int) -> list[str]:
        """Generate the proof of inclusion for a leaf at a given index.

        The proof is a simple list of sibling hashes in hex format.
        """
        if index < 0 or index >= len(self.leaves):
            raise IndexError("Leaf index out of range.")

        proof: list[str] = []
        for level in self.levels[:-1]:
            is_right_node = index % 2 == 1
            sibling_index = index - 1 if is_right_node else index + 1
            proof.append(level[sibling_index].hex())
            index //= 2
        return proof

    @staticmethod
    def verify_proof(
        proof: list[str],
        leaf_data: str,
        root: bytes,
    ) -> bool:
        """Verify a proof without needing the entire tree."""
        # --- The leaf_data is the hex hash. Do not re-hash. ---
        current_hash = bytes.fromhex(leaf_data)

        for sibling_hex in proof:
            sibling_hash = bytes.fromhex(sibling_hex)
            current_hash = _hash_pair(current_hash, sibling_hash)

        return current_hash == root
