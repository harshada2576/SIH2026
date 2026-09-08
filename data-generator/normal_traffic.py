"""
normal_traffic.py — Accounts, terminals, and legitimate transaction traffic
SIH26184 — Predictive Cash Egress Interception — Workstream 1

CHANGELOG (this revision):
  - Accounts now carry account_status, account_region, and a primary_device_fingerprint
    (assigned once at creation) instead of a single throwaway device field.
  - Normal transactions mostly reuse the source account's primary device
    (NORMAL_TXN_PRIMARY_DEVICE_PROBABILITY in config.py), matching real
    behaviour — most people use one phone most of the time.
  - Terminals now carry a separate district name + pincode + status field
    (update request §5) instead of one combined district_pincode field.
    >>> This drifts from Architecture.md's locked §6.3 terminal schema —
    flagged in chat, needs a group-chat confirmation per Rules.md §7. <<<
  - All random draws now go through the single seeded `rng` argument — no
    more bare `random.xxx()` calls, which were a reproducibility bug before.

Every function has a one-line docstring per Rules.md §3.
"""

import random
import hashlib
from datetime import datetime, timedelta, timezone

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
    """Generate a synthetic transaction ID, drawn from the seeded rng (not the bare random module)."""
    return f"TXN-{rng.getrandbits(32):08x}"


def generate_accounts(num_accounts: int, rng: random.Random) -> list[dict]:
    """Create the pool of synthetic accounts, all initially tagged 'legit'.

    patterns.py overwrites `account_tier` (and may overwrite
    `primary_device_fingerprint` or `kyc_identity_id`) for whichever accounts it pulls into a
    fraud scenario, so this function's output is the "before" state.
    """
    kyc_pool = []
    while len(kyc_pool) < num_accounts:
        k_id = make_kyc_identity_id(rng)
        r = rng.random()
        if r < 0.85 or len(kyc_pool) + 1 == num_accounts:
            kyc_pool.append(k_id)
        elif r < 0.95 or len(kyc_pool) + 2 == num_accounts:
            kyc_pool.extend([k_id, k_id])
        else:
            kyc_pool.extend([k_id, k_id, k_id])
    kyc_pool = kyc_pool[:num_accounts]
    rng.shuffle(kyc_pool)

    accounts = []
    for i in range(1, num_accounts + 1):
        account_id = f"ACC-{i:05d}"
        accounts.append({
            "account_id": account_id,
            "account_tier": "legit",  # patterns.py overwrites this for accounts pulled into a scenario
            "account_age_days": rng.randint(1, 2000),
            "account_status": rng.choice(config.ACCOUNT_STATUSES),
            "historical_terminal_ids": [],  # filled in once cash-out history is known
            "primary_device_fingerprint": make_device_fingerprint(rng),
            "account_region": rng.choice(config.ACCOUNT_REGIONS),
            "kyc_identity_id": kyc_pool[i - 1],
        })
    return accounts


def generate_terminals(num_terminals: int, rng: random.Random) -> list[dict]:
    """Create the pool of synthetic ATM/AEPS/POS terminals spread across fake districts."""
    terminals = []
    banks = ["SBI", "HDFC", "ICICI", "PNB", "AXIS", "BOI"]
    for i in range(1, num_terminals + 1):
        district_idx = rng.randrange(len(config.DISTRICT_PINCODES))
        lat_center, lon_center = config.DISTRICT_CENTERS[district_idx]
        terminals.append({
            "terminal_id": f"ATM-{rng.choice(banks)}-{i:03d}",
            "terminal_type": rng.choice(config.TERMINAL_TYPES),
            "latitude": round(lat_center + rng.uniform(-0.05, 0.05), 6),
            "longitude": round(lon_center + rng.uniform(-0.05, 0.05), 6),
            "district": config.DISTRICT_NAMES[district_idx],
            "pincode": config.DISTRICT_PINCODES[district_idx],
            "status": rng.choice(config.TERMINAL_STATUSES),
        })
    return terminals


def _pareto_amount(min_amount: float, max_amount: float, shape: float, rng: random.Random) -> float:
    """Sample a power-law-ish transaction amount, clipped to [min_amount, max_amount]."""
    raw = min_amount * (1 + rng.paretovariate(shape))
    return round(min(raw, max_amount), 2)


def _pick_device_for_normal_txn(account: dict, rng: random.Random) -> str:
    """Pick the device fingerprint for a normal transaction — mostly the account's own phone."""
    if rng.random() < config.NORMAL_TXN_PRIMARY_DEVICE_PROBABILITY:
        return account["primary_device_fingerprint"]
    return make_device_fingerprint(rng)  # occasional different device — still normal behaviour


def generate_normal_transactions(accounts: list[dict], num_transactions: int,
                                  rng: random.Random) -> list[dict]:
    """Generate ordinary transactions with no fraud pattern between random distinct accounts."""
    accounts_by_id = {a["account_id"]: a for a in accounts}
    account_ids = list(accounts_by_id.keys())
    start = datetime.strptime(config.SIMULATION_START, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

    transactions = []
    for _ in range(num_transactions):
        source_id, target_id = rng.sample(account_ids, 2)  # guarantees source != target
        source_acc = accounts_by_id[source_id]
        amount = _pareto_amount(config.NORMAL_AMOUNT_MIN, config.NORMAL_AMOUNT_MAX,
                                 config.NORMAL_AMOUNT_PARETO_SHAPE, rng)
        channel = rng.choices(config.PAYMENT_CHANNELS, weights=config.PAYMENT_CHANNEL_WEIGHTS, k=1)[0]
        ts = _random_timestamp(start, config.SIMULATION_DURATION_HOURS, rng)

        transactions.append({
            "transaction_id": make_transaction_id(rng),
            "source_account_id": source_id,
            "target_account_id": target_id,
            "amount_inr": amount,
            "timestamp_dt": ts,   # kept as a datetime internally for chronological sorting
            "timestamp": _iso(ts),
            "payment_channel": channel,
            "device_fingerprint": _pick_device_for_normal_txn(source_acc, rng),
            # Internal evaluation fields — stripped before writing transactions.csv's
            # Kafka-mirroring section and never sent to Kafka (see producer.py).
            "_scenario_id": "",
            "_pattern_type": "normal",
            "_is_fraud": False,
            "_involved_account_ids": [],
            "_expected_cashout_terminal_id": "",
        })
    return transactions
