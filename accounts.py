import csv
import random
import os

from config import NUM_ACCOUNTS, NUM_TERMINALS, OUTPUT_DIR


ACCOUNT_TIERS = [
    "victim",
    "mule_l1",
    "mule_l2",
    "aggregator"
]

REGIONS = [
    "Mumbai",
    "Thane",
    "Navi Mumbai",
    "Pune",
    "Nagpur"
]


def generate_accounts():

    accounts = []

    for i in range(1, NUM_ACCOUNTS + 1):

        account_id = f"ACC{i:03d}"

        # Keep most accounts normal/victim accounts
        if i <= 117:
            tier = "victim"
        elif i <= 157:
            tier = "mule_l1"
        elif i <= 195:
            tier = "mule_l2"
        else:
            tier = "aggregator"

        account = {
            "account_id": account_id,
            "account_tier": tier,
            "account_age_days": random.randint(10, 2500),
            "account_status": random.choice(
                ["active", "active", "active", "inactive"]
            ),
            "historical_terminal_ids": ",".join(
                f"ATM{i:03d}"
                for i in random.sample(
                    range(1, NUM_TERMINALS + 1),
                    random.randint(1, 3)
                )
            ),
            "primary_device_fingerprint": f"DEV{i:03d}",
            "account_region": random.choice(REGIONS),
            "kyc_identity_id": f"KYC-IND-{i:05d}"
        }

        accounts.append(account)

    return accounts


def save_accounts(accounts):

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    filename = f"{OUTPUT_DIR}/accounts.csv"

    fields = [
        "account_id",
        "account_tier",
        "account_age_days",
        "account_status",
        "historical_terminal_ids",
        "primary_device_fingerprint",
        "account_region",
        "kyc_identity_id"
    ]

    with open(filename, "w", newline="", encoding="utf-8") as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fields
        )

        writer.writeheader()
        writer.writerows(accounts)


if __name__ == "__main__":

    accounts = generate_accounts()

    save_accounts(accounts)

    print(f"Generated {len(accounts)} accounts.")