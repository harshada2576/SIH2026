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
# Dataset scale defaults (10x expansion for production realism)
# ---------------------------------------------------------------------------
NUM_ACCOUNTS = 25000
NUM_NORMAL_TRANSACTIONS = 235000
NUM_TERMINALS = 2500

# Fraud scenario injection frequencies (~700+ campaign instances)
NUM_SIMPLE_MULE_SCENARIOS = 50
NUM_LAYERING_SCENARIOS = 60
NUM_FAN_IN_SCENARIOS = 50
NUM_FAN_OUT_SCENARIOS = 50
NUM_FAN_IN_FAN_OUT_SCENARIOS = 40
NUM_RAPID_FORWARDING_SCENARIOS = 50
NUM_SHARED_DEVICE_SCENARIOS = 40
NUM_SHARED_KYC_SCENARIOS = 40
NUM_GEO_VELOCITY_SCENARIOS = 40
NUM_REPEATED_ATM_SCENARIOS = 40
NUM_MULTI_VICTIM_SCENARIOS = 40
NUM_DISTRIBUTED_CASHOUT_SCENARIOS = 40
NUM_DORMANT_ACTIVATION_SCENARIOS = 40
NUM_PROBING_THEN_LARGE_SCENARIOS = 40
NUM_CROSS_CITY_MULE_SCENARIOS = 50
NUM_CONCURRENT_CAMPAIGN_SCENARIOS = 30

# Legacy alias
NUM_TRIADIC_SCENARIOS = 20

# ---------------------------------------------------------------------------
# Pattern shape parameters
# ---------------------------------------------------------------------------
FAN_IN_MIN_SOURCES = 4
FAN_IN_MAX_SOURCES = 12
FAN_IN_WINDOW_MINUTES = 4

FAN_OUT_MIN_TARGETS = 4
FAN_OUT_MAX_TARGETS = 10
FAN_OUT_WINDOW_MINUTES = 6

LAYERING_MIN_HOPS = 3
LAYERING_MAX_HOPS = 6
LAYERING_AMOUNT_DECAY = 0.88
LAYERING_HOP_DELAY_MIN_SECONDS = 20
LAYERING_HOP_DELAY_MAX_SECONDS = 120

TRIADIC_CYCLE_LENGTH = 3

FRAUD_LARGE_AMOUNT_PROBABILITY = 0.22
FRAUD_LARGE_AMOUNT_MIN = 50000
FRAUD_LARGE_AMOUNT_MAX = 350000

FRAUD_AMOUNT_MIN = 500
FRAUD_AMOUNT_MAX = 50000

# ---------------------------------------------------------------------------
# Payment channels
# ---------------------------------------------------------------------------
PAYMENT_CHANNELS = ["UPI", "IMPS", "NEFT", "RTGS", "AEPS"]
PAYMENT_CHANNEL_WEIGHTS = [0.58, 0.20, 0.11, 0.04, 0.07]

# ---------------------------------------------------------------------------
# Amount distribution (INR)
# ---------------------------------------------------------------------------
NORMAL_AMOUNT_MIN = 10
NORMAL_AMOUNT_MAX = 150000
NORMAL_AMOUNT_PARETO_SHAPE = 1.75

# ---------------------------------------------------------------------------
# Timestamps
# ---------------------------------------------------------------------------
SIMULATION_START = "2026-09-01T00:00:00Z"
SIMULATION_DURATION_HOURS = 72

# ---------------------------------------------------------------------------
# Account tiers, status
# ---------------------------------------------------------------------------
ACCOUNT_TIERS = ["victim", "mule_l1", "mule_l2", "aggregator", "legit"]
ACCOUNT_STATUSES = ["active", "active", "active", "active", "dormant", "frozen"]

INITIAL_BALANCE_RANGE_BY_TIER = {
    "legit": (5000, 350000),
    "victim": (10000, 500000),
    "mule_l1": (200, 8000),
    "mule_l2": (200, 8000),
    "aggregator": (500, 25000),
}
BALANCE_BUFFER_RANGE = (500, 10000)

NORMAL_TXN_PRIMARY_DEVICE_PROBABILITY = 0.88

