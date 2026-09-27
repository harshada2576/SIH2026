"""audit/tamper_demo.py — the stage demo for Part 3 (Trust & Audit).

Run: python -m audit.tamper_demo

Story:
  1. Append 4 signed alert blocks.
  2. Verify -> chain intact.
  3. Directly edit one block's payload on disk (simulating an insider or
     attacker trying to quietly change a risk score after the fact).
  4. Verify again -> tamper detected, with the exact block flagged.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from audit.blockchain_lite import AuditLedger, DEFAULT_LEDGER_PATH, DEFAULT_KEYS_DIR


def main() -> None:
    demo_ledger_path = DEFAULT_LEDGER_PATH.parent / "audit_ledger_DEMO.jsonl"
    demo_keys_dir = DEFAULT_KEYS_DIR.parent / "audit_keys_DEMO"
    if demo_ledger_path.exists():
        demo_ledger_path.unlink()
    if demo_keys_dir.exists():
        shutil.rmtree(demo_keys_dir)

    ledger = AuditLedger(ledger_path=demo_ledger_path, keys_dir=demo_keys_dir)

    sample_alerts = [
        {"complaint_id": "CMP-2026-000101", "flagged_account_id": "ACC-M001", "risk_score": 0.42, "band": "MEDIUM"},
        {"complaint_id": "CMP-2026-000102", "flagged_account_id": "ACC-M002", "risk_score": 0.67, "band": "HIGH"},
        {"complaint_id": "CMP-2026-000103", "flagged_account_id": "ACC-M003", "risk_score": 0.91, "band": "CRITICAL"},
        {"complaint_id": "CMP-2026-000104", "flagged_account_id": "ACC-M004", "risk_score": 0.35, "band": "MEDIUM"},
    ]

    print("=" * 72)
    print("STEP 1 — appending 4 signed alerts to the ledger")
    print("=" * 72)
    for alert in sample_alerts:
        b = ledger.append(alert)
        print(f"  block {b.index}: {alert['complaint_id']} (risk={alert['risk_score']}) "
              f"hash={b.hash[:16]}...")

    print("\n" + "=" * 72)
    print("STEP 2 — verifying chain (should be clean)")
    print("=" * 72)
    ok, problems = ledger.verify()
    print("VERIFIED — chain intact." if ok else f"UNEXPECTED PROBLEMS: {problems}")

    print("\n" + "=" * 72)
    print("STEP 3 — tampering with block 2 directly on disk")
    print("   (simulating someone quietly changing CMP-2026-000103's risk_score")
    print("    from 0.91/CRITICAL down to 0.40/MEDIUM after the fact)")
    print("=" * 72)
    lines = demo_ledger_path.read_text(encoding="utf-8").splitlines()
    tampered_block = json.loads(lines[2])
    tampered_block["payload"]["risk_score"] = 0.40
    tampered_block["payload"]["band"] = "MEDIUM"
    lines[2] = json.dumps(tampered_block)
    demo_ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("  ...done. Note: hash/signature fields were left untouched — only the payload changed.")

    print("\n" + "=" * 72)
    print("STEP 4 — verifying chain again")
    print("=" * 72)
    ok, problems = ledger.verify()
    if ok:
        print("ERROR: tamper was not detected (this should not happen)")
    else:
        print("TAMPER DETECTED:")
        for p in problems:
            print(f"  - {p}")

    print("\n" + "=" * 72)
    print("PART 3B — SPARSE MERKLE TREE (SMT) INCLUSION PROOF VERIFICATION")
    print("=" * 72)
    from audit.merkle_ledger import MerkleAuditLedger

    demo_merkle_dir = DEFAULT_KEYS_DIR.parent / "merkle_demo"
    if demo_merkle_dir.exists():
        shutil.rmtree(demo_merkle_dir)

    mledger = MerkleAuditLedger(ledger_dir=demo_merkle_dir)
    block = mledger.commit_batch(sample_alerts)
    print(f"  Committed Merkle Block #{block.block_index} with Root: {block.merkle_root[:24]}...")
    print(f"  Leaves indexed: {block.leaf_count}")

    # Verify inclusion proof for CMP-2026-000103
    res = mledger.get_proof_for_case("CMP-2026-000103")
    assert res is not None
    mblock, proof = res
    is_valid = proof.verify()
    print(f"  [PROOF] SMT $O(\\log N)$ Inclusion Proof for CMP-2026-000103: {'VALID (VERIFIED)' if is_valid else 'INVALID'}")
    print(f"  [PROOF] Sibling audit path depth: {len(proof.steps)} hashes")

    # Simulate tampered proof
    proof.leaf_hash = "0000000000000000000000000000000000000000000000000000000000000000"
    is_tampered_valid = proof.verify()
    print(f"  [TAMPER DETECTED] Tampered SMT leaf verification: {'PASSED (BUG)' if is_tampered_valid else 'REJECTED (PROOF FAILED)'}")

    print("\nDemo ledger: " + str(demo_ledger_path))
    print("(Run this again any time — it resets the demo ledger on each run.)")


if __name__ == "__main__":
    main()

