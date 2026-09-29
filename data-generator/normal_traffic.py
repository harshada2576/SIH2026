"""
normal_traffic.py — Deeply Interconnected & Realistic Legitimate Financial Graph Generator
SIH26184 — Predictive Cash Egress Interception — Workstream 1

Generates synthetic accounts, multi-city ATM/AEPS terminals, and diversified,
topologically interconnected legitimate banking transactions:
  1. Social Circle P2P (Small-world network clustering)
  2. Local Merchant & Kirana Retail (Star topologies centered on neighborhood stores)
  3. National Online Merchant Aggregators (Quick-commerce, e-commerce, food delivery)
  4. Corporate Payroll Disbursements (Enterprise batch salary credits on salary mornings)
  5. Utility & Telecom Billers (Recurring domestic bill payments)
  6. Normal Local ATM/AEPS Cash Withdrawals (Terminal affinity lookups)
  7. Commercial B2B Supply Chains (Distributor -> Wholesaler -> Retailer trades)
  8. Self / Own-Account Transfers (Within linked KYC household clusters)
  9. Travel & Commute (Transit and interstate mobility)
 10. Legitimate Festive & Shopping Bursts (Multi-purchase customer sessions)
"""
from __future__ import annotations

import hashlib
import math
import random
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import config


def _iso(dt: datetime) -> str:
    """Format a datetime as an ISO-8601 UTC string matching the locked schema."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# Pre-calculated multi-year weights cache
_CACHED_DAY_WEIGHTS: Optional[List[float]] = None
_CACHED_TOTAL_DAYS: int = 0

# 24-hour activity density weight distribution (Indian banking diurnal pattern)
HOURLY_WEIGHTS = [
    0.008, 0.005, 0.004, 0.004, 0.006, 0.012,  # 00:00 - 05:59 (Deep Night lull)
    0.025, 0.045, 0.065, 0.080, 0.085, 0.075,  # 06:00 - 11:59 (Morning surge & office start)
    0.070, 0.065, 0.060, 0.065, 0.075, 0.085,  # 12:00 - 17:59 (Lunch & afternoon retail)
    0.090, 0.080, 0.060, 0.035, 0.020, 0.013,  # 18:00 - 23:59 (Evening peak & night wind-down)
]


def _get_day_weights(start: datetime, total_days: int) -> List[float]:
    """
    Calculate realistic multi-year day weights capturing:
    1. Digital payment macro growth across 2024-2026 (~1.55x growth drift)
    2. Day-of-week seasonality (retail surges on weekends, business on Mondays)
    3. Day-of-month cycles (Salary disbursements on 1st-5th, month-end billing on 28th-31st)
    4. Indian festive & seasonal peaks (Diwali / Durga Puja in Oct/Nov, March financial year-end)
    """
    global _CACHED_DAY_WEIGHTS, _CACHED_TOTAL_DAYS
    if _CACHED_DAY_WEIGHTS is not None and _CACHED_TOTAL_DAYS == total_days:
        return _CACHED_DAY_WEIGHTS

    weights = []
    for day_idx in range(total_days):
        dt = start + timedelta(days=day_idx)
        # 1. Macro adoption growth
        macro = 1.0 + 0.55 * (day_idx / max(1, total_days))
        # 2. Day of week
        dow = dt.weekday()
        dow_f = 1.16 if dow in (5, 6) else (1.10 if dow == 0 else 1.0)
        # 3. Day of month
        dom = dt.day
        dom_f = 1.32 if 1 <= dom <= 5 else (1.20 if dom >= 28 else 1.0)
        # 4. Indian Festive / Annual Cycle
        month = dt.month
        festive = 1.48 if month in (10, 11) else (1.22 if month in (3, 12) else 1.0)
        weights.append(macro * dow_f * dom_f * festive)

    _CACHED_DAY_WEIGHTS = weights
    _CACHED_TOTAL_DAYS = total_days
    return weights


def _sample_diurnal_timestamp(start: datetime, duration_hours: int, rng: random.Random) -> datetime:
    """
    Sample a realistic timestamp according to multi-year natural timeline:
    Multi-year macroeconomic growth, weekly rhythms, salary/festive bursts, and 24h diurnal curve.
    """
    total_days = max(1, math.ceil(duration_hours / 24))
    weights = _get_day_weights(start, total_days)
    
    day_idx = rng.choices(range(total_days), weights=weights, k=1)[0]
    hour = rng.choices(range(24), weights=HOURLY_WEIGHTS, k=1)[0]
    minute = rng.randint(0, 59)
    second = rng.randint(0, 59)
    microsecond = rng.randint(0, 999999)
    
    return start + timedelta(days=day_idx, hours=hour, minutes=minute, seconds=second, microseconds=microsecond)


def make_device_fingerprint(rng: random.Random) -> str:
    """Generate one synthetic device fingerprint hash."""
    return "DEV-" + hashlib.sha1(str(rng.random()).encode()).hexdigest()[:12].upper()


def make_kyc_identity_id(rng: random.Random) -> str:
    """Generate one synthetic KYC identity hash."""
    return "KYC-IND-" + hashlib.sha1(str(rng.random()).encode()).hexdigest()[:12].upper()


def make_transaction_id(rng: random.Random) -> str:
    """Generate a collision-free synthetic transaction ID."""
    return f"TXN-{rng.getrandbits(64):016x}"


def _pareto_amount(min_amount: float, max_amount: float, shape: float, rng: random.Random) -> float:
    """Sample a power-law distributed transaction amount, clipped to [min_amount, max_amount]."""
    raw = min_amount * (1 + rng.paretovariate(shape))
    return round(min(raw, max_amount), 2)


# ---------------------------------------------------------------------------
# Account Generation with Structural Graph Topology
# ---------------------------------------------------------------------------
def generate_accounts(num_accounts: int, rng: random.Random) -> list[dict]:
    """
    Create the pool of synthetic accounts spread across all 20+ Indian hubs,
    establishing roles, small-world social clusters, corporate employee cohorts,
    and business supply chain structures.
    """
    # 1. Distribute KYC Identity pool with realistic family/household sharing
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

    # 2. Map KYC -> Shared Primary Device (Family members sharing a device or distinct)
    kyc_to_device = {}
    district_count = len(config.DISTRICT_NAMES)
    accounts = []

    # Calculate role partition sizes
    # 82% Retail consumers, 8% Local merchants, 2% Online hubs, 2% Utility billers, 3% Corporate, 3% B2B
    num_merchants = max(10, int(num_accounts * 0.08))
    num_online_hubs = max(5, int(num_accounts * 0.02))
    num_utilities = max(5, int(num_accounts * 0.02))
    num_corporates = max(5, int(num_accounts * 0.03))
    num_b2b = max(5, int(num_accounts * 0.03))

    roles = (
        ["merchant_local"] * num_merchants
        + ["merchant_online"] * num_online_hubs
        + ["utility_biller"] * num_utilities
        + ["corporate_employer"] * num_corporates
        + ["commercial_b2b"] * num_b2b
    )
    num_special = len(roles)
    num_retail = num_accounts - num_special
    roles.extend(["retail_consumer"] * num_retail)
    rng.shuffle(roles)

    for i in range(1, num_accounts + 1):
        account_id = f"ACC-{i:05d}"
        dist_idx = (i - 1) % district_count
        region = config.DISTRICT_NAMES[dist_idx]
        role = roles[i - 1]
        k_id = kyc_pool[i - 1]

        # Device assignment: shared for ~60% of joint KYC accounts, unique otherwise
        if k_id not in kyc_to_device:
            kyc_to_device[k_id] = make_device_fingerprint(rng)
        
        if rng.random() < 0.65:
            device = kyc_to_device[k_id]
        else:
            device = make_device_fingerprint(rng)

        # Realistic multi-year account age distribution:
        # - 20% veteran accounts (> 1000 days, established before 2024)
        # - 50% established accounts (270 to 1000 days, opened during 2024-2025)
        # - 30% newer accounts (1 to 270 days, opened in 2026)
        age_tier = rng.random()
        if age_tier < 0.30:
            age_days = rng.randint(1, 270)
        elif age_tier < 0.80:
            age_days = rng.randint(271, 1000)
        else:
            age_days = rng.randint(1001, 2800)

        accounts.append({
            "account_id": account_id,
            "account_tier": "legit",
            "account_role": role,
            "account_age_days": age_days,
            "account_status": rng.choice(config.ACCOUNT_STATUSES),
            "historical_terminal_ids": [],
            "primary_device_fingerprint": device,
            "account_region": region,
            "kyc_identity_id": k_id,
            "social_circle": [],  # Populated during graph structuring
            "employee_pool": [],  # For corporate employers
        })

    # 3. Structure Social Graph & Corporate Employee Cohorts
    _build_social_and_corporate_graph(accounts, rng)

    return accounts


def _build_social_and_corporate_graph(accounts: list[dict], rng: random.Random) -> None:
    """
    Connects accounts into a realistic social small-world network and corporate employer-employee clusters.
    """
    by_region_ids: Dict[str, List[str]] = defaultdict(list)
    retail_accounts: List[dict] = []
    retail_ids: List[str] = []
    corporate_accounts: List[dict] = []
    
    for a in accounts:
        by_region_ids[a["account_region"]].append(a["account_id"])
        if a["account_role"] == "retail_consumer":
            retail_accounts.append(a)
            retail_ids.append(a["account_id"])
        elif a["account_role"] == "corporate_employer":
            corporate_accounts.append(a)

    # A. Build Local Social Circles for Retail Consumers (3 to 10 contacts per person)
    for a in retail_accounts:
        aid = a["account_id"]
        region_peers = by_region_ids.get(a["account_region"], retail_ids)
        circle_size = rng.randint(3, 10)
        
        # 70% same district friends/family, 30% cross-district
        local_sample_size = min(len(region_peers) - 1, int(circle_size * 0.70))
        remote_sample_size = circle_size - local_sample_size
        
        peers = [p for p in rng.sample(region_peers, max(1, local_sample_size)) if p != aid]
        if remote_sample_size > 0 and len(retail_ids) > circle_size:
            remote_peers = [p for p in rng.sample(retail_ids, remote_sample_size) if p != aid]
            peers.extend(remote_peers)
            
        a["social_circle"] = list(set(peers))

    # B. Assign Corporate Employers their Employee Pools (15 to 60 employees each)
    if corporate_accounts and retail_ids:
        for corp in corporate_accounts:
            pool_size = min(len(retail_ids), rng.randint(15, 60))
            corp["employee_pool"] = rng.sample(retail_ids, pool_size)


# ---------------------------------------------------------------------------
# Terminal Generation & Historical Affinities
# ---------------------------------------------------------------------------
def generate_terminals(num_terminals: int, rng: random.Random, accounts: Optional[list[dict]] = None) -> list[dict]:
    """
    Create the pool of synthetic ATM/AEPS/POS terminals across all districts,
    and associate 2 to 4 nearest historical terminals with every account.
    """
    terminals = []
    district_count = len(config.DISTRICT_NAMES)

    terminals_by_district: Dict[str, List[str]] = defaultdict(list)

    for i in range(1, num_terminals + 1):
        dist_idx = (i - 1) % district_count
        lat_center, lon_center = config.DISTRICT_CENTERS[dist_idx]
        bank = rng.choice(config.TERMINAL_BANKS)
        t_type = rng.choice(config.TERMINAL_TYPES)
        prefix = "AEPS" if t_type == "AEPS_MICRO_ATM" else ("POS" if t_type == "POS" else "ATM")

        term_id = f"{prefix}-{bank}-{dist_idx:02d}-{i:04d}"
        d_name = config.DISTRICT_NAMES[dist_idx]
        terminals_by_district[d_name].append(term_id)

        terminals.append({
            "terminal_id": term_id,
            "terminal_type": t_type,
            "latitude": round(lat_center + rng.uniform(-0.035, 0.035), 6),
            "longitude": round(lon_center + rng.uniform(-0.035, 0.035), 6),
            "district": d_name,
            "pincode": config.DISTRICT_PINCODES[dist_idx],
            "status": rng.choice(config.TERMINAL_STATUSES),
            "bank_name": bank,
        })

    # Associate accounts with their local historical terminals
    if accounts:
        all_term_ids = [t["terminal_id"] for t in terminals]
        for a in accounts:
            dist_terms = terminals_by_district.get(a["account_region"], all_term_ids)
            sample_count = min(len(dist_terms), rng.randint(2, 4))
            a["historical_terminal_ids"] = rng.sample(dist_terms, sample_count)

    return terminals


# ---------------------------------------------------------------------------
# Interconnected Legitimate Transactions Generator
# ---------------------------------------------------------------------------
def _pick_device_for_normal_txn(account: dict, rng: random.Random) -> str:
    """Pick device fingerprint for normal transaction (primary device with occasional alternate)."""
    if rng.random() < config.NORMAL_TXN_PRIMARY_DEVICE_PROBABILITY:
        return account["primary_device_fingerprint"]
    return make_device_fingerprint(rng)


def generate_normal_transactions(
    accounts: list[dict],
    num_transactions: int,
    rng: random.Random,
    terminals: Optional[list[dict]] = None,
) -> list[dict]:
    """
    Generate an interconnected, topologically rich, realistic legitimate transaction stream:
    - 30% Social Circle & Family P2P (Small-world clustering)
    - 22% Local Merchant & Kirana Retail (Star network in local district)
    - 14% Online Merchant Hubs & Quick Commerce (Swiggy/Zomato/Amazon/Blinkit)
    - 8%  Corporate Payroll & Salary Disbursements (Corporate -> Employee batches)
    - 7%  Utility & Telecom Bills (Domestic billers)
    - 6%  Normal ATM / AEPS Cash Withdrawals (Account's historical affinity terminals)
    - 5%  Commercial B2B Trade & Supply Chain (Distributor -> Wholesaler settlements)
    - 4%  Self / Own-Account Transfers (Within joint KYC clusters)
    - 2%  Travel & Commute (Interstate transit and ticketing)
    - 2%  Shopping / Festive Bursts (Multi-purchase customer sessions)
    """
    accounts_by_id = {a["account_id"]: a for a in accounts}
    by_region: Dict[str, List[dict]] = defaultdict(list)
    by_role: Dict[str, List[dict]] = defaultdict(list)
    by_kyc: Dict[str, List[dict]] = defaultdict(list)

    for a in accounts:
        by_region[a["account_region"]].append(a)
        by_role[a.get("account_role", "retail_consumer")].append(a)
        by_kyc[a["kyc_identity_id"]].append(a)

    local_merchants_by_region: Dict[str, List[dict]] = defaultdict(list)
    for m in by_role.get("merchant_local", []):
        local_merchants_by_region[m["account_region"]].append(m)

    online_hubs = by_role.get("merchant_online", accounts[:10])
    utility_billers = by_role.get("utility_biller", accounts[:10])
    corporate_employers = by_role.get("corporate_employer", accounts[:10])
    b2b_actors = by_role.get("commercial_b2b", accounts[:10])
    retail_consumers = by_role.get("retail_consumer", accounts)

    joint_kyc_groups = [group for group in by_kyc.values() if len(group) > 1]

    start = datetime.strptime(config.SIMULATION_START, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    duration_hours = config.SIMULATION_DURATION_HOURS
    transactions: List[dict] = []

    all_account_ids = [a["account_id"] for a in accounts]
    num_bursts = int(num_transactions * 0.02)
    num_standard = num_transactions - num_bursts

    for _ in range(num_standard):
        r = rng.random()
        ts = _sample_diurnal_timestamp(start, duration_hours, rng)

        if r < 0.30:
            # 1. Social Circle & Family P2P (Small-world clustering)
            s_acc = rng.choice(retail_consumers)
            source_id = s_acc["account_id"]
            if s_acc.get("social_circle"):
                target_id = rng.choice(s_acc["social_circle"])
            else:
                target_id = rng.choice(all_account_ids)
            if target_id == source_id:
                target_id = rng.choice(all_account_ids)
            amount = _pareto_amount(50, 18000, 1.8, rng)
            channel = rng.choice(["UPI", "UPI", "UPI", "IMPS"])

        elif r < 0.52:
            # 2. Local Merchant & Kirana Retail (Star network in local district)
            s_acc = rng.choice(retail_consumers)
            source_id = s_acc["account_id"]
            local_merchants = local_merchants_by_region.get(s_acc["account_region"], by_role.get("merchant_local", accounts))
            t_acc = rng.choice(local_merchants) if local_merchants else rng.choice(accounts)
            target_id = t_acc["account_id"]
            if target_id == source_id:
                target_id = rng.choice(all_account_ids)
            amount = round(rng.uniform(25, 4200), 2)
            channel = rng.choice(["UPI", "UPI", "UPI", "AEPS", "IMPS"])

        elif r < 0.66:
            # 3. Online Merchant Hubs & Quick Commerce (Swiggy, Zomato, Amazon, Blinkit)
            s_acc = rng.choice(retail_consumers)
            source_id = s_acc["account_id"]
            t_acc = rng.choice(online_hubs)
            target_id = t_acc["account_id"]
            amount = round(rng.uniform(120, 8500), 2)
            channel = rng.choice(["UPI", "UPI", "IMPS"])

        elif r < 0.74:
            # 4. Corporate Payroll & Salary Disbursements (Corporate -> Employee cohorts)
            corp = rng.choice(corporate_employers) if corporate_employers else rng.choice(accounts)
            source_id = corp["account_id"]
            if corp.get("employee_pool"):
                target_id = rng.choice(corp["employee_pool"])
            else:
                target_id = rng.choice(retail_consumers)["account_id"]
            if target_id == source_id:
                target_id = rng.choice(all_account_ids)
            amount = round(rng.uniform(28000, 240000), 2)
            channel = rng.choice(["NEFT", "NEFT", "IMPS", "RTGS"])
            # Payrolls cluster on salary mornings (1st-5th of each month, 09:00 - 13:00)
            total_months = max(1, duration_hours // (24 * 30))
            m_idx = rng.randint(0, total_months - 1)
            dom = rng.randint(1, 5)
            salary_day_offset = min(max(1, duration_hours // 24) - 1, m_idx * 30 + dom)
            ts = start + timedelta(days=salary_day_offset, hours=rng.uniform(9.0, 13.0), minutes=rng.uniform(0, 59))

        elif r < 0.81:
            # 5. Utility & Telecom Bills (BESCOM, Jio, Airtel, Water)
            s_acc = rng.choice(retail_consumers)
            source_id = s_acc["account_id"]
            t_acc = rng.choice(utility_billers)
            target_id = t_acc["account_id"]
            amount = round(rng.uniform(199, 6500), 2)
            channel = rng.choice(["UPI", "UPI", "NEFT", "IMPS"])

        elif r < 0.87:
            # 6. Normal Local ATM / AEPS Cash Withdrawals (Terminal affinity lookups)
            s_acc = rng.choice(retail_consumers)
            source_id = s_acc["account_id"]
            # Cashout destination is bank cash-pool account
            t_acc = rng.choice(local_merchants_by_region.get(s_acc["account_region"], accounts))
            target_id = t_acc["account_id"]
            amount = round(rng.choice([500, 1000, 2000, 2500, 4000, 5000, 8000, 10000]), 2)
            channel = "AEPS"

        elif r < 0.92:
            # 7. Commercial B2B Supply Chains (Distributor -> Wholesaler settlements)
            s_acc = rng.choice(b2b_actors) if b2b_actors else rng.choice(accounts)
            t_acc = rng.choice(b2b_actors) if b2b_actors else rng.choice(accounts)
            source_id = s_acc["account_id"]
            target_id = t_acc["account_id"]
            if target_id == source_id:
                target_id = rng.choice(all_account_ids)
            amount = round(rng.uniform(45000, 650000), 2)
            channel = rng.choice(["RTGS", "RTGS", "NEFT"])

        elif r < 0.96:
            # 8. Self / Own-Account Transfers (Within linked KYC household clusters)
            if joint_kyc_groups:
                kyc_cluster = rng.choice(joint_kyc_groups)
                pair = rng.sample(kyc_cluster, 2)
                source_id, target_id = pair[0]["account_id"], pair[1]["account_id"]
            else:
                s_acc, t_acc = rng.sample(accounts, 2)
                source_id, target_id = s_acc["account_id"], t_acc["account_id"]
            amount = _pareto_amount(500, 45000, 1.7, rng)
            channel = rng.choice(["IMPS", "UPI", "NEFT"])

        else:
            # 9. Travel & Commute (Transit, flights, metro, hotel bookings)
            s_acc = rng.choice(retail_consumers)
            source_id = s_acc["account_id"]
            t_acc = rng.choice(online_hubs)
            target_id = t_acc["account_id"]
            amount = round(rng.uniform(450, 18500), 2)
            channel = rng.choice(["UPI", "UPI", "IMPS"])

        src_acc = accounts_by_id.get(source_id, accounts[0])
        transactions.append({
            "transaction_id": make_transaction_id(rng),
            "source_account_id": source_id,
            "target_account_id": target_id,
            "amount_inr": amount,
            "timestamp_dt": ts,
            "timestamp": _iso(ts),
            "payment_channel": channel,
            "device_fingerprint": _pick_device_for_normal_txn(src_acc, rng),
            "_scenario_id": "",
            "_pattern_type": "normal",
            "_is_fraud": False,
            "_involved_account_ids": [],
            "_expected_cashout_terminal_id": "",
        })

    # 10. Legitimate Festive & Shopping Bursts (Multi-purchase customer sessions in 1-2 hours)
    for _ in range(num_bursts // 4 + 1):
        s_acc = rng.choice(retail_consumers)
        source_id = s_acc["account_id"]
        burst_start = _sample_diurnal_timestamp(start, duration_hours - 3, rng)
        sampled_targets = rng.sample(all_account_ids, min(6, len(all_account_ids)))
        burst_targets = [tid for tid in sampled_targets if tid != source_id][:4]

        for idx, t_id in enumerate(burst_targets):
            offset_m = idx * rng.uniform(3, 20)
            ts = burst_start + timedelta(minutes=offset_m)
            transactions.append({
                "transaction_id": make_transaction_id(rng),
                "source_account_id": source_id,
                "target_account_id": t_id,
                "amount_inr": round(rng.uniform(150, 4800), 2),
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
