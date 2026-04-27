"""Unit tests for services/merkle.py.

Pure-Python tests — no DB, no network. Exhaustive coverage of:
- Tree construction (1, 2, 4, odd, large)
- Root determinism + sensitivity
- Proof generation correctness (verify each generated proof)
- Stateless verification (doesn't need tree)
- Tamper detection (modified leaf, modified sibling, wrong root)
- Edge cases + validation
"""
from __future__ import annotations

import hashlib

import pytest

from services.merkle import (
    MerkleTree,
    ProofStep,
    hash_pair,
    sha256_hex,
)


def _h(s: str) -> str:
    return sha256_hex(s)


# ── Hash helpers ────────────────────────────────────────────────────────────

class TestHashHelpers:
    def test_sha256_hex_returns_64_chars(self):
        h = sha256_hex("hello")
        assert len(h) == 64
        # Ensure all hex
        int(h, 16)

    def test_sha256_hex_deterministic(self):
        assert sha256_hex("hello") == sha256_hex("hello")

    def test_sha256_hex_changes_on_tiny_change(self):
        assert sha256_hex("hello") != sha256_hex("hellp")

    def test_hash_pair_concatenates_bytes_then_hashes(self):
        # Reference: sha256(bytes(a) + bytes(b))
        a = _h("a")
        b = _h("b")
        expected = hashlib.sha256(bytes.fromhex(a) + bytes.fromhex(b)).hexdigest()
        assert hash_pair(a, b) == expected

    def test_hash_pair_rejects_invalid_hex(self):
        with pytest.raises(ValueError):
            hash_pair("not-hex", _h("b"))
        with pytest.raises(ValueError):
            hash_pair(_h("a"), "short")


# ── Construction ────────────────────────────────────────────────────────────

class TestTreeConstruction:
    def test_rejects_empty_input(self):
        with pytest.raises(ValueError, match="at least one leaf"):
            MerkleTree([])

    def test_rejects_invalid_leaf(self):
        with pytest.raises(ValueError, match="invalid leaf"):
            MerkleTree([_h("a"), "not-a-real-hash"])

    def test_single_leaf_tree_root_equals_leaf(self):
        leaf = _h("only")
        tree = MerkleTree([leaf])
        assert tree.root == leaf
        assert tree.leaf_count == 1
        assert tree.depth == 0

    def test_two_leaves_root_is_hash_of_pair(self):
        a, b = _h("a"), _h("b")
        tree = MerkleTree([a, b])
        assert tree.root == hash_pair(a, b)
        assert tree.depth == 1

    def test_four_leaves_root(self):
        a, b, c, d = (_h(c) for c in "abcd")
        tree = MerkleTree([a, b, c, d])
        ab = hash_pair(a, b)
        cd = hash_pair(c, d)
        assert tree.root == hash_pair(ab, cd)
        assert tree.depth == 2

    def test_odd_leaves_duplicate_last_pair(self):
        # 3 leaves: pad last → still hashes correctly
        a, b, c = (_h(x) for x in "abc")
        tree = MerkleTree([a, b, c])
        ab = hash_pair(a, b)
        cc = hash_pair(c, c)  # duplicated
        assert tree.root == hash_pair(ab, cc)

    def test_seven_leaves_uneven_levels(self):
        leaves = [_h(f"cert-{i}") for i in range(7)]
        tree = MerkleTree(leaves)
        # depth should be 3 (7 → 4 → 2 → 1)
        assert tree.depth == 3
        # Root must be deterministic
        tree2 = MerkleTree(leaves)
        assert tree.root == tree2.root

    def test_large_tree_1024_leaves(self):
        leaves = [_h(f"cert-{i}") for i in range(1024)]
        tree = MerkleTree(leaves)
        # 1024 = 2^10 → depth 10, no padding needed
        assert tree.depth == 10
        assert tree.leaf_count == 1024


# ── Root sensitivity ────────────────────────────────────────────────────────

class TestRootSensitivity:
    def test_changing_one_leaf_changes_root(self):
        leaves = [_h(f"cert-{i}") for i in range(8)]
        original = MerkleTree(leaves).root
        # Mutate leaf 3
        leaves[3] = _h("cert-tampered")
        mutated = MerkleTree(leaves).root
        assert original != mutated

    def test_reordering_leaves_changes_root(self):
        leaves = [_h(f"cert-{i}") for i in range(4)]
        a = MerkleTree(leaves).root
        # Swap leaves 1 and 2
        leaves[1], leaves[2] = leaves[2], leaves[1]
        b = MerkleTree(leaves).root
        assert a != b


# ── Proof generation ───────────────────────────────────────────────────────

