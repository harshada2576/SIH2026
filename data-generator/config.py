"""
config.py — Central configuration for the Synthetic Data Generator (Workstream 1)
SIH26184 — Predictive Cash Egress Interception

Every tunable knob lives here. Nothing else should hard-code a count, rate,
or path — import from this module instead. That's what makes "scale from 100
accounts to 100,000 transactions" a config change, not a code change.

CHANGELOG (this revision):
  - Added balance-simulation parameters (§3 of the update request).
  - Added account_status, account_region, primary-device-reuse parameters (§4, §8).
  - Added terminal status parameter (§5) and split district name from pincode.
  - Tightened layering hop delay to match the "rapid chain" example in §10.
  - Added an occasional-large-amount knob for fraud scenarios (§9).
"""

import os

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
# Same seed + same config = same output, always. Every random draw anywhere
# in this codebase MUST come from the single rng object created from this
# seed and threaded through every function call — never from the bare
# `random` module. (This was a real bug in the previous revision — see README
# changelog — now fixed.)
RANDOM_SEED = 42  # Set to None for a different random dataset every run

# ---------------------------------------------------------------------------
# Dataset scale
# ---------------------------------------------------------------------------
NUM_ACCOUNTS = 100
NUM_NORMAL_TRANSACTIONS = 400
NUM_TERMINALS = 50

NUM_FAN_IN_SCENARIOS = 3
NUM_FAN_OUT_SCENARIOS = 3
NUM_LAYERING_SCENARIOS = 3
NUM_TRIADIC_SCENARIOS = 2

# ---------------------------------------------------------------------------
# Pattern shape parameters
# ---------------------------------------------------------------------------
FAN_IN_MIN_SOURCES = 4
FAN_IN_MAX_SOURCES = 8
FAN_IN_WINDOW_MINUTES = 3

FAN_OUT_MIN_TARGETS = 4
FAN_OUT_MAX_TARGETS = 8
FAN_OUT_WINDOW_MINUTES = 5

LAYERING_MIN_HOPS = 3
LAYERING_MAX_HOPS = 6
LAYERING_AMOUNT_DECAY = 0.85
# Tightened per update request §10 ("10:00 A->B, 10:01 B->C, ..." — ~60s/hop).
LAYERING_HOP_DELAY_MIN_SECONDS = 30
LAYERING_HOP_DELAY_MAX_SECONDS = 150

TRIADIC_CYCLE_LENGTH = 3

# Chance that a given fraud scenario uses an unusually large amount instead
# of the normal fraud amount range (update request §9: "occasional very
# large transactions" in fraud scenarios).
FRAUD_LARGE_AMOUNT_PROBABILITY = 0.15
FRAUD_LARGE_AMOUNT_MIN = 45000
FRAUD_LARGE_AMOUNT_MAX = 190000  # still under RTGS's typical 2-lakh+ territory

# ---------------------------------------------------------------------------
# LOCKED — payment channels (Architecture.md §6.1). Do not add/remove without
# posting it in the group chat and updating shared/schemas.py first.
# NOTE: kept all 5 (including AEPS) — see flagged conflict in chat reply,
# AEPS is central to the project's rural micro-ATM cash-out premise (§9).
# ---------------------------------------------------------------------------
PAYMENT_CHANNELS = ["UPI", "IMPS", "NEFT", "RTGS", "AEPS"]
PAYMENT_CHANNEL_WEIGHTS = [0.55, 0.25, 0.10, 0.03, 0.07]

# ---------------------------------------------------------------------------
# Amount distribution (INR) — heavy-tailed: many small/medium, few large,
# occasional very large (update request §9).
# ---------------------------------------------------------------------------
NORMAL_AMOUNT_MIN = 50
NORMAL_AMOUNT_MAX = 50000
NORMAL_AMOUNT_PARETO_SHAPE = 1.8

FRAUD_AMOUNT_MIN = 500
FRAUD_AMOUNT_MAX = 45000

# ---------------------------------------------------------------------------
# Timestamps
# ---------------------------------------------------------------------------
SIMULATION_START = "2026-09-01T00:00:00Z"
SIMULATION_DURATION_HOURS = 24

