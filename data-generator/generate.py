#!/usr/bin/env python3
"""
generate.py — Entry point for the Synthetic Data Generator (Workstream 1)
SIH26184 — Predictive Cash Egress Interception

Run this file to produce the full test dataset:

    python generate.py

It will:
  1. Generate accounts and terminals.
  2. Generate normal transaction traffic.
  3. Inject fan_in / fan_out / layering / triadic fraud scenarios.
  4. Simulate account balances CHRONOLOGICALLY across every transaction, so
     balance_before/balance_after are always mathematically consistent and no
     account is ever asked to spend money it doesn't have.
  5. Validate everything.
  6. Write four CSVs into data/.

CHANGELOG (this revision):
  - Added compute_balances(): a two-pass "minimum required starting balance"
    calculation (see the long comment on that function) so every account can
    always afford what it's asked to send, without ever changing a
    scenario's carefully-designed transaction amounts.
  - transactions.csv now includes balance_before/balance_after. These are
    NEVER sent to Kafka — see producer.py, which filters to the locked
    7-field schema explicitly.
  - ground_truth.csv now uses the richer schema: scenario_id, transaction_id,
    pattern_type, is_fraud, involved_account_ids, expected_cashout_terminal_id.
  - Validation extended to cover balance consistency, tiers, terminal status,
    and that ground truth actually matches injected scenarios.
  - All random draws go through one seeded rng — no more bare `random.x()`
    calls, fixing a reproducibility bug from the previous revision.

All the numbers below can be overridden with command-line flags — see
`python generate.py --help`.
"""

import argparse
import csv
import json
import os
import random
import sys
from datetime import datetime

import config
from normal_traffic import generate_accounts, generate_terminals, generate_normal_transactions
from patterns import inject_all_scenarios


def parse_args():
    """Read command-line overrides for dataset scale, falling back to config.py defaults."""
    p = argparse.ArgumentParser(description="Generate synthetic fraud-detection dataset.")
    p.add_argument("--accounts", type=int, default=config.NUM_ACCOUNTS)
    p.add_argument("--normal-transactions", type=int, default=config.NUM_NORMAL_TRANSACTIONS)
    p.add_argument("--terminals", type=int, default=config.NUM_TERMINALS)
    p.add_argument("--seed", type=int, default=config.RANDOM_SEED,
                    help="Random seed for reproducibility (omit for a fresh random dataset)")
    p.add_argument("--out-dir", type=str, default=config.DATA_DIR)
    p.add_argument("--shuffle-rows", action="store_true", default=True,
                    help="Shuffle CSV row order (default on). Chronological balance math is "
                         "unaffected either way — that's always computed by timestamp.")
    return p.parse_args()


def compute_balances(transactions: list[dict], accounts: list[dict], rng: random.Random) -> dict:
    """Assign balance_before/balance_after to every transaction, guaranteed non-negative.

    How this works (the "minimum required starting balance" trick):
      1. Walk every transaction in TRUE chronological order, starting every
         account's ledger at 0, and track the lowest (most negative) value
         each account's running balance ever hits.
      2. An account's real starting balance only needs to be big enough to
         cover that lowest dip — so we set initial_balance = (that deficit)
         + a small random cash buffer (tier-dependent: legit/victim accounts
         get a bigger cushion, freshly-opened mule accounts a thin one).
      3. Replay chronologically again with the real starting balances. Every
         balance_after is now guaranteed >= 0, and — importantly — none of
         the transaction AMOUNTS had to be changed to make that true, so
         fraud-scenario amounts stay exactly as patterns.py designed them.

    Returns the map of account_id -> assigned starting balance (not written
    to accounts.csv per the agreed account schema — used internally only).
    """
    sorted_txns = sorted(transactions, key=lambda t: t["timestamp_dt"])

    # Pass 1: find each account's worst-case (most negative) running balance.
    running = {a["account_id"]: 0.0 for a in accounts}
    min_seen = {a["account_id"]: 0.0 for a in accounts}
    for t in sorted_txns:
        s, tgt, amt = t["source_account_id"], t["target_account_id"], t["amount_inr"]
        running[s] -= amt
        min_seen[s] = min(min_seen[s], running[s])
        running[tgt] += amt
        min_seen[tgt] = min(min_seen[tgt], running[tgt])

    # Pass 2: pick a real starting balance that covers the worst dip, plus a
    # realistic cash buffer on top so accounts don't sit at exactly zero.
    initial_balance = {}
    for a in accounts:
        acc_id = a["account_id"]
        lo, hi = config.INITIAL_BALANCE_RANGE_BY_TIER.get(a["account_tier"], (1000, 20000))
        base = rng.uniform(lo, hi)
        buffer = rng.uniform(*config.BALANCE_BUFFER_RANGE)
        required_min = max(0.0, -min_seen[acc_id])
        initial_balance[acc_id] = round(required_min + max(base, buffer), 2)

    # Pass 3: replay chronologically for real, recording balance_before/after
    # on the SOURCE (paying) account for each transaction — see the "whose
    # balance" note flagged in chat: this tracks the paying account's ledger.
    current = dict(initial_balance)
    for t in sorted_txns:
        s, tgt, amt = t["source_account_id"], t["target_account_id"], t["amount_inr"]
        t["balance_before"] = round(current[s], 2)
        current[s] = round(current[s] - amt, 2)
        t["balance_after"] = current[s]
        current[tgt] = round(current[tgt] + amt, 2)

    return initial_balance


