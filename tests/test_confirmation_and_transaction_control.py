"""tests/test_confirmation_and_transaction_control.py — Test suite for Part 1: Confirmation & Transaction Control.

Scenarios tested:
1. Scenario A: High-value transfer placed under PENDING_CONFIRMATION; downstream online transfers (UPI/IMPS) ALLOWED + MONITORED.
2. Scenario B: Channel-differentiated restriction: ATM cash withdrawal attempting to drain suspicious funds is RESTRICTED, while withdrawal within pre-existing balance is ALLOWED.
3. Scenario C: CONFIRMED_LEGITIMATE response clears provisional holds cleanly.
4. Scenario D: CONFIRMED_FRAUD traces downstream mule/aggregator network via GraphStore, generates RecoveryWorkflowRecord, and places selective holds.
5. Scenario E: Window expiry transitions to EXPIRED / NO_RESPONSE without false auto-fraud classification.
6. Scenario F: Idempotency under duplicate submissions and persistence reload across Store instances.
"""
import time
from datetime import datetime, timezone, timedelta
import pytest

from audit.blockchain_lite import AuditLedger
from detection.transaction_control import TransactionControlManager
from pipeline.graph_store import GraphStore
from shared.persistence import Store
from shared.schemas import (
    ConfirmationRecord,
    ConfirmationStatus,
    ControlAction,
    TransactionChannel,
    TransactionEvent,
)


@pytest.fixture
def test_env(tmp_path):
    db_path = tmp_path / "test_sih2026.db"
    store = Store(db_path=db_path)
    graph_store = GraphStore()
    ledger = AuditLedger()
    manager = TransactionControlManager(store=store, graph_store=graph_store, ledger=ledger)
    return {
        "db_path": db_path,
        "store": store,
        "graph_store": graph_store,
        "ledger": ledger,
        "manager": manager,
    }


def test_scenario_a_pending_confirmation_downstream_online_allowed(test_env):
    """Scenario A: Unusual transfer A -> B (₹100,000) requires confirmation.

    While pending:
    - B -> C (₹40,000 via UPI) is ALLOWED and MONITORED.
    - B's account is NOT frozen.
    """
    manager = test_env["manager"]

    # 1. Request confirmation for A -> B ₹1,00,000
    conf = manager.request_confirmation(
        transaction_id="TX-A-B-100K",
        sender_id="ACC-VICTIM-A",
        beneficiary_id="ACC-MULE-B",
        amount=100000.0,
        reason="Unusual high-value transfer A -> B",
        timeout_seconds=300,
        case_id="CASE-1001",
    )

    assert conf.status == ConfirmationStatus.PENDING_CONFIRMATION
    assert conf.amount_inr == 100000.0
    assert conf.destination_account_id == "ACC-MULE-B"

    # 2. Downstream online transfer B -> C (UPI ₹40,000)
    decision = manager.evaluate_transaction_control(
        transaction_id="TX-B-C-40K",
        from_account="ACC-MULE-B",
        to_account="ACC-MULE-C",
        amount=40000.0,
        channel_or_type="UPI",
        existing_balance=25000.0,
    )

    assert decision.channel == TransactionChannel.ONLINE_TRANSFER
    assert decision.action == ControlAction.MONITOR
    assert decision.allowed is True
    assert "ALLOWED and MONITORED" in decision.reason
    assert decision.correlated_case_id == "CASE-1001"


