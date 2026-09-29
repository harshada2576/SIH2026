import csv

def get_transaction_ids(filename):
    ids = set()
    with open("data/output/" + filename, newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            ids.add(row["transaction_id"])
    return ids


print("Streaming and verifying datasets in data/output/...")
transaction_ids = get_transaction_ids("transactions.csv")

missing = []
ground_truth_count = 0
with open("data/output/ground_truth.csv", newline="", encoding="utf-8") as file:
    reader = csv.DictReader(file)
    for row in reader:
        ground_truth_count += 1
        if row["transaction_id"] not in transaction_ids:
            missing.append(row["transaction_id"])

print("Total transactions:", len(transaction_ids))
print("Ground-truth records:", ground_truth_count)
print("Missing ground-truth transactions:", len(missing))

if missing:
    print("Missing IDs:")
    for transaction_id in missing[:10]:
        print(transaction_id)
else:
    print("All ground-truth transactions exist in transactions.csv ✅")