class TestProofGeneration:
    def test_proof_for_known_leaf(self):
        leaves = [_h(f"cert-{i}") for i in range(4)]
        tree = MerkleTree(leaves)
        proof = tree.proof_for(leaves[2])
        # 4 leaves → depth 2 → proof has 2 steps
        assert len(proof) == 2

    def test_proof_round_trip_verifies_with_static_method(self):
        leaves = [_h(f"cert-{i}") for i in range(8)]
        tree = MerkleTree(leaves)
        for i, leaf in enumerate(leaves):
            proof = tree.proof_for_index(i)
            assert MerkleTree.verify_proof(leaf, proof, tree.root), \
                f"proof for leaf #{i} did not verify"

    def test_proof_works_for_odd_size_tree(self):
        leaves = [_h(f"cert-{i}") for i in range(7)]
        tree = MerkleTree(leaves)
        for i, leaf in enumerate(leaves):
            proof = tree.proof_for_index(i)
            assert MerkleTree.verify_proof(leaf, proof, tree.root)

    def test_proof_for_unknown_leaf_raises(self):
        leaves = [_h(f"cert-{i}") for i in range(4)]
        tree = MerkleTree(leaves)
        with pytest.raises(ValueError, match="not in tree"):
            tree.proof_for(_h("not-there"))

    def test_proof_for_invalid_index_raises(self):
        leaves = [_h(f"cert-{i}") for i in range(4)]
        tree = MerkleTree(leaves)
        with pytest.raises(ValueError, match="out of range"):
            tree.proof_for_index(10)

    def test_proof_size_is_log2_of_leaf_count(self):
        # 1024 leaves should give exactly 10 proof steps
        leaves = [_h(f"cert-{i}") for i in range(1024)]
        tree = MerkleTree(leaves)
        proof = tree.proof_for_index(500)
        assert len(proof) == 10


# ── Verification (stateless) ───────────────────────────────────────────────

class TestVerifyProof:
    def test_verify_accepts_valid_proof(self):
        leaves = [_h(f"cert-{i}") for i in range(8)]
        tree = MerkleTree(leaves)
        proof = tree.proof_for_index(3)
        assert MerkleTree.verify_proof(leaves[3], proof, tree.root) is True

    def test_verify_rejects_tampered_leaf(self):
        leaves = [_h(f"cert-{i}") for i in range(8)]
        tree = MerkleTree(leaves)
        proof = tree.proof_for_index(3)
        # Use a different leaf with the same proof — must fail
        assert MerkleTree.verify_proof(_h("forged"), proof, tree.root) is False

    def test_verify_rejects_tampered_proof_step(self):
        leaves = [_h(f"cert-{i}") for i in range(8)]
        tree = MerkleTree(leaves)
        proof = tree.proof_for_index(3)
        # Mutate the first sibling
        bad = [ProofStep(sibling=_h("evil"), position=proof[0].position)] + proof[1:]
        assert MerkleTree.verify_proof(leaves[3], bad, tree.root) is False

    def test_verify_rejects_wrong_root(self):
        leaves = [_h(f"cert-{i}") for i in range(8)]
        tree = MerkleTree(leaves)
        proof = tree.proof_for_index(3)
        wrong_root = _h("not the root")
        assert MerkleTree.verify_proof(leaves[3], proof, wrong_root) is False

    def test_verify_accepts_proof_as_dicts(self):
        # External verifier may load proof from JSON — must accept dict form
        leaves = [_h(f"cert-{i}") for i in range(4)]
        tree = MerkleTree(leaves)
        proof_dicts = [step.to_dict() for step in tree.proof_for_index(1)]
        assert MerkleTree.verify_proof(leaves[1], proof_dicts, tree.root) is True

    def test_verify_rejects_invalid_position_value(self):
        leaves = [_h(f"cert-{i}") for i in range(2)]
        tree = MerkleTree(leaves)
        bad_proof = [ProofStep(sibling=_h("x"), position="DIAGONAL")]
        assert MerkleTree.verify_proof(leaves[0], bad_proof, tree.root) is False

    def test_verify_rejects_non_hex_input(self):
        assert MerkleTree.verify_proof("not-hex", [], _h("root")) is False
        assert MerkleTree.verify_proof(_h("leaf"), [], "not-hex") is False


# ── Serialization for DB ───────────────────────────────────────────────────

class TestSerialization:
    def test_proofs_for_all_returns_dicts_per_leaf(self):
        leaves = [_h(f"cert-{i}") for i in range(4)]
        tree = MerkleTree(leaves)
        all_proofs = tree.proofs_for_all()
        assert len(all_proofs) == 4
        # Each proof is a list of dicts with the right keys
        for p in all_proofs:
            assert all(set(step.keys()) == {"sibling", "position"} for step in p)

    def test_proof_step_dict_round_trip(self):
        original = ProofStep(sibling=_h("x"), position="left")
        d = original.to_dict()
        restored = ProofStep.from_dict(d)
        assert original == restored


# ── Real-world scenario: cert anchoring ────────────────────────────────────

class TestCertAnchoringScenario:
    """End-to-end Merkle scenario as used by the daily anchor job."""

    def test_100_certs_anchor_and_individual_verify(self):
        # Simulate 100 cert hashes
        cert_hashes = [_h(f"HALAL-2026-{i:04d}") for i in range(100)]
        tree = MerkleTree(cert_hashes)
        root = tree.root

        # Persist proofs (simulating DB write)
        all_proofs = tree.proofs_for_all()
        assert len(all_proofs) == 100

        # Verifier (e.g., importer) only knows the root + a single proof
        # Pick cert #42 — verify it's part of the anchored batch
        idx = 42
        leaf = cert_hashes[idx]
        proof_for_42 = all_proofs[idx]
        assert MerkleTree.verify_proof(leaf, proof_for_42, root) is True

        # If someone tampers cert #42, verification fails
        tampered = _h("HALAL-2026-0042-FORGED")
        assert MerkleTree.verify_proof(tampered, proof_for_42, root) is False

    def test_proof_size_practical(self):
        # 100 certs → proof is at most ceil(log2(100)) = 7 hashes = ~480 bytes JSON.
        # That's tiny — fits in a QR code or URL parameter.
        cert_hashes = [_h(f"HALAL-2026-{i:04d}") for i in range(100)]
        tree = MerkleTree(cert_hashes)
        proof = tree.proof_for_index(50)
        assert len(proof) <= 7
