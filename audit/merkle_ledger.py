"""audit/merkle_ledger.py — High-Performance Sparse Merkle Tree (SMT) & Cryptographic Audit Ledger.

Provides:
1. Deterministic SHA-256 Merkle Tree generation over audit blocks and intervention events.
2. O(log N) inclusion proofs for instant mathematical verification without full chain scan.
3. Tamper-evident root hash chaining and Ed25519 multi-institution signing.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

log = logging.getLogger("merkle_ledger")

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MERKLE_DIR = REPO_ROOT / "data" / "output" / "merkle_audit"
DEFAULT_KEYS_DIR = REPO_ROOT / "data" / "output" / "audit_keys"
GENESIS_HASH = "0" * 64


def _canonical_json(payload: Dict[str, Any]) -> str:
    """Deterministic canonical JSON serialization."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(text: str | bytes) -> str:
    """Compute SHA-256 hex digest."""
    if isinstance(text, str):
        text = text.encode("utf-8")
    return hashlib.sha256(text).hexdigest()


def _combine_hashes(left: str, right: str) -> str:
    """Combine two child node hashes in a deterministic order."""
    return _sha256(f"{left}:{right}")


@dataclass
class MerkleProofStep:
    """One step in an O(log N) Merkle audit branch proof."""
    sibling_hash: str
    is_left: bool  # True if sibling is on the left, False if on the right

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MerkleProofStep":
        return cls(sibling_hash=str(data["sibling_hash"]), is_left=bool(data["is_left"]))


