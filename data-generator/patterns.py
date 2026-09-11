"""
patterns.py — 16 Diverse Synthetic Fraud Scenario Archetypes
SIH26184 — Predictive Cash Egress Interception — Workstream 1

Implements:
 1. Simple mule chain (Victim -> Mule -> Cashout)
 2. Multi-hop layering (Victim -> A -> B -> C -> D -> Cashout)
 3. Fan-in (Many -> One Aggregator -> Cashout)
 4. Fan-out (One -> Many Mules)
 5. Fan-in + Fan-out (Many -> Aggregator -> Many Mules -> Cashouts)
 6. Rapid forwarding (High-velocity hops under 90s)
 7. Shared device relationship (Cluster on same synthetic device)
 8. Shared KYC identity cluster (Ring on same synthetic identity)
 9. Geo-velocity (Physically impossible travel across distant cities)
10. Repeated ATM targeting (Multiple attempts at same physical terminal)
11. Multi-victim -> Common mule (Independent victims funneling to one node)
12. Distributed cashout (Stolen funds cash out across multiple terminals)
13. Long dormant account sudden activation (Dormant >200 days suddenly moves funds)
14. Small probing then large transfer (Probes then large fund drain)
15. Cross-city mule network (Interstate hop chain: Delhi -> Mumbai -> Pune -> ATM)
16. Multiple concurrent chains (Simultaneous overlapping fraud campaigns)
"""

import random
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import config
from normal_traffic import make_transaction_id, _iso, _pareto_amount


def _fraud_amount(rng: random.Random) -> float:
    """Pick a fraud transaction amount (normal fraud range or large fraud spike)."""
    if rng.random() < config.FRAUD_LARGE_AMOUNT_PROBABILITY:
        return _pareto_amount(config.FRAUD_LARGE_AMOUNT_MIN, config.FRAUD_LARGE_AMOUNT_MAX, 1.3, rng)
    return _pareto_amount(config.FRAUD_AMOUNT_MIN, config.FRAUD_AMOUNT_MAX, 1.5, rng)


def _new_txn(source: str, target: str, amount: float, ts: datetime, channel: str,
             device_fp: str, scenario_id: str, pattern_type: str,
             involved_ids: list[str], expected_terminal_id: str, rng: random.Random,
             campaign_id: str = "", root_tx_id: str = "", chain_id: str = "",
             hop_depth: int = 1) -> dict:
    """Build one transaction record with rich ground truth metadata."""
    t_id = make_transaction_id(rng)
    return {
        "transaction_id": t_id,
        "source_account_id": source,
        "target_account_id": target,
        "amount_inr": round(amount, 2),
        "timestamp_dt": ts,
        "timestamp": _iso(ts),
        "payment_channel": channel,
        "device_fingerprint": device_fp,
        "_scenario_id": scenario_id,
        "_campaign_id": campaign_id or f"CMP-{scenario_id}",
        "_root_transaction_id": root_tx_id or t_id,
        "_chain_id": chain_id or f"CHN-{scenario_id}",
        "_pattern_type": pattern_type,
        "_is_fraud": True,
        "_hop_depth": hop_depth,
        "_involved_account_ids": involved_ids,
        "_expected_cashout_terminal_id": expected_terminal_id,
    }


def _apply_shared_device(accounts: list[dict], shared_fp: str) -> None:
    """Assign shared device fingerprint across the group."""
    for acc in accounts:
        acc["primary_device_fingerprint"] = shared_fp


def _apply_shared_kyc_identity(accounts: list[dict], shared_kyc: str) -> None:
    """Assign shared synthetic KYC identity hash across the group."""
    for acc in accounts:
        acc["kyc_identity_id"] = shared_kyc


def _pick_cashout_terminal(cashout_account: dict, terminals: list[dict], rng: random.Random) -> dict:
    """Pick terminal in or near account's district, or fallback to pool."""
    same_district = [t for t in terminals if t["district"] == cashout_account.get("account_region")]
    pool = same_district if same_district else terminals
    return rng.choice(pool)


def _record_terminal_history(accounts: list[dict], terminal_id: str) -> None:
    """Record historical terminal affinity."""
    for acc in accounts:
        if terminal_id not in acc["historical_terminal_ids"]:
            acc["historical_terminal_ids"].append(terminal_id)


