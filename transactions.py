import random
import uuid
from datetime import datetime, timedelta


CHANNELS = [
    "UPI",
    "IMPS",
    "NEFT",
    "RTGS",
    "AEPS"
]


def generate_amount():

    # Heavy-tailed / realistic transaction amounts
    amount = random.lognormvariate(7.2, 1.1)

    return round(
        min(max(amount, 100), 300000),
        2
    )


def generate_normal_transaction(accounts, transaction_id):

    source = random.choice(accounts)

    target = random.choice(accounts)

    while target["account_id"] == source["account_id"]:
        target = random.choice(accounts)

    amount = generate_amount()

    balance_before = round(
        random.uniform(20000, 300000),
        2
    )

    # Make sure balance is sufficient
    if amount > balance_before:
        amount = round(balance_before * 0.5, 2)

    balance_after = round(
        balance_before - amount,
        2
    )

    timestamp = datetime.now() - timedelta(
        minutes=random.randint(0, 4320)
    )

    return {
        "transaction_id": transaction_id,
        "source_account_id": source["account_id"],
        "target_account_id": target["account_id"],
        "amount_inr": amount,
        "timestamp": timestamp.isoformat(),
        "payment_channel": random.choice(CHANNELS),
        "device_fingerprint":
            source["primary_device_fingerprint"],
        "balance_before": balance_before,
        "balance_after": balance_after
    }