import random
from datetime import datetime, timedelta


FAST_CHANNELS = [
    "UPI",
    "IMPS"
]

OTHER_CHANNELS = [
    "NEFT",
    "RTGS"
]


def create_transaction(
    transaction_id,
    source,
    target,
    amount,
    timestamp,
    channel,
    device
):

    balance_before = round(
        random.uniform(50000, 300000),
        2
    )

    if amount >= balance_before:
        amount = round(balance_before * 0.7, 2)

    return {
        "transaction_id": transaction_id,
        "source_account_id": source["account_id"],
        "target_account_id": target["account_id"],
        "amount_inr": round(amount, 2),
        "timestamp": timestamp.isoformat(),
        "payment_channel": channel,
        "device_fingerprint": device,
        "balance_before": balance_before,
        "balance_after": round(
            balance_before - amount,
            2
        )
    }


def fan_in(
    accounts,
    terminals,
    scenario_id,
    transactions,
    ground_truth
):

    victims = [
        a for a in accounts
        if a["account_tier"] == "victim"
    ]

    mules = [
        a for a in accounts
        if a["account_tier"] == "mule_l1"
    ]

    mule = random.choice(mules)

    selected = random.sample(victims, 5)

    terminal = random.choice(terminals)

    base_time = datetime.now()

    involved = [
        a["account_id"]
        for a in selected + [mule]
    ]

    for i, victim in enumerate(selected):

        tx_id = f"{scenario_id}-TX{i+1:03d}"

        timestamp = base_time + timedelta(
            seconds=i * random.randint(20, 50)
        )

        transaction = create_transaction(
            tx_id,
            victim,
            mule,
            random.uniform(5000, 40000),
            timestamp,
            random.choice(FAST_CHANNELS),
            victim["primary_device_fingerprint"]
        )

        transactions.append(transaction)

        ground_truth.append({
            "scenario_id": scenario_id,
            "transaction_id": tx_id,
            "pattern_type": "fan_in",
            "is_fraud": True,
            "involved_account_ids": ",".join(involved),
            "expected_cashout_terminal_id":
                terminal["terminal_id"]
        })


def fan_out(
    accounts,
    terminals,
    scenario_id,
    transactions,
    ground_truth
):

    mules = [
        a for a in accounts
        if a["account_tier"] == "mule_l1"
    ]

    receivers = [
        a for a in accounts
        if a["account_tier"] in [
            "mule_l2",
            "aggregator"
        ]
    ]

    mule = random.choice(mules)

    selected = random.sample(receivers, 5)

    terminal = random.choice(terminals)

    base_time = datetime.now()

    involved = [
        mule["account_id"]
    ] + [
        a["account_id"] for a in selected
    ]

    # Shared device is intentional fraud signal
    shared_device = mule["primary_device_fingerprint"]

    for i, receiver in enumerate(selected):

        tx_id = f"{scenario_id}-TX{i+1:03d}"

        timestamp = base_time + timedelta(
            seconds=i * random.randint(20, 50)
        )

        transaction = create_transaction(
            tx_id,
            mule,
            receiver,
            random.uniform(5000, 40000),
            timestamp,
            random.choice(FAST_CHANNELS),
            shared_device
        )

        transactions.append(transaction)

        ground_truth.append({
            "scenario_id": scenario_id,
            "transaction_id": tx_id,
            "pattern_type": "fan_out",
            "is_fraud": True,
            "involved_account_ids": ",".join(involved),
            "expected_cashout_terminal_id":
                terminal["terminal_id"]
        })


def layering(
    accounts,
    terminals,
    scenario_id,
    transactions,
    ground_truth
):

    mule_l1 = random.choice([
        a for a in accounts
        if a["account_tier"] == "mule_l1"
    ])

    mule_l2 = random.choice([
        a for a in accounts
        if a["account_tier"] == "mule_l2"
    ])

    aggregator = random.choice([
        a for a in accounts
        if a["account_tier"] == "aggregator"
    ])

    chain = [
        mule_l1,
        mule_l2,
        aggregator
    ]

    terminal = random.choice(terminals)

    base_time = datetime.now()

    involved = [
        a["account_id"]
        for a in chain
    ]

    amount = random.uniform(
        30000,
        100000
    )

    for i in range(len(chain) - 1):

        source = chain[i]
        target = chain[i + 1]

        tx_id = f"{scenario_id}-TX{i+1:03d}"

        timestamp = base_time + timedelta(
            seconds=i * random.randint(60, 150)
        )

        transaction = create_transaction(
            tx_id,
            source,
            target,
            amount * random.uniform(0.85, 1.0),
            timestamp,
            random.choice(
                FAST_CHANNELS + OTHER_CHANNELS
            ),
            source["primary_device_fingerprint"]
        )

        transactions.append(transaction)

        ground_truth.append({
            "scenario_id": scenario_id,
            "transaction_id": tx_id,
            "pattern_type": "layering",
            "is_fraud": True,
            "involved_account_ids": ",".join(involved),
            "expected_cashout_terminal_id":
                terminal["terminal_id"]
        })


def triadic(
    accounts,
    terminals,
    scenario_id,
    transactions,
    ground_truth
):

    selected = random.sample(accounts, 3)

    terminal = random.choice(terminals)

    base_time = datetime.now()

    involved = [
        a["account_id"]
        for a in selected
    ]

    for i in range(3):

        source = selected[i]

        target = selected[
            (i + 1) % 3
        ]

        tx_id = f"{scenario_id}-TX{i+1:03d}"

        timestamp = base_time + timedelta(
            seconds=i * random.randint(30, 70)
        )

        transaction = create_transaction(
            tx_id,
            source,
            target,
            random.uniform(10000, 50000),
            timestamp,
            random.choice(FAST_CHANNELS),
            source["primary_device_fingerprint"]
        )

        transactions.append(transaction)

        ground_truth.append({
            "scenario_id": scenario_id,
            "transaction_id": tx_id,
            "pattern_type": "triadic",
            "is_fraud": True,
            "involved_account_ids": ",".join(involved),
            "expected_cashout_terminal_id":
                terminal["terminal_id"]
        })