# ----------------------------------------------------------------------------
# 1. Simple Mule Chain (Victim -> Mule -> Cashout)
# ----------------------------------------------------------------------------
def inject_simple_mule(accounts: list[dict], terminals: list[dict], scenario_id: str,
                       sim_start: datetime, rng: random.Random) -> tuple[list[dict], dict]:
    chosen = rng.sample(accounts, 2)
    victim, mule = chosen[0], chosen[1]
    victim["account_tier"] = "victim"
    mule["account_tier"] = "mule_l1"

    involved = [victim["account_id"], mule["account_id"]]
    shared_fp = f"DEV-SHARED-{scenario_id}"
    mule["primary_device_fingerprint"] = shared_fp

    terminal = _pick_cashout_terminal(mule, terminals, rng)
    _record_terminal_history([mule], terminal["terminal_id"])

    t0 = sim_start + timedelta(seconds=rng.uniform(3600, 20 * 3600))
    amount = _fraud_amount(rng)
    channel = rng.choice(["UPI", "IMPS"])

    tx1 = _new_txn(victim["account_id"], mule["account_id"], amount, t0, channel,
                    victim["primary_device_fingerprint"], scenario_id, "simple_mule",
                    involved, terminal["terminal_id"], rng, hop_depth=1)

    meta = {
        "scenario_id": scenario_id,
        "pattern_type": "simple_mule",
        "involved_account_ids": involved,
        "expected_cashout_terminal_id": terminal["terminal_id"],
    }
    return [tx1], meta


# ----------------------------------------------------------------------------
# 2. Multi-Hop Layering (Victim -> Mule 1 -> Mule 2 -> ... -> Aggregator)
# ----------------------------------------------------------------------------
def inject_layering(accounts: list[dict], terminals: list[dict], scenario_id: str,
                    sim_start: datetime, rng: random.Random) -> tuple[list[dict], dict]:
    num_hops = rng.randint(config.LAYERING_MIN_HOPS, config.LAYERING_MAX_HOPS)
    chain = rng.sample(accounts, num_hops + 1)
    chain[0]["account_tier"] = "victim"
    for acc in chain[1:-1]:
        acc["account_tier"] = "mule_l1"
    chain[-1]["account_tier"] = "aggregator"

    involved = [a["account_id"] for a in chain]
    shared_fp = f"DEV-SHARED-{scenario_id}"
    _apply_shared_device(chain[1:], shared_fp)
    _apply_shared_kyc_identity(chain[1:], f"KYC-RING-{scenario_id}")

    final_account = chain[-1]
    terminal = _pick_cashout_terminal(final_account, terminals, rng)
    _record_terminal_history([final_account], terminal["terminal_id"])

    t0 = sim_start + timedelta(seconds=rng.uniform(1800, 18 * 3600))
    amount = _fraud_amount(rng)
    channel = rng.choice(["UPI", "IMPS"])

    txns = []
    current_time = t0
    root_tx_id = ""
    chain_id = f"CHN-{scenario_id}"

    for hop, (src, tgt) in enumerate(zip(chain[:-1], chain[1:])):
        decay = config.LAYERING_AMOUNT_DECAY ** hop
        hop_amount = round(amount * decay, 2)
        dev = src["primary_device_fingerprint"]
        t = _new_txn(src["account_id"], tgt["account_id"], hop_amount, current_time, channel,
                     dev, scenario_id, "layering", involved, terminal["terminal_id"], rng,
                     chain_id=chain_id, hop_depth=hop + 1)
        if hop == 0:
            root_tx_id = t["transaction_id"]
        t["_root_transaction_id"] = root_tx_id
        txns.append(t)
        hop_delay = rng.uniform(config.LAYERING_HOP_DELAY_MIN_SECONDS, config.LAYERING_HOP_DELAY_MAX_SECONDS)
        current_time += timedelta(seconds=hop_delay)

    meta = {
        "scenario_id": scenario_id,
        "pattern_type": "layering",
        "involved_account_ids": involved,
        "expected_cashout_terminal_id": terminal["terminal_id"],
    }
    return txns, meta


# ----------------------------------------------------------------------------
# 3. Fan-In (Multiple victims/mules -> Common Aggregator)
# ----------------------------------------------------------------------------
def inject_fan_in(accounts: list[dict], terminals: list[dict], scenario_id: str,
                  sim_start: datetime, rng: random.Random) -> tuple[list[dict], dict]:
    num_sources = rng.randint(config.FAN_IN_MIN_SOURCES, config.FAN_IN_MAX_SOURCES)
    chosen = rng.sample(accounts, num_sources + 1)
    aggregator, sources = chosen[0], chosen[1:]
    aggregator["account_tier"] = "aggregator"
    for acc in sources:
        acc["account_tier"] = "mule_l1"

    involved = [aggregator["account_id"]] + [s["account_id"] for s in sources]
    shared_fp = f"DEV-SHARED-{scenario_id}"
    shared_kyc = f"KYC-RING-{scenario_id}"
    _apply_shared_device(sources, shared_fp)
    _apply_shared_kyc_identity(sources, shared_kyc)

    terminal = _pick_cashout_terminal(aggregator, terminals, rng)
    _record_terminal_history([aggregator], terminal["terminal_id"])

    t0 = sim_start + timedelta(seconds=rng.uniform(3600, 20 * 3600))
    window_secs = config.FAN_IN_WINDOW_MINUTES * 60
    channel = rng.choice(["UPI", "IMPS", "AEPS"])

    txns = []
    chain_id = f"CHN-FANIN-{scenario_id}"
    for src in sources:
        offset = rng.uniform(0, window_secs)
        ts = t0 + timedelta(seconds=offset)
        amount = _fraud_amount(rng)
        t = _new_txn(src["account_id"], aggregator["account_id"], amount, ts, channel,
                     src["primary_device_fingerprint"], scenario_id, "fan_in", involved,
                     terminal["terminal_id"], rng, chain_id=chain_id, hop_depth=1)
        txns.append(t)

    meta = {
        "scenario_id": scenario_id,
        "pattern_type": "fan_in",
        "involved_account_ids": involved,
        "expected_cashout_terminal_id": terminal["terminal_id"],
    }
    return txns, meta


