"""
patterns.py — Fraud scenario injection: fan_in, fan_out, layering, triadic
SIH26184 — Predictive Cash Egress Interception — Workstream 1

CHANGELOG (this revision):
  - Each scenario now returns a scenario-metadata record (scenario_id,
    pattern_type, involved_account_ids, expected_cashout_terminal_id) instead
    of just a bag of transactions with a loose scenario_id string. This is
    what ground_truth.csv is built from in generate.py.
  - Shared device fingerprints are now applied by OVERWRITING the involved
    accounts' primary_device_fingerprint, so every transaction they make
    (not just the ones in this scenario) shows the shared device — a much
    stronger, more realistic signal for the "shared device across unrelated
    accounts" detection rule than a one-off per-transaction value.
  - Each scenario picks an expected cash-out terminal (favoring a terminal in
    the same synthetic district as the account that ends up holding the
    money), and records it on the involved accounts' historical_terminal_ids.
  - Fraud amounts occasionally spike to "unusually large" per config's
    FRAUD_LARGE_AMOUNT_PROBABILITY (update request §9).
  - All random draws use the passed-in seeded `rng` — no bare `random.x()`
    calls anywhere (fixes a reproducibility bug from the previous revision).
"""

import random
from datetime import datetime, timedelta, timezone

import config
from normal_traffic import make_transaction_id, _iso, _pareto_amount


def _fraud_amount(rng: random.Random) -> float:
    """Pick a fraud transaction amount — usually normal-range, occasionally unusually large."""
    if rng.random() < config.FRAUD_LARGE_AMOUNT_PROBABILITY:
        return _pareto_amount(config.FRAUD_LARGE_AMOUNT_MIN, config.FRAUD_LARGE_AMOUNT_MAX, 1.3, rng)
    return _pareto_amount(config.FRAUD_AMOUNT_MIN, config.FRAUD_AMOUNT_MAX, 1.5, rng)


def _new_txn(source, target, amount, ts, channel, device_fp, scenario_id, pattern_type,
             involved_ids, expected_terminal_id, rng: random.Random) -> dict:
    """Build one transaction dict — locked 7-field shape plus internal evaluation fields."""
    return {
        "transaction_id": make_transaction_id(rng),
        "source_account_id": source,
        "target_account_id": target,
        "amount_inr": round(amount, 2),
        "timestamp_dt": ts,
        "timestamp": _iso(ts),
        "payment_channel": channel,
        "device_fingerprint": device_fp,
        "_scenario_id": scenario_id,
        "_pattern_type": pattern_type,
        "_is_fraud": True,
        "_involved_account_ids": involved_ids,
        "_expected_cashout_terminal_id": expected_terminal_id,
    }


def _apply_shared_device(accounts: list[dict], shared_fp: str) -> None:
    """Overwrite the given accounts' primary device so ALL their transactions show the shared device."""
    for acc in accounts:
        acc["primary_device_fingerprint"] = shared_fp


def _apply_shared_kyc_identity(accounts: list[dict], shared_kyc: str) -> None:
    """Overwrite the given accounts' kyc_identity_id so they share a synthetic identity cluster."""
    for acc in accounts:
        acc["kyc_identity_id"] = shared_kyc


def _pick_cashout_terminal(cashout_account: dict, terminals: list[dict], rng: random.Random) -> dict:
    """Pick a plausible cash-out terminal, preferring one in the account's own district."""
    same_district = [t for t in terminals if t["district"] == cashout_account["account_region"]]
    pool = same_district if same_district else terminals
    return rng.choice(pool)


def _record_terminal_history(accounts: list[dict], terminal_id: str) -> None:
    """Add a terminal to each account's historical_terminal_ids if it isn't already there."""
    for acc in accounts:
        if terminal_id not in acc["historical_terminal_ids"]:
            acc["historical_terminal_ids"].append(terminal_id)


