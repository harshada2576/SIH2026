"""tests/test_fund_traceability_and_recovery.py — Test suite for Part 2: Fund Traceability & Recovery.

Tests:
1. Test A: Basic chain A -> B -> C -> D -> E (complete descendant provenance retrievable).
2. Test B: Pending confirmation (downstream online transfers allowed and tracked without auto-fraud).
3. Test C: Confirmed fraud (descendants discovered, chain persisted, recovery case created, exposure identified).
4. Test D: Multiple sources converging into common account (A -> M, B -> M, C -> M -> N -> ATM).
5. Test E: Commingled funds handling (separate legitimate balance & suspicious exposure without FIFO fallacy).
6. Test F: Idempotency under duplicate events (transactions, edges, recovery cases).
7. Test G: Persistence & component reload across separate Store instances.
8. Test H: Bank API HTTP endpoints for chains, exposures, and recovery workflows.
"""
from datetime import datetime, timezone
import json
import io
import pytest

from audit.blockchain_lite import AuditLedger
from detection.transaction_control import TransactionControlManager
from pipeline.fund_traceability import FundTraceabilityEngine
from pipeline.graph_store import GraphStore
from shared.persistence import Store
from shared.schemas import (
    ConfirmationStatus,
    ControlAction,
    RecoveryState,
    TransactionChannel,
    TransactionEvent,
)


@pytest.fixture
def test_env(tmp_path):
    db_path = tmp_path / "test_fund_traceability.db"
    store = Store(db_path=db_path)
    graph_store = GraphStore()
    ledger = AuditLedger()
    engine = FundTraceabilityEngine(store=store, graph_store=graph_store, ledger=ledger)
    control_mgr = TransactionControlManager(
        store=store, graph_store=graph_store, ledger=ledger, traceability_engine=engine
    )
    return {
        "db_path": db_path,
        "store": store,
        "graph_store": graph_store,
        "ledger": ledger,
        "engine": engine,
        "control_mgr": control_mgr,
    }


def test_test_a_basic_chain_tracking(test_env):
    """Test A: A -> B -> C -> D -> E.

    Verify complete descendant chain is retrievable with structured metadata:
    - root transaction
    - direct child transactions
    - descendant transactions
    - current known accounts
    - timestamps, amounts, channels, depth, status
    """
    engine = test_env["engine"]

    # 1. Establish origin trace root: A -> B ₹1,00,000
    root_chain = engine.establish_trace_root(
        root_transaction_id="TX-A-B-100K",
        origin_account_id="ACC-A",
        destination_account_id="ACC-B",
        amount_inr=100000.0,
        payment_channel="IMPS",
        timestamp="2026-09-10T10:00:00+00:00",
    )
    assert root_chain.chain_id == "CHAIN-TX-A-B-100K"
    assert root_chain.root_transaction_id == "TX-A-B-100K"
    assert root_chain.original_amount == 100000.0

    # 2. Track B -> C ₹99,000
    engine.track_descendant_transaction(
        parent_transaction_id="TX-A-B-100K",
        child_transaction_id="TX-B-C-99K",
        from_account_id="ACC-B",
        to_account_id="ACC-C",
        amount_inr=99000.0,
        payment_channel="UPI",
        timestamp="2026-09-10T10:05:00+00:00",
    )

    # 3. Track C -> D ₹96,000
    engine.track_descendant_transaction(
        parent_transaction_id="TX-B-C-99K",
        child_transaction_id="TX-C-D-96K",
        from_account_id="ACC-C",
        to_account_id="ACC-D",
        amount_inr=96000.0,
        payment_channel="UPI",
        timestamp="2026-09-10T10:10:00+00:00",
    )

    # 4. Track D -> E ₹90,000
    engine.track_descendant_transaction(
        parent_transaction_id="TX-C-D-96K",
        child_transaction_id="TX-D-E-90K",
        from_account_id="ACC-D",
        to_account_id="ACC-E",
        amount_inr=90000.0,
        payment_channel="NEFT",
        timestamp="2026-09-10T10:15:00+00:00",
    )

    # 5. Retrieve structured chain
    retrieved = engine.get_transaction_chain("CHAIN-TX-A-B-100K")
    assert retrieved is not None
    assert retrieved["root_transaction_id"] == "TX-A-B-100K"
    assert retrieved["origin_account_id"] == "ACC-A"
    assert retrieved["chain_depth"] == 4
    assert len(retrieved["traceable_transactions"]) == 4

    tx_ids = [t["transaction_id"] for t in retrieved["traceable_transactions"]]
    assert tx_ids == ["TX-A-B-100K", "TX-B-C-99K", "TX-C-D-96K", "TX-D-E-90K"]

    assert "ACC-E" in retrieved["current_known_accounts"]
    assert retrieved["destination_account_chain"] == ["ACC-B", "ACC-C", "ACC-D", "ACC-E"]

    # Verify query for descendants of specific transaction
    descendants_of_b = engine.get_transaction_descendants("TX-B-C-99K")
    assert len(descendants_of_b) == 2
    assert descendants_of_b[0]["transaction_id"] == "TX-C-D-96K"
    assert descendants_of_b[1]["transaction_id"] == "TX-D-E-90K"