def test_scenario_b_cash_withdrawal_channel_differentiation(test_env):
    """Scenario B: Cash withdrawal behavior while confirmation is pending:

    - B has existing legitimate balance ₹20,000 + pending suspicious ₹100,000.
    - ATM withdrawal of ₹15,000 <= legitimate balance is ALLOWED.
    - ATM withdrawal of ₹50,000 > legitimate balance (attempts to drain suspicious funds) is RESTRICTED.
    """
    manager = test_env["manager"]

    manager.request_confirmation(
        transaction_id="TX-A-B-100K",
        sender_id="ACC-VICTIM-A",
        beneficiary_id="ACC-MULE-B",
        amount=100000.0,
        case_id="CASE-1002",
    )

    # 1. Cash withdrawal within legitimate balance (₹15,000 <= ₹20,000) -> ALLOWED
    dec_allowed = manager.evaluate_transaction_control(
        transaction_id="TX-ATM-15K",
        from_account="ACC-MULE-B",
        to_account="ATM-MUMBAI-01",
        amount=15000.0,
        channel_or_type="ATM_CASH_OUT",
        existing_balance=20000.0,
    )
    assert dec_allowed.channel == TransactionChannel.CASH_WITHDRAWAL
    assert dec_allowed.action == ControlAction.ALLOW
    assert dec_allowed.allowed is True
    assert dec_allowed.held_amount == 100000.0
    assert dec_allowed.available_balance == 5000.0

    # 2. Cash withdrawal attempting to drain suspicious provisional funds (₹50,000 > ₹20,000) -> RESTRICTED
    dec_restricted = manager.evaluate_transaction_control(
        transaction_id="TX-ATM-50K",
        from_account="ACC-MULE-B",
        to_account="ATM-MUMBAI-01",
        amount=50000.0,
        channel_or_type="ATM",
        existing_balance=20000.0,
    )
    assert dec_restricted.channel == TransactionChannel.CASH_WITHDRAWAL
    assert dec_restricted.action == ControlAction.RESTRICT
    assert dec_restricted.allowed is False
    assert "RESTRICTED" in dec_restricted.reason
    assert dec_restricted.held_amount == 100000.0


def test_scenario_c_confirmed_legitimate_clears_restrictions(test_env):
    """Scenario C: When A confirms transaction is legitimate:

    - Status becomes CONFIRMED_LEGITIMATE
    - Provisional restrictions are cleared
    - Subsequent cash withdrawals are evaluated under clean standard operations.
    """
    manager = test_env["manager"]
    store = test_env["store"]

    conf = manager.request_confirmation(
        transaction_id="TX-A-B-LEGIT",
        sender_id="ACC-CUSTOMER-A",
        beneficiary_id="ACC-VENDOR-B",
        amount=75000.0,
        case_id="CASE-LEGIT-1",
    )

    # Confirm legitimate
    updated = manager.submit_confirmation_response(
        confirmation_id=conf.confirmation_id,
        response_status=ConfirmationStatus.CONFIRMED_LEGITIMATE,
        notes="Customer verified payment for wedding catering via mobile app OTP",
    )

    assert updated["status"] == ConfirmationStatus.CONFIRMED_LEGITIMATE
    assert updated["outcome"] == "LEGITIMATE_CLEARED"
    assert updated["intervention_state"] == "UNENCUMBERED"

    # Verify standard withdrawal is now ALLOWED without pending holds
    dec = manager.evaluate_transaction_control(
        transaction_id="TX-ATM-60K",
        from_account="ACC-VENDOR-B",
        to_account="ATM-VENDOR-01",
        amount=60000.0,
        channel_or_type="ATM",
        existing_balance=80000.0,
    )
    assert dec.action == ControlAction.ALLOW
    assert dec.allowed is True
    assert dec.held_amount == 0.0


