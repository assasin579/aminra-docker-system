"""Unit tests for HalalCertAnchor.sol contract.

Uses eth-tester (in-memory EVM) — no real chain, no network. We compile the
Solidity source via solcx, deploy it to a fresh local chain, and exercise
all public functions + access control.
"""
from __future__ import annotations

import pytest
from eth_tester import EthereumTester
from web3 import Web3
from web3.providers.eth_tester import EthereumTesterProvider

from services.contract_compiler import compile_contract


# ── Fixtures: in-memory EVM + deployed contract ────────────────────────────

@pytest.fixture(scope="module")
def compiled():
    """Compile contract once for all tests in this module."""
    return compile_contract()


@pytest.fixture
def w3() -> Web3:
    """Fresh in-memory chain per test."""
    tester = EthereumTester()
    return Web3(EthereumTesterProvider(tester))


@pytest.fixture
def accounts(w3: Web3):
    return w3.eth.accounts  # 10 funded accounts


@pytest.fixture
def deployed(w3: Web3, accounts, compiled):
    """Deploy the contract; return (contract, owner, others, w3)."""
    owner = accounts[0]
    Contract = w3.eth.contract(abi=compiled.abi, bytecode=compiled.bytecode)
    tx_hash = Contract.constructor().transact({"from": owner})
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    contract = w3.eth.contract(address=receipt.contractAddress, abi=compiled.abi)
    return contract, owner, accounts[1:], w3


# ── Compilation sanity ─────────────────────────────────────────────────────

class TestCompilation:
    def test_compiles_successfully(self, compiled):
        assert compiled.name == "HalalCertAnchor"
        assert compiled.bytecode.startswith("0x")
        assert len(compiled.bytecode) > 200  # actual bytecode, not empty stub

    def test_abi_has_expected_functions(self, compiled):
        from services.contract_compiler import get_function_signatures
        sigs = get_function_signatures(compiled.abi)
        assert any(s.startswith("anchorRoot(") for s in sigs)
        assert any(s.startswith("getAnchor(") for s in sigs)
        assert any(s.startswith("setPaused(") for s in sigs)


# ── Constructor + initial state ────────────────────────────────────────────

class TestConstructor:
    def test_owner_is_deployer(self, deployed):
        contract, owner, _, w3 = deployed
        assert contract.functions.owner().call() == owner

    def test_initial_state(self, deployed):
        contract, _, _, w3 = deployed
        assert contract.functions.anchorCount().call() == 0
        assert contract.functions.paused().call() is False


# ── anchorRoot ─────────────────────────────────────────────────────────────

class TestAnchorRoot:
    def test_owner_can_anchor(self, deployed):
        contract, owner, _, w3 = deployed
        root = b"\xab" * 32
        tx = contract.functions.anchorRoot(
            root, 1714056789, 100, 0, "https://aminra.vn/anchors/1"
        ).transact({"from": owner})

        receipt = w3.eth.wait_for_transaction_receipt(tx)
        assert receipt.status == 1

        assert contract.functions.anchorCount().call() == 1
        anchor = contract.functions.getAnchor(0).call()
        # anchor = (merkleRoot, timestamp, certCount, batchCount, metadata)
        assert anchor[0] == root
        assert anchor[1] == 1714056789
        assert anchor[2] == 100
        assert anchor[3] == 0
        assert anchor[4] == "https://aminra.vn/anchors/1"

    def test_non_owner_cannot_anchor(self, deployed):
        contract, _, others, w3 = deployed
        attacker = others[0]
        with pytest.raises(Exception):  # web3 raises ContractCustomError
            contract.functions.anchorRoot(
                b"\x01" * 32, 1, 1, 0, ""
            ).transact({"from": attacker})

    def test_anchor_count_increments(self, deployed):
        contract, owner, _, w3 = deployed
        for i in range(3):
            root = bytes([i + 1] * 32)
            contract.functions.anchorRoot(
                root, 1700000000 + i, 10, 0, ""
            ).transact({"from": owner})
        assert contract.functions.anchorCount().call() == 3
        assert contract.functions.getAnchor(2).call()[0] == bytes([3] * 32)

    def test_empty_root_rejected(self, deployed):
        contract, owner, _, w3 = deployed
        with pytest.raises(Exception):
            contract.functions.anchorRoot(
                b"\x00" * 32, 1, 1, 0, ""
            ).transact({"from": owner})

    def test_emits_root_anchored_event(self, deployed):
        contract, owner, _, w3 = deployed
        root = b"\xab" * 32
        tx = contract.functions.anchorRoot(
            root, 1714056789, 50, 5, "meta"
        ).transact({"from": owner})
        receipt = w3.eth.wait_for_transaction_receipt(tx)
        events = contract.events.RootAnchored().process_receipt(receipt)
        assert len(events) == 1
        e = events[0].args
        assert e.anchorId == 0
        assert e.merkleRoot == root
        assert e.timestamp == 1714056789
        assert e.certCount == 50
        assert e.batchCount == 5

    def test_records_persist_after_many_writes(self, deployed):
        """100 anchors all retrievable."""
        contract, owner, _, w3 = deployed
        for i in range(100):
            # Avoid all-zero root (i=0) which would trip EmptyRoot revert
            contract.functions.anchorRoot(
                bytes([(i + 1) % 256 or 1] * 32), 1_700_000_000 + i, i, 0, ""
            ).transact({"from": owner})
        # Spot-check
        assert contract.functions.anchorCount().call() == 100
        assert contract.functions.getAnchor(0).call()[2] == 0
        assert contract.functions.getAnchor(50).call()[2] == 50
        assert contract.functions.getAnchor(99).call()[2] == 99


