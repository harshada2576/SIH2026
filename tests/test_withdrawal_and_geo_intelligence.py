"""tests/test_withdrawal_and_geo_intelligence.py — Test suite for Part 3: Withdrawal & Geo Intelligence.

Tests:
1. Test A: Normal withdrawal for clean legitimate account (ALLOWED + recorded).
2. Test B: Marked account cashout under active hold / confirmed fraud (BLOCKED / INTERCEPTED).
3. Test C: Predicted terminal hit (exact match distance = 0.0 km, strong case correlation).
4. Test D: Nearby alternate terminal deviation (actual location recorded + distance to prediction).
5. Test E: Nearby terminal ranking (ordered nearest first via Haversine distance).
6. Test F: Repeated account-terminal targeting (1 -> MONITORED, 2 -> ELEVATED_RISK, 3+ -> PERSISTENT_TERMINAL_RISK).
7. Test G: Persistence and component reload across separate Store instances.
8. Test H: Idempotency under duplicate attempt_id submissions.
9. Test I: Mock Bank API HTTP endpoints for withdrawals, locations, and terminal history.
"""
from datetime import datetime, timezone
import json
import io
import pytest

from audit.blockchain_lite import AuditLedger
from pipeline.geo_intelligence import WithdrawalGeoIntelligence
from pipeline.graph_store import GraphStore
from shared.persistence import Store
from shared.schemas import (
    CaseLifecycleState,
    CaseRecord,
    ConfirmationStatus,
    PredictedTerminal,
    TerminalBlockRequest,
    WithdrawalAttemptEvent,
)


@pytest.fixture
def test_env(tmp_path):
    db_path = tmp_path / "test_geo_intel.db"
    store = Store(db_path=db_path)
    graph_store = GraphStore()
    ledger = AuditLedger()

    # Load mock terminals into GraphStore
    mock_terminals = [
        {"terminal_id": "ATM-JAIPUR-001", "terminal_type": "ATM_KIOSK", "district": "Jaipur", "pincode": "302001", "latitude": 26.9124, "longitude": 75.7873},
        {"terminal_id": "ATM-JAIPUR-002", "terminal_type": "ATM_KIOSK", "district": "Jaipur", "pincode": "302001", "latitude": 26.9150, "longitude": 75.7900},
        {"terminal_id": "ATM-JAIPUR-003", "terminal_type": "ATM_KIOSK", "district": "Jaipur", "pincode": "302001", "latitude": 26.9200, "longitude": 75.7950},
        {"terminal_id": "ATM-DELHI-001", "terminal_type": "ATM_KIOSK", "district": "New Delhi", "pincode": "110001", "latitude": 28.6139, "longitude": 77.2090},
    ]
    graph_store.load_terminals(mock_terminals)

    geo_intel = WithdrawalGeoIntelligence(store=store, graph_store=graph_store, ledger=ledger)

    return {
        "db_path": db_path,
        "store": store,
        "graph_store": graph_store,
        "ledger": ledger,
        "geo_intel": geo_intel,
    }


def test_test_a_normal_withdrawal(test_env):
    """Test A: Normal withdrawal for clean legitimate account.

    Expected: ALLOWED, attempt is recorded in persistence.
    """
    geo_intel = test_env["geo_intel"]
    store = test_env["store"]

    attempt = geo_intel.process_withdrawal_attempt(
        attempt_id="ATT-NORMAL-001",
        account_id="ACC-CLEAN-01",
        terminal_id="ATM-JAIPUR-001",
        amount_inr=5000.0,
        timestamp="2026-09-10T11:00:00+00:00",
    )

    assert attempt.status == "ALLOWED"
    assert attempt.is_blocked is False
    assert attempt.action_taken == "ALLOWED"

    # Verify persisted in Store
    persisted = store.get_withdrawal_attempt("ATT-NORMAL-001")
    assert persisted is not None
    assert persisted["attempt_id"] == "ATT-NORMAL-001"
    assert persisted["terminal_id"] == "ATM-JAIPUR-001"
    assert float(persisted["amount_inr"]) == 5000.0


def test_test_b_suspicious_marked_account_blocked(test_env):
    """Test B: Marked account cashout under active terminal block or confirmed fraud.

    Expected: BLOCKED / INTERCEPTED.
    """
    geo_intel = test_env["geo_intel"]
    store = test_env["store"]

    # Place active block on terminal
    store.save_terminal_block(
        TerminalBlockRequest(
            terminal_id="ATM-JAIPUR-001",
            case_id="CASE-FRAUD-55",
            reason="PREDICTED_CASH_EGRESS",
        )
    )

    attempt = geo_intel.process_withdrawal_attempt(
        attempt_id="ATT-BLOCKED-001",
        account_id="ACC-MULE-99",
        terminal_id="ATM-JAIPUR-001",
        amount_inr=15000.0,
        case_id="CASE-FRAUD-55",
    )

    assert attempt.status == "BLOCKED"
    assert attempt.is_blocked is True
    assert attempt.action_taken == "BLOCKED"
    assert "intercepted" in attempt.reason.lower() or "blocked" in attempt.reason.lower()