# ----------------------------------------------------------------------------
# 4. Fan-Out (Compromised Mule -> Multiple Target Mules)
# ----------------------------------------------------------------------------
def inject_fan_out(accounts: list[dict], terminals: list[dict], scenario_id: str,
                   sim_start: datetime, rng: random.Random) -> tuple[list[dict], dict]:
    num_targets = rng.randint(config.FAN_OUT_MIN_TARGETS, config.FAN_OUT_MAX_TARGETS)
    chosen = rng.sample(accounts, num_targets + 1)
    source, targets = chosen[0], chosen[1:]
    source["account_tier"] = "aggregator"
    for acc in targets:
        acc["account_tier"] = "mule_l1"

    involved = [source["account_id"]] + [t["account_id"] for t in targets]
    shared_fp = f"DEV-SHARED-{scenario_id}"
    _apply_shared_device(targets, shared_fp)
    _apply_shared_kyc_identity(targets, f"KYC-RING-{scenario_id}")

    final_target = targets[0]
    terminal = _pick_cashout_terminal(final_target, terminals, rng)
    _record_terminal_history([final_target], terminal["terminal_id"])

    t0 = sim_start + timedelta(seconds=rng.uniform(3600, 20 * 3600))
    window_secs = config.FAN_OUT_WINDOW_MINUTES * 60
    channel = rng.choice(["UPI", "IMPS"])

    txns = []
    chain_id = f"CHN-FANOUT-{scenario_id}"
    for tgt in targets:
        offset = rng.uniform(0, window_secs)
        ts = t0 + timedelta(seconds=offset)
        amount = _fraud_amount(rng)
        t = _new_txn(source["account_id"], tgt["account_id"], amount, ts, channel,
                     source["primary_device_fingerprint"], scenario_id, "fan_out", involved,
                     terminal["terminal_id"], rng, chain_id=chain_id, hop_depth=1)
        txns.append(t)

    meta = {
        "scenario_id": scenario_id,
        "pattern_type": "fan_out",
        "involved_account_ids": involved,
        "expected_cashout_terminal_id": terminal["terminal_id"],
    }
    return txns, meta


# ----------------------------------------------------------------------------
# 5. Fan-In + Fan-Out (Inbound convergence followed by parallel dispersion)
# ----------------------------------------------------------------------------
def inject_fan_in_fan_out(accounts: list[dict], terminals: list[dict], scenario_id: str,
                          sim_start: datetime, rng: random.Random) -> tuple[list[dict], dict]:
    chosen = rng.sample(accounts, 7)
    sources = chosen[:3]
    hub = chosen[3]
    targets = chosen[4:]
    for s in sources: s["account_tier"] = "victim"
    hub["account_tier"] = "aggregator"
    for t in targets: t["account_tier"] = "mule_l2"

    involved = [a["account_id"] for a in chosen]
    shared_fp = f"DEV-SHARED-{scenario_id}"
    _apply_shared_device(targets, shared_fp)

    terminal = _pick_cashout_terminal(targets[0], terminals, rng)
    _record_terminal_history(targets, terminal["terminal_id"])

    t0 = sim_start + timedelta(seconds=rng.uniform(1800, 18 * 3600))
    txns = []
    chain_id = f"CHN-FIFO-{scenario_id}"

    # Inbound fan-in
    total_in = 0.0
    for idx, s in enumerate(sources):
        ts = t0 + timedelta(seconds=idx * 45)
        amt = _fraud_amount(rng)
        total_in += amt
        txns.append(_new_txn(s["account_id"], hub["account_id"], amt, ts, "UPI",
                             s["primary_device_fingerprint"], scenario_id, "fan_in_fan_out",
                             involved, terminal["terminal_id"], rng, chain_id=chain_id, hop_depth=1))

    # Outbound fan-out (split total_in across targets)
    t_out = t0 + timedelta(minutes=4)
    split_amt = round((total_in * 0.92) / len(targets), 2)
    for idx, tgt in enumerate(targets):
        ts = t_out + timedelta(seconds=idx * 30)
        txns.append(_new_txn(hub["account_id"], tgt["account_id"], split_amt, ts, "IMPS",
                             hub["primary_device_fingerprint"], scenario_id, "fan_in_fan_out",
                             involved, terminal["terminal_id"], rng, chain_id=chain_id, hop_depth=2))

    meta = {
        "scenario_id": scenario_id,
        "pattern_type": "fan_in_fan_out",
        "involved_account_ids": involved,
        "expected_cashout_terminal_id": terminal["terminal_id"],
    }
    return txns, meta


