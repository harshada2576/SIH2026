"""scripts/demo_phase2.py — the single script to run for the Sept 5 demo.

Exercises every Phase 2 addition end-to-end, deliberately WITHOUT requiring
Kafka/Docker to be running, so it can't fail on stage for infra reasons:

  1. Loads terminals (including the new Mumbai/Hyderabad demo terminals).
  2. Builds a mule identity-ring: 12 accounts sharing one kyc_identity_id
     (the mentor's "12-20 accounts on one identity" scenario).
  3. Feeds a normal transaction chain into that ring so the existing 8 rules
     + the new identity_cluster + ml_anomaly rules all have something to see.
  4. Records a geo-velocity "impossible travel" scenario: the same account
     cashes out in Mumbai, then 40 minutes later in Hyderabad.
  5. Scores every account, and for every one that crosses the alert
     threshold: prints the investigator alert, runs the tiered
     auto-intervention (calls the mock Bank + NCRP/I4C APIs if they're
     running), and writes a signed entry to the audit ledger.

Run:
  # optional, in two other terminals, for the automated-action part to have
  # something to call (the script degrades gracefully if these aren't up):
  python -m mock_services.bank_api.server
  python -m mock_services.ncrp_i4c_api.server

  # then:
  python -m scripts.demo_phase2
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from detection import alert_dispatcher, scorer
from pipeline.graph_store import GraphStore
from shared.schemas import AccountNodeMetadata, TransactionEvent


def build_mule_identity_ring(graph: GraphStore, base: datetime, n: int = 12) -> list[str]:
    """12 accounts opened under one stolen/purchased KYC identity — mentor's
    '12-20 mule accounts on unaware people's names' scenario. Chained deep
    enough (victim -> ... -> ring -> aggregator -> cash-out) to also light up
    velocity/layering/fan-out/amount-movement/terminal-affinity, so the demo
    shows a realistic CRITICAL-band, multi-signal alert rather than a single
    isolated rule."""
    kyc_id = "KYC-STOLEN-AADHAAR-771290"
    account_ids = [f"ACC-MULE{i:02d}" for i in range(1, n + 1)]
    shared_terminal = "ATM-HDFC-Ce-001"
    for aid in account_ids:
        graph.add_account_metadata(AccountNodeMetadata(
            account_id=aid, account_tier="mule_l1", account_age_days=3,
            kyc_identity_id=kyc_id, district_pincode="110001",
            historical_terminal_ids=[shared_terminal],
        ))

    victim0, victim1, pre_mule = "ACC-VICTIM01", "ACC-VICTIM01B", "ACC-PREMULE01"
    for vid, tier, age in [(victim0, "victim", 900), (victim1, "victim", 600), (pre_mule, "mule_l1", 5)]:
        graph.add_account_metadata(AccountNodeMetadata(account_id=vid, account_tier=tier, account_age_days=age))

    aggregator = account_ids[0]
    t = base - timedelta(minutes=6)

    # 5-hop chain -> aggregator sits at layering depth 5 (victim0->victim1->pre_mule->ring->aggregator)
    graph.add_transaction(TransactionEvent(
        transaction_id="TXN-RING-V0", source_account_id=victim0, target_account_id=victim1,
        amount_inr=200000, timestamp=t, payment_channel="IMPS", device_fingerprint="DEV-VICTIM-PHONE"))
    t += timedelta(seconds=30)
    graph.add_transaction(TransactionEvent(
        transaction_id="TXN-RING-V1", source_account_id=victim1, target_account_id=pre_mule,
        amount_inr=195000, timestamp=t, payment_channel="IMPS", device_fingerprint="DEV-VICTIM-PHONE"))
    t += timedelta(seconds=30)
    for i, target in enumerate(account_ids[1:9]):  # pre_mule fans out to 8 ring accounts
        graph.add_transaction(TransactionEvent(
            transaction_id=f"TXN-RING-FANOUT-{i:03d}", source_account_id=pre_mule, target_account_id=target,
            amount_inr=22000 + i * 400, timestamp=t + timedelta(seconds=i * 5),
            payment_channel="UPI", device_fingerprint="DEV-RING-SHARED"))
    t += timedelta(minutes=1)
    for i, source in enumerate(account_ids[1:9]):  # those 8 fan INTO the aggregator
        graph.add_transaction(TransactionEvent(
            transaction_id=f"TXN-RING-FANIN-{i:03d}", source_account_id=source, target_account_id=aggregator,
            amount_inr=18000 + i * 500, timestamp=t + timedelta(seconds=i * 20),
            payment_channel="UPI", device_fingerprint="DEV-RING-SHARED"))
    t += timedelta(minutes=1)
    # aggregator rapidly forwards to 4 cash-out accounts (fan-out + velocity + amount-movement)
    for i, target in enumerate([f"ACC-CASHOUT{i:02d}" for i in range(4)]):
        graph.add_account_metadata(AccountNodeMetadata(
            account_id=target, account_tier="mule_l2", account_age_days=4,
            historical_terminal_ids=[shared_terminal]))
        graph.add_transaction(TransactionEvent(
            transaction_id=f"TXN-RING-CASHOUT-{i:03d}", source_account_id=aggregator, target_account_id=target,
            amount_inr=35000, timestamp=t + timedelta(seconds=i * 15),
            payment_channel="AEPS", device_fingerprint="DEV-RING-SHARED"))

    return account_ids + [victim0, victim1, pre_mule]


def build_critical_saturation_case(graph: GraphStore, base: datetime) -> str:
    """A blatant, multi-signal case tuned to land in CRITICAL band with HIGH
    confidence, so the demo shows the top tier of auto_intervention
    (AUTO_FREEZE) as well as the HIGH-band SOFT_NOTIFY case above — the
    tiered response is the point, not "always freeze"."""
    aggregator = "ACC-CRITICAL01"
    graph.add_account_metadata(AccountNodeMetadata(
        account_id=aggregator, account_tier="aggregator", account_age_days=2,
        historical_terminal_ids=["ATM-HDFC-Ce-001", "AEPS-BCR-002", "POS-PNB-003"],
    ))
    t = base - timedelta(minutes=6)
    # 5-hop upstream chain feeding into one of the senders -> layering depth 5
    chain = ["ACC-CRITVICTIM", "ACC-CRITHOP1", "ACC-CRITHOP2", "ACC-CRITHOP3"]
    for cid in chain:
        graph.add_account_metadata(AccountNodeMetadata(account_id=cid, account_tier="victim", account_age_days=800))
    for i in range(len(chain) - 1):
        graph.add_transaction(TransactionEvent(
            transaction_id=f"TXN-CRIT-CHAIN-{i:03d}", source_account_id=chain[i], target_account_id=chain[i + 1],
            amount_inr=250000, timestamp=t + timedelta(seconds=i * 15),
            payment_channel="IMPS", device_fingerprint="DEV-CRIT-VICTIM"))
    t += timedelta(seconds=60)

    senders = [f"ACC-CRITFEED{i:02d}" for i in range(9)]
    for i, s in enumerate(senders):
        graph.add_account_metadata(AccountNodeMetadata(account_id=s, account_tier="mule_l1", account_age_days=4))
    # last hop of the chain feeds into senders[0], so aggregator inherits depth 5
    graph.add_transaction(TransactionEvent(
        transaction_id="TXN-CRIT-CHAIN-LAST", source_account_id=chain[-1], target_account_id=senders[0],
        amount_inr=240000, timestamp=t - timedelta(seconds=20),
        payment_channel="IMPS", device_fingerprint="DEV-CRIT-VICTIM"))
    for i, s in enumerate(senders):
        graph.add_transaction(TransactionEvent(
            transaction_id=f"TXN-CRIT-IN-{i:03d}", source_account_id=s, target_account_id=aggregator,
            amount_inr=30000 + i * 1000, timestamp=t + timedelta(seconds=i * 10),
            payment_channel="UPI", device_fingerprint="DEV-CRIT-SHARED"))
    t += timedelta(seconds=90)  # rapid pass-through: <2 min -> velocity severity 1.0
    for i, target in enumerate([f"ACC-CRITOUT{i:02d}" for i in range(7)]):
        graph.add_account_metadata(AccountNodeMetadata(account_id=target, account_tier="mule_l2", account_age_days=4))
        graph.add_transaction(TransactionEvent(
            transaction_id=f"TXN-CRIT-OUT-{i:03d}", source_account_id=aggregator, target_account_id=target,
            amount_inr=45000, timestamp=t + timedelta(seconds=i * 5),
            payment_channel="AEPS", device_fingerprint="DEV-CRIT-SHARED"))
    return aggregator


def build_geo_velocity_scenario(graph: GraphStore, base: datetime) -> str:
    """Same account cashes out in Mumbai, then 40 minutes later in Hyderabad."""
    account_id = "ACC-GEOFLAG01"
    graph.add_account_metadata(AccountNodeMetadata(account_id=account_id, account_tier="mule_l2", account_age_days=12))
    # A transaction so the account has *some* activity for the other rules too.
    graph.add_transaction(TransactionEvent(
        transaction_id="TXN-GEO-IN", source_account_id="ACC-VICTIM02", target_account_id=account_id,
        amount_inr=42000, timestamp=base - timedelta(minutes=50),
        payment_channel="AEPS", device_fingerprint="DEV-GEO-1",
    ))
    graph.add_account_metadata(AccountNodeMetadata(account_id="ACC-VICTIM02", account_tier="victim", account_age_days=700))

    graph.record_terminal_usage(account_id, "AEPS-MUM-902", base - timedelta(minutes=45))
    graph.record_terminal_usage(account_id, "ATM-ICICI-HYD-903", base - timedelta(minutes=5))
    return account_id


def main() -> None:
    base = datetime.now(timezone.utc)
    graph = GraphStore()
    graph.load_terminals([t.to_dict() for t in scorer.load_terminals()])

    print("Building mule identity-ring scenario (12 accounts, 1 shared KYC identity)...")
    ring_accounts = build_mule_identity_ring(graph, base)

    print("Building geo-velocity scenario (Mumbai -> Hyderabad in 40 minutes)...")
    geo_account = build_geo_velocity_scenario(graph, base)

    print("Building a saturated CRITICAL-band case (to show the AUTO_FREEZE tier)...")
    critical_account = build_critical_saturation_case(graph, base)

    candidates = [ring_accounts[0], geo_account, critical_account]
    print(f"\nScoring {len(candidates)} candidate account(s)...\n")

    any_alert = False
    for account_id in candidates:
        ev = scorer.evaluate_account(graph, account_id, as_of=base)
        print(f"--- {account_id}: score={ev.score}/100 band={ev.band} ---")
        for r in ev.rules:
            if r.severity > 0:
                print(f"    [{r.name}] severity={r.severity:.2f} pts={r.points}/{r.weight} — {r.measured}")
        alert = scorer.analyze(graph, account_id, as_of=base)
        if alert:
            any_alert = True
            alert_dispatcher.dispatch(alert, band=ev.band)
        print()

    if not any_alert:
        print("No account crossed the alert threshold — check WEIGHTS/ALERT_THRESHOLD in detection/scorer.py")

    print("\nTo see the signed audit trail: python -m audit.blockchain_lite verify")
    print("To see mock bank state:        curl http://localhost:8001/accounts")
    print("To see mock NCRP/I4C state:    curl http://localhost:8002/alerts")


if __name__ == "__main__":
    main()
