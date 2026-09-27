"""tests/test_merkle_and_security.py

Comprehensive tests for:
1. Sparse Merkle Tree (SMT) and O(log N) branch inclusion proof mathematical verification.
2. MerkleAuditLedger persistent batch commits, root hash chaining, and tamper detection.
3. Cryptographic API request signing, timestamp sliding window, nonce replay defense, and ABAC.
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from audit.merkle_ledger import MerkleAuditLedger, MerkleAuditProof, MerkleTree
from api.security import (
    NONCE_STORE,
    generate_action_signature,
    verify_intervention_security,
)


# ============================================================================
# 1. MERKLE TREE & O(log N) PROOFS
# ============================================================================

def test_merkle_tree_root_deterministic():
    leaves = [{"tx": "T1", "amount": 100}, {"tx": "T2", "amount": 200}, {"tx": "T3", "amount": 300}]
    tree1 = MerkleTree(leaves)
    tree2 = MerkleTree(leaves)
    assert tree1.root_hash == tree2.root_hash
    assert len(tree1.root_hash) == 64


def test_merkle_proof_verification_success():
    leaves = [f"LEAF-{i}" for i in range(8)]
    tree = MerkleTree(leaves)

    for i in range(8):
        proof = tree.get_proof(i)
        assert proof.leaf_index == i
        assert proof.tree_size == 8
        assert proof.root_hash == tree.root_hash
        assert proof.verify() is True, f"Proof failed for leaf index {i}"


def test_merkle_proof_detects_tampered_leaf():
    leaves = [f"LEAF-{i}" for i in range(4)]
    tree = MerkleTree(leaves)
    proof = tree.get_proof(0)

    # Tamper with leaf hash
    tampered_proof = MerkleAuditProof(
        leaf_hash="0" * 64,
        leaf_index=proof.leaf_index,
        root_hash=proof.root_hash,
        tree_size=proof.tree_size,
        steps=proof.steps,
    )
    assert tampered_proof.verify() is False


# ============================================================================
# 2. MERKLE AUDIT LEDGER
# ============================================================================

def test_merkle_ledger_commit_and_verify(tmp_path):
    ledger = MerkleAuditLedger(ledger_dir=tmp_path / "ledger", keys_dir=tmp_path / "keys")
    batch1 = [{"case_id": "CMP-1", "risk": 0.9}, {"case_id": "CMP-2", "risk": 0.8}]
    block1 = ledger.commit_batch(batch1)

    batch2 = [{"case_id": "CMP-3", "risk": 0.7}]
    block2 = ledger.commit_batch(batch2)

    assert block2.block_index == 1
    assert block2.prev_root_hash == block1.merkle_root

    ok, problems = ledger.verify_ledger_integrity()
    assert ok is True
    assert len(problems) == 0

    # Retrieve inclusion proof for a case
    proof_tuple = ledger.get_proof_for_case("CMP-2")
    assert proof_tuple is not None
    block, proof = proof_tuple
    assert proof.verify() is True


def test_merkle_ledger_tampering_detected(tmp_path):
    ledger = MerkleAuditLedger(ledger_dir=tmp_path / "ledger", keys_dir=tmp_path / "keys")
    ledger.commit_batch([{"case_id": "CMP-1", "amount": 50000}])
    ledger.commit_batch([{"case_id": "CMP-2", "amount": 75000}])

    # Corrupt the blocks file directly
    blocks_file = tmp_path / "ledger" / "merkle_blocks.jsonl"
    lines = blocks_file.read_text().splitlines()
    corrupted = lines[0].replace("50000", "999999")
    blocks_file.write_text(corrupted + "\n" + lines[1] + "\n")

    ok, problems = ledger.verify_ledger_integrity()
    assert ok is False
    assert len(problems) > 0


# ============================================================================
# 3. API SECURITY, REPLAY DEFENSE & ABAC
# ============================================================================

def test_signature_generation_and_verification():
    payload = {"case_id": "CMP-123", "action": "hold", "officer": "OFFICER-SHARMA"}
    now_ts = str(int(time.time()))
    nonce = "NONCE-UNIQUE-001"
    officer = "OFFICER-SHARMA"

    sig = generate_action_signature(payload, now_ts, nonce, officer)
    ok, msg = verify_intervention_security(
        payload=payload,
        signature=sig,
        timestamp=now_ts,
        nonce=nonce,
        officer_id=officer,
        officer_role="BANK_OFFICER",
        enforce_strict=True,
    )
    assert ok is True


def test_replay_attack_rejected():
    payload = {"case_id": "CMP-123", "action": "hold"}
    now_ts = str(int(time.time()))
    nonce = "NONCE-REPLAY-TEST"
    officer = "OFFICER-TEST"

    sig = generate_action_signature(payload, now_ts, nonce, officer)
    # First request succeeds
    verify_intervention_security(payload, sig, now_ts, nonce, officer, "BANK_OFFICER", enforce_strict=True)

    # Second request with same nonce MUST raise 401
    with pytest.raises(HTTPException) as exc:
        verify_intervention_security(payload, sig, now_ts, nonce, officer, "BANK_OFFICER", enforce_strict=True)
    assert exc.value.status_code == 401
    assert "replay attack detected" in exc.value.detail.lower()


def test_expired_timestamp_rejected():
    payload = {"case_id": "CMP-123", "action": "hold"}
    old_ts = str(int(time.time()) - 600)  # 10 minutes ago
    nonce = "NONCE-OLD-001"
    officer = "OFFICER-TEST"

    sig = generate_action_signature(payload, old_ts, nonce, officer)
    with pytest.raises(HTTPException) as exc:
        verify_intervention_security(payload, sig, old_ts, nonce, officer, "BANK_OFFICER", enforce_strict=True)
    assert exc.value.status_code == 401
    assert "timestamp expired" in exc.value.detail.lower()


def test_abac_unauthorized_role_rejected():
    payload = {"case_id": "CMP-123", "action": "hold"}  # Bank fund action
    now_ts = str(int(time.time()))
    nonce = "NONCE-ROLE-001"
    officer = "OFFICER-POLICE"

    sig = generate_action_signature(payload, now_ts, nonce, officer)
    # Police role trying to execute bank fund hold
    with pytest.raises(HTTPException) as exc:
        verify_intervention_security(payload, sig, now_ts, nonce, officer, "POLICE_PATROL", enforce_strict=True)
    assert exc.value.status_code == 403
    assert "not authorized" in exc.value.detail.lower()
