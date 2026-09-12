#!/usr/bin/env python3
"""
scripts/live_demo/normal_traffic.py — Realistic Normal Background Transaction Stream
SIH26184 — Predictive Cash Egress Interception

Generates continuous, realistic legitimate transaction volume passing through
Kafka -> GraphStore -> Detection Engine without triggering false alarms.
Volume is configurable (e.g. 2-5 tx/s) to run continuously alongside live fraud demos.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import random
import signal
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.kafka_utils import (
    KAFKA_BOOTSTRAP_SERVERS,
    TRANSACTIONS_TOPIC,
    get_kafka_producer,
)
from scripts.live_demo.common import (
    DEFAULT_API_URL,
    _http_get_json,
    _http_post_json,
    format_iso,
    get_now_utc,
    make_account,
    make_transaction,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("normal_traffic")

# ---------------------------------------------------------------------------
# TERMINALS & REGIONS
# ---------------------------------------------------------------------------
KNOWN_TERMINALS = [
    "ATM-HDFC-Ce-001",
    "AEPS-BCR-002",
    "POS-PNB-003",
    "ATM-ICICI-Ce-004",
    "AEPS-BCR-005",
    "POS-SBI-006",
    "ATM-SBI-Ce-007",
    "AEPS-BCR-008",
    "POS-PNB-009",
    "ATM-SBI-Ce-010",
]

REGIONS = ["Delhi", "Mumbai", "Bengaluru", "Hyderabad", "Chennai", "Pune", "Kolkata"]

# ---------------------------------------------------------------------------
# 15 LEGITIMATE BEHAVIORAL CLASSES
# ---------------------------------------------------------------------------
CLASS_ORDINARY_P2P = "01_ordinary_p2p"
CLASS_FAMILY_FRIEND = "02_family_friends"
CLASS_SALARY_PAYROLL = "03_salary_payroll"
CLASS_MERCHANT_RETAIL = "04_merchant_retail"
CLASS_UTILITY_BILLS = "05_utility_bills"
CLASS_SUBSCRIPTIONS = "06_subscriptions"
CLASS_MICRO_UPI = "07_micro_upi"
CLASS_ATM_WITHDRAWAL = "08_atm_withdrawal"
CLASS_B2B_VENDOR = "09_b2b_vendor"
CLASS_OWN_ACCOUNT_TRANSFER = "10_own_account_self"
CLASS_LARGE_LEGIT_PURCHASE = "11_large_purchase"
CLASS_TRAVEL_COMMUTE = "12_travel_commute"
CLASS_FAVORITE_MERCHANT = "13_frequent_merchant"
CLASS_LEGIT_SUPPLY_CHAIN = "14_commercial_supply"
CLASS_BORDERLINE_LEGIT = "15_borderline_burst"

BEHAVIOR_WEIGHTS = {
    CLASS_ORDINARY_P2P: 18,
    CLASS_FAMILY_FRIEND: 12,
    CLASS_SALARY_PAYROLL: 5,
    CLASS_MERCHANT_RETAIL: 20,
    CLASS_UTILITY_BILLS: 8,
    CLASS_SUBSCRIPTIONS: 6,
    CLASS_MICRO_UPI: 14,
    CLASS_ATM_WITHDRAWAL: 6,
    CLASS_B2B_VENDOR: 4,
    CLASS_OWN_ACCOUNT_TRANSFER: 5,
    CLASS_LARGE_LEGIT_PURCHASE: 2,
    CLASS_TRAVEL_COMMUTE: 4,
    CLASS_FAVORITE_MERCHANT: 8,
    CLASS_LEGIT_SUPPLY_CHAIN: 3,
    CLASS_BORDERLINE_LEGIT: 2,
}

# ---------------------------------------------------------------------------
# ACCOUNT POOL GENERATOR (Deterministic & Realistic)
# ---------------------------------------------------------------------------
class AccountPool:
    """Manages diverse pools of realistic legitimate Indian retail & merchant entities."""

    def __init__(self, seed: Optional[int] = 42):
        if seed is not None:
            random.seed(seed)
        
        self.retail_users: List[dict] = []
        self.merchants: List[dict] = []
        self.utilities: List[dict] = []
        self.corporates: List[dict] = []
        self.businesses: List[dict] = []
        self.user_linked_secondary: Dict[str, str] = {}
        self.user_fav_merchants: Dict[str, str] = {}
        self.user_family_pairs: List[Tuple[str, str]] = []
        self.all_metadata: List[dict] = []

        self._build_pool()

    def _build_pool(self):
        # 1. Retail Users (60 accounts)
        for i in range(1, 61):
            acc_id = f"ACC-USR-{1000 + i}"
            dev_id = f"DEV-USR-{1000 + i}"
            kyc_id = f"KYC-IND-{200000 + i}"
            region = random.choice(REGIONS)
            assigned_terminals = random.sample(KNOWN_TERMINALS, k=random.randint(1, 3))
            meta = make_account(
                account_id=acc_id,
                tier="victim",  # Legitimate retail citizen tier
                age_days=random.randint(60, 2400),
                terminals=assigned_terminals,
                kyc_id=kyc_id,
                device=dev_id,
            )
            meta["region"] = region
            self.retail_users.append(meta)
            self.all_metadata.append(meta)

            # Secondary account for self-transfers (Savings -> Salary / Current)
            if i <= 20:
                sec_id = f"ACC-USR-{1000 + i}-SEC"
                sec_meta = make_account(
                    account_id=sec_id,
                    tier="victim",
                    age_days=random.randint(90, 1800),
                    terminals=assigned_terminals,
                    kyc_id=kyc_id,  # Same KYC identity
                    device=dev_id,   # Same phone device
                )
                sec_meta["region"] = region
                self.user_linked_secondary[acc_id] = sec_id
                self.all_metadata.append(sec_meta)

        # 2. Merchants (20 accounts)
        merchant_names = [
            ("Zepto-QuickMart", "UPI"), ("Swiggy-Insta", "UPI"), ("Zomato-Delivery", "UPI"),
            ("DMart-Retail", "POS"), ("Reliance-Smart", "POS"), ("Apollo-Pharmacy", "UPI"),
            ("Shell-Fuel-Station", "POS"), ("Starbucks-Coffee", "UPI"), ("Blue-Tokai", "UPI"),
            ("Blinkit-Express", "UPI"), ("Myntra-Fashion", "UPI"), ("Decathlon-Sports", "POS"),
            ("BigBasket-Grocery", "UPI"), ("Croma-Electronics", "POS"), ("HP-Petrol-Pump", "POS"),
            ("McDonalds-Food", "UPI"), ("Subway-Sandwiches", "UPI"), ("Nature-Basket", "POS"),
            ("Local-Kirana-Store", "UPI"), ("Modern-Stationery", "UPI")
        ]
        for idx, (name, channel) in enumerate(merchant_names, 1):
            m_id = f"ACC-MERCH-{2000 + idx}"
            dev_id = f"DEV-MERCH-POS-{2000 + idx}"
            meta = make_account(
                account_id=m_id,
                tier="victim",
                age_days=random.randint(300, 3000),
                terminals=random.sample(KNOWN_TERMINALS, 2),
                kyc_id=f"KYC-GSTIN-{880000 + idx}",
                device=dev_id,
            )
            meta["name"] = name
            meta["channel"] = channel
            self.merchants.append(meta)
            self.all_metadata.append(meta)

        # Map each retail user to a favorite regular merchant
        for u in self.retail_users:
            fav = random.choice(self.merchants)
            self.user_fav_merchants[u["account_id"]] = fav["account_id"]

        # 3. Utility Billers (8 accounts)
        util_names = [
            "BESCOM-Power", "Tata-Power-Delhi", "Airtel-Broadband", "Jio-Fiber-Telecom",
            "Indraprastha-Gas", "Delhi-Jal-Board", "HDFC-Ergo-Insurance", "Adani-Electricity"
        ]
        for idx, uname in enumerate(util_names, 1):
            u_id = f"ACC-UTIL-{3000 + idx}"
            meta = make_account(
                account_id=u_id,
                tier="victim",
                age_days=random.randint(1000, 4000),
                terminals=["ATM-HDFC-Ce-001"],
                kyc_id=f"KYC-CORP-UTIL-{990000 + idx}",
                device=f"SRV-UTIL-BILLER-{3000 + idx}",
            )
            meta["name"] = uname
            self.utilities.append(meta)
            self.all_metadata.append(meta)

        # 4. Corporate Employers (6 accounts)
        corp_names = [
            "Infosys-Technologies", "Tata-Consultancy-Services", "Wipro-Global",
            "HDFC-Bank-Payroll", "Flipkart-Internet", "Zomato-Media-Corp"
        ]
        for idx, cname in enumerate(corp_names, 1):
            c_id = f"ACC-CORP-{4000 + idx}"
            meta = make_account(
                account_id=c_id,
                tier="victim",
                age_days=random.randint(1500, 5000),
                terminals=["ATM-HDFC-Ce-001"],
                kyc_id=f"KYC-CORP-CIN-{770000 + idx}",
                device=f"SRV-CORP-HOST-{4000 + idx}",
            )
            meta["name"] = cname
            self.corporates.append(meta)
            self.all_metadata.append(meta)

        # 5. Small Businesses & B2B Suppliers (10 accounts)
        for idx in range(1, 11):
            b_id = f"ACC-BIZ-{5000 + idx}"
            meta = make_account(
                account_id=b_id,
                tier="victim",
                age_days=random.randint(200, 1800),
                terminals=random.sample(KNOWN_TERMINALS, 2),
                kyc_id=f"KYC-MSME-{660000 + idx}",
                device=f"DEV-BIZ-TERM-{5000 + idx}",
            )
            self.businesses.append(meta)
            self.all_metadata.append(meta)

        # 6. Set up family/friend pairs
        for i in range(0, len(self.retail_users) - 1, 2):
            self.user_family_pairs.append((
                self.retail_users[i]["account_id"],
                self.retail_users[i+1]["account_id"]
            ))


# ---------------------------------------------------------------------------
# NORMAL TRANSACTION GENERATOR
# ---------------------------------------------------------------------------
class NormalTrafficGenerator:
    """Generates continuous realistic background traffic matching 15 behavioral classes."""

    def __init__(self, pool: AccountPool, seed: Optional[int] = None):
        if seed is not None:
            random.seed(seed)
        self.pool = pool
        self.tx_counter = 0
        self.behavior_keys = list(BEHAVIOR_WEIGHTS.keys())
        self.behavior_probs = list(BEHAVIOR_WEIGHTS.values())

    def next_transaction(self, now: Optional[datetime] = None) -> Tuple[dict, str]:
        """Generates one realistic transaction according to weighted legitimate classes."""
        self.tx_counter += 1
        now = now or get_now_utc()
        tx_id = f"TXN-NRM-{now.strftime('%H%M%S')}-{self.tx_counter:06d}"
        
        # Select behavioral class
        cls = random.choices(self.behavior_keys, weights=self.behavior_probs, k=1)[0]

        # 1. Ordinary P2P
        if cls == CLASS_ORDINARY_P2P:
            u1, u2 = random.sample(self.pool.retail_users, 2)
            amount = round(random.lognormvariate(7.0, 0.8), 2)  # ~₹500 to ₹5,000
            amount = max(100.0, min(amount, 12000.0))
            channel = random.choice(["UPI", "UPI", "IMPS"])
            tx = make_transaction(tx_id, u1["account_id"], u2["account_id"], amount, now, channel, u1["primary_device_fingerprint"])

        # 2. Family & Friends Transfer
        elif cls == CLASS_FAMILY_FRIEND:
            pair = random.choice(self.pool.user_family_pairs)
            sender_id, recipient_id = pair if random.random() > 0.5 else (pair[1], pair[0])
            amount = round(random.uniform(1000.0, 25000.0), 2)
            channel = random.choice(["UPI", "IMPS"])
            tx = make_transaction(tx_id, sender_id, recipient_id, amount, now, channel, f"DEV-FAM-{sender_id}")

        # 3. Corporate Salary Payroll Credit
        elif cls == CLASS_SALARY_PAYROLL:
            corp = random.choice(self.pool.corporates)
            emp = random.choice(self.pool.retail_users)
            amount = round(random.uniform(35000.0, 175000.0), 2)
            channel = random.choice(["NEFT", "RTGS", "IMPS"])
            tx = make_transaction(tx_id, corp["account_id"], emp["account_id"], amount, now, channel, corp["primary_device_fingerprint"])

        # 4. Merchant Retail Payment
        elif cls == CLASS_MERCHANT_RETAIL:
            user = random.choice(self.pool.retail_users)
            merch = random.choice(self.pool.merchants)
            amount = round(random.lognormvariate(6.2, 0.9), 2)  # ~₹200 to ₹2,500
            amount = max(49.0, min(amount, 8500.0))
            channel = merch.get("channel", "UPI")
            tx = make_transaction(tx_id, user["account_id"], merch["account_id"], amount, now, channel, user["primary_device_fingerprint"])

        # 5. Utility & Bill Payment
        elif cls == CLASS_UTILITY_BILLS:
            user = random.choice(self.pool.retail_users)
            biller = random.choice(self.pool.utilities)
            amount = round(random.uniform(250.0, 4800.0), 2)
            tx = make_transaction(tx_id, user["account_id"], biller["account_id"], amount, now, "UPI", user["primary_device_fingerprint"])

        # 6. Recurring Subscription
        elif cls == CLASS_SUBSCRIPTIONS:
            user = random.choice(self.pool.retail_users)
            sub_merch = random.choice(self.pool.merchants[:6])
            amount = float(random.choice([199.0, 299.0, 499.0, 799.0, 1199.0, 1499.0]))
            tx = make_transaction(tx_id, user["account_id"], sub_merch["account_id"], amount, now, "UPI", user["primary_device_fingerprint"])

        # 7. Micro UPI Spend (Chai / Auto / Snacks)
        elif cls == CLASS_MICRO_UPI:
            user = random.choice(self.pool.retail_users)
            merch = random.choice(self.pool.merchants)
            amount = round(random.uniform(10.0, 240.0), 2)
            tx = make_transaction(tx_id, user["account_id"], merch["account_id"], amount, now, "UPI", user["primary_device_fingerprint"])

        # 8. Normal ATM Cash Withdrawal
        elif cls == CLASS_ATM_WITHDRAWAL:
            user = random.choice(self.pool.retail_users)
            term_id = user["historical_terminal_ids"][0] if user["historical_terminal_ids"] else "ATM-HDFC-Ce-001"
            amount = float(random.choice([500.0, 1000.0, 2000.0, 4000.0, 5000.0, 10000.0]))
            tx = make_transaction(tx_id, user["account_id"], f"ACC-CASH-{term_id}", amount, now, "AEPS", user["primary_device_fingerprint"])

        # 9. Small Business B2B Invoice Settlement
        elif cls == CLASS_B2B_VENDOR:
            b1, b2 = random.sample(self.pool.businesses, 2)
            amount = round(random.uniform(15000.0, 120000.0), 2)
            channel = random.choice(["NEFT", "RTGS", "IMPS"])
            tx = make_transaction(tx_id, b1["account_id"], b2["account_id"], amount, now, channel, b1["primary_device_fingerprint"])

        # 10. Self Account Transfer (Savings -> Secondary)
        elif cls == CLASS_OWN_ACCOUNT_TRANSFER:
            user_keys = list(self.pool.user_linked_secondary.keys())
            u_primary = random.choice(user_keys)
            u_sec = self.pool.user_linked_secondary[u_primary]
            amount = round(random.uniform(2000.0, 45000.0), 2)
            tx = make_transaction(tx_id, u_primary, u_sec, amount, now, "IMPS", f"DEV-USR-{u_primary}")

        # 11. Large Legitimate Purchase
        elif cls == CLASS_LARGE_LEGIT_PURCHASE:
            user = random.choice(self.pool.retail_users)
            merch = random.choice(self.pool.merchants)
            amount = round(random.uniform(60000.0, 220000.0), 2)
            tx = make_transaction(tx_id, user["account_id"], merch["account_id"], amount, now, "NEFT", user["primary_device_fingerprint"])

        # 12. Plausible Travel & Commute
        elif cls == CLASS_TRAVEL_COMMUTE:
            user = random.choice(self.pool.retail_users)
            merch = random.choice(self.pool.merchants)
            amount = round(random.uniform(850.0, 14500.0), 2)
            tx = make_transaction(tx_id, user["account_id"], merch["account_id"], amount, now, "UPI", user["primary_device_fingerprint"])

        # 13. Regular / Favorite Merchant Spend
        elif cls == CLASS_FAVORITE_MERCHANT:
            user = random.choice(self.pool.retail_users)
            fav_merch = self.pool.user_fav_merchants.get(user["account_id"], self.pool.merchants[0]["account_id"])
            amount = round(random.uniform(120.0, 950.0), 2)
            tx = make_transaction(tx_id, user["account_id"], fav_merch, amount, now, "UPI", user["primary_device_fingerprint"])

        # 14. Legitimate Commercial Supply Chain
        elif cls == CLASS_LEGIT_SUPPLY_CHAIN:
            biz = random.choice(self.pool.businesses)
            merch = random.choice(self.pool.merchants)
            amount = round(random.uniform(25000.0, 85000.0), 2)
            tx = make_transaction(tx_id, merch["account_id"], biz["account_id"], amount, now, "NEFT", merch["primary_device_fingerprint"])

        # 15. Borderline / Festive Rush Burst (High volume, but non-fraudulent)
        else:
            user = random.choice(self.pool.retail_users)
            merch = random.choice(self.pool.merchants)
            amount = round(random.uniform(1500.0, 18000.0), 2)
            tx = make_transaction(tx_id, user["account_id"], merch["account_id"], amount, now, "UPI", user["primary_device_fingerprint"])

        return tx, cls


# ---------------------------------------------------------------------------
# STREAMING RUNNER ENGINE
# ---------------------------------------------------------------------------
class TrafficStreamRunner:
    """Manages the real-time background injection loop into Kafka and Backend API."""

    def __init__(
        self,
        rate_tps: float = 5.0,
        duration_sec: Optional[int] = 300,
        continuous: bool = False,
        api_url: str = DEFAULT_API_URL,
        seed: Optional[int] = 42,
        quiet: bool = False,
    ):
        self.rate_tps = max(0.1, rate_tps)
        self.duration_sec = duration_sec if not continuous else None
        self.continuous = continuous
        self.api_url = api_url
        self.seed = seed
        self.quiet = quiet
        self.stop_requested = False

        self.pool = AccountPool(seed=seed)
        self.generator = NormalTrafficGenerator(self.pool, seed=seed)
        self.class_counts = Counter()
        self.total_sent = 0
        self.start_time = 0.0

        # Producer init
        self.kafka_producer = None
        try:
            self.kafka_producer = get_kafka_producer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)
        except Exception:
            self.kafka_producer = None

    def request_stop(self, signum=None, frame=None):
        """Signal handler for graceful stop."""
        self.stop_requested = True
        print("\n[*] Stopping normal traffic generator cleanly...")

    def run(self):
        """Main streaming loop."""
        signal.signal(signal.SIGINT, self.request_stop)
        signal.signal(signal.SIGTERM, self.request_stop)

        print("\n" + "=" * 78)
        print("  CYBERSHIELD LIVE DEMO — REALISTIC NORMAL BACKGROUND TRAFFIC STREAM")
        print("=" * 78)
        print(f"  Target Rate:       {self.rate_tps:.1f} transactions/second")
        print(f"  Execution Mode:    {'CONTINUOUS (Indefinite)' if self.continuous else f'{self.duration_sec} seconds'}")
        print(f"  Backend Ingestion: {self.api_url}")
        print(f"  Kafka Topic:       {TRANSACTIONS_TOPIC} ({'Active' if self.kafka_producer else 'Standalone Fallback'})")
        print(f"  Account Pool:      {len(self.pool.all_metadata)} total accounts initialized")
        print("  Press Ctrl+C to stop cleanly anytime.")
        print("-" * 78 + "\n")

        # Initial account metadata registration to backend
        _http_post_json(f"{self.api_url}/transactions", {"transactions": [], "accounts": self.pool.all_metadata}, timeout=4.0)

        self.start_time = time.time()
        interval = 1.0 / self.rate_tps
        batch_buffer: List[dict] = []
        last_flush_time = time.time()
        last_report_time = time.time()

        initial_case_count = self._get_case_count()

        try:
            while not self.stop_requested:
                now_utc = get_now_utc()
                tx, cls = self.generator.next_transaction(now_utc)
                self.class_counts[cls] += 1
                self.total_sent += 1
                batch_buffer.append(tx)

                # 1. Send to Kafka if active
                if self.kafka_producer:
                    try:
                        self.kafka_producer.send(TRANSACTIONS_TOPIC, key=tx["source_account_id"], value=tx)
                    except Exception:
                        pass

                # 2. Flush batch to backend API every ~0.5s or if buffer size >= 5
                current_time = time.time()
                if (current_time - last_flush_time >= 0.5) or len(batch_buffer) >= 8:
                    if batch_buffer:
                        _http_post_json(f"{self.api_url}/transactions", {"transactions": batch_buffer}, timeout=3.0)
                        batch_buffer.clear()
                        last_flush_time = current_time

                # 3. Periodic console throughput reporting (every 2.5s)
                if current_time - last_report_time >= 2.5:
                    elapsed = current_time - self.start_time
                    eff_rate = self.total_sent / elapsed if elapsed > 0 else 0.0
                    current_cases = self._get_case_count()
                    alerts_diff = max(0, current_cases - initial_case_count)
                    
                    if not self.quiet:
                        sys.stdout.write(
                            f"\r  [STREAMING] Elapsed: {elapsed:5.1f}s | Injected: {self.total_sent:6d} txs | "
                            f"Throughput: {eff_rate:4.1f} tx/s | Alerts: {alerts_diff} (Normal/Expected: 0)   "
                        )
                        sys.stdout.flush()
                    last_report_time = current_time

                # Check duration if not continuous
                if not self.continuous and self.duration_sec and (current_time - self.start_time >= self.duration_sec):
                    break

                # Sleep to maintain requested rate
                time.sleep(interval)

        finally:
            # Flush any remaining buffer
            if batch_buffer:
                _http_post_json(f"{self.api_url}/transactions", {"transactions": batch_buffer}, timeout=3.0)
            if self.kafka_producer:
                try:
                    self.kafka_producer.flush(timeout=2)
                except Exception:
                    pass

        self._print_final_summary(initial_case_count)

    def _get_case_count(self) -> int:
        """Helper to get current total cases count."""
        try:
            data = _http_get_json(f"{self.api_url}/cases?role=BANK", timeout=2.0)
            if data and "cases" in data:
                return len(data["cases"])
        except Exception:
            pass
        return 0

    def _print_final_summary(self, initial_case_count: int):
        """Prints formatted summary report upon termination."""
        elapsed = time.time() - self.start_time
        eff_rate = self.total_sent / elapsed if elapsed > 0 else 0.0
        final_cases = self._get_case_count()
        new_alerts = max(0, final_cases - initial_case_count)

        print("\n\n" + "=" * 78)
        print("  NORMAL BACKGROUND TRAFFIC STREAM — EXECUTION SUMMARY REPORT")
        print("=" * 78)
        print(f"  Total Run Duration:     {elapsed:.2f} seconds")
        print(f"  Total Transactions:     {self.total_sent} transactions")
        print(f"  Observed Throughput:    {eff_rate:.2f} tx/second (Target: {self.rate_tps:.1f} tx/s)")
        print(f"  Normal Accounts Active: {len(self.pool.all_metadata)} distinct entities")
        print(f"  Elevated Alerts Raised: {new_alerts} alerts (False Positive Rate: {new_alerts/max(1, self.total_sent)*100:.2f}%)")
        print("-" * 78)
        print("  BEHAVIORAL CLASS BREAKDOWN:")
        for cls_name, count in sorted(self.class_counts.items(), key=lambda x: x[1], reverse=True):
            pct = (count / max(1, self.total_sent)) * 100
            print(f"    • {cls_name:<30} : {count:5d} txs ({pct:5.1f}%)")
        print("=" * 78 + "\n")


# ---------------------------------------------------------------------------
# CLI ENTRYPOINT
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="CyberShield Normal Background Traffic Generator (SIH26184)")
    parser.add_argument("--rate", type=float, default=5.0, help="Target transactions per second (default 5.0)")
    parser.add_argument("--duration", type=int, default=300, help="Duration in seconds (default 300s = 5 min)")
    parser.add_argument("--continuous", action="store_true", help="Run indefinitely until stopped with Ctrl+C")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help=f"Backend API URL (default {DEFAULT_API_URL})")
    parser.add_argument("--quiet", action="store_true", help="Suppress streaming progress line")
    args = parser.parse_args()

    runner = TrafficStreamRunner(
        rate_tps=args.rate,
        duration_sec=args.duration,
        continuous=args.continuous,
        api_url=args.api_url,
        seed=args.seed,
        quiet=args.quiet,
    )
    runner.run()


if __name__ == "__main__":
    main()
