import csv
import random
import os

from config import NUM_TERMINALS, OUTPUT_DIR


TERMINAL_TYPES = [
    "ATM_KIOSK",
    "AEPS_MICRO_ATM",
    "POS"
]

LOCATIONS = [
    ("Mumbai", "400001", 19.0760, 72.8777),
    ("Mumbai", "400050", 19.0596, 72.8295),
    ("Thane", "400601", 19.2183, 72.9781),
    ("Navi Mumbai", "400703", 19.0330, 73.0297),
    ("Pune", "411001", 18.5204, 73.8567),
    ("Nagpur", "440001", 21.1458, 79.0882)
]


def generate_terminals():

    terminals = []

    for i in range(1, NUM_TERMINALS + 1):

        district, pincode, latitude, longitude = random.choice(
            LOCATIONS
        )

        # Small random variation keeps locations synthetic
        latitude += random.uniform(-0.03, 0.03)
        longitude += random.uniform(-0.03, 0.03)

        terminals.append({
            "terminal_id": f"ATM{i:03d}",
            "terminal_type": random.choice(TERMINAL_TYPES),
            "latitude": round(latitude, 6),
            "longitude": round(longitude, 6),
            "district": district,
            "pincode": pincode,
            "status": "active"
        })

    return terminals


def save_terminals(terminals):

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    filename = f"{OUTPUT_DIR}/terminals.csv"

    fields = [
        "terminal_id",
        "terminal_type",
        "latitude",
        "longitude",
        "district",
        "pincode",
        "status"
    ]

    with open(filename, "w", newline="", encoding="utf-8") as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fields
        )

        writer.writeheader()
        writer.writerows(terminals)


if __name__ == "__main__":

    terminals = generate_terminals()

    save_terminals(terminals)

    print(f"Generated {len(terminals)} terminals.")