#!/usr/bin/env python3
"""
generate.py — Entry point for the Synthetic Data Generator (Workstream 1)
SIH26184 — Predictive Cash Egress Interception

Generates expanded, diversified multi-city accounts, terminals, normal traffic,
and 16 fraud scenario archetypes with complete ground truth metadata.
"""

import argparse
import csv
import json
import os
import random
import sys
from datetime import datetime, timezone

import config
from normal_traffic import generate_accounts, generate_terminals, generate_normal_transactions
from patterns import inject_all_scenarios


def parse_args():
    """Read command-line overrides for dataset scale, falling back to config.py defaults."""
    p = argparse.ArgumentParser(description="Generate synthetic fraud-detection dataset.")
    p.add_argument("--accounts", type=int, default=config.NUM_ACCOUNTS)
    p.add_argument("--normal-transactions", type=int, default=config.NUM_NORMAL_TRANSACTIONS)
    p.add_argument("--terminals", type=int, default=config.NUM_TERMINALS)
    p.add_argument("--validation-scenarios", type=int, default=0,
                    help="Number of validation scenarios across EASY/MEDIUM/HARD difficulty tiers")
    p.add_argument("--seed", type=int, default=config.RANDOM_SEED,
                    help="Random seed for reproducibility (omit for a fresh random dataset)")
    p.add_argument("--out-dir", type=str, default=config.DATA_DIR)
    p.add_argument("--shuffle-rows", action="store_true", default=True,
                    help="Shuffle CSV row order (default on). Chronological balance math is "
                         "unaffected either way — that's always computed by timestamp.")
    return p.parse_args()


def compute_balances(transactions: list[dict], accounts: list[dict], rng: random.Random) -> dict:
    """Assign balance_before/balance_after to every transaction, guaranteed non-negative."""
    sorted_txns = sorted(transactions, key=lambda t: t["timestamp_dt"])

    # Pass 1: find each account's worst-case running balance.
    running = {a["account_id"]: 0.0 for a in accounts}
    min_seen = {a["account_id"]: 0.0 for a in accounts}
    for t in sorted_txns:
        s, tgt, amt = t["source_account_id"], t["target_account_id"], t["amount_inr"]
        running[s] -= amt
        min_seen[s] = min(min_seen[s], running[s])
        running[tgt] += amt
        min_seen[tgt] = min(min_seen[tgt], running[tgt])

    # Pass 2: assign starting balance covering worst dip plus cushion.
    initial_balance = {}
    for a in accounts:
        acc_id = a["account_id"]
        lo, hi = config.INITIAL_BALANCE_RANGE_BY_TIER.get(a["account_tier"], (1000, 25000))
        base = rng.uniform(lo, hi)
        buffer = rng.uniform(*config.BALANCE_BUFFER_RANGE)
        required_min = max(0.0, -min_seen[acc_id])
        initial_balance[acc_id] = round(required_min + max(base, buffer), 2)

    # Pass 3: replay chronologically recording balance_before/after on source account.
    current = dict(initial_balance)
    for t in sorted_txns:
        s, tgt, amt = t["source_account_id"], t["target_account_id"], t["amount_inr"]
        t["balance_before"] = round(current[s], 2)
        current[s] = round(current[s] - amt, 2)
        t["balance_after"] = current[s]
        current[tgt] = round(current[tgt] + amt, 2)

    return initial_balance


def validate_dataset(accounts, terminals, transactions, scenarios):
    """Run comprehensive validation checks on generated data."""
    account_ids = {a["account_id"] for a in accounts}
    assert len(account_ids) == len(accounts), "Duplicate account_id detected"
    for a in accounts:
        assert a["account_tier"] in config.ACCOUNT_TIERS, f"Invalid account_tier: {a['account_tier']}"
        assert a["account_status"] in config.ACCOUNT_STATUSES, f"Invalid account_status: {a['account_status']}"
        assert "kyc_identity_id" in a and a["kyc_identity_id"], f"Missing kyc_identity_id on account {a['account_id']}"

    kyc_counts = {}
    for a in accounts:
        k = a["kyc_identity_id"]
        kyc_counts[k] = kyc_counts.get(k, 0) + 1
    shared_clusters = [k for k, count in kyc_counts.items() if count > 1]
    assert len(shared_clusters) > 0, "No shared KYC identity clusters found in accounts dataset"

    terminal_ids = {t["terminal_id"] for t in terminals}
    assert len(terminal_ids) == len(terminals), "Duplicate terminal_id detected"
    for t in terminals:
        assert t["terminal_type"] in config.TERMINAL_TYPES, f"Invalid terminal_type: {t['terminal_type']}"
        assert t["status"] in config.TERMINAL_STATUSES, f"Invalid terminal status: {t['status']}"

    seen_txn_ids = set()
    for t in transactions:
        assert t["transaction_id"] not in seen_txn_ids, f"Duplicate transaction_id: {t['transaction_id']}"
        seen_txn_ids.add(t["transaction_id"])
        assert t["source_account_id"] in account_ids, f"Unknown source account: {t['source_account_id']}"
        assert t["target_account_id"] in account_ids, f"Unknown target account: {t['target_account_id']}"
        assert t["source_account_id"] != t["target_account_id"], f"source == target on {t['transaction_id']}"
        assert t["amount_inr"] > 0, f"Non-positive amount on {t['transaction_id']}"
        assert t["payment_channel"] in config.PAYMENT_CHANNELS, \
            f"Invalid payment_channel on {t['transaction_id']}: {t['payment_channel']}"
        datetime.strptime(t["timestamp"], "%Y-%m-%dT%H:%M:%SZ")

        expected_after = round(t["balance_before"] - t["amount_inr"], 2)
        assert abs(t["balance_after"] - expected_after) < 0.01, \
            f"Balance math inconsistent on {t['transaction_id']}"
        assert t["balance_after"] >= -0.01, f"Account overdrawn on {t['transaction_id']}"

    scenarios_by_id = {s["scenario_id"]: s for s in scenarios}
    for t in transactions:
        if t["_is_fraud"]:
            assert t["_scenario_id"] in scenarios_by_id, \
                f"Fraud transaction {t['transaction_id']} references unknown scenario {t['_scenario_id']}"
            assert scenarios_by_id[t["_scenario_id"]]["pattern_type"] == t["_pattern_type"], \
                f"pattern_type mismatch on {t['transaction_id']}"

    pattern_counts = {}
    for t in transactions:
        pattern_counts[t["_pattern_type"]] = pattern_counts.get(t["_pattern_type"], 0) + 1

    print(f"  validation OK — {len(transactions)} transactions, pattern breakdown:")
    for p_type, cnt in sorted(pattern_counts.items()):
        print(f"    - {p_type}: {cnt}")