def test_test_b_pending_confirmation_downstream_allowed_and_tracked(test_env):
    """Test B: Root transaction pending confirmation.

    - Downstream transfers B -> C continue normally (ALLOW + MONITOR)
    - Descendants are linked to the pending root transaction
    - Downstream accounts are NOT prematurely frozen
    """
    control_mgr = test_env["control_mgr"]
    engine = test_env["engine"]

    # 1. Request confirmation for A -> B ₹1L
    conf = control_mgr.request_confirmation(
        transaction_id="TX-PENDING-001",
        sender_id="ACC-SENDER-A",
        beneficiary_id="ACC-MULE-B",
        amount=100000.0,
        case_id="CASE-PENDING-001",
    )
    assert conf.status == ConfirmationStatus.PENDING_CONFIRMATION

    # 2. Downstream online transfer B -> C evaluated
    dec_b_c = control_mgr.evaluate_transaction_control(
        transaction_id="TX-B-C-50K",
        from_account="ACC-MULE-B",
        to_account="ACC-MULE-C",
        amount=50000.0,
        channel_or_type="UPI",
        existing_balance=20000.0,
    )
    assert dec_b_c.allowed is True
    assert dec_b_c.action == ControlAction.MONITOR

    # 3. Track downstream transaction B -> C
    engine.track_descendant_transaction(
        parent_transaction_id="TX-PENDING-001",
        child_transaction_id="TX-B-C-50K",
        from_account_id="ACC-MULE-B",
        to_account_id="ACC-MULE-C",
        amount_inr=50000.0,
        payment_channel="UPI",
    )

    # 4. Track further C -> D
    engine.track_descendant_transaction(
        parent_transaction_id="TX-B-C-50K",
        child_transaction_id="TX-C-D-45K",
        from_account_id="ACC-MULE-C",
        to_account_id="ACC-MULE-D",
        amount_inr=45000.0,
        payment_channel="IMPS",
    )

    # 5. Verify chain is tracked under PENDING_CONFIRMATION status
    chain = engine.get_transaction_chain("CHAIN-TX-PENDING-001")
    assert chain is not None
    assert chain["chain_status"] == ConfirmationStatus.PENDING_CONFIRMATION
    assert len(chain["traceable_transactions"]) == 3
    assert "ACC-MULE-D" in chain["current_known_accounts"]