# ----------------------------------------------------------------------------
# 6. Rapid Forwarding (High-velocity hops under 90 seconds)
# ----------------------------------------------------------------------------
def inject_rapid_forwarding(accounts: list[dict], terminals: list[dict], scenario_id: str,
                            sim_start: datetime, rng: random.Random) -> tuple[list[dict], dict]:
    chain = rng.sample(accounts, 4)
    chain[0]["account_tier"] = "victim"
    chain[1]["account_tier"] = "mule_l1"
    chain[2]["account_tier"] = "mule_l2"
    chain[3]["account_tier"] = "aggregator"

    involved = [a["account_id"] for a in chain]
    terminal = _pick_cashout_terminal(chain[-1], terminals, rng)
    _record_terminal_history([chain[-1]], terminal["terminal_id"])

    t0 = sim_start + timedelta(seconds=rng.uniform(3600, 20 * 3600))
    amount = _fraud_amount(rng)
    txns = []
    cur_time = t0
    chain_id = f"CHN-RAPID-{scenario_id}"

    for hop, (src, tgt) in enumerate(zip(chain[:-1], chain[1:])):
        hop_amt = round(amount * (0.95 ** hop), 2)
        txns.append(_new_txn(src["account_id"], tgt["account_id"], hop_amt, cur_time, "UPI",
                             src["primary_device_fingerprint"], scenario_id, "rapid_forwarding",
                             involved, terminal["terminal_id"], rng, chain_id=chain_id, hop_depth=hop + 1))
        # Rapid forwarding: 20 to 60 seconds hop delay
        cur_time += timedelta(seconds=rng.uniform(20, 60))

    meta = {
        "scenario_id": scenario_id,
        "pattern_type": "rapid_forwarding",
        "involved_account_ids": involved,
        "expected_cashout_terminal_id": terminal["terminal_id"],
    }
    return txns, meta


# ----------------------------------------------------------------------------
# 7. Shared Device Relationship
# ----------------------------------------------------------------------------
def inject_shared_device(accounts: list[dict], terminals: list[dict], scenario_id: str,
                         sim_start: datetime, rng: random.Random) -> tuple[list[dict], dict]:
    cluster = rng.sample(accounts, 4)
    for a in cluster: a["account_tier"] = "mule_l1"
    shared_fp = f"DEV-FINGERPRINT-RING-{scenario_id}"
    _apply_shared_device(cluster, shared_fp)

    involved = [a["account_id"] for a in cluster]
    terminal = _pick_cashout_terminal(cluster[0], terminals, rng)
    _record_terminal_history(cluster, terminal["terminal_id"])

    t0 = sim_start + timedelta(seconds=rng.uniform(1800, 18 * 3600))
    txns = []
    # All cluster accounts send funds to an outside target or among each other with same device
    for idx in range(len(cluster) - 1):
        ts = t0 + timedelta(minutes=idx * 10)
        txns.append(_new_txn(cluster[idx]["account_id"], cluster[idx + 1]["account_id"],
                             round(rng.uniform(12000, 48000), 2), ts, "UPI", shared_fp,
                             scenario_id, "shared_device", involved, terminal["terminal_id"], rng, hop_depth=idx + 1))

    meta = {
        "scenario_id": scenario_id,
        "pattern_type": "shared_device",
        "involved_account_ids": involved,
        "expected_cashout_terminal_id": terminal["terminal_id"],
    }
    return txns, meta


# ----------------------------------------------------------------------------
# 8. Shared KYC Identity Cluster
# ----------------------------------------------------------------------------
def inject_shared_kyc_cluster(accounts: list[dict], terminals: list[dict], scenario_id: str,
                              sim_start: datetime, rng: random.Random) -> tuple[list[dict], dict]:
    cluster = rng.sample(accounts, 4)
    for a in cluster: a["account_tier"] = "mule_l1"
    shared_kyc = f"KYC-RING-HASH-{scenario_id}"
    _apply_shared_kyc_identity(cluster, shared_kyc)

    involved = [a["account_id"] for a in cluster]
    terminal = _pick_cashout_terminal(cluster[0], terminals, rng)
    _record_terminal_history(cluster, terminal["terminal_id"])

    t0 = sim_start + timedelta(seconds=rng.uniform(1800, 18 * 3600))
    txns = []
    # Funnel into the last mule
    for idx, acc in enumerate(cluster[:-1]):
        ts = t0 + timedelta(minutes=idx * 8)
        txns.append(_new_txn(acc["account_id"], cluster[-1]["account_id"],
                             round(rng.uniform(15000, 50000), 2), ts, "IMPS",
                             acc["primary_device_fingerprint"], scenario_id, "shared_kyc_cluster",
                             involved, terminal["terminal_id"], rng, hop_depth=1))

    meta = {
        "scenario_id": scenario_id,
        "pattern_type": "shared_kyc_cluster",
        "involved_account_ids": involved,
        "expected_cashout_terminal_id": terminal["terminal_id"],
    }
    return txns, meta


