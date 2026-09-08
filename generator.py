import csv
import os
import random

from config import (
    NUM_ACCOUNTS,
    NUM_TERMINALS,
    NUM_TRANSACTIONS,
    FRAUD_PERCENTAGE,
    FAN_IN_SCENARIOS,
    FAN_OUT_SCENARIOS,
    LAYERING_SCENARIOS,
    TRIADIC_SCENARIOS,
    OUTPUT_DIR
)

from accounts import generate_accounts
from terminals import generate_terminals
from transactions import generate_normal_transaction
from patterns import (
    fan_in,
    fan_out,
    layering,
    triadic
)


def save_csv(filename, data, fields):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, filename)

    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(data)


def main():
    print("Starting synthetic data generation...\n")

    # -------------------------
    # ACCOUNTS
    # -------------------------
    accounts = generate_accounts()
    save_csv(
        "accounts.csv",
        accounts,
        [
            "account_id",
            "account_tier",
            "account_age_days",
            "account_status",
            "historical_terminal_ids",
            "primary_device_fingerprint",
            "account_region",
            "kyc_identity_id"
        ]
    )
    print(f"✓ Generated {len(accounts)} accounts")

    # -------------------------
    # TERMINALS
    # -------------------------
    terminals = generate_terminals()
    save_csv(
        "terminals.csv",
        terminals,
        [
            "terminal_id",
            "terminal_type",
            "latitude",
            "longitude",
            "district",
            "pincode",
            "status"
        ]
    )
    print(f"✓ Generated {len(terminals)} terminals")

    # -------------------------
    # TRANSACTIONS
    # -------------------------
    transactions = []
    ground_truth = []

    fraud_budget = int(NUM_TRANSACTIONS * FRAUD_PERCENTAGE / 100)
    normal_budget = NUM_TRANSACTIONS - fraud_budget

    for i in range(normal_budget):
        transactions.append(
            generate_normal_transaction(accounts, f"TX{i+1:06d}")
        )

    # -------------------------
    # FRAUD PATTERNS
    # -------------------------
    fraud_functions = []
    fraud_functions.extend([fan_in] * FAN_IN_SCENARIOS)
    fraud_functions.extend([fan_out] * FAN_OUT_SCENARIOS)
    fraud_functions.extend([layering] * LAYERING_SCENARIOS)
    fraud_functions.extend([triadic] * TRIADIC_SCENARIOS)

    for index, function in enumerate(fraud_functions, start=1):
        scenario_id = f"SC{index:03d}"
        function(accounts, terminals, scenario_id, transactions, ground_truth)

    # -------------------------
    # FILL REMAINING TRANSACTIONS
    # -------------------------
    while len(transactions) < NUM_TRANSACTIONS:
        transaction_id = f"TX{len(transactions) + 1:06d}"
        transactions.append(generate_normal_transaction(accounts, transaction_id))

    random.shuffle(transactions)
    transactions = transactions[:NUM_TRANSACTIONS]

    # -------------------------
    # SAVE TRANSACTIONS
    # -------------------------
    save_csv(
        "transactions.csv",
        transactions,
        [
            "transaction_id",
            "source_account_id",
            "target_account_id",
            "amount_inr",
            "timestamp",
            "payment_channel",
            "device_fingerprint",
            "balance_before",
            "balance_after"
        ]
    )

    # -------------------------
    # SAVE GROUND TRUTH
    # -------------------------
    save_csv(
        "ground_truth.csv",
        ground_truth,
        [
            "scenario_id",
            "transaction_id",
            "pattern_type",
            "is_fraud",
            "involved_account_ids",
            "expected_cashout_terminal_id"
        ]
    )

    print(f"✓ Generated {len(transactions)} transactions")
    print(f"✓ Generated {len(ground_truth)} ground-truth records")
    print("\nGeneration completed successfully!")
    print(f"Files saved in: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