def test_test_c_confirmed_fraud_triggers_recovery_case(test_env):
    """Test C: Root transaction transitions to CONFIRMED_FRAUD.

    - Complete money trail is discovered
    - Recovery case is created with recovery_status and affected accounts
    - Traceable exposed amounts calculated
    """
    control_mgr = test_env["control_mgr"]
    engine = test_env["engine"]
    store = test_env["store"]

    conf = control_mgr.request_confirmation(
        transaction_id="TX-FRAUD-ROOT-01",
        sender_id="ACC-VICTIM-01",
        beneficiary_id="ACC-MULE-01",
        amount=100000.0,
        case_id="CASE-FRAUD-001",
    )

    # Track downstream layering
    engine.track_descendant_transaction(
        parent_transaction_id="TX-FRAUD-ROOT-01",
        child_transaction_id="TX-M1-M2",
        from_account_id="ACC-MULE-01",
        to_account_id="ACC-MULE-02",
        amount_inr=95000.0,
        payment_channel="IMPS",
    )
    engine.track_descendant_transaction(
        parent_transaction_id="TX-M1-M2",
        child_transaction_id="TX-M2-ATM",
        from_account_id="ACC-MULE-02",
        to_account_id="ATM-DELHI-01",
        amount_inr=90000.0,
        payment_channel="ATM_CASH_OUT",
        is_cashout=True,
        terminal_id="ATM-DELHI-01",
    )

    # Respond with CONFIRMED_FRAUD
    resp = control_mgr.submit_confirmation_response(
        confirmation_id=conf.confirmation_id,
        response_status=ConfirmationStatus.CONFIRMED_FRAUD,
        notes="Victim confirmed phishing fraud",
    )
    assert resp["status"] == ConfirmationStatus.CONFIRMED_FRAUD

    # Verify RecoveryCaseRecord was created
    rec_case = engine.get_recovery_case_query("CASE-FRAUD-001")
    assert rec_case is not None
    assert rec_case["root_transaction_id"] == "TX-FRAUD-ROOT-01"
    assert rec_case["original_amount"] == 100000.0
    assert rec_case["recovery_status"] == RecoveryState.INTERVENTION_PENDING
    assert len(rec_case["known_withdrawals"]) >= 1
    assert rec_case["known_withdrawals"][0]["terminal_id"] == "ATM-DELHI-01"

    # Test advancing recovery status to PARTIALLY_RECOVERED
    updated_case = engine.update_recovery_status(
        case_id="CASE-FRAUD-001",
        new_status=RecoveryState.PARTIALLY_RECOVERED,
        recovered_amount=40000.0,
        action_note="Simulated interbank hold recovered ₹40,000 from ACC-MULE-02",
    )
    assert updated_case.recovery_status == RecoveryState.PARTIALLY_RECOVERED
    assert updated_case.recovered_amount == 40000.0
    assert len(updated_case.simulated_actions) >= 1


def test_test_d_multiple_victims_converging_on_common_account(test_env):
    """Test D: Multiple victims converge into common account M.

    A -> M (₹100k)
    B -> M (₹80k)
    C -> M (₹60k)
         ↓
         N (₹220k)
         ↓
        ATM
    """
    engine = test_env["engine"]

    # 1. Establish 3 distinct origin chains converging into ACC-AGGREGATOR-M
    engine.establish_trace_root("TX-VICTIM-A-M", "ACC-VICTIM-A", "ACC-AGGREGATOR-M", 100000.0, "IMPS")
    engine.establish_trace_root("TX-VICTIM-B-M", "ACC-VICTIM-B", "ACC-AGGREGATOR-M", 80000.0, "UPI")
    engine.establish_trace_root("TX-VICTIM-C-M", "ACC-VICTIM-C", "ACC-AGGREGATOR-M", 60000.0, "NEFT")

    # 2. Common account M passes funds to N
    engine.track_descendant_transaction(
        parent_transaction_id="TX-VICTIM-A-M",
        child_transaction_id="TX-M-N-220K",
        from_account_id="ACC-AGGREGATOR-M",
        to_account_id="ACC-HANDLER-N",
        amount_inr=220000.0,
        payment_channel="RTGS",
    )

    # 3. Detect convergent chains
    conv = engine.get_convergent_chains("ACC-AGGREGATOR-M")
    assert conv.common_account_id == "ACC-AGGREGATOR-M"
    assert len(conv.root_transaction_ids) == 3
    assert conv.aggregate_suspicious_exposure == 240000.0  # 100k + 80k + 60k
    assert "TX-VICTIM-A-M" in conv.root_transaction_ids
    assert "TX-VICTIM-B-M" in conv.root_transaction_ids
    assert "TX-VICTIM-C-M" in conv.root_transaction_ids