# ---------------------------------------------------------------------------
# Account tiers, status, region
# ---------------------------------------------------------------------------
# LOCKED base vocabulary (Architecture.md §6.2): victim, mule_l1, mule_l2,
# aggregator. "legit" is ADDED (not in the original doc) so accounts never
# touched by a fraud scenario have a clean label.
# >>> Still flagged for team confirmation — see chat message. <<<
ACCOUNT_TIERS = ["victim", "mule_l1", "mule_l2", "aggregator", "legit"]

# New in this revision (update request §4) — synthetic-only, no real meaning.
ACCOUNT_STATUSES = ["active", "active", "active", "dormant", "frozen"]  # weighted via repetition
ACCOUNT_REGIONS = [f"District-{i+1}" for i in range(8)]  # matches the 8 terminal districts

# Balance simulation (update request §3)
# Starting balance ranges are tier-dependent so the story stays realistic:
# freshly-opened mule accounts start thin, established/victim accounts don't.
INITIAL_BALANCE_RANGE_BY_TIER = {
    "legit": (5000, 200000),
    "victim": (5000, 200000),
    "mule_l1": (200, 5000),
    "mule_l2": (200, 5000),
    "aggregator": (200, 8000),
}
# Extra cash buffer added on top of the mathematically-required minimum so
# balances don't sit at exactly zero after every debit (see generate.py
# compute_balances() for how the minimum-required amount is derived).
BALANCE_BUFFER_RANGE = (200, 5000)

# ---------------------------------------------------------------------------
# Device fingerprints (update request §8)
# ---------------------------------------------------------------------------
# Probability that a normal transaction reuses the source account's primary
# device rather than showing a different one. Real people mostly use one
# phone; a used a different device once in a while is normal (lost phone,
# new SIM, shared family device) and shouldn't itself be a fraud signal.
NORMAL_TXN_PRIMARY_DEVICE_PROBABILITY = 0.9

# ---------------------------------------------------------------------------
# Terminal types / status (update request §5)
# ---------------------------------------------------------------------------
TERMINAL_TYPES = ["ATM_KIOSK", "AEPS_MICRO_ATM", "POS"]
TERMINAL_STATUSES = ["ACTIVE", "ACTIVE", "ACTIVE", "ACTIVE", "MAINTENANCE", "INACTIVE"]
DISTRICT_PINCODES = [str(110001 + i * 37) for i in range(8)]
DISTRICT_NAMES = ACCOUNT_REGIONS  # same 8 fake districts used for accounts and terminals
DISTRICT_CENTERS = [
    (28.6139, 77.2090), (28.7041, 77.1025), (28.4595, 77.0266),
    (28.5355, 77.3910), (28.6692, 77.4538), (28.4089, 77.3178),
    (28.9845, 77.7064), (28.2180, 76.9800),
]

# ---------------------------------------------------------------------------
# Kafka
# ---------------------------------------------------------------------------
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TRANSACTIONS_TOPIC = "transactions"
KAFKA_EVENTS_PER_SECOND = 20
KAFKA_PARTITION_KEY_STRATEGY = "hash_source_account"  # or "district_pincode"

# The Kafka event contract is exactly these 7 fields, in this order — used by
# producer.py to strip out balance_before/balance_after before publishing.
# LOCKED — Architecture.md §6.1.
KAFKA_EVENT_FIELDS = [
    "transaction_id", "source_account_id", "target_account_id",
    "amount_inr", "timestamp", "payment_channel", "device_fingerprint",
]

# ---------------------------------------------------------------------------
# Output paths
# ---------------------------------------------------------------------------
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
ACCOUNTS_CSV = os.path.join(DATA_DIR, "accounts.csv")
TERMINALS_CSV = os.path.join(DATA_DIR, "terminals.csv")
TRANSACTIONS_CSV = os.path.join(DATA_DIR, "transactions.csv")
GROUND_TRUTH_CSV = os.path.join(DATA_DIR, "ground_truth.csv")
