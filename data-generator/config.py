"""
config.py — Central configuration for the Synthetic Data Generator (Workstream 1)
SIH26184 — Predictive Cash Egress Interception

Configures multi-city geographic hubs across India, realistic multi-channel legitimate
traffic patterns, and 16 distinct fraud scenario archetypes.
"""

import os
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
RANDOM_SEED = 42

# ---------------------------------------------------------------------------
# Dataset scale defaults (can be overridden via CLI flags in generate.py)
# ---------------------------------------------------------------------------
NUM_ACCOUNTS = 1200
NUM_NORMAL_TRANSACTIONS = 8500
NUM_TERMINALS = 250

# Fraud scenario injection frequencies
NUM_SIMPLE_MULE_SCENARIOS = 5
NUM_LAYERING_SCENARIOS = 6
NUM_FAN_IN_SCENARIOS = 5
NUM_FAN_OUT_SCENARIOS = 5
NUM_FAN_IN_FAN_OUT_SCENARIOS = 4
NUM_RAPID_FORWARDING_SCENARIOS = 5
NUM_SHARED_DEVICE_SCENARIOS = 4
NUM_SHARED_KYC_SCENARIOS = 4
NUM_GEO_VELOCITY_SCENARIOS = 4
NUM_REPEATED_ATM_SCENARIOS = 4
NUM_MULTI_VICTIM_SCENARIOS = 4
NUM_DISTRIBUTED_CASHOUT_SCENARIOS = 4
NUM_DORMANT_ACTIVATION_SCENARIOS = 4
NUM_PROBING_THEN_LARGE_SCENARIOS = 4
NUM_CROSS_CITY_MULE_SCENARIOS = 5
NUM_CONCURRENT_CAMPAIGN_SCENARIOS = 3

# Legacy alias
NUM_TRIADIC_SCENARIOS = 2

# ---------------------------------------------------------------------------
# Pattern shape parameters
# ---------------------------------------------------------------------------
FAN_IN_MIN_SOURCES = 4
FAN_IN_MAX_SOURCES = 9
FAN_IN_WINDOW_MINUTES = 4

FAN_OUT_MIN_TARGETS = 4
FAN_OUT_MAX_TARGETS = 8
FAN_OUT_WINDOW_MINUTES = 6

LAYERING_MIN_HOPS = 3
LAYERING_MAX_HOPS = 6
LAYERING_AMOUNT_DECAY = 0.88
LAYERING_HOP_DELAY_MIN_SECONDS = 25
LAYERING_HOP_DELAY_MAX_SECONDS = 120

TRIADIC_CYCLE_LENGTH = 3

FRAUD_LARGE_AMOUNT_PROBABILITY = 0.20
FRAUD_LARGE_AMOUNT_MIN = 50000
FRAUD_LARGE_AMOUNT_MAX = 250000

FRAUD_AMOUNT_MIN = 500
FRAUD_AMOUNT_MAX = 50000

# ---------------------------------------------------------------------------
# Payment channels
# ---------------------------------------------------------------------------
PAYMENT_CHANNELS = ["UPI", "IMPS", "NEFT", "RTGS", "AEPS"]
PAYMENT_CHANNEL_WEIGHTS = [0.55, 0.22, 0.12, 0.04, 0.07]

# ---------------------------------------------------------------------------
# Amount distribution (INR)
# ---------------------------------------------------------------------------
NORMAL_AMOUNT_MIN = 20
NORMAL_AMOUNT_MAX = 65000
NORMAL_AMOUNT_PARETO_SHAPE = 1.75

# ---------------------------------------------------------------------------
# Timestamps
# ---------------------------------------------------------------------------
SIMULATION_START = "2026-09-01T00:00:00Z"
SIMULATION_DURATION_HOURS = 24

# ---------------------------------------------------------------------------
# Account tiers, status
# ---------------------------------------------------------------------------
ACCOUNT_TIERS = ["victim", "mule_l1", "mule_l2", "aggregator", "legit"]
ACCOUNT_STATUSES = ["active", "active", "active", "dormant", "frozen"]

INITIAL_BALANCE_RANGE_BY_TIER = {
    "legit": (5000, 250000),
    "victim": (8000, 300000),
    "mule_l1": (200, 6000),
    "mule_l2": (200, 6000),
    "aggregator": (300, 12000),
}
BALANCE_BUFFER_RANGE = (200, 5000)

NORMAL_TXN_PRIMARY_DEVICE_PROBABILITY = 0.88