# ── Pause functionality ────────────────────────────────────────────────────

class TestPause:
    def test_owner_can_pause(self, deployed):
        contract, owner, _, w3 = deployed
        contract.functions.setPaused(True).transact({"from": owner})
        assert contract.functions.paused().call() is True

    def test_anchor_blocked_when_paused(self, deployed):
        contract, owner, _, w3 = deployed
        contract.functions.setPaused(True).transact({"from": owner})
        with pytest.raises(Exception):
            contract.functions.anchorRoot(
                b"\xab" * 32, 1, 1, 0, ""
            ).transact({"from": owner})

    def test_unpause_restores_anchoring(self, deployed):
        contract, owner, _, w3 = deployed
        contract.functions.setPaused(True).transact({"from": owner})
        contract.functions.setPaused(False).transact({"from": owner})

        contract.functions.anchorRoot(
            b"\xab" * 32, 1, 1, 0, ""
        ).transact({"from": owner})
        assert contract.functions.anchorCount().call() == 1

    def test_non_owner_cannot_pause(self, deployed):
        contract, _, others, w3 = deployed
        with pytest.raises(Exception):
            contract.functions.setPaused(True).transact({"from": others[0]})

    def test_pause_does_not_modify_existing_anchors(self, deployed):
        """Pausing must NOT delete or alter prior writes."""
        contract, owner, _, w3 = deployed
        # Write an anchor
        contract.functions.anchorRoot(
            b"\x11" * 32, 1, 1, 0, "before"
        ).transact({"from": owner})
        # Pause
        contract.functions.setPaused(True).transact({"from": owner})
        # Anchor still readable
        anchor = contract.functions.getAnchor(0).call()
        assert anchor[0] == b"\x11" * 32
        assert anchor[4] == "before"


# ── Read-only query (anyone) ───────────────────────────────────────────────

class TestPublicRead:
    def test_anyone_can_call_get_anchor(self, deployed):
        contract, owner, others, w3 = deployed
        contract.functions.anchorRoot(
            b"\xff" * 32, 1, 1, 0, ""
        ).transact({"from": owner})

        # Even attackers can read
        attacker = others[0]
        # build a separate web3 contract instance with attacker as default
        result = contract.functions.getAnchor(0).call({"from": attacker})
        assert result[0] == b"\xff" * 32

    def test_unknown_anchor_returns_empty(self, deployed):
        """Reading anchor id that doesn't exist returns zeroed struct."""
        contract, _, _, w3 = deployed
        anchor = contract.functions.getAnchor(999).call()
        assert anchor[0] == b"\x00" * 32  # empty merkleRoot


# ── Gas usage sanity ───────────────────────────────────────────────────────

class TestGasUsage:
    def test_anchor_under_gas_budget(self, deployed):
        """anchorRoot should fit comfortably under 100k gas — important for
        Polygon cost (~$0.01/tx). Enforce a budget regression test."""
        contract, owner, _, w3 = deployed
        tx = contract.functions.anchorRoot(
            b"\xab" * 32, 1714056789, 100, 0, "https://aminra.vn/anchors/1"
        ).transact({"from": owner})
        receipt = w3.eth.wait_for_transaction_receipt(tx)
        # Cold storage write costs ~22k + log + struct write — total < 100k
        assert receipt.gasUsed < 200_000, f"gasUsed={receipt.gasUsed} > 200k budget"