def test_scenario_d_confirmed_fraud_triggers_downstream_recovery_workflow(test_env):
    """Scenario D: When A confirms transaction is FRAUD:

    - Downstream chain A -> B -> C -> D is traced via GraphStore.
    - RecoveryWorkflowRecord is created with affected accounts and holds.
    - Subsequent transactions from affected accounts are RESTRICTED.
    """
    manager = test_env["manager"]
    graph_store = test_env["graph_store"]
    store = test_env["store"]

    # Populate GraphStore with downstream mule transactions
    # A -> B (₹100k)
    # B -> C (₹60k)
    # C -> D (₹55k)
    graph_store.add_transaction(
        TransactionEvent(
            transaction_id="TX-1",
            source_account_id="ACC-VICTIM-A",
            target_account_id="ACC-MULE-B",
            amount_inr=100000.0,
            payment_channel="IMPS",
            timestamp=datetime.now(timezone.utc),
            device_fingerprint="DEV-VICTIM",
        )
    )
    graph_store.add_transaction(
        TransactionEvent(
            transaction_id="TX-2",
            source_account_id="ACC-MULE-B",
            target_account_id="ACC-MULE-C",
            amount_inr=60000.0,
            payment_channel="UPI",
            timestamp=datetime.now(timezone.utc),
            device_fingerprint="DEV-MULE-B",
        )
    )
    graph_store.add_transaction(
        TransactionEvent(
            transaction_id="TX-3",
            source_account_id="ACC-MULE-C",
            target_account_id="ACC-MULE-D",
            amount_inr=55000.0,
            payment_channel="UPI",
            timestamp=datetime.now(timezone.utc),
            device_fingerprint="DEV-MULE-C",
        )
    )

    conf = manager.request_confirmation(
        transaction_id="TX-1",
        sender_id="ACC-VICTIM-A",
        beneficiary_id="ACC-MULE-B",
        amount=100000.0,
        case_id="CASE-FRAUD-99",
    )

    # Submit response: CONFIRMED_FRAUD
    resp = manager.submit_confirmation_response(
        confirmation_id=conf.confirmation_id,
        response_status=ConfirmationStatus.CONFIRMED_FRAUD,
        notes="Victim confirmed unauthorized APK remote-access screen sharing fraud",
    )

    assert resp["status"] == ConfirmationStatus.CONFIRMED_FRAUD
    assert resp["outcome"] == "FRAUD_ESCALATED"

    # Verify RecoveryWorkflow was created in Store
    workflow = store.get_recovery_workflow("REC-CASE-FRAUD-99")
    assert workflow is not None
    assert workflow["fraud_amount"] == 100000.0
    assert "ACC-MULE-B" in workflow["affected_accounts"]
    assert "ACC-MULE-C" in workflow["affected_accounts"]
    assert "ACC-MULE-D" in workflow["affected_accounts"]
    assert workflow["status"] == "INITIATED"

    # Evaluation on mule account should now be RESTRICTED
    dec = manager.evaluate_transaction_control(
        transaction_id="TX-EGRESS-D",
        from_account="ACC-MULE-B",
        to_account="ATM-01",
        amount=10000.0,
        channel_or_type="ATM",
    )
    assert dec.allowed is False
    assert dec.action == ControlAction.RESTRICT


def test_scenario_e_timeout_expiration_no_auto_fraud(test_env):
    """Scenario E: Pending confirmation window expires without response.

    - Transitions to EXPIRED
    - Does NOT falsely brand as fraud or freeze clean accounts
    - Audit log reflects timeout
    """
    manager = test_env["manager"]
    store = test_env["store"]

    conf = manager.request_confirmation(
        transaction_id="TX-TIMEOUT-TEST",
        sender_id="ACC-SENDER-1",
        beneficiary_id="ACC-RECV-1",
        amount=50000.0,
        timeout_seconds=0,  # Expire immediately
        case_id="CASE-EXP-1",
    )

    # Force expiration check
    expired_list = manager.check_timeouts()
    assert len(expired_list) >= 1
    assert any(e["confirmation_id"] == conf.confirmation_id for e in expired_list)

    reloaded = store.get_confirmation(conf.confirmation_id)
    assert reloaded["status"] == ConfirmationStatus.EXPIRED
    assert reloaded["outcome"] == "TIMEOUT_EXPIRED"


def test_scenario_f_idempotency_and_store_reloading(test_env):
    """Scenario F: Submitting same response multiple times is idempotent, and data survives new Store instances."""
    manager = test_env["manager"]
    db_path = test_env["db_path"]

    conf = manager.request_confirmation(
        transaction_id="TX-IDEMPOTENT-1",
        sender_id="ACC-1",
        beneficiary_id="ACC-2",
        amount=30000.0,
        case_id="CASE-IDEMP-1",
    )

    resp1 = manager.submit_confirmation_response(
        confirmation_id=conf.confirmation_id,
        response_status=ConfirmationStatus.CONFIRMED_LEGITIMATE,
        notes="First submission",
    )

    resp2 = manager.submit_confirmation_response(
        confirmation_id=conf.confirmation_id,
        response_status=ConfirmationStatus.CONFIRMED_LEGITIMATE,
        notes="Duplicate submission",
    )

    assert resp1["confirmation_id"] == resp2["confirmation_id"]
    assert resp1["status"] == resp2["status"]

    # Verify reloading from a fresh Store instance against same SQLite file
    fresh_store = Store(db_path=db_path)
    fresh_conf = fresh_store.get_confirmation(conf.confirmation_id)
    assert fresh_conf is not None
    assert fresh_conf["status"] == ConfirmationStatus.CONFIRMED_LEGITIMATE
    assert fresh_conf["amount_inr"] == 30000.0