def inject_fan_in(accounts: list[dict], terminals: list[dict], scenario_id: str,
                   sim_start: datetime, rng: random.Random) -> tuple[list[dict], dict]:
    """Build one fan-in scenario: several source accounts all pay into one aggregator account."""
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

    window_start = sim_start + timedelta(seconds=rng.uniform(0, config.SIMULATION_DURATION_HOURS * 3600))
    txns = []
    for src in sources:
        offset = rng.uniform(0, config.FAN_IN_WINDOW_MINUTES * 60)
        ts = window_start + timedelta(seconds=offset)
        amount = _fraud_amount(rng)
        channel = rng.choice(["UPI", "IMPS", "AEPS"])
        txns.append(_new_txn(src["account_id"], aggregator["account_id"], amount, ts, channel,
                              shared_fp, scenario_id, "fan_in", involved, terminal["terminal_id"], rng))

    scenario = {"scenario_id": scenario_id, "pattern_type": "fan_in",
                "involved_account_ids": involved, "expected_cashout_terminal_id": terminal["terminal_id"]}
    return txns, scenario


def inject_fan_out(accounts: list[dict], terminals: list[dict], scenario_id: str,
                    sim_start: datetime, rng: random.Random) -> tuple[list[dict], dict]:
    """Build one fan-out scenario: one source account rapidly pays out to many targets."""
    num_targets = rng.randint(config.FAN_OUT_MIN_TARGETS, config.FAN_OUT_MAX_TARGETS)
    chosen = rng.sample(accounts, num_targets + 1)
    source, targets = chosen[0], chosen[1:]
    source["account_tier"] = "mule_l1"
    for acc in targets:
        acc["account_tier"] = "mule_l2"

    involved = [source["account_id"]] + [t["account_id"] for t in targets]
    shared_fp = f"DEV-SHARED-{scenario_id}"
    shared_kyc = f"KYC-RING-{scenario_id}"
    _apply_shared_device(targets, shared_fp)  # the receiving mules share a device/handler
    _apply_shared_kyc_identity(targets, shared_kyc)

    # Cash-out is expected at whichever target ends up holding the money —
    # pick one target as the "final" holder for the expected-terminal story.
    final_holder = rng.choice(targets)
    terminal = _pick_cashout_terminal(final_holder, terminals, rng)
    _record_terminal_history([final_holder], terminal["terminal_id"])

    window_start = sim_start + timedelta(seconds=rng.uniform(0, config.SIMULATION_DURATION_HOURS * 3600))
    txns = []
    for tgt in targets:
        offset = rng.uniform(0, config.FAN_OUT_WINDOW_MINUTES * 60)
        ts = window_start + timedelta(seconds=offset)
        amount = _fraud_amount(rng)
        channel = rng.choice(["UPI", "IMPS", "AEPS"])
        txns.append(_new_txn(source["account_id"], tgt["account_id"], amount, ts, channel,
                              shared_fp, scenario_id, "fan_out", involved, terminal["terminal_id"], rng))

    scenario = {"scenario_id": scenario_id, "pattern_type": "fan_out",
                "involved_account_ids": involved, "expected_cashout_terminal_id": terminal["terminal_id"]}
    return txns, scenario


def inject_layering(accounts: list[dict], terminals: list[dict], scenario_id: str,
                     sim_start: datetime, rng: random.Random) -> tuple[list[dict], dict]:
    """Build one layering chain: A -> B -> C -> D..., amount shrinking and moving fast at each hop."""
    num_hops = rng.randint(config.LAYERING_MIN_HOPS, config.LAYERING_MAX_HOPS)
    chain = rng.sample(accounts, num_hops + 1)
    chain[0]["account_tier"] = "victim"
    for acc in chain[1:-1]:
        acc["account_tier"] = "mule_l1"
    chain[-1]["account_tier"] = "mule_l2"

    involved = [a["account_id"] for a in chain]
    shared_fp = f"DEV-SHARED-{scenario_id}"
    shared_kyc = f"KYC-RING-{scenario_id}"
    _apply_shared_device(chain[1:], shared_fp)  # every mule hop shares a device; victim keeps their own
    _apply_shared_kyc_identity(chain[1:], shared_kyc)

    final_account = chain[-1]
    terminal = _pick_cashout_terminal(final_account, terminals, rng)
    _record_terminal_history([final_account], terminal["terminal_id"])

    ts = sim_start + timedelta(seconds=rng.uniform(0, config.SIMULATION_DURATION_HOURS * 3600))
    amount = _fraud_amount(rng)

    txns = []
    for i in range(len(chain) - 1):
        channel = rng.choice(["UPI", "IMPS"])
        txns.append(_new_txn(chain[i]["account_id"], chain[i + 1]["account_id"], amount, ts, channel,
                              shared_fp if i > 0 else chain[i]["primary_device_fingerprint"],
                              scenario_id, "layering", involved, terminal["terminal_id"], rng))
        delay = rng.uniform(config.LAYERING_HOP_DELAY_MIN_SECONDS, config.LAYERING_HOP_DELAY_MAX_SECONDS)
        ts = ts + timedelta(seconds=delay)
        amount *= config.LAYERING_AMOUNT_DECAY

    scenario = {"scenario_id": scenario_id, "pattern_type": "layering",
                "involved_account_ids": involved, "expected_cashout_terminal_id": terminal["terminal_id"]}
    return txns, scenario