def test_test_e_commingled_funds_no_suspicious_funds_first_fallacy(test_env):
    """Test E: Commingled funds.

    Account B has ₹50,000 legitimate balance and receives ₹1,00,000 suspicious exposure.
    B -> C ₹30,000 happens.

    Verify:
    - B's legitimate balance and suspicious exposure are preserved separately.
    - System does NOT falsely claim physical rupee certainty or FIFO consumption.
    - C is marked with traceable exposure bounded by transfer amount.
    """
    engine = test_env["engine"]

    # 1. Origin transfer: A -> B ₹1,00,000 where B already had ₹50,000 legitimate balance
    engine.establish_trace_root(
        root_transaction_id="TX-COMMINGLE-01",
        origin_account_id="ACC-VICTIM-A",
        destination_account_id="ACC-COMMINGLED-B",
        amount_inr=100000.0,
        existing_legitimate_balance=50000.0,
    )

    # Verify B's exposure record
    exp_b = engine.get_account_exposure_query("ACC-COMMINGLED-B")
    assert exp_b is not None
    assert exp_b["legitimate_balance"] == 50000.0
    assert exp_b["suspicious_exposure"] == 100000.0
    assert exp_b["total_balance"] == 150000.0

    # 2. B -> C ₹30,000
    engine.track_descendant_transaction(
        parent_transaction_id="TX-COMMINGLE-01",
        child_transaction_id="TX-B-C-30K",
        from_account_id="ACC-COMMINGLED-B",
        to_account_id="ACC-RECEIVER-C",
        amount_inr=30000.0,
        payment_channel="UPI",
    )

    # Verify C's exposure is tracked as traceable exposure (₹30,000), not fabricated certainty
    exp_c = engine.get_account_exposure_query("ACC-RECEIVER-C")
    assert exp_c is not None
    assert exp_c["suspicious_exposure"] == 30000.0
    assert "TX-COMMINGLE-01" in exp_c["contributing_root_transactions"]

    # Verify B's original exposure and legitimate balance tracking remain uncorrupted
    exp_b_after = engine.get_account_exposure_query("ACC-COMMINGLED-B")
    assert exp_b_after["legitimate_balance"] == 50000.0
    assert exp_b_after["suspicious_exposure"] >= 100000.0


def test_test_f_idempotency_duplicate_events(test_env):
    """Test F: Repeated processing does not create duplicate edges, duplicate chains, or corrupted state."""
    engine = test_env["engine"]
    store = test_env["store"]

    # 1. Establish trace root twice
    c1 = engine.establish_trace_root("TX-IDEMP-01", "ACC-A", "ACC-B", 50000.0)
    c2 = engine.establish_trace_root("TX-IDEMP-01", "ACC-A", "ACC-B", 50000.0)
    assert c1.chain_id == c2.chain_id

    # 2. Track same descendant transaction twice
    engine.track_descendant_transaction("TX-IDEMP-01", "TX-IDEMP-CHILD", "ACC-B", "ACC-C", 40000.0, "UPI")
    engine.track_descendant_transaction("TX-IDEMP-01", "TX-IDEMP-CHILD", "ACC-B", "ACC-C", 40000.0, "UPI")

    chain = engine.get_transaction_chain(c1.chain_id)
    # Traceable transactions must not have duplicates
    child_count = sum(1 for t in chain["traceable_transactions"] if t["transaction_id"] == "TX-IDEMP-CHILD")
    assert child_count == 1

    # 3. Trigger handle_fraud_confirmation twice
    r1 = engine.handle_fraud_confirmation("TX-IDEMP-01", case_id="CASE-IDEMP-99")
    r2 = engine.handle_fraud_confirmation("TX-IDEMP-01", case_id="CASE-IDEMP-99")
    assert r1.case_id == r2.case_id


