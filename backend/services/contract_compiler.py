"""Compile + load HalalCertAnchor.sol via py-solc-x.

Caches the compiled artifact on disk so we don't recompile every test run.
Returns ABI + bytecode in a form web3.py can consume directly.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import solcx

log = logging.getLogger("aminra.contract_compiler")

CONTRACT_DIR = Path(__file__).resolve().parent.parent / "contracts"
SOURCE_FILE = CONTRACT_DIR / "HalalCertAnchor.sol"
CONTRACT_NAME = "HalalCertAnchor"
COMPILED_FILE = CONTRACT_DIR / ".artifacts" / f"{CONTRACT_NAME}.json"

SOLC_VERSION = "0.8.24"


@dataclass
class CompiledContract:
    name: str
    abi: list[dict]
    bytecode: str  # 0x-prefixed hex
    metadata: dict

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "abi": self.abi,
            "bytecode": self.bytecode,
            "metadata": self.metadata,
        }


def _ensure_solc_installed() -> None:
    """solcx caches compilers on disk; first call downloads."""
    if SOLC_VERSION not in [str(v) for v in solcx.get_installed_solc_versions()]:
        log.info("[compiler] installing solc %s", SOLC_VERSION)
        solcx.install_solc(SOLC_VERSION)
    solcx.set_solc_version(SOLC_VERSION)


def compile_contract(force: bool = False) -> CompiledContract:
    """Compile HalalCertAnchor.sol. Cached unless `force=True`."""
    if not force and COMPILED_FILE.exists():
        # Use cache if source hasn't changed since compile
        if COMPILED_FILE.stat().st_mtime >= SOURCE_FILE.stat().st_mtime:
            data = json.loads(COMPILED_FILE.read_text())
            return CompiledContract(**data)

    _ensure_solc_installed()
    if not SOURCE_FILE.exists():
        raise FileNotFoundError(f"Solidity source not found: {SOURCE_FILE}")

    log.info("[compiler] compiling %s (solc %s)", SOURCE_FILE.name, SOLC_VERSION)
    output = solcx.compile_files(
        [str(SOURCE_FILE)],
        output_values=["abi", "bin", "metadata"],
        solc_version=SOLC_VERSION,
        optimize=True,
        optimize_runs=200,
    )

    # solcx normalizes paths; the key may be either absolute or relative
    # followed by ":ContractName". Match by suffix.
    suffix = f":{CONTRACT_NAME}"
    matching_keys = [k for k in output if k.endswith(suffix)]
    if not matching_keys:
        raise RuntimeError(
            f"contract {CONTRACT_NAME} not found in compile output. "
            f"available: {list(output.keys())}"
        )
    artifact = output[matching_keys[0]]
    metadata = artifact.get("metadata") or "{}"
    if isinstance(metadata, str):
        metadata = json.loads(metadata) if metadata else {}

    compiled = CompiledContract(
        name=CONTRACT_NAME,
        abi=artifact["abi"],
        bytecode="0x" + artifact["bin"] if not artifact["bin"].startswith("0x") else artifact["bin"],
        metadata=metadata,
    )

    COMPILED_FILE.parent.mkdir(parents=True, exist_ok=True)
    COMPILED_FILE.write_text(json.dumps(compiled.to_dict(), indent=2))
    log.info("[compiler] cached → %s", COMPILED_FILE)

    return compiled


def get_function_signatures(abi: list[dict]) -> list[str]:
    """Helpful for tests — list the callable methods on the contract."""
    return [
        f"{item['name']}({','.join(i['type'] for i in item.get('inputs', []))})"
        for item in abi
        if item.get("type") == "function"
    ]
