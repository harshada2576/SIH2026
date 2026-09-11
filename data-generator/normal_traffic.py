"""
normal_traffic.py — Accounts, terminals, and diversified legitimate transaction traffic
SIH26184 — Predictive Cash Egress Interception — Workstream 1

Generates synthetic accounts, realistic multi-city ATM/AEPS terminals, and diversified
legitimate transaction archetypes (P2P, salary, merchants, recurring bills, B2B transfers, bursts).
"""

import random
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import config


def _iso(dt: datetime) -> str:
    """Format a datetime as an ISO-8601 UTC string matching the locked schema."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _random_timestamp(start: datetime, duration_hours: int, rng: random.Random) -> datetime:
    """Return a random timestamp uniformly spread across the simulation window."""
    offset_seconds = rng.uniform(0, duration_hours * 3600)
    return start + timedelta(seconds=offset_seconds)


def make_device_fingerprint(rng: random.Random) -> str:
    """Generate one synthetic device fingerprint hash, drawn from the seeded rng."""
    return "DEV-" + hashlib.sha1(str(rng.random()).encode()).hexdigest()[:10].upper()


def make_kyc_identity_id(rng: random.Random) -> str:
    """Generate one synthetic KYC identity hash, drawn from the seeded rng."""
    return "KYC-IND-" + hashlib.sha1(str(rng.random()).encode()).hexdigest()[:10].upper()


def make_transaction_id(rng: random.Random) -> str:
    """Generate a synthetic transaction ID, drawn from the seeded rng."""
    return f"TXN-{rng.getrandbits(32):08x}"


def generate_accounts(num_accounts: int, rng: random.Random) -> list[dict]:
    """Create the pool of synthetic accounts spread across all 12 major Indian hubs."""
    kyc_pool = []
    while len(kyc_pool) < num_accounts:
        k_id = make_kyc_identity_id(rng)
        r = rng.random()
        if r < 0.88 or len(kyc_pool) + 1 == num_accounts:
            kyc_pool.append(k_id)
        elif r < 0.96 or len(kyc_pool) + 2 == num_accounts:
            kyc_pool.extend([k_id, k_id])
        else:
            kyc_pool.extend([k_id, k_id, k_id])
    kyc_pool = kyc_pool[:num_accounts]
    rng.shuffle(kyc_pool)

    # Distribute accounts across all districts
    district_count = len(config.DISTRICT_NAMES)
    accounts = []
    for i in range(1, num_accounts + 1):
        account_id = f"ACC-{i:05d}"
        dist_idx = (i - 1) % district_count
        region = config.DISTRICT_NAMES[dist_idx]
        
        # Realistic account age: mixture of fresh (1-10 days), established (30-365 days), and long-standing (>365 days)
        age_tier = rng.random()
        if age_tier < 0.12:
            age_days = rng.randint(1, 14)
        elif age_tier < 0.70:
            age_days = rng.randint(15, 365)
        else:
            age_days = rng.randint(366, 2500)

        accounts.append({
            "account_id": account_id,
            "account_tier": "legit",
            "account_age_days": age_days,
            "account_status": rng.choice(config.ACCOUNT_STATUSES),
            "historical_terminal_ids": [],
            "primary_device_fingerprint": make_device_fingerprint(rng),
            "account_region": region,
            "kyc_identity_id": kyc_pool[i - 1],
        })
    return accounts


def generate_terminals(num_terminals: int, rng: random.Random) -> list[dict]:
    """Create the pool of synthetic ATM/AEPS/POS terminals across all 12 cities."""
    terminals = []
    district_count = len(config.DISTRICT_NAMES)
    
    for i in range(1, num_terminals + 1):
        dist_idx = (i - 1) % district_count
        lat_center, lon_center = config.DISTRICT_CENTERS[dist_idx]
        bank = rng.choice(config.TERMINAL_BANKS)
        t_type = rng.choice(config.TERMINAL_TYPES)
        prefix = "AEPS" if t_type == "AEPS_MICRO_ATM" else "ATM"

        terminals.append({
            "terminal_id": f"{prefix}-{bank}-{dist_idx:02d}-{i:03d}",
            "terminal_type": t_type,
            "latitude": round(lat_center + rng.uniform(-0.035, 0.035), 6),
            "longitude": round(lon_center + rng.uniform(-0.035, 0.035), 6),
            "district": config.DISTRICT_NAMES[dist_idx],
            "pincode": config.DISTRICT_PINCODES[dist_idx],
            "status": rng.choice(config.TERMINAL_STATUSES),
            "bank_name": bank,
        })
    return terminals


def _pareto_amount(min_amount: float, max_amount: float, shape: float, rng: random.Random) -> float:
    """Sample a power-law-ish transaction amount, clipped to [min_amount, max_amount]."""
    raw = min_amount * (1 + rng.paretovariate(shape))
    return round(min(raw, max_amount), 2)


def _pick_device_for_normal_txn(account: dict, rng: random.Random) -> str:
    """Pick device fingerprint for normal transaction (mostly primary device, occasional alternate)."""
    if rng.random() < config.NORMAL_TXN_PRIMARY_DEVICE_PROBABILITY:
        return account["primary_device_fingerprint"]
    return make_device_fingerprint(rng)


def generate_normal_transactions(accounts: list[dict], num_transactions: int,
                                  rng: random.Random) -> list[dict]:
    """Generate diversified legitimate transaction traffic across all categories and cities."""
    accounts_by_id = {a["account_id"]: a for a in accounts}
    account_ids = list(accounts_by_id.keys())
    accounts_by_region = {}
    for a in accounts:
        accounts_by_region.setdefault(a["account_region"], []).append(a)

    start = datetime.strptime(config.SIMULATION_START, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    transactions = []

    # Categorization of normal traffic:
    # 1. Intra-city P2P (35%)
    # 2. Inter-city P2P (25%) - normal mobility & interstate remittances
    # 3. Merchant Payments (20%) - frequent small/medium UPI/POS
    # 4. Salary / Payroll Credits (8%) - regular higher NEFT/IMPS
    # 5. Recurring Bills / Utilities (7%) - recurring bills
    # 6. Commercial B2B / High-Value Transfers (3%) - RTGS/NEFT
    # 7. Shopping/Festive Bursts (2%) - multiple transactions from same user in short window

    num_bursts = int(num_transactions * 0.02)
    num_standard = num_transactions - num_bursts

    for _ in range(num_standard):
        archetype = rng.random()

        if archetype < 0.35:
            # 1. Intra-city P2P
            region = rng.choice(list(accounts_by_region.keys()))
            reg_accounts = accounts_by_region[region]
            if len(reg_accounts) >= 2:
                s_acc, t_acc = rng.sample(reg_accounts, 2)
            else:
                s_acc, t_acc = rng.sample(accounts, 2)
            source_id, target_id = s_acc["account_id"], t_acc["account_id"]
            amount = _pareto_amount(50, 8000, 1.8, rng)
            channel = rng.choice(["UPI", "UPI", "IMPS"])
            ts = _random_timestamp(start, config.SIMULATION_DURATION_HOURS, rng)

        elif archetype < 0.60:
            # 2. Inter-city P2P
            s_acc, t_acc = rng.sample(accounts, 2)
            source_id, target_id = s_acc["account_id"], t_acc["account_id"]
            amount = _pareto_amount(100, 15000, 1.7, rng)
            channel = rng.choice(["UPI", "IMPS", "NEFT"])
            ts = _random_timestamp(start, config.SIMULATION_DURATION_HOURS, rng)

        elif archetype < 0.80:
            # 3. Merchant Payments
            s_acc, t_acc = rng.sample(accounts, 2)
            source_id, target_id = s_acc["account_id"], t_acc["account_id"]
            amount = round(rng.uniform(20, 2500), 2)
            channel = rng.choice(["UPI", "UPI", "AEPS"])
            ts = _random_timestamp(start, config.SIMULATION_DURATION_HOURS, rng)

        elif archetype < 0.88:
            # 4. Salary / Payroll Credits
            s_acc, t_acc = rng.sample(accounts, 2)
            source_id, target_id = s_acc["account_id"], t_acc["account_id"]
            amount = round(rng.uniform(25000, 180000), 2)
            channel = rng.choice(["NEFT", "IMPS", "RTGS"])
            # Typically 1st of month morning
            salary_hour = rng.uniform(8.0, 14.0)
            ts = start + timedelta(hours=salary_hour, minutes=rng.uniform(0, 59))

        elif archetype < 0.95:
            # 5. Recurring Bills / Utilities
            s_acc, t_acc = rng.sample(accounts, 2)
            source_id, target_id = s_acc["account_id"], t_acc["account_id"]
            amount = round(rng.uniform(450, 18000), 2)
            channel = rng.choice(["UPI", "NEFT", "IMPS"])
            ts = _random_timestamp(start, config.SIMULATION_DURATION_HOURS, rng)

        else:
            # 6. Commercial B2B / High-Value Transfers (Testing False Positives)
            s_acc, t_acc = rng.sample(accounts, 2)
            source_id, target_id = s_acc["account_id"], t_acc["account_id"]
            amount = round(rng.uniform(75000, 450000), 2)
            channel = rng.choice(["RTGS", "NEFT"])
            ts = _random_timestamp(start, config.SIMULATION_DURATION_HOURS, rng)

        source_acc = accounts_by_id[source_id]
        transactions.append({
            "transaction_id": make_transaction_id(rng),
            "source_account_id": source_id,
            "target_account_id": target_id,
            "amount_inr": amount,
            "timestamp_dt": ts,
            "timestamp": _iso(ts),
            "payment_channel": channel,
            "device_fingerprint": _pick_device_for_normal_txn(source_acc, rng),
            "_scenario_id": "",
            "_pattern_type": "normal",
            "_is_fraud": False,
            "_involved_account_ids": [],
            "_expected_cashout_terminal_id": "",
        })

    # 7. Shopping/Festive Bursts (single legitimate customer buying multiple items in 2 hours)
    for _ in range(num_bursts // 4 + 1):
        s_acc = rng.choice(accounts)
        source_id = s_acc["account_id"]
        burst_start = _random_timestamp(start, config.SIMULATION_DURATION_HOURS - 3, rng)
        burst_targets = rng.sample([a["account_id"] for a in accounts if a["account_id"] != source_id], min(4, len(accounts) - 1))
        
        for idx, t_id in enumerate(burst_targets):
            offset_m = idx * rng.uniform(4, 25)
            ts = burst_start + timedelta(minutes=offset_m)
            transactions.append({
                "transaction_id": make_transaction_id(rng),
                "source_account_id": source_id,
                "target_account_id": t_id,
                "amount_inr": round(rng.uniform(150, 3200), 2),
                "timestamp_dt": ts,
                "timestamp": _iso(ts),
                "payment_channel": "UPI",
                "device_fingerprint": s_acc["primary_device_fingerprint"],
                "_scenario_id": "",
                "_pattern_type": "normal_burst",
                "_is_fraud": False,
                "_involved_account_ids": [],
                "_expected_cashout_terminal_id": "",
            })

    return transactions