def test_test_c_predicted_terminal_hit(test_env):
    """Test C: Predicted ATM = actual ATM.

    Expected: distance_to_predicted_km = 0.0, strong case correlation.
    """
    geo_intel = test_env["geo_intel"]
    store = test_env["store"]

    # Seed an active investigation case with predicted terminal
    case = CaseRecord(
        case_id="CASE-PRED-HIT",
        flagged_account_id="ACC-AGGREGATOR-01",
        predicted_terminals=[
            PredictedTerminal(terminal_id="ATM-JAIPUR-001", probability=0.92, latitude=26.9124, longitude=75.7873)
        ],
        suspicious_amount=100000.0,
        protected_amount=100000.0,
    )
    store.save_case(case.to_dict())

    attempt = geo_intel.process_withdrawal_attempt(
        attempt_id="ATT-HIT-001",
        account_id="ACC-AGGREGATOR-01",
        terminal_id="ATM-JAIPUR-001",
        amount_inr=20000.0,
        case_id="CASE-PRED-HIT",
    )

    assert attempt.correlated_case_id == "CASE-PRED-HIT"
    assert attempt.distance_to_predicted_km == 0.0


def test_test_d_nearby_alternate_terminal_deviation(test_env):
    """Test D: Cashout attempt at a nearby alternate terminal instead of top prediction.

    Expected: deviation distance from prediction is calculated, case correlation retained.
    """
    geo_intel = test_env["geo_intel"]
    store = test_env["store"]

    # Seed active case with predicted terminal ATM-JAIPUR-001 (lat: 26.9124, lon: 75.7873)
    case = CaseRecord(
        case_id="CASE-DEV-001",
        flagged_account_id="ACC-MULE-DEV",
        predicted_terminals=[
            PredictedTerminal(terminal_id="ATM-JAIPUR-001", probability=0.88, latitude=26.9124, longitude=75.7873)
        ],
    )
    store.save_case(case.to_dict())

    # Attempt occurs at ATM-JAIPUR-002 (lat: 26.9150, lon: 75.7900)
    attempt = geo_intel.process_withdrawal_attempt(
        attempt_id="ATT-DEV-001",
        account_id="ACC-MULE-DEV",
        terminal_id="ATM-JAIPUR-002",
        amount_inr=10000.0,
        case_id="CASE-DEV-001",
    )

    assert attempt.correlated_case_id == "CASE-DEV-001"
    assert attempt.distance_to_predicted_km is not None
    assert 0.1 <= attempt.distance_to_predicted_km <= 1.0  # Approx 0.4 km away
    assert len(attempt.nearby_terminals) >= 1


def test_test_e_nearby_terminal_ranking(test_env):
    """Test E: Verify nearest terminals are returned in ascending distance order."""
    geo_intel = test_env["geo_intel"]

    nearby = geo_intel.find_nearby_terminals("ATM-JAIPUR-001", radius_km=10.0, limit=5)
    assert len(nearby) >= 2

    # Verify distances are monotonically increasing
    distances = [t["distance_km"] for t in nearby]
    assert distances == sorted(distances)
    assert nearby[0]["terminal_id"] == "ATM-JAIPUR-002"


def test_test_f_repeated_targeting_escalation(test_env):
    """Test F: Repeated account-terminal attempts produce escalation tiers:

    1 attempt  -> MONITORED (1.0x)
    2 attempts -> ELEVATED_RISK (1.25x)
    3+         -> PERSISTENT_TERMINAL_RISK (1.5x)
    """
    geo_intel = test_env["geo_intel"]

    # 1st attempt
    h1 = geo_intel.get_account_terminal_history("ACC-TARGET-1", "ATM-JAIPUR-001")
    geo_intel.process_withdrawal_attempt("ATT-R1", "ACC-TARGET-1", "ATM-JAIPUR-001", 5000.0)
    h1_post = geo_intel.get_account_terminal_history("ACC-TARGET-1", "ATM-JAIPUR-001")
    assert h1_post["attempt_count"] == 1
    assert h1_post["escalation_state"] == "MONITORED"
    assert h1_post["risk_multiplier"] == 1.0

    # 2nd attempt
    geo_intel.process_withdrawal_attempt("ATT-R2", "ACC-TARGET-1", "ATM-JAIPUR-001", 5000.0)
    h2 = geo_intel.get_account_terminal_history("ACC-TARGET-1", "ATM-JAIPUR-001")
    assert h2["attempt_count"] == 2
    assert h2["escalation_state"] == "ELEVATED_RISK"
    assert h2["risk_multiplier"] == 1.25

    # 3rd attempt
    geo_intel.process_withdrawal_attempt("ATT-R3", "ACC-TARGET-1", "ATM-JAIPUR-001", 5000.0)
    h3 = geo_intel.get_account_terminal_history("ACC-TARGET-1", "ATM-JAIPUR-001")
    assert h3["attempt_count"] == 3
    assert h3["escalation_state"] == "PERSISTENT_TERMINAL_RISK"
    assert h3["risk_multiplier"] == 1.5
    assert h3["recommended_action"] == "ESCALATE_TERMINAL_BLOCK"