# ----------------------------------------------------------------------------
# 9. Geo-Velocity Anomaly (Impossible travel speed across distant cities)
# ----------------------------------------------------------------------------
def inject_geo_velocity(accounts: list[dict], terminals: list[dict], scenario_id: str,
                        sim_start: datetime, rng: random.Random) -> tuple[list[dict], dict]:
    chosen = rng.sample(accounts, 3)
    acc1, acc2, acc3 = chosen[0], chosen[1], chosen[2]
    acc1["account_tier"] = "mule_l1"

    involved = [a["account_id"] for a in chosen]
    
    # Pick 2 terminals in widely separated cities (e.g. Mumbai vs Delhi / BLR)
    t1 = rng.choice(terminals)
    far_terminals = [t for t in terminals if t.get("district") != t1.get("district")]
    t2 = rng.choice(far_terminals) if far_terminals else terminals[0]

    _record_terminal_history([acc1], t1["terminal_id"])
    _record_terminal_history([acc1], t2["terminal_id"])

    t0 = sim_start + timedelta(seconds=rng.uniform(3600, 18 * 3600))
    txns = []

    # Transaction 1 in City A
    txns.append(_new_txn(acc1["account_id"], acc2["account_id"], round(rng.uniform(20000, 60000), 2),
                         t0, "AEPS", acc1["primary_device_fingerprint"], scenario_id, "geo_velocity",
                         involved, t1["terminal_id"], rng, hop_depth=1))

    # Transaction 2 in distant City B only 15 minutes later (impossible travel speed > 800 km/h)
    t1_hop = t0 + timedelta(minutes=15)
    txns.append(_new_txn(acc1["account_id"], acc3["account_id"], round(rng.uniform(25000, 70000), 2),
                         t1_hop, "AEPS", acc1["primary_device_fingerprint"], scenario_id, "geo_velocity",
                         involved, t2["terminal_id"], rng, hop_depth=2))

    meta = {
        "scenario_id": scenario_id,
        "pattern_type": "geo_velocity",
        "involved_account_ids": involved,
        "expected_cashout_terminal_id": t2["terminal_id"],
    }
    return txns, meta


# ----------------------------------------------------------------------------
# 10. Repeated ATM Targeting (Repeated attempts at same terminal)
# ----------------------------------------------------------------------------
def inject_repeated_atm_targeting(accounts: list[dict], terminals: list[dict], scenario_id: str,
                                  sim_start: datetime, rng: random.Random) -> tuple[list[dict], dict]:
    mule = rng.choice(accounts)
    target_partner = rng.choice([a for a in accounts if a["account_id"] != mule["account_id"]])
    mule["account_tier"] = "aggregator"

    involved = [mule["account_id"], target_partner["account_id"]]
    target_terminal = _pick_cashout_terminal(mule, terminals, rng)
    _record_terminal_history([mule], target_terminal["terminal_id"])

    t0 = sim_start + timedelta(seconds=rng.uniform(3600, 18 * 3600))
    txns = []

    # 4 consecutive transactions targeting the same terminal within short intervals
    for i in range(4):
        ts = t0 + timedelta(minutes=i * 6)
        txns.append(_new_txn(mule["account_id"], target_partner["account_id"],
                             round(rng.uniform(9000, 10000), 2), ts, "AEPS",
                             mule["primary_device_fingerprint"], scenario_id, "repeated_atm_targeting",
                             involved, target_terminal["terminal_id"], rng, hop_depth=i + 1))

    meta = {
        "scenario_id": scenario_id,
        "pattern_type": "repeated_atm_targeting",
        "involved_account_ids": involved,
        "expected_cashout_terminal_id": target_terminal["terminal_id"],
    }
    return txns, meta


# ----------------------------------------------------------------------------
# 11. Multi-Victim -> Common Mule (Multiple independent victims funneling)
# ----------------------------------------------------------------------------
def inject_multi_victim_common_mule(accounts: list[dict], terminals: list[dict], scenario_id: str,
                                    sim_start: datetime, rng: random.Random) -> tuple[list[dict], dict]:
    chosen = rng.sample(accounts, 4)
    victims = chosen[:3]
    common_mule = chosen[3]
    for v in victims: v["account_tier"] = "victim"
    common_mule["account_tier"] = "aggregator"

    involved = [a["account_id"] for a in chosen]
    terminal = _pick_cashout_terminal(common_mule, terminals, rng)
    _record_terminal_history([common_mule], terminal["terminal_id"])

    t0 = sim_start + timedelta(seconds=rng.uniform(1800, 18 * 3600))
    txns = []
    for idx, v in enumerate(victims):
        ts = t0 + timedelta(minutes=idx * 12)
        amt = round(rng.uniform(30000, 95000), 2)
        txns.append(_new_txn(v["account_id"], common_mule["account_id"], amt, ts, "UPI",
                             v["primary_device_fingerprint"], scenario_id, "multi_victim_common_mule",
                             involved, terminal["terminal_id"], rng, hop_depth=1))

    meta = {
        "scenario_id": scenario_id,
        "pattern_type": "multi_victim_common_mule",
        "involved_account_ids": involved,
        "expected_cashout_terminal_id": terminal["terminal_id"],
    }
    return txns, meta