@dataclass
class MerkleAuditProof:
    """Complete O(log N) cryptographic proof of inclusion."""
    leaf_hash: str
    leaf_index: int
    root_hash: str
    tree_size: int
    steps: List[MerkleProofStep]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def verify(self) -> bool:
        """Verify that leaf_hash mathematically reproduces root_hash through steps."""
        current = self.leaf_hash
        for step in self.steps:
            if step.is_left:
                current = _combine_hashes(step.sibling_hash, current)
            else:
                current = _combine_hashes(current, step.sibling_hash)
        return current == self.root_hash

    def to_dict(self) -> Dict[str, Any]:
        return {
            "leaf_hash": self.leaf_hash,
            "leaf_index": self.leaf_index,
            "root_hash": self.root_hash,
            "tree_size": self.tree_size,
            "steps": [s.to_dict() for s in self.steps],
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MerkleAuditProof":
        return cls(
            leaf_hash=str(data["leaf_hash"]),
            leaf_index=int(data["leaf_index"]),
            root_hash=str(data["root_hash"]),
            tree_size=int(data["tree_size"]),
            steps=[MerkleProofStep.from_dict(s) for s in data.get("steps", [])],
            timestamp=str(data.get("timestamp", datetime.now(timezone.utc).isoformat())),
        )


class MerkleTree:
    """Binary Merkle Tree built over an ordered batch of leaf payloads or hashes."""

    def __init__(self, leaves: Optional[List[str | Dict[str, Any]]] = None) -> None:
        self.leaf_hashes: List[str] = []
        self.levels: List[List[str]] = []
        if leaves:
            for item in leaves:
                if isinstance(item, dict):
                    self.leaf_hashes.append(_sha256(_canonical_json(item)))
                else:
                    self.leaf_hashes.append(str(item))
            self._build_tree()

    def _build_tree(self) -> None:
        if not self.leaf_hashes:
            self.levels = [[GENESIS_HASH]]
            return

        current_level = list(self.leaf_hashes)
        self.levels = [current_level]

        while len(current_level) > 1:
            next_level = []
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                if i + 1 < len(current_level):
                    right = current_level[i + 1]
                else:
                    right = left  # Duplicate odd leaf to balance tree
                parent = _combine_hashes(left, right)
                next_level.append(parent)
            self.levels.append(next_level)
            current_level = next_level

    @property
    def root_hash(self) -> str:
        """Root hash of the Merkle Tree."""
        if not self.levels or not self.levels[-1]:
            return GENESIS_HASH
        return self.levels[-1][0]

    def get_proof(self, leaf_index: int) -> MerkleAuditProof:
        """Generate an O(log N) branch proof for leaf at index leaf_index."""
        if leaf_index < 0 or leaf_index >= len(self.leaf_hashes):
            raise IndexError(f"Leaf index {leaf_index} out of range [0, {len(self.leaf_hashes)-1}]")

        target_leaf_hash = self.leaf_hashes[leaf_index]
        steps: List[MerkleProofStep] = []
        idx = leaf_index

        for level_idx in range(len(self.levels) - 1):
            level = self.levels[level_idx]
            is_odd = (idx % 2 == 1)
            sibling_idx = idx - 1 if is_odd else idx + 1

            if sibling_idx < len(level):
                sibling_hash = level[sibling_idx]
            else:
                sibling_hash = level[idx]  # Duplicated boundary sibling

            steps.append(MerkleProofStep(sibling_hash=sibling_hash, is_left=is_odd))
            idx //= 2

        return MerkleAuditProof(
            leaf_hash=target_leaf_hash,
            leaf_index=leaf_index,
            root_hash=self.root_hash,
            tree_size=len(self.leaf_hashes),
            steps=steps,
        )


@dataclass
class MerkleBlock:
    """A signed block containing a Merkle Root of intervention events."""
    block_index: int
    timestamp: str
    prev_root_hash: str
    merkle_root: str
    leaf_count: int
    leaf_hashes: List[str]
    payloads: List[Dict[str, Any]]
    signature: str  # Ed25519 signature over (block_index|timestamp|prev_root|merkle_root)
    signer_institution: str = "I4C-NCRP-NATIONAL-HUB"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MerkleBlock":
        return cls(**data)


class MerkleAuditLedger:
    """Persistent, Merkle-indexed, tamper-evident audit ledger."""

    def __init__(
        self,
        ledger_dir: Optional[Path] = None,
        keys_dir: Optional[Path] = None,
        institution_id: str = "I4C-NCRP-NATIONAL-HUB",
    ) -> None:
        self.ledger_dir = Path(ledger_dir or DEFAULT_MERKLE_DIR)
        self.keys_dir = Path(keys_dir or DEFAULT_KEYS_DIR)
        self.institution_id = institution_id
        self.blocks_file = self.ledger_dir / "merkle_blocks.jsonl"
        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        self.keys_dir.mkdir(parents=True, exist_ok=True)
        self._private_key, self._public_key = self._load_or_create_keys()

    def _load_or_create_keys(self) -> Tuple[Ed25519PrivateKey, Ed25519PublicKey]:
        priv_path = self.keys_dir / "merkle_issuer_ed25519_private.pem"
        pub_path = self.keys_dir / "merkle_issuer_ed25519_public.pem"

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
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

    def _read_blocks(self) -> List[MerkleBlock]:
        if not self.blocks_file.exists():
            return []
        blocks = []
        with open(self.blocks_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    blocks.append(MerkleBlock.from_dict(json.loads(line)))
        return blocks

    def get_latest_block(self) -> Optional[MerkleBlock]:
        blocks = self._read_blocks()
        return blocks[-1] if blocks else None

    def commit_batch(self, events: List[Dict[str, Any]]) -> MerkleBlock:
        """Create a Merkle Tree over events, sign the root, and append block."""
        if not events:
            raise ValueError("Cannot commit empty event batch to Merkle ledger")

        latest = self.get_latest_block()
        idx = (latest.block_index + 1) if latest else 0
        prev_root = latest.merkle_root if latest else GENESIS_HASH
        timestamp = datetime.now(timezone.utc).isoformat()

        tree = MerkleTree(events)
        merkle_root = tree.root_hash

        header_bytes = f"{idx}|{timestamp}|{prev_root}|{merkle_root}|{self.institution_id}".encode("utf-8")
        signature = self._private_key.sign(header_bytes).hex()

        block = MerkleBlock(
            block_index=idx,
            timestamp=timestamp,
            prev_root_hash=prev_root,
            merkle_root=merkle_root,
            leaf_count=len(events),
            leaf_hashes=list(tree.leaf_hashes),
            payloads=list(events),
            signature=signature,
            signer_institution=self.institution_id,
        )

        with open(self.blocks_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(block.to_dict()) + "\n")

        log.info(f"[MerkleLedger] Committed Block #{idx} (Root: {merkle_root[:16]}..., Leaves: {len(events)})")
        return block

    def get_proof_for_case(self, case_id: str) -> Optional[Tuple[MerkleBlock, MerkleAuditProof]]:
        """Find the block containing case_id and return O(log N) inclusion proof."""
        blocks = self._read_blocks()
        for block in reversed(blocks):
            for i, p in enumerate(block.payloads):
                if p.get("case_id") == case_id or p.get("ncrpId") == case_id or p.get("complaint_id") == case_id:
                    tree = MerkleTree(block.payloads)
                    proof = tree.get_proof(i)
                    return block, proof
        return None

    def verify_ledger_integrity(self) -> Tuple[bool, List[str]]:
        """Verify mathematical integrity and digital signatures across all blocks."""
        blocks = self._read_blocks()
        if not blocks:
            return True, []

        problems = []
        expected_prev = GENESIS_HASH

        for i, b in enumerate(blocks):
            if b.block_index != i:
                problems.append(f"Block #{i} has invalid index {b.block_index}")

            if b.prev_root_hash != expected_prev:
                problems.append(f"Block #{i} broken chain: prev_root {b.prev_root_hash} != expected {expected_prev}")

            # Recompute Merkle Root
            tree = MerkleTree(b.payloads)
            if tree.root_hash != b.merkle_root:
                problems.append(f"Block #{i} root mismatch: calculated {tree.root_hash} != stored {b.merkle_root}")

            # Verify Ed25519 signature
            header_bytes = f"{b.block_index}|{b.timestamp}|{b.prev_root_hash}|{b.merkle_root}|{b.signer_institution}".encode("utf-8")
            try:
                self._public_key.verify(bytes.fromhex(b.signature), header_bytes)
            except InvalidSignature:
                problems.append(f"Block #{i} invalid digital signature")

            expected_prev = b.merkle_root

        return (len(problems) == 0), problems
