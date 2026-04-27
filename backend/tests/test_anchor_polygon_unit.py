"""Unit tests for services/anchor_polygon.py.

Strategy: deploy the real compiled contract to an in-memory eth-tester EVM,
then point PolygonAnchor at it. This exercises the full producer flow
(estimate gas → sign → submit → parse receipt) without touching real
Polygon — faster and free.
"""
from __future__ import annotations

import pytest
from eth_account import Account
from eth_tester import EthereumTester
from web3 import Web3
from web3.providers.eth_tester import EthereumTesterProvider

from services.anchor_polygon import PolygonAnchor, PolygonConfig
from services.contract_compiler import compile_contract


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def compiled():
    return compile_contract()


@pytest.fixture
def chain_setup(compiled):
    """In-memory EVM with deployed contract + funded test account.

    Returns: (w3, deployer_account, contract_address, private_key_hex)
    """
    tester = EthereumTester()
    w3 = Web3(EthereumTesterProvider(tester))

    # Create a fresh account; fund it from one of the pre-funded test accounts
    deployer_acct = Account.create()
    funder = w3.eth.accounts[0]
    w3.eth.send_transaction({
        "from": funder, "to": deployer_acct.address,
        "value": w3.to_wei(10, "ether"),
    })

    # Deploy contract from deployer_acct
    Contract = w3.eth.contract(abi=compiled.abi, bytecode=compiled.bytecode)
    deploy_tx = Contract.constructor().build_transaction({
        "from":  deployer_acct.address,
        "nonce": w3.eth.get_transaction_count(deployer_acct.address),
        "gas":   3_000_000,
        "gasPrice": w3.to_wei("1", "gwei"),
    })
    signed = deployer_acct.sign_transaction(deploy_tx)
    raw = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction")
    tx_hash = w3.eth.send_raw_transaction(raw)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    return w3, deployer_acct, receipt.contractAddress, deployer_acct.key.hex()


@pytest.fixture
def anchor(chain_setup):
    """A PolygonAnchor wired to the in-memory chain + deployed contract."""
    w3, _, contract_addr, private_key = chain_setup
    cfg = PolygonConfig(
        rpc_url="http://unused-test",  # not actually used
        private_key=private_key,
        contract_address=contract_addr,
        chain_id=131277322940537,  # eth-tester default
        confirmation_blocks=0,
        gas_buffer=1.5,
        tx_timeout_seconds=30,
    )
    return PolygonAnchor(cfg, w3=w3)


# ── PolygonConfig ───────────────────────────────────────────────────────────

class TestConfig:
    def test_from_env_reads_required_vars(self, monkeypatch):
        monkeypatch.setenv("POLYGON_RPC_URL", "https://rpc.test")
        monkeypatch.setenv("POLYGON_PRIVATE_KEY", "0x" + "a" * 64)
        monkeypatch.setenv("POLYGON_CONTRACT_ADDRESS", "0x" + "b" * 40)
        monkeypatch.setenv("POLYGON_CHAIN_ID", "80001")
        cfg = PolygonConfig.from_env()
        assert cfg.rpc_url == "https://rpc.test"
        assert cfg.chain_id == 80001
        assert cfg.private_key == "0x" + "a" * 64

    def test_from_env_missing_var_raises(self, monkeypatch):
        monkeypatch.delenv("POLYGON_RPC_URL", raising=False)
        with pytest.raises(KeyError):
            PolygonConfig.from_env()


# ── Wallet helpers ──────────────────────────────────────────────────────────

class TestWallet:
    def test_address_matches_private_key(self, anchor, chain_setup):
        _, deployer_acct, _, _ = chain_setup
        assert anchor.address == deployer_acct.address

    def test_balance_returns_funded_amount(self, anchor):
        bal = anchor.balance_matic()
        assert bal > 0
        # Initial fund was 10 ether minus gas for deploy
        assert 9.0 < bal < 10.0


# ── anchor_root: happy path ─────────────────────────────────────────────────