# ---------------------------------------------------------------------------
# Multi-City Geographic Coverage (20 Major Indian Financial, Commercial & Regional Hubs)
# ---------------------------------------------------------------------------
CITY_HUBS: Dict[str, Dict] = {
    "Delhi / NCR": {
        "districts": ["New Delhi Central", "South Delhi", "Noida", "Gurugram", "Dwarka", "Karol Bagh", "Ghaziabad", "Faridabad"],
        "pincodes": ["110001", "110016", "201301", "122001", "110075", "110005", "201001", "121001"],
        "centers": [(28.6139, 77.2090), (28.5494, 77.2001), (28.5355, 77.3910), (28.4595, 77.0266), (28.5921, 77.0460), (28.6514, 77.1907), (28.6692, 77.4538), (28.4089, 77.3178)],
    },
    "Mumbai MMR": {
        "districts": ["South Mumbai", "Bandra BKC", "Andheri", "Navi Mumbai", "Thane", "Borivali", "Powai", "Dadar"],
        "pincodes": ["400001", "400051", "400053", "400703", "400601", "400091", "400076", "400028"],
        "centers": [(18.9322, 72.8347), (19.0596, 72.8295), (19.1136, 72.8697), (19.0330, 73.0297), (19.2183, 72.9781), (19.2307, 72.8567), (19.1176, 72.9060), (19.0178, 72.8478)],
    },
    "Bengaluru": {
        "districts": ["Central BLR", "Koramangala", "Whitefield", "Electronic City", "Indiranagar", "HSR Layout", "Malleshwaram", "Bellandur"],
        "pincodes": ["560001", "560034", "560066", "560100", "560038", "560102", "560003", "560103"],
        "centers": [(12.9716, 77.5946), (12.9352, 77.6245), (12.9698, 77.7499), (12.8399, 77.6770), (12.9784, 77.6408), (12.9121, 77.6446), (13.0031, 77.5643), (12.9260, 77.6762)],
    },
    "Hyderabad": {
        "districts": ["Hitec City", "Banjara Hills", "Secunderabad", "Old City Hyderabad", "Gachibowli", "Kukatpally", "Madhapur", "Jubilee Hills"],
        "pincodes": ["500081", "500034", "500003", "500002", "500032", "500072", "500081", "500033"],
        "centers": [(17.4435, 78.3772), (17.4156, 78.4350), (17.4399, 78.4983), (17.3616, 78.4747), (17.4401, 78.3489), (17.4849, 78.4138), (17.4483, 78.3915), (17.4319, 78.4073)],
    },
    "Chennai": {
        "districts": ["Anna Salai", "OMR Taramani", "T-Nagar", "Guindy", "Velachery", "Adyar", "Kilpauk", "Tambaram"],
        "pincodes": ["600002", "600113", "600017", "600032", "600042", "600020", "600010", "600045"],
        "centers": [(13.0827, 80.2707), (12.9863, 80.2432), (13.0418, 80.2341), (13.0067, 80.2025), (12.9815, 80.2180), (13.0012, 80.2565), (13.0784, 80.2413), (12.9249, 80.1000)],
    },
    "Kolkata": {
        "districts": ["Park Street", "Salt Lake Sector V", "New Town Kolkata", "Howrah", "Ballygunge", "Alipore", "Gariahat", "Dum Dum"],
        "pincodes": ["700016", "700091", "700156", "711101", "700019", "700027", "700029", "700028"],
        "centers": [(22.5510, 88.3533), (22.5804, 88.4378), (22.5958, 88.4795), (22.5958, 88.2636), (22.5280, 88.3656), (22.5320, 88.3270), (22.5167, 88.3670), (22.6420, 88.4312)],
    },
    "Pune": {
        "districts": ["Shivaji Nagar Pune", "Hinjewadi IT Park", "Magarpatta Hadapsar", "Kothrud", "Viman Nagar", "Wakad", "Baner", "Camp"],
        "pincodes": ["411005", "411057", "411028", "411038", "411014", "411057", "411045", "411001"],
        "centers": [(18.5314, 73.8446), (18.5913, 73.7389), (18.5134, 73.9317), (18.5074, 73.8077), (18.5679, 73.9143), (18.5987, 73.7680), (18.5590, 73.7868), (18.5158, 73.8786)],
    },
    "Ahmedabad": {
        "districts": ["Navrangpura", "SG Highway", "Maninagar", "Gandhinagar Center", "Vastrapur", "Satellite", "Prahlad Nagar"],
        "pincodes": ["380009", "380054", "380008", "382010", "380015", "380015", "380015"],
        "centers": [(23.0365, 72.5611), (23.0538, 72.5085), (22.9968, 72.6015), (23.2156, 72.6369), (23.0350, 72.5293), (23.0270, 72.5180), (23.0118, 72.5065)],
    },
    "Jaipur": {
        "districts": ["MI Road Jaipur", "Malviya Nagar Jaipur", "Vaishali Nagar", "Mansarovar", "C-Scheme", "Raja Park"],
        "pincodes": ["302001", "302017", "302021", "302020", "302001", "302004"],
        "centers": [(26.9124, 75.7873), (26.8532, 75.8055), (26.9157, 75.7412), (26.8640, 75.7650), (26.9080, 75.8020), (26.8970, 75.8280)],
    },
    "Lucknow": {
        "districts": ["Hazratganj", "Gomti Nagar Lucknow", "Alambagh", "Indira Nagar", "Mahanagar", "Charbagh"],
        "pincodes": ["226001", "226010", "226005", "226016", "226006", "226004"],
        "centers": [(26.8467, 80.9462), (26.8524, 80.9992), (26.8122, 80.9022), (26.8830, 80.9820), (26.8720, 80.9530), (26.8310, 80.9230)],
    },
    "Kochi": {
        "districts": ["Ernakulam Central", "Kakkanad InfoPark", "Fort Kochi", "Edappally", "Marine Drive"],
        "pincodes": ["682011", "682042", "682001", "682024", "682031"],
        "centers": [(9.9816, 76.2999), (10.0159, 76.3639), (9.9658, 76.2421), (10.0230, 76.3080), (9.9790, 76.2770)],
    },
    "Surat": {
        "districts": ["Ring Road Surat", "Adajan", "Vesu Surat", "Varachha", "Piplod"],
        "pincodes": ["395002", "395009", "395007", "395006", "395007"],
        "centers": [(21.1959, 72.8302), (21.1926, 72.7997), (21.1418, 72.7709), (21.2180, 72.8620), (21.1630, 72.7780)],
    },
    "Chandigarh / Tricity": {
        "districts": ["Sector 17 Chandigarh", "Mohali Phase 7", "Panchkula Sector 5", "IT Park Chandigarh"],
        "pincodes": ["160017", "160062", "134109", "160101"],
        "centers": [(30.7398, 76.7827), (30.7046, 76.7179), (30.6942, 76.8606), (30.7240, 76.8430)],
    },
    "Indore": {
        "districts": ["Vijay Nagar", "Palasia", "Rajwada", "AB Road"],
        "pincodes": ["452010", "452001", "452002", "452008"],
        "centers": [(22.7533, 75.8937), (22.7244, 75.8839), (22.7186, 75.8554), (22.7410, 75.8880)],
    },
    "Patna": {
        "districts": ["Boring Road", "Bailey Road", "Kankarbagh", "Fraser Road"],
        "pincodes": ["800001", "800014", "800020", "800001"],
        "centers": [(25.6178, 85.1167), (25.6090, 85.0880), (25.5940, 85.1580), (25.6120, 85.1390)],
    },
    "Bhopal": {
        "districts": ["MP Nagar", "Arera Colony", "New Market", "Kolar Road"],
        "pincodes": ["462011", "462016", "462003", "462042"],
        "centers": [(23.2332, 77.4343), (23.2130, 77.4280), (23.2420, 77.4010), (23.1760, 77.4210)],
    },
    "Bhubaneswar": {
        "districts": ["Saheed Nagar", "Patia Infocity", "Master Canteen", "Jayadev Vihar"],
        "pincodes": ["751007", "751024", "751001", "751013"],
        "centers": [(20.2882, 85.8453), (20.3540, 85.8190), (20.2670, 85.8390), (20.3010, 85.8230)],
    },
    "Coimbatore": {
        "districts": ["Gandhipuram", "RS Puram", "Peelamedu", "Race Course"],
        "pincodes": ["641012", "641002", "641004", "641018"],
        "centers": [(11.0183, 76.9634), (11.0090, 76.9480), (11.0280, 77.0020), (11.0010, 76.9740)],
    },
    "Visakhapatnam": {
        "districts": ["Dwaraka Nagar", "Beach Road", "MVP Colony", "Gajuwaka"],
        "pincodes": ["530016", "530002", "530017", "530026"],
        "centers": [(17.7290, 83.3080), (17.7120, 83.3230), (17.7420, 83.3410), (17.6910, 83.2180)],
    },
    "Guwahati": {
        "districts": ["GS Road", "Paltan Bazaar", "Dispur", "Fancy Bazaar"],
        "pincodes": ["781005", "781008", "781006", "781001"],
        "centers": [(26.1520, 91.7780), (26.1810, 91.7520), (26.1420, 91.7910), (26.1890, 91.7410)],
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
TERMINAL_BANKS = ["SBI", "HDFC", "ICICI", "PNB", "AXIS", "CANARA", "BOI", "KOTAK", "INDUSIND", "YES", "PAYTM", "FINO", "IPPB", "UNION", "BARODA"]

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
ROOT_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "output")
ACCOUNTS_CSV = os.path.join(DATA_DIR, "accounts.csv")
TERMINALS_CSV = os.path.join(DATA_DIR, "terminals.csv")
TRANSACTIONS_CSV = os.path.join(DATA_DIR, "transactions.csv")
GROUND_TRUTH_CSV = os.path.join(DATA_DIR, "ground_truth.csv")