# ----------------------------------------------------------------------------
# 12. Distributed Cashout (Funds split to multiple terminals)
# ----------------------------------------------------------------------------
def inject_distributed_cashout(accounts: list[dict], terminals: list[dict], scenario_id: str,
                               sim_start: datetime, rng: random.Random) -> tuple[list[dict], dict]:
    chosen = rng.sample(accounts, 4)
    origin, mules = chosen[0], chosen[1:]
    origin["account_tier"] = "aggregator"
    for m in mules: m["account_tier"] = "mule_l1"

    involved = [a["account_id"] for a in chosen]
    selected_terminals = rng.sample(terminals, min(3, len(terminals)))
    for idx, m in enumerate(mules):
        t_id = selected_terminals[idx % len(selected_terminals)]["terminal_id"]
        _record_terminal_history([m], t_id)

    t0 = sim_start + timedelta(seconds=rng.uniform(3600, 18 * 3600))
    txns = []
    for idx, m in enumerate(mules):
        ts = t0 + timedelta(minutes=idx * 5)
        t_id = selected_terminals[idx % len(selected_terminals)]["terminal_id"]
        txns.append(_new_txn(origin["account_id"], m["account_id"], round(rng.uniform(20000, 40000), 2),
                             ts, "AEPS", origin["primary_device_fingerprint"], scenario_id,
                             "distributed_cashout", involved, t_id, rng, hop_depth=1))

    meta = {
        "scenario_id": scenario_id,
        "pattern_type": "distributed_cashout",
        "involved_account_ids": involved,
        "expected_cashout_terminal_id": selected_terminals[0]["terminal_id"],
    }
    return txns, meta


# ----------------------------------------------------------------------------
# 13. Long Dormant Account Suddenly Activated
# ----------------------------------------------------------------------------
def inject_dormant_activation(accounts: list[dict], terminals: list[dict], scenario_id: str,
                              sim_start: datetime, rng: random.Random) -> tuple[list[dict], dict]:
    chosen = rng.sample(accounts, 3)
    dormant_acc, feeder, cashout_acc = chosen[0], chosen[1], chosen[2]
    dormant_acc["account_tier"] = "mule_l1"
    dormant_acc["account_status"] = "dormant"
    dormant_acc["account_age_days"] = rng.randint(250, 1200)

    involved = [a["account_id"] for a in chosen]
    terminal = _pick_cashout_terminal(cashout_acc, terminals, rng)
    _record_terminal_history([cashout_acc], terminal["terminal_id"])

    t0 = sim_start + timedelta(seconds=rng.uniform(3600, 18 * 3600))
    amount = round(rng.uniform(80000, 220000), 2)
    txns = []

    # Large sudden influx into dormant account
    txns.append(_new_txn(feeder["account_id"], dormant_acc["account_id"], amount, t0, "RTGS",
                         feeder["primary_device_fingerprint"], scenario_id, "dormant_activation",
                         involved, terminal["terminal_id"], rng, hop_depth=1))

    # Immediate rapid forward out of dormant account
    t_fwd = t0 + timedelta(minutes=2)
    txns.append(_new_txn(dormant_acc["account_id"], cashout_acc["account_id"], round(amount * 0.96, 2),
                         t_fwd, "IMPS", dormant_acc["primary_device_fingerprint"], scenario_id,
                         "dormant_activation", involved, terminal["terminal_id"], rng, hop_depth=2))

    meta = {
        "scenario_id": scenario_id,
        "pattern_type": "dormant_activation",
        "involved_account_ids": involved,
        "expected_cashout_terminal_id": terminal["terminal_id"],
    }
    return txns, meta


# ----------------------------------------------------------------------------
# 14. Small-Value Probing Followed by Large Transfer
# ----------------------------------------------------------------------------
def inject_probing_then_large(accounts: list[dict], terminals: list[dict], scenario_id: str,
                              sim_start: datetime, rng: random.Random) -> tuple[list[dict], dict]:
    chosen = rng.sample(accounts, 2)
    source, target = chosen[0], chosen[1]
    source["account_tier"] = "victim"
    target["account_tier"] = "aggregator"

    involved = [source["account_id"], target["account_id"]]
    terminal = _pick_cashout_terminal(target, terminals, rng)
    _record_terminal_history([target], terminal["terminal_id"])

    t0 = sim_start + timedelta(seconds=rng.uniform(3600, 18 * 3600))
    txns = []

    # 3 small test probes (e.g. ₹10, ₹50, ₹100)
    for idx, probe_amt in enumerate([10.0, 50.0, 100.0]):
        ts = t0 + timedelta(minutes=idx * 3)
        txns.append(_new_txn(source["account_id"], target["account_id"], probe_amt, ts, "UPI",
                             source["primary_device_fingerprint"], scenario_id, "probing_then_large",
                             involved, terminal["terminal_id"], rng, hop_depth=1))

    # Followed immediately by huge transfer
    t_large = t0 + timedelta(minutes=12)
    large_amt = round(rng.uniform(75000, 185000), 2)
    txns.append(_new_txn(source["account_id"], target["account_id"], large_amt, t_large, "IMPS",
                         source["primary_device_fingerprint"], scenario_id, "probing_then_large",
                         involved, terminal["terminal_id"], rng, hop_depth=2))

    meta = {
        "scenario_id": scenario_id,
        "pattern_type": "probing_then_large",
        "involved_account_ids": involved,
        "expected_cashout_terminal_id": terminal["terminal_id"],
    }
    return txns, meta


