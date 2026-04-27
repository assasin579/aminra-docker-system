"""Pure-Python Merkle tree for anchoring cert/batch hashes.

Design:
- SHA-256 throughout (compatible with Solidity keccak/sha256 if normalized)
- Hex string interface (no raw bytes leaking out)
- Odd leaves duplicated last leaf (Bitcoin-style; deterministic)
- Proof = list of {sibling_hash, position} where position is "left"|"right"
- Verification recomputes root from leaf + proof, compares against expected

No external deps — uses only stdlib hashlib. 100% testable in-process.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable


# ── Hash helpers ────────────────────────────────────────────────────────────

def sha256_hex(data: str | bytes) -> str:
    """Hex digest of SHA-256."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def hash_pair(left_hex: str, right_hex: str) -> str:
    """Concatenate two hex hashes (as bytes) and SHA-256 the result.

    Bitcoin/Solidity-style: convert hex to bytes, concat, hash. Keeps
    on-chain verification simple if we expose the same scheme there later.
    """
    if not (_is_valid_hex(left_hex) and _is_valid_hex(right_hex)):
        raise ValueError("hash inputs must be 64-char hex strings")
    combined = bytes.fromhex(left_hex) + bytes.fromhex(right_hex)
    return hashlib.sha256(combined).hexdigest()


def _is_valid_hex(s: str) -> bool:
    if not isinstance(s, str) or len(s) != 64:
        return False
    try:
        int(s, 16)
    except ValueError:
        return False
    return True


# ── Proof record ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ProofStep:
    sibling: str       # hex hash of sibling at this level
    position: str      # "left" if sibling on the left, else "right"

    def to_dict(self) -> dict:
        return {"sibling": self.sibling, "position": self.position}

    @classmethod
    def from_dict(cls, d: dict) -> "ProofStep":
        return cls(sibling=d["sibling"], position=d["position"])


# ── Tree ────────────────────────────────────────────────────────────────────

class MerkleTree:
    """Build a Merkle tree from a list of hex-leaf-hashes."""

    def __init__(self, leaves: list[str]):
        if not leaves:
            raise ValueError("MerkleTree requires at least one leaf")
        for leaf in leaves:
            if not _is_valid_hex(leaf):
                raise ValueError(f"invalid leaf hash: {leaf!r}")
        self.leaves = list(leaves)
        # `levels[0]` = leaves; `levels[-1]` = [root]
        self.levels: list[list[str]] = [list(leaves)]
        self._build()

    def _build(self) -> None:
        current = list(self.leaves)
        while len(current) > 1:
            # Duplicate last hash if odd count (Bitcoin-style)
            if len(current) % 2 == 1:
                current = current + [current[-1]]
            next_level = [
                hash_pair(current[i], current[i + 1])
                for i in range(0, len(current), 2)
            ]
            self.levels.append(next_level)
            current = next_level

    @property
    def root(self) -> str:
        """Final Merkle root hash (hex)."""
        return self.levels[-1][0]

    @property
    def leaf_count(self) -> int:
        return len(self.leaves)

    @property
    def depth(self) -> int:
        """Number of hash-levels above leaves."""
        return len(self.levels) - 1

    # ── Proof generation ───────────────────────────────────────────────────

    def proof_for(self, leaf: str) -> list[ProofStep]:
        """Return the Merkle proof path for a given leaf.

        Raises ValueError if leaf not found.
        """
        try:
            index = self.leaves.index(leaf)
        except ValueError:
            raise ValueError(f"leaf not in tree: {leaf!r}")
        return self.proof_for_index(index)

    def proof_for_index(self, index: int) -> list[ProofStep]:
        """Return the Merkle proof path for the leaf at `index`."""
        if not (0 <= index < self.leaf_count):
            raise ValueError(f"leaf_index {index} out of range [0, {self.leaf_count})")
        path: list[ProofStep] = []
        idx = index
        for level in self.levels[:-1]:  # all but root
            # Bitcoin-style duplicate: at every level, if idx is the last and odd,
            # the sibling is itself.
            level_with_duplicates = level + ([level[-1]] if len(level) % 2 == 1 else [])
            sibling_idx = idx ^ 1  # flip last bit
            sibling = level_with_duplicates[sibling_idx]
            position = "left" if sibling_idx < idx else "right"
            path.append(ProofStep(sibling=sibling, position=position))
            idx //= 2
        return path

    # ── Verification (static — verifier doesn't need the whole tree) ───────

    @staticmethod
    def verify_proof(leaf: str, proof: Iterable[ProofStep | dict], root: str) -> bool:
        """Recompute root from leaf + proof and compare to expected root.

        Pure stateless — caller does NOT need the original tree. This is what
        an external verifier (importer, regulator, on-chain contract) runs.
        """
        if not _is_valid_hex(leaf) or not _is_valid_hex(root):
            return False

        current = leaf
        for step in proof:
            if isinstance(step, dict):
                step = ProofStep.from_dict(step)
            try:
                if step.position == "left":
                    current = hash_pair(step.sibling, current)
                elif step.position == "right":
                    current = hash_pair(current, step.sibling)
                else:
                    return False
            except ValueError:
                return False
        return current == root

    # ── Serialization helpers for DB storage ───────────────────────────────

    def proofs_for_all(self) -> list[list[dict]]:
        """Return proof paths for every leaf as JSON-ready dicts.

        Matches the schema we'll persist into cert_anchor_proofs.proof_path
        (JSONB column).
        """
        return [
            [step.to_dict() for step in self.proof_for_index(i)]
            for i in range(self.leaf_count)
        ]