def validate_dataset(accounts, terminals, transactions, scenarios):
    """Run every check from the update request §15. Fails loudly on the first problem found."""
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
        datetime.strptime(t["timestamp"], "%Y-%m-%dT%H:%M:%SZ")  # raises if malformed

        # Balance consistency: balance_after must equal balance_before - amount,
        # and must never go negative.
        expected_after = round(t["balance_before"] - t["amount_inr"], 2)
        assert abs(t["balance_after"] - expected_after) < 0.01, \
            f"Balance math inconsistent on {t['transaction_id']}"
        assert t["balance_after"] >= -0.01, f"Account overdrawn on {t['transaction_id']}"

    # Ground truth <-> scenario cross-check: every fraud transaction's scenario_id
    # must correspond to a real scenario record with a matching pattern_type.
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
    for expected in ["fan_in", "fan_out", "layering", "triadic"]:
        assert pattern_counts.get(expected, 0) > 0, f"No transactions found for pattern type: {expected}"

    print(f"  validation OK — {len(transactions)} transactions, pattern breakdown: {pattern_counts}")


def write_csvs(accounts, terminals, transactions, out_dir, shuffle_rows, rng):
    """Write the four output CSVs matching the agreed schemas."""
    os.makedirs(out_dir, exist_ok=True)
    rows = list(transactions)
    if shuffle_rows:
        rng.shuffle(rows)  # row order only — balance math already computed chronologically

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
        writer.writerows(terminals)

    # transactions.csv: the 7 LOCKED Kafka fields + balance_before/balance_after
    # (supporting/ML attributes only — see producer.py for the Kafka-side filter).
    with open(os.path.join(out_dir, "transactions.csv"), "w", newline="") as f:
        fieldnames = config.KAFKA_EVENT_FIELDS + ["balance_before", "balance_after"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for t in rows:
            writer.writerow({k: t[k] for k in fieldnames})

    with open(os.path.join(out_dir, "ground_truth.csv"), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "scenario_id", "transaction_id", "pattern_type", "is_fraud",
            "involved_account_ids", "expected_cashout_terminal_id",
        ])
        writer.writeheader()
        for t in rows:
            writer.writerow({
                "scenario_id": t["_scenario_id"],
                "transaction_id": t["transaction_id"],
                "pattern_type": t["_pattern_type"],
                "is_fraud": t["_is_fraud"],
                "involved_account_ids": json.dumps(t["_involved_account_ids"]),
                "expected_cashout_terminal_id": t["_expected_cashout_terminal_id"],
            })


def main():
    args = parse_args()
    rng = random.Random(args.seed)

    print(f"Generating dataset: {args.accounts} accounts, {args.terminals} terminals, "
          f"{args.normal_transactions} normal transactions + configured fraud scenarios "
          f"(seed={args.seed})")

    accounts = generate_accounts(args.accounts, rng)
    terminals = generate_terminals(args.terminals, rng)

    normal_txns = generate_normal_transactions(accounts, args.normal_transactions, rng)
    fraud_txns, scenarios = inject_all_scenarios(accounts, terminals, rng)
    all_txns = normal_txns + fraud_txns

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
    print("  - ground_truth.csv   (evaluation only — never published to Kafka)")


if __name__ == "__main__":
    main()