# ----------------------------------------------------------------------------
# 15. Cross-City Mule Network (Interstate hop chain)
# ----------------------------------------------------------------------------
def inject_cross_city_mule_network(accounts: list[dict], terminals: list[dict], scenario_id: str,
                                   sim_start: datetime, rng: random.Random) -> tuple[list[dict], dict]:
    # Select accounts from distinct regions if possible
    regions = list(set(a["account_region"] for a in accounts))
    if len(regions) >= 3:
        reg_samples = rng.sample(regions, 3)
        acc1 = next(a for a in accounts if a["account_region"] == reg_samples[0])
        acc2 = next(a for a in accounts if a["account_region"] == reg_samples[1])
        acc3 = next(a for a in accounts if a["account_region"] == reg_samples[2])
        chain = [acc1, acc2, acc3]
    else:
        chain = rng.sample(accounts, 3)

    chain[0]["account_tier"] = "victim"
    chain[1]["account_tier"] = "mule_l1"
    chain[2]["account_tier"] = "aggregator"

    involved = [a["account_id"] for a in chain]
    terminal = _pick_cashout_terminal(chain[-1], terminals, rng)
    _record_terminal_history([chain[-1]], terminal["terminal_id"])

    t0 = sim_start + timedelta(seconds=rng.uniform(3600, 18 * 3600))
    amount = _fraud_amount(rng)
    txns = []

    # Hop 1: City A -> City B
    txns.append(_new_txn(chain[0]["account_id"], chain[1]["account_id"], amount, t0, "UPI",
                         chain[0]["primary_device_fingerprint"], scenario_id, "cross_city_mule_network",
                         involved, terminal["terminal_id"], rng, hop_depth=1))

    # Hop 2: City B -> City C (2 minutes later)
    t_hop2 = t0 + timedelta(minutes=2)
    txns.append(_new_txn(chain[1]["account_id"], chain[2]["account_id"], round(amount * 0.94, 2),
                         t_hop2, "IMPS", chain[1]["primary_device_fingerprint"], scenario_id,
                         "cross_city_mule_network", involved, terminal["terminal_id"], rng, hop_depth=2))

    meta = {
        "scenario_id": scenario_id,
        "pattern_type": "cross_city_mule_network",
        "involved_account_ids": involved,
        "expected_cashout_terminal_id": terminal["terminal_id"],
    }
    return txns, meta


# ----------------------------------------------------------------------------
# 16. Multiple Concurrent Chains (Simultaneous independent fraud campaigns)
# ----------------------------------------------------------------------------
def inject_concurrent_campaigns(accounts: list[dict], terminals: list[dict], scenario_id: str,
                                sim_start: datetime, rng: random.Random) -> tuple[list[dict], dict]:
    # Launch 2 parallel 3-hop chains in the exact same hour window
    chosen = rng.sample(accounts, 6)
    chain1 = chosen[:3]
    chain2 = chosen[3:]

    for c in (chain1, chain2):
        c[0]["account_tier"] = "victim"
        c[1]["account_tier"] = "mule_l1"
        c[2]["account_tier"] = "aggregator"

    involved = [a["account_id"] for a in chosen]
    terminal = _pick_cashout_terminal(chain1[-1], terminals, rng)
    _record_terminal_history([chain1[-1], chain2[-1]], terminal["terminal_id"])

    t0 = sim_start + timedelta(seconds=rng.uniform(3600, 18 * 3600))
    txns = []

    for chain_idx, chain in enumerate((chain1, chain2)):
        c_id = f"CHN-CONC-{scenario_id}-{chain_idx+1}"
        amt = _fraud_amount(rng)
        t_cur = t0 + timedelta(seconds=rng.uniform(0, 120))
        for hop, (src, tgt) in enumerate(zip(chain[:-1], chain[1:])):
            txns.append(_new_txn(src["account_id"], tgt["account_id"], round(amt * (0.92 ** hop), 2),
                                 t_cur, "UPI", src["primary_device_fingerprint"], scenario_id,
                                 "concurrent_campaigns", involved, terminal["terminal_id"], rng,
                                 chain_id=c_id, hop_depth=hop + 1))
            t_cur += timedelta(seconds=rng.uniform(30, 90))

    meta = {
        "scenario_id": scenario_id,
        "pattern_type": "concurrent_campaigns",
        "involved_account_ids": involved,
        "expected_cashout_terminal_id": terminal["terminal_id"],
    }
    return txns, meta


