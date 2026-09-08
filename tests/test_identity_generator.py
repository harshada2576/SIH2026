"""tests/test_identity_generator.py

Tests covering:
- accounts dataset generation includes kyc_identity_id
- identity IDs are valid strings
- synthetic identity clusters exist (shared kyc_identity_id across multiple accounts)
- identity_cluster_rule consumes generated data and evaluates risk correctly
"""
import csv
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "data-generator") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "data-generator"))

from normal_traffic import generate_accounts
from patterns import inject_fan_in
from detection.rules import identity_cluster_rule
from pipeline.graph_store import GraphStore
from shared.schemas import AccountNodeMetadata


def test_generate_accounts_includes_valid_kyc_identity_id():
    rng = random.Random(42)
    accounts = generate_accounts(50, rng)
    assert len(accounts) == 50
    for acc in accounts:
        assert "kyc_identity_id" in acc
        assert isinstance(acc["kyc_identity_id"], str)
        assert acc["kyc_identity_id"].startswith("KYC-IND-")


def test_generated_accounts_contain_shared_identity_clusters():
    rng = random.Random(42)
    accounts = generate_accounts(100, rng)
    kyc_counts = {}
    for acc in accounts:
        k = acc["kyc_identity_id"]
        kyc_counts[k] = kyc_counts.get(k, 0) + 1

    shared_clusters = [k for k, count in kyc_counts.items() if count > 1]
    assert len(shared_clusters) > 0, "Generated dataset should contain legitimate shared identity clusters"


def test_fraud_scenarios_inject_mule_identity_clusters():
    rng = random.Random(42)
    accounts = generate_accounts(30, rng)
    terminals = [{"terminal_id": "ATM-001", "district": "District-1"}]
    txns, scenario = inject_fan_in(accounts, terminals, "SCN-TEST-01", now_utc_dt(), rng)

    involved_ids = scenario["involved_account_ids"]
    accounts_by_id = {a["account_id"]: a for a in accounts}

    # Sources in fan-in scenario should share a KYC ring ID
    source_kycs = {accounts_by_id[aid]["kyc_identity_id"] for aid in involved_ids[1:]}
    assert len(source_kycs) == 1
    shared_kyc = list(source_kycs)[0]
    assert shared_kyc.startswith("KYC-RING-")


def test_identity_cluster_rule_consumes_generated_identity_data():
    g = GraphStore()
    rng = random.Random(42)
    accounts = generate_accounts(20, rng)

    # Pick 9 accounts and assign them the same KYC ID to simulate a mule cluster
    mule_kyc = "KYC-RING-TEST-CLUSTER"
    for acc in accounts[:9]:
        acc["kyc_identity_id"] = mule_kyc

    g.load_accounts(accounts)

    target_acc = accounts[0]["account_id"]
    res = identity_cluster_rule.evaluate(g, target_acc)
    assert res.severity == 1.0
    assert "8 other account(s)" in res.measured or "8" in res.evidence


def now_utc_dt():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)
