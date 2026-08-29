import csv

def read_csv(filename):
    with open(
        "data/output/" + filename,
        newline="",
        encoding="utf-8"
    ) as file:
        return list(csv.DictReader(file))


transactions = read_csv("transactions.csv")
ground_truth = read_csv("ground_truth.csv")

transaction_ids = {
    row["transaction_id"]
    for row in transactions
}

missing = []

for row in ground_truth:
    if row["transaction_id"] not in transaction_ids:
        missing.append(row["transaction_id"])


print("Total transactions:", len(transactions))
print("Ground-truth records:", len(ground_truth))
print("Missing ground-truth transactions:", len(missing))

if missing:
    print("Missing IDs:")
    for transaction_id in missing:
        print(transaction_id)
else:
    print("All ground-truth transactions exist in transactions.csv ✅")