def test_test_g_location_persistence_and_reload(test_env):
    """Test G: Persist withdrawal attempts & case location events, re-instantiate Store, verify intact."""
    geo_intel = test_env["geo_intel"]
    db_path = test_env["db_path"]
    store = test_env["store"]

    case = CaseRecord(
        case_id="CASE-LOC-01",
        flagged_account_id="ACC-LOC-01",
        predicted_terminals=[
            PredictedTerminal(terminal_id="ATM-JAIPUR-001", probability=0.9, latitude=26.9124, longitude=75.7873)
        ],
    )
    store.save_case(case.to_dict())

    geo_intel.process_withdrawal_attempt(
        attempt_id="ATT-LOC-1",
        account_id="ACC-LOC-01",
        terminal_id="ATM-JAIPUR-002",
        amount_inr=8000.0,
        case_id="CASE-LOC-01",
    )

    # Fresh store and geo intelligence instance
    fresh_store = Store(db_path=db_path)
    fresh_graph = test_env["graph_store"]
    fresh_geo = WithdrawalGeoIntelligence(store=fresh_store, graph_store=fresh_graph)

    history = fresh_geo.get_case_location_history("CASE-LOC-01")
    assert len(history) >= 2  # 1 predicted + 1 actual withdrawal event
    event_types = [h.event_type for h in history]
    assert "PREDICTED_EGRESS" in event_types
    assert "RECORDED_WITHDRAWAL" in event_types


def test_test_h_idempotency_duplicate_attempt(test_env):
    """Test H: Submit same attempt_id multiple times -> single persisted attempt."""
    geo_intel = test_env["geo_intel"]
    store = test_env["store"]

    a1 = geo_intel.process_withdrawal_attempt(
        attempt_id="ATT-IDEMP-99",
        account_id="ACC-IDEMP-01",
        terminal_id="ATM-JAIPUR-001",
        amount_inr=4000.0,
    )
    a2 = geo_intel.process_withdrawal_attempt(
        attempt_id="ATT-IDEMP-99",
        account_id="ACC-IDEMP-01",
        terminal_id="ATM-JAIPUR-001",
        amount_inr=4000.0,
    )

    assert a1.attempt_id == a2.attempt_id
    all_matching = [a for a in store.get_withdrawal_attempts() if a["attempt_id"] == "ATT-IDEMP-99"]
    assert len(all_matching) == 1


def test_test_i_bank_api_http_endpoints(tmp_path, test_env):
    """Test I: Verify mock bank API HTTP endpoints for withdrawals, locations, and terminal history."""
    from mock_services.bank_api import server

    db_file = tmp_path / "test_api_geo.db"
    test_store = Store(db_file)
    test_graph = test_env["graph_store"]
    test_geo = WithdrawalGeoIntelligence(store=test_store, graph_store=test_graph)

    server._STORE = test_store
    server._GEO_INTEL = test_geo

    class DummyHandler(server.Handler):
        def __init__(self, method, path, body=None):
            self.path = path
            self.command = method
            self.headers = {"Content-Length": str(len(body)) if body else "0"}
            self.rfile = io.BytesIO(body.encode("utf-8") if body else b"")
            self.wfile = io.BytesIO()
            self._headers_buffer = []

        def send_response(self, code, message=None):
            self.status_code = code

        def send_header(self, keyword, value):
            self._headers_buffer.append((keyword, value))

        def end_headers(self):
            pass

    # 1. POST /terminal/attempt
    attempt_body = {
        "attempt_id": "ATT-HTTP-001",
        "account_id": "ACC-HTTP-01",
        "terminal_id": "ATM-JAIPUR-001",
        "amount_inr": 7500.0,
    }
    h_post = DummyHandler("POST", "/terminal/attempt", json.dumps(attempt_body))
    h_post.do_POST()
    assert h_post.status_code == 200
    res_post = json.loads(h_post.wfile.getvalue().decode("utf-8"))
    assert res_post["status"] == "SUCCESS"
    assert res_post["attempt"]["attempt_id"] == "ATT-HTTP-001"

    # 2. GET /terminals/ATM-JAIPUR-001/nearby
    h_nearby = DummyHandler("GET", "/terminals/ATM-JAIPUR-001/nearby")
    h_nearby.do_GET()
    assert h_nearby.status_code == 200
    res_nearby = json.loads(h_nearby.wfile.getvalue().decode("utf-8"))
    assert len(res_nearby["nearby_terminals"]) >= 1

    # 3. GET /accounts/ACC-HTTP-01/terminal-history
    h_hist = DummyHandler("GET", "/accounts/ACC-HTTP-01/terminal-history")
    h_hist.do_GET()
    assert h_hist.status_code == 200
    res_hist = json.loads(h_hist.wfile.getvalue().decode("utf-8"))
    assert res_hist["account_id"] == "ACC-HTTP-01"
    assert res_hist["attempt_count"] == 1