def inject_triadic(accounts: list[dict], terminals: list[dict], scenario_id: str,
                    sim_start: datetime, rng: random.Random) -> tuple[list[dict], dict]:
    """Build one triadic/circular scenario: A -> B -> C -> A, money returns to its origin."""
    cycle_len = config.TRIADIC_CYCLE_LENGTH
    chain = rng.sample(accounts, cycle_len)
    for acc in chain:
        acc["account_tier"] = "mule_l2"

    involved = [a["account_id"] for a in chain]
    shared_fp = f"DEV-SHARED-{scenario_id}"
    shared_kyc = f"KYC-RING-{scenario_id}"
    _apply_shared_device(chain, shared_fp)
    _apply_shared_kyc_identity(chain, shared_kyc)

    # In a closed loop there's no single "final holder" — cash-out risk is
    # spread across all three; pick one to associate as the expected terminal.
    cashout_account = rng.choice(chain)
    terminal = _pick_cashout_terminal(cashout_account, terminals, rng)
    _record_terminal_history([cashout_account], terminal["terminal_id"])

    ts = sim_start + timedelta(seconds=rng.uniform(0, config.SIMULATION_DURATION_HOURS * 3600))
    amount = _fraud_amount(rng)

    txns = []
    for i in range(cycle_len):
        src, tgt = chain[i], chain[(i + 1) % cycle_len]
        channel = rng.choice(["UPI", "IMPS"])
        txns.append(_new_txn(src["account_id"], tgt["account_id"], amount, ts, channel, shared_fp,
                              scenario_id, "triadic", involved, terminal["terminal_id"], rng))
        delay = rng.uniform(config.LAYERING_HOP_DELAY_MIN_SECONDS, config.LAYERING_HOP_DELAY_MAX_SECONDS)
        ts = ts + timedelta(seconds=delay)
        amount *= config.LAYERING_AMOUNT_DECAY

    scenario = {"scenario_id": scenario_id, "pattern_type": "triadic",
                "involved_account_ids": involved, "expected_cashout_terminal_id": terminal["terminal_id"]}
    return txns, scenario


def inject_all_scenarios(accounts: list[dict], terminals: list[dict],
                          rng: random.Random) -> tuple[list[dict], list[dict]]:
    """Run all configured fraud scenarios; return (all fraud transactions, all scenario records)."""
    sim_start = datetime.strptime(config.SIMULATION_START, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    all_txns, all_scenarios = [], []
    counter = 1

    def next_id(prefix):
        nonlocal counter
        sid = f"SCN-{prefix}-{counter:04d}"
        counter += 1
        return sid

    for _ in range(config.NUM_FAN_IN_SCENARIOS):
        txns, meta = inject_fan_in(accounts, terminals, next_id("FANIN"), sim_start, rng)
        all_txns += txns
        all_scenarios.append(meta)
    for _ in range(config.NUM_FAN_OUT_SCENARIOS):
        txns, meta = inject_fan_out(accounts, terminals, next_id("FANOUT"), sim_start, rng)
        all_txns += txns
        all_scenarios.append(meta)
    for _ in range(config.NUM_LAYERING_SCENARIOS):
        txns, meta = inject_layering(accounts, terminals, next_id("LAYER"), sim_start, rng)
        all_txns += txns
        all_scenarios.append(meta)
    for _ in range(config.NUM_TRIADIC_SCENARIOS):
        txns, meta = inject_triadic(accounts, terminals, next_id("TRIAD"), sim_start, rng)
        all_txns += txns
        all_scenarios.append(meta)

    return all_txns, all_scenarios