# ---------------------------------------------------------------------------
# Multi-City Geographic Coverage (12 Major Indian Financial & Tech Hubs)
# ---------------------------------------------------------------------------
CITY_HUBS: Dict[str, Dict] = {
    "Delhi / NCR": {
        "districts": ["New Delhi Central", "South Delhi", "Noida", "Gurugram"],
        "pincodes": ["110001", "110016", "201301", "122001"],
        "centers": [(28.6139, 77.2090), (28.5494, 77.2001), (28.5355, 77.3910), (28.4595, 77.0266)],
    },
    "Mumbai": {
        "districts": ["South Mumbai", "Bandra BKC", "Andheri", "Navi Mumbai"],
        "pincodes": ["400001", "400051", "400053", "400703"],
        "centers": [(18.9322, 72.8347), (19.0596, 72.8295), (19.1136, 72.8697), (19.0330, 73.0297)],
    },
    "Bengaluru": {
        "districts": ["Central BLR", "Koramangala", "Whitefield", "Electronic City"],
        "pincodes": ["560001", "560034", "560066", "560100"],
        "centers": [(12.9716, 77.5946), (12.9352, 77.6245), (12.9698, 77.7499), (12.8399, 77.6770)],
    },
    "Hyderabad": {
        "districts": ["Hitec City", "Banjara Hills", "Secunderabad", "Old City Hyderabad"],
        "pincodes": ["500081", "500034", "500003", "500002"],
        "centers": [(17.4435, 78.3772), (17.4156, 78.4350), (17.4399, 78.4983), (17.3616, 78.4747)],
    },
    "Chennai": {
        "districts": ["Anna Salai", "OMR Taramani", "T-Nagar", "Guindy"],
        "pincodes": ["600002", "600113", "600017", "600032"],
        "centers": [(13.0827, 80.2707), (12.9863, 80.2432), (13.0418, 80.2341), (13.0067, 80.2025)],
    },
    "Kolkata": {
        "districts": ["Park Street", "Salt Lake Sector V", "New Town Kolkata", "Howrah"],
        "pincodes": ["700016", "700091", "700156", "711101"],
        "centers": [(22.5510, 88.3533), (22.5804, 88.4378), (22.5958, 88.4795), (22.5958, 88.2636)],
    },
    "Pune": {
        "districts": ["Shivaji Nagar Pune", "Hinjewadi IT Park", "Magarpatta Hadapsar", "Kothrud"],
        "pincodes": ["411005", "411057", "411028", "411038"],
        "centers": [(18.5314, 73.8446), (18.5913, 73.7389), (18.5134, 73.9317), (18.5074, 73.8077)],
    },
    "Ahmedabad": {
        "districts": ["Navrangpura", "SG Highway", "Maninagar", "Gandhinagar Center"],
        "pincodes": ["380009", "380054", "380008", "382010"],
        "centers": [(23.0365, 72.5611), (23.0538, 72.5085), (22.9968, 72.6015), (23.2156, 72.6369)],
    },
    "Jaipur": {
        "districts": ["MI Road Jaipur", "Malviya Nagar Jaipur", "Vaishali Nagar"],
        "pincodes": ["302001", "302017", "302021"],
        "centers": [(26.9124, 75.7873), (26.8532, 75.8055), (26.9157, 75.7412)],
    },
    "Lucknow": {
        "districts": ["Hazratganj", "Gomti Nagar Lucknow", "Alambagh"],
        "pincodes": ["226001", "226010", "226005"],
        "centers": [(26.8467, 80.9462), (26.8524, 80.9992), (26.8122, 80.9022)],
    },
    "Kochi": {
        "districts": ["Ernakulam Central", "Kakkanad InfoPark", "Fort Kochi"],
        "pincodes": ["682011", "682042", "682001"],
        "centers": [(9.9816, 76.2999), (10.0159, 76.3639), (9.9658, 76.2421)],
    },
    "Surat": {
        "districts": ["Ring Road Surat", "Adajan", "Vesu Surat"],
        "pincodes": ["395002", "395009", "395007"],
        "centers": [(21.1959, 72.8302), (21.1926, 72.7997), (21.1418, 72.7709)],
    },
}

# Flattened lookup lists for fast sampling and legacy compatibility
ACCOUNT_REGIONS: List[str] = []
DISTRICT_NAMES: List[str] = []
DISTRICT_PINCODES: List[str] = []
DISTRICT_CENTERS: List[Tuple[float, float]] = []

for city_name, data in CITY_HUBS.items():
    for d_name, pin, center in zip(data["districts"], data["pincodes"], data["centers"]):
        ACCOUNT_REGIONS.append(d_name)
        DISTRICT_NAMES.append(d_name)
        DISTRICT_PINCODES.append(pin)
        DISTRICT_CENTERS.append(center)

# ---------------------------------------------------------------------------
# Terminal types / status
# ---------------------------------------------------------------------------
TERMINAL_TYPES = ["ATM_KIOSK", "AEPS_MICRO_ATM", "POS"]
TERMINAL_STATUSES = ["ACTIVE", "ACTIVE", "ACTIVE", "ACTIVE", "MAINTENANCE", "INACTIVE"]
TERMINAL_BANKS = ["SBI", "HDFC", "ICICI", "PNB", "AXIS", "CANARA", "BOI", "PAYTM", "FINO", "JIO"]

# ---------------------------------------------------------------------------
# Kafka
# ---------------------------------------------------------------------------
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TRANSACTIONS_TOPIC = "transactions"
KAFKA_EVENTS_PER_SECOND = 20
KAFKA_PARTITION_KEY_STRATEGY = "hash_source_account"

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