def test_bank_api_confirmation_endpoints_via_server_handler(tmp_path):
    """Test HTTP API Handler routing for confirmations and transaction control evaluation."""
    import json
    import io
    from unittest.mock import MagicMock
    from mock_services.bank_api import server

    db_file = tmp_path / "test_api_bank.db"
    test_store = Store(db_path=db_file)
    test_ctrl = TransactionControlManager(store=test_store)

    # Patch global instances in server module for isolated test
    server._STORE = test_store
    server._CONTROL_MGR = test_ctrl

    # 1. POST /confirmations/request
    req_payload = {
        "transaction_id": "TX-API-001",
        "sender_id": "ACC-VICTIM-01",
        "beneficiary_id": "ACC-MULE-01",
        "amount": 95000.0,
        "reason": "Suspicious large transfer",
        "timeout_seconds": 600,
        "case_id": "CASE-API-001",
    }

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

    # Test POST /confirmations/request
    h_post_req = DummyHandler("POST", "/confirmations/request", json.dumps(req_payload))
    h_post_req.do_POST()
    assert h_post_req.status_code == 200
    res_req = json.loads(h_post_req.wfile.getvalue().decode("utf-8"))
    assert res_req["status"] == "SUCCESS"
    conf_id = res_req["confirmation"]["confirmation_id"]
    assert conf_id == "CONF-TX-API-001"

    # Test GET /confirmations/{id}
    h_get_conf = DummyHandler("GET", f"/confirmations/{conf_id}")
    h_get_conf.do_GET()
    assert h_get_conf.status_code == 200
    res_get = json.loads(h_get_conf.wfile.getvalue().decode("utf-8"))
    assert res_get["confirmation_id"] == conf_id
    assert res_get["status"] == ConfirmationStatus.PENDING_CONFIRMATION

    # Test POST /transaction-control/evaluate
    eval_payload = {
        "transaction_id": "TX-MULE-TRANSFER",
        "from_account": "ACC-MULE-01",
        "to_account": "ACC-MULE-02",
        "amount": 40000.0,
        "channel": "IMPS",
        "existing_balance": 10000.0,
    }
    h_eval = DummyHandler("POST", "/transaction-control/evaluate", json.dumps(eval_payload))
    h_eval.do_POST()
    assert h_eval.status_code == 200
    res_eval = json.loads(h_eval.wfile.getvalue().decode("utf-8"))
    assert res_eval["status"] == "SUCCESS"
    decision = res_eval["decision"]
    assert decision["channel"] == TransactionChannel.ONLINE_TRANSFER
    assert decision["allowed"] is True
    assert decision["action"] == ControlAction.MONITOR

    # Test POST /confirmations/{id}/respond -> CONFIRMED_FRAUD
    respond_payload = {
        "status": ConfirmationStatus.CONFIRMED_FRAUD,
        "notes": "Victim reported caller impersonated bank official",
    }
    h_resp = DummyHandler("POST", f"/confirmations/{conf_id}/respond", json.dumps(respond_payload))
    h_resp.do_POST()
    assert h_resp.status_code == 200
    res_resp = json.loads(h_resp.wfile.getvalue().decode("utf-8"))
    assert res_resp["status"] == "SUCCESS"
    assert res_resp["confirmation"]["status"] == ConfirmationStatus.CONFIRMED_FRAUD

    # Test GET /recovery-workflows
    h_rec = DummyHandler("GET", "/recovery-workflows")
    h_rec.do_GET()
    assert h_rec.status_code == 200
    res_rec = json.loads(h_rec.wfile.getvalue().decode("utf-8"))
    assert len(res_rec["recovery_workflows"]) >= 1
    assert res_rec["recovery_workflows"][0]["case_id"] == "CASE-API-001"
