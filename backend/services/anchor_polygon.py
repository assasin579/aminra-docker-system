"""Polygon anchor service.

Wraps the deployed HalalCertAnchor contract behind an async-friendly
interface. Used by the daily ARQ job to submit Merkle roots and by the
public verify endpoint to read confirmed anchors.

Wallet private key + RPC URL come from env (populated from Vault in prod).

Reusability: the same code targets Polygon mainnet, Polygon Mumbai testnet,
or any local in-memory EVM (eth-tester) — `web3` is just configured with
the right provider URL.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Optional

from eth_account import Account
from web3 import Web3

from services.contract_compiler import compile_contract

log = logging.getLogger("aminra.anchor_polygon")


# ── Config ──────────────────────────────────────────────────────────────────


@dataclass
class PolygonConfig:
    rpc_url: str
    private_key: str  # hex, 0x-prefixed, 64 chars
    contract_address: str  # 0x-prefixed
    chain_id: int  # 137 mainnet, 80001 mumbai
    confirmation_blocks: int = 1
    gas_buffer: float = 1.2  # multiply estimated gas by this for safety
    tx_timeout_seconds: int = 120

    @classmethod
    def from_env(cls) -> "PolygonConfig":
        return cls(
            rpc_url=os.environ["POLYGON_RPC_URL"],
            private_key=os.environ["POLYGON_PRIVATE_KEY"],
            contract_address=os.environ["POLYGON_CONTRACT_ADDRESS"],
            chain_id=int(os.getenv("POLYGON_CHAIN_ID", "137")),
            confirmation_blocks=int(os.getenv("POLYGON_CONFIRMATIONS", "1")),
            gas_buffer=float(os.getenv("POLYGON_GAS_BUFFER", "1.2")),
            tx_timeout_seconds=int(os.getenv("POLYGON_TX_TIMEOUT", "120")),
        )


# ── Result types ────────────────────────────────────────────────────────────


@dataclass
class AnchorResult:
    anchor_id: int  # on-chain sequential ID
    tx_hash: str  # 0x-prefixed
    block_number: int
    gas_used: int
    merkle_root: str  # 0x-prefixed hex (echo back for caller)


@dataclass
class OnChainAnchor:
    anchor_id: int
    merkle_root: str  # 0x-prefixed hex
    timestamp: int
    cert_count: int
    batch_count: int
    metadata: str


# ── Service ─────────────────────────────────────────────────────────────────


class PolygonAnchor:
    """Producer-side facade for the HalalCertAnchor contract."""

    def __init__(self, config: PolygonConfig, w3: Optional[Web3] = None):
        self.config = config
        self.w3 = w3 or Web3(Web3.HTTPProvider(config.rpc_url))
        self.account = Account.from_key(config.private_key)
        compiled = compile_contract()
        self.abi = compiled.abi
        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(config.contract_address),
            abi=self.abi,
        )

    # ── Wallet helpers ──────────────────────────────────────────────────────

    @property
    def address(self) -> str:
        return self.account.address

    def balance_wei(self) -> int:
        return self.w3.eth.get_balance(self.address)

    def balance_matic(self) -> float:
        """Return balance in MATIC (1 MATIC = 1e18 wei)."""
        return self.balance_wei() / 1e18

    # ── Write: anchor a Merkle root ─────────────────────────────────────────

    async def anchor_root(
        self,
        merkle_root: str,
        timestamp: int,
        cert_count: int,
        batch_count: int = 0,
        metadata: str = "",
    ) -> AnchorResult:
        """Submit a Merkle root and wait for confirmation.

        Raises ValueError on invalid input, RuntimeError on chain failure.
        """
        if not merkle_root.startswith("0x"):
            merkle_root = "0x" + merkle_root
        root_bytes = bytes.fromhex(merkle_root[2:])
        if len(root_bytes) != 32:
            raise ValueError(f"merkle_root must be 32 bytes, got {len(root_bytes)}")
        if root_bytes == b"\x00" * 32:
            raise ValueError("merkle_root must be non-zero")

        # Run blocking web3 calls in a thread so we don't block the event loop.
        return await asyncio.to_thread(
            self._submit_and_wait,
            root_bytes,
            timestamp,
            cert_count,
            batch_count,
            metadata,
        )

    def _submit_and_wait(
        self,
        root_bytes: bytes,
        timestamp: int,
        cert_count: int,
        batch_count: int,
        metadata: str,
    ) -> AnchorResult:
        nonce = self.w3.eth.get_transaction_count(self.address)
        fn = self.contract.functions.anchorRoot(
            root_bytes,
            timestamp,
            cert_count,
            batch_count,
            metadata,
        )

        # Estimate gas, add safety buffer. Any failure here means the call
        # would revert on-chain — we surface that as RuntimeError so callers
        # don't waste gas submitting a doomed tx.
        try:
            estimated = fn.estimate_gas({"from": self.address})
            gas_limit = int(estimated * self.config.gas_buffer)
        except Exception as e:
            raise RuntimeError(f"gas estimation failed (will revert): {e}") from e

        tx = fn.build_transaction(
            {
                "from": self.address,
                "nonce": nonce,
                "gas": gas_limit,
                "chainId": self.config.chain_id,
                "maxFeePerGas": self.w3.to_wei("100", "gwei"),
                "maxPriorityFeePerGas": self.w3.to_wei("30", "gwei"),
            }
        )

        signed = self.account.sign_transaction(tx)
        raw_bytes = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction")
        tx_hash = self.w3.eth.send_raw_transaction(raw_bytes)

        log.info("[anchor] submitted tx=%s", tx_hash.hex())

        receipt = self.w3.eth.wait_for_transaction_receipt(
            tx_hash,
            timeout=self.config.tx_timeout_seconds,
        )
        if receipt.status != 1:
            raise RuntimeError(f"anchor tx reverted: {tx_hash.hex()}")

        # Parse RootAnchored event to retrieve anchor_id
        events = self.contract.events.RootAnchored().process_receipt(receipt)
        if not events:
            raise RuntimeError("RootAnchored event missing from receipt")
        anchor_id = events[0].args.anchorId

        return AnchorResult(
            anchor_id=anchor_id,
            tx_hash=tx_hash.hex() if isinstance(tx_hash, bytes) else str(tx_hash),
            block_number=receipt.blockNumber,
            gas_used=receipt.gasUsed,
            merkle_root="0x" + root_bytes.hex(),
        )

    # ── Read: fetch a stored anchor ─────────────────────────────────────────

    async def get_anchor(self, anchor_id: int) -> OnChainAnchor:
        return await asyncio.to_thread(self._get_anchor_sync, anchor_id)

    def _get_anchor_sync(self, anchor_id: int) -> OnChainAnchor:
        result = self.contract.functions.getAnchor(anchor_id).call()
        # tuple: (merkleRoot, timestamp, certCount, batchCount, metadata)
        return OnChainAnchor(
            anchor_id=anchor_id,
            merkle_root="0x" + result[0].hex(),
            timestamp=result[1],
            cert_count=result[2],
            batch_count=result[3],
            metadata=result[4],
        )

    async def anchor_count(self) -> int:
        return await asyncio.to_thread(lambda: self.contract.functions.anchorCount().call())

    async def is_paused(self) -> bool:
        return await asyncio.to_thread(lambda: self.contract.functions.paused().call())

    # ── Admin ───────────────────────────────────────────────────────────────

    async def set_paused(self, paused: bool) -> str:
        return await asyncio.to_thread(self._set_paused_sync, paused)

    def _set_paused_sync(self, paused: bool) -> str:
        nonce = self.w3.eth.get_transaction_count(self.address)
        fn = self.contract.functions.setPaused(paused)
        tx = fn.build_transaction(
            {
                "from": self.address,
                "nonce": nonce,
                "chainId": self.config.chain_id,
                "maxFeePerGas": self.w3.to_wei("100", "gwei"),
                "maxPriorityFeePerGas": self.w3.to_wei("30", "gwei"),
            }
        )
        signed = self.account.sign_transaction(tx)
        raw_bytes = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction")
        tx_hash = self.w3.eth.send_raw_transaction(raw_bytes)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        if receipt.status != 1:
            raise RuntimeError(f"setPaused tx reverted: {tx_hash.hex()}")
        return tx_hash.hex() if isinstance(tx_hash, bytes) else str(tx_hash)