def write_csvs(accounts, terminals, transactions, out_dir, shuffle_rows, rng):
    """Write the four output CSVs matching agreed schemas."""
    os.makedirs(out_dir, exist_ok=True)
    rows = list(transactions)
    if shuffle_rows:
        rng.shuffle(rows)

    with open(os.path.join(out_dir, "accounts.csv"), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "account_id", "account_tier", "account_age_days", "account_status",
            "historical_terminal_ids", "primary_device_fingerprint", "account_region",
            "kyc_identity_id",
        ])
        writer.writeheader()
        for a in accounts:
            writer.writerow({**a, "historical_terminal_ids": json.dumps(a["historical_terminal_ids"])})

    with open(os.path.join(out_dir, "terminals.csv"), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "terminal_id", "terminal_type", "latitude", "longitude", "district", "pincode", "status",
        ])
        writer.writeheader()
        for t in terminals:
            writer.writerow({
                "terminal_id": t["terminal_id"],
                "terminal_type": t["terminal_type"],
                "latitude": t["latitude"],
                "longitude": t["longitude"],
                "district": t["district"],
                "pincode": t["pincode"],
                "status": t["status"],
            })

    with open(os.path.join(out_dir, "transactions.csv"), "w", newline="") as f:
        fieldnames = config.KAFKA_EVENT_FIELDS + ["balance_before", "balance_after"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for t in rows:
            writer.writerow({k: t[k] for k in fieldnames})

    with open(os.path.join(out_dir, "ground_truth.csv"), "w", newline="") as f:
        fieldnames = [
            "scenario_id", "transaction_id", "pattern_type", "is_fraud",
            "involved_account_ids", "expected_cashout_terminal_id",
            "campaign_id", "root_transaction_id", "chain_id", "hop_depth", "difficulty_tier",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for t in rows:
            writer.writerow({
                "scenario_id": t.get("_scenario_id", ""),
                "transaction_id": t["transaction_id"],
                "pattern_type": t.get("_pattern_type", "normal"),
                "is_fraud": t.get("_is_fraud", False),
                "involved_account_ids": json.dumps(t.get("_involved_account_ids", [])),
                "expected_cashout_terminal_id": t.get("_expected_cashout_terminal_id", ""),
                "campaign_id": t.get("_campaign_id", ""),
                "root_transaction_id": t.get("_root_transaction_id", t["transaction_id"]),
                "chain_id": t.get("_chain_id", ""),
                "hop_depth": t.get("_hop_depth", 1),
                "difficulty_tier": t.get("_difficulty_tier", "EASY"),
            })


def main():
    args = parse_args()
    rng = random.Random(args.seed)

    print(f"Generating dataset: {args.accounts} accounts, {args.terminals} terminals, "
          f"{args.normal_transactions} normal transactions + 16 fraud scenario archetypes "
          f"(seed={args.seed})")

    accounts = generate_accounts(args.accounts, rng)
    terminals = generate_terminals(args.terminals, rng)

    sim_start = datetime.strptime(config.SIMULATION_START, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    normal_txns = generate_normal_transactions(accounts, args.normal_transactions, rng)
    fraud_txns, scenarios = inject_all_scenarios(accounts, terminals, sim_start, rng)
    all_txns = normal_txns + fraud_txns

    print(f"Total transactions before balance simulation: {len(all_txns)} ({len(normal_txns)} normal, {len(fraud_txns)} fraud)")
    print("Simulating chronological account balances...")
    compute_balances(all_txns, accounts, rng)

    print("Validating dataset...")
    try:
        validate_dataset(accounts, terminals, all_txns, scenarios)
    except AssertionError as e:
        print(f"VALIDATION FAILED: {e}", file=sys.stderr)
        sys.exit(1)

    write_csvs(accounts, terminals, all_txns, args.out_dir, args.shuffle_rows, rng)
    print(f"Done. CSVs written to: {args.out_dir}")
    print("  - accounts.csv")
    print("  - terminals.csv")
    print("  - transactions.csv   (7 locked Kafka fields + balance_before/balance_after)")
    print("  - ground_truth.csv   (rich evaluation metadata)")


if __name__ == "__main__":
    main()