def test_test_g_persistence_reload_across_store_instances(test_env):
    """Test G: Persist chain & recovery case, re-instantiate Store from DB path, verify complete state intact."""
    engine = test_env["engine"]
    db_path = test_env["db_path"]

    engine.establish_trace_root("TX-PERSIST-01", "ACC-ORIGIN", "ACC-MULE-1", 75000.0)
    engine.track_descendant_transaction("TX-PERSIST-01", "TX-P-LEG-2", "ACC-MULE-1", "ACC-MULE-2", 70000.0, "UPI")
    engine.handle_fraud_confirmation("TX-PERSIST-01", case_id="CASE-PERSIST-01")

    # Re-instantiate a fresh Store and Engine against the same SQLite file
    fresh_store = Store(db_path=db_path)
    fresh_engine = FundTraceabilityEngine(store=fresh_store)

    chain = fresh_engine.get_transaction_chain("CHAIN-TX-PERSIST-01")
    assert chain is not None
    assert chain["original_amount"] == 75000.0
    assert len(chain["traceable_transactions"]) == 2
    assert chain["destination_account_chain"] == ["ACC-MULE-1", "ACC-MULE-2"]

    rec_case = fresh_engine.get_recovery_case_query("CASE-PERSIST-01")
    assert rec_case is not None
    assert rec_case["root_transaction_id"] == "TX-PERSIST-01"
    assert rec_case["original_amount"] == 75000.0
    assert len(rec_case["simulated_actions"]) >= 2


def test_test_h_bank_api_http_endpoints(tmp_path):
    """Test H: Verify mock bank API HTTP endpoints for chains, exposures, and recovery workflows."""
    from mock_services.bank_api import server

    db_file = tmp_path / "test_api_chains.db"
    test_store = Store(db_path=db_file)
    test_trace = FundTraceabilityEngine(store=test_store)
    test_ctrl = TransactionControlManager(store=test_store, traceability_engine=test_trace)

    server._STORE = test_store
    server._CONTROL_MGR = test_ctrl
    server._TRACE_ENGINE = test_trace

    # 1. Establish trace root
    test_trace.establish_trace_root("TX-API-ROOT", "ACC-V", "ACC-M1", 85000.0)

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

    # GET /chains/CHAIN-TX-API-ROOT
    h_get_chain = DummyHandler("GET", "/chains/CHAIN-TX-API-ROOT")
    h_get_chain.do_GET()
    assert h_get_chain.status_code == 200
    res_chain = json.loads(h_get_chain.wfile.getvalue().decode("utf-8"))
    assert res_chain["chain_id"] == "CHAIN-TX-API-ROOT"
    assert res_chain["original_amount"] == 85000.0

    # POST /chains/track-descendant
    track_body = {
        "parent_transaction_id": "TX-API-ROOT",
        "child_transaction_id": "TX-API-CHILD",
        "from_account_id": "ACC-M1",
        "to_account_id": "ACC-M2",
        "amount_inr": 80000.0,
        "payment_channel": "UPI",
    }
    h_track = DummyHandler("POST", "/chains/track-descendant", json.dumps(track_body))
    h_track.do_POST()
    assert h_track.status_code == 200

    # GET /chains/account/ACC-M1/exposure
    h_exp = DummyHandler("GET", "/chains/account/ACC-M1/exposure")
    h_exp.do_GET()
    assert h_exp.status_code == 200
    res_exp = json.loads(h_exp.wfile.getvalue().decode("utf-8"))
    assert res_exp["account_id"] == "ACC-M1"
    assert res_exp["suspicious_exposure"] == 85000.0

    # GET /chains/account/ACC-M1/convergent
    h_conv = DummyHandler("GET", "/chains/account/ACC-M1/convergent")
    h_conv.do_GET()
    assert h_conv.status_code == 200
    res_conv = json.loads(h_conv.wfile.getvalue().decode("utf-8"))
    assert res_conv["common_account_id"] == "ACC-M1"
    assert res_conv["aggregate_suspicious_exposure"] == 85000.0