# Legacy compatibility: triadic cycle
def inject_triadic(accounts: list[dict], terminals: list[dict], scenario_id: str,
                   sim_start: datetime, rng: random.Random) -> tuple[list[dict], dict]:
    chain = rng.sample(accounts, 3)
    for acc in chain: acc["account_tier"] = "mule_l1"
    involved = [a["account_id"] for a in chain]
    terminal = _pick_cashout_terminal(chain[0], terminals, rng)
    _record_terminal_history(chain, terminal["terminal_id"])

    t0 = sim_start + timedelta(seconds=rng.uniform(3600, 20 * 3600))
    amount = _fraud_amount(rng)
    txns = []
    t_cur = t0
    tri_pairs = [(chain[0], chain[1]), (chain[1], chain[2]), (chain[2], chain[0])]
    for hop, (src, tgt) in enumerate(tri_pairs):
        txns.append(_new_txn(src["account_id"], tgt["account_id"], amount, t_cur, "UPI",
                             src["primary_device_fingerprint"], scenario_id, "triadic",
                             involved, terminal["terminal_id"], rng, hop_depth=hop + 1))
        t_cur += timedelta(seconds=rng.uniform(30, 90))

    meta = {
        "scenario_id": scenario_id,
        "pattern_type": "triadic",
        "involved_account_ids": involved,
        "expected_cashout_terminal_id": terminal["terminal_id"],
    }
    return txns, meta


# ----------------------------------------------------------------------------
# Master Injection Dispatcher
# ----------------------------------------------------------------------------
def inject_all_scenarios(accounts: list[dict], terminals: list[dict], sim_start: datetime,
                         rng: random.Random) -> tuple[list[dict], list[dict]]:
    """Inject all 16 configured fraud scenario archetypes across accounts and terminals."""
    fraud_transactions = []
    scenarios_meta = []
    idx = 1

    scenario_matrix = [
        ("simple_mule", inject_simple_mule, getattr(config, "NUM_SIMPLE_MULE_SCENARIOS", 4)),
        ("layering", inject_layering, getattr(config, "NUM_LAYERING_SCENARIOS", 5)),
        ("fan_in", inject_fan_in, getattr(config, "NUM_FAN_IN_SCENARIOS", 4)),
        ("fan_out", inject_fan_out, getattr(config, "NUM_FAN_OUT_SCENARIOS", 4)),
        ("fan_in_fan_out", inject_fan_in_fan_out, getattr(config, "NUM_FAN_IN_FAN_OUT_SCENARIOS", 3)),
        ("rapid_forwarding", inject_rapid_forwarding, getattr(config, "NUM_RAPID_FORWARDING_SCENARIOS", 4)),
        ("shared_device", inject_shared_device, getattr(config, "NUM_SHARED_DEVICE_SCENARIOS", 3)),
        ("shared_kyc_cluster", inject_shared_kyc_cluster, getattr(config, "NUM_SHARED_KYC_SCENARIOS", 3)),
        ("geo_velocity", inject_geo_velocity, getattr(config, "NUM_GEO_VELOCITY_SCENARIOS", 3)),
        ("repeated_atm_targeting", inject_repeated_atm_targeting, getattr(config, "NUM_REPEATED_ATM_SCENARIOS", 3)),
        ("multi_victim_common_mule", inject_multi_victim_common_mule, getattr(config, "NUM_MULTI_VICTIM_SCENARIOS", 3)),
        ("distributed_cashout", inject_distributed_cashout, getattr(config, "NUM_DISTRIBUTED_CASHOUT_SCENARIOS", 3)),
        ("dormant_activation", inject_dormant_activation, getattr(config, "NUM_DORMANT_ACTIVATION_SCENARIOS", 3)),
        ("probing_then_large", inject_probing_then_large, getattr(config, "NUM_PROBING_THEN_LARGE_SCENARIOS", 3)),
        ("cross_city_mule_network", inject_cross_city_mule_network, getattr(config, "NUM_CROSS_CITY_MULE_SCENARIOS", 4)),
        ("concurrent_campaigns", inject_concurrent_campaigns, getattr(config, "NUM_CONCURRENT_CAMPAIGN_SCENARIOS", 3)),
        ("triadic", inject_triadic, getattr(config, "NUM_TRIADIC_SCENARIOS", 2)),
    ]

    for name, func, count in scenario_matrix:
        for _ in range(count):
            sid = f"SCN-{name.upper()}-{idx:03d}"
            txs, meta = func(accounts, terminals, sid, sim_start, rng)
            fraud_transactions.extend(txs)
            scenarios_meta.append(meta)
            idx += 1

    return fraud_transactions, scenarios_meta
