"""audit/blockchain_lite.py — tamper-evident, signed, append-only alert ledger.

Usage:
    from audit.blockchain_lite import AuditLedger
    ledger = AuditLedger()
    block = ledger.append({"complaint_id": "CMP-2026-000123", "risk_score": 0.91, ...})
    ok, problems = ledger.verify()

CLI:
    python -m audit.blockchain_lite verify
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.exceptions import InvalidSignature

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LEDGER_PATH = REPO_ROOT / "data" / "output" / "audit_ledger.jsonl"
DEFAULT_KEYS_DIR = REPO_ROOT / "data" / "output" / "audit_keys"
GENESIS_HASH = "0" * 64


def _canonical(payload: Dict[str, Any]) -> str:
    """Deterministic JSON encoding so the same payload always hashes the same way."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class Block:
    index: int
    timestamp: str
    payload: Dict[str, Any]
    prev_hash: str
    hash: str
    signature: str  # hex-encoded Ed25519 signature over `hash`

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Block":
        return cls(**data)


class AuditLedger:
    """Append-only, hash-chained, Ed25519-signed alert log."""

    def __init__(self, ledger_path: Optional[Path] = None, keys_dir: Optional[Path] = None) -> None:
        self.ledger_path = Path(ledger_path or DEFAULT_LEDGER_PATH)
        self.keys_dir = Path(keys_dir or DEFAULT_KEYS_DIR)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self.keys_dir.mkdir(parents=True, exist_ok=True)
        self._private_key, self._public_key = self._load_or_create_keys()

    # ------------------------------------------------------------------
    # Key management
    # ------------------------------------------------------------------

    def _load_or_create_keys(self) -> Tuple[Ed25519PrivateKey, Ed25519PublicKey]:
        priv_path = self.keys_dir / "issuer_ed25519_private.pem"
        pub_path = self.keys_dir / "issuer_ed25519_public.pem"

        if priv_path.exists() and pub_path.exists():
            private_key = serialization.load_pem_private_key(priv_path.read_bytes(), password=None)
            public_key = serialization.load_pem_public_key(pub_path.read_bytes())
            return private_key, public_key

        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        priv_path.write_bytes(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ))
        pub_path.write_bytes(public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ))
        return private_key, public_key

    def public_key_pem(self) -> str:
        """Public key other institutions would use to verify our alerts."""
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    def _read_blocks(self) -> List[Block]:
        if not self.ledger_path.exists():
            return []
        blocks = []
        with open(self.ledger_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    blocks.append(Block.from_dict(json.loads(line)))
        return blocks

    def _last_block(self) -> Optional[Block]:
        if not self.ledger_path.exists():
            return None
        try:
            with open(self.ledger_path, "rb") as f:
                f.seek(0, 2)
                size = f.tell()
                if size == 0:
                    return None
                buffer_size = min(4096, size)
                f.seek(size - buffer_size)
                lines = f.read().decode("utf-8", errors="ignore").strip().splitlines()
                if lines:
                    return Block.from_dict(json.loads(lines[-1]))
        except Exception:
            pass
        blocks = self._read_blocks()
        return blocks[-1] if blocks else None

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def append(self, payload: Dict[str, Any]) -> Block:
        """Hash, sign, and append one alert (or any dict) to the ledger."""
        last = self._last_block()
        index = (last.index + 1) if last else 0
        prev_hash = last.hash if last else GENESIS_HASH
        timestamp = datetime.now(timezone.utc).isoformat()

        block_hash = _sha256(f"{index}|{timestamp}|{prev_hash}|{_canonical(payload)}")
        signature = self._private_key.sign(bytes.fromhex(block_hash)).hex()

        block = Block(
            index=index, timestamp=timestamp, payload=payload,
            prev_hash=prev_hash, hash=block_hash, signature=signature,
        )
        with open(self.ledger_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(block.to_dict(), default=str) + "\n")
        return block

    # ------------------------------------------------------------------
    # Verify — the live-demo moment
    # ------------------------------------------------------------------

    def verify(self) -> Tuple[bool, List[str]]:
        """Walk the whole chain. Returns (all_ok, [human-readable problems])."""
        problems: List[str] = []
        blocks = self._read_blocks()
        expected_prev = GENESIS_HASH

        for b in blocks:
            recomputed_hash = _sha256(f"{b.index}|{b.timestamp}|{b.prev_hash}|{_canonical(b.payload)}")
            if recomputed_hash != b.hash:
                problems.append(
                    f"Block {b.index}: PAYLOAD TAMPERED — stored hash does not match "
                    f"recomputed hash of the payload on disk"
                )
            if b.prev_hash != expected_prev:
                problems.append(
                    f"Block {b.index}: CHAIN BROKEN — prev_hash does not match the previous "
                    f"block's hash (block removed, reordered, or inserted)"
                )
            try:
                self._public_key.verify(bytes.fromhex(b.signature), bytes.fromhex(b.hash))
            except (InvalidSignature, ValueError):
                problems.append(f"Block {b.index}: INVALID SIGNATURE — not issued by this ledger's key")
            expected_prev = b.hash

        return (len(problems) == 0), problems


def _cli() -> None:
    ledger = AuditLedger()
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        ok, problems = ledger.verify()
        blocks = ledger._read_blocks()
        print(f"Ledger: {ledger.ledger_path} ({len(blocks)} block(s))")
        if ok:
            print("VERIFIED — chain intact, all signatures valid.")
        else:
            print("TAMPER DETECTED:")
            for p in problems:
                print(f"  - {p}")
        sys.exit(0 if ok else 1)
    print("Usage: python -m audit.blockchain_lite verify")


if __name__ == "__main__":
    _cli()