class TestAnchorRoot:
    async def test_anchor_succeeds_and_returns_anchor_id(self, anchor):
        root_hex = "0x" + ("ab" * 32)  # all 0xAB bytes
        result = await anchor.anchor_root(
            merkle_root=root_hex,
            timestamp=1714056789,
            cert_count=100,
            batch_count=5,
            metadata="https://aminra.vn/anchors/0",
        )
        assert result.anchor_id == 0
        assert result.tx_hash.startswith("0x") or len(result.tx_hash) == 64
        assert result.block_number > 0
        assert result.gas_used > 0
        assert result.merkle_root == root_hex

    async def test_consecutive_anchors_increment_id(self, anchor):
        for expected_id in range(3):
            r = await anchor.anchor_root(
                merkle_root=bytes([expected_id + 1] * 32).hex(),
                timestamp=1700000000 + expected_id,
                cert_count=10,
            )
            assert r.anchor_id == expected_id

    async def test_accepts_root_with_or_without_0x_prefix(self, anchor):
        # Without 0x
        r1 = await anchor.anchor_root(
            merkle_root="aa" * 32, timestamp=1, cert_count=1,
        )
        # With 0x
        r2 = await anchor.anchor_root(
            merkle_root="0x" + "bb" * 32, timestamp=2, cert_count=1,
        )
        assert r1.anchor_id == 0
        assert r2.anchor_id == 1


# ── anchor_root: validation ────────────────────────────────────────────────

class TestAnchorRootValidation:
    async def test_rejects_zero_root(self, anchor):
        with pytest.raises(ValueError, match="non-zero"):
            await anchor.anchor_root(
                merkle_root="0x" + "00" * 32,
                timestamp=1, cert_count=1,
            )

    async def test_rejects_wrong_length(self, anchor):
        with pytest.raises(ValueError, match="32 bytes"):
            await anchor.anchor_root(
                merkle_root="0x" + "ab" * 16,  # only 16 bytes
                timestamp=1, cert_count=1,
            )


# ── get_anchor: read-back ──────────────────────────────────────────────────

class TestGetAnchor:
    async def test_round_trip_anchor_then_read(self, anchor):
        root_hex = "0x" + ("cd" * 32)
        await anchor.anchor_root(
            merkle_root=root_hex, timestamp=1714056789, cert_count=42,
            batch_count=7, metadata="round-trip-test",
        )
        on_chain = await anchor.get_anchor(0)
        assert on_chain.anchor_id == 0
        assert on_chain.merkle_root == root_hex
        assert on_chain.timestamp == 1714056789
        assert on_chain.cert_count == 42
        assert on_chain.batch_count == 7
        assert on_chain.metadata == "round-trip-test"

    async def test_unknown_anchor_returns_zero_root(self, anchor):
        result = await anchor.get_anchor(999)
        assert result.merkle_root == "0x" + "00" * 32

    async def test_anchor_count_reflects_writes(self, anchor):
        assert await anchor.anchor_count() == 0
        await anchor.anchor_root(
            merkle_root="0x" + "01" * 32, timestamp=1, cert_count=1,
        )
        await anchor.anchor_root(
            merkle_root="0x" + "02" * 32, timestamp=2, cert_count=1,
        )
        assert await anchor.anchor_count() == 2


# ── Pause behavior ─────────────────────────────────────────────────────────

class TestPauseControl:
    async def test_paused_status_default_false(self, anchor):
        assert await anchor.is_paused() is False

    async def test_owner_can_pause(self, anchor):
        await anchor.set_paused(True)
        assert await anchor.is_paused() is True
        await anchor.set_paused(False)
        assert await anchor.is_paused() is False

    async def test_anchor_fails_when_paused(self, anchor):
        await anchor.set_paused(True)
        with pytest.raises(RuntimeError, match="gas estimation failed|reverted"):
            await anchor.anchor_root(
                merkle_root="0x" + "ab" * 32,
                timestamp=1, cert_count=1,
            )
        await anchor.set_paused(False)  # cleanup
