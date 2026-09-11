"""Integration tests for dynamic LAN discovery, FastAPI REST endpoints, and WebSocket broadcasting."""
import asyncio
import json
import socket
import pytest
from fastapi.testclient import TestClient

from api.discovery import DiscoveryService, get_all_lan_ips, get_primary_lan_ip
from api.server import app, ENGINE


@pytest.fixture
def client():
    return TestClient(app)


def test_lan_ip_detection():
    ip = get_primary_lan_ip()
    assert isinstance(ip, str)
    assert len(ip.split(".")) == 4
    all_ips = get_all_lan_ips()
    assert len(all_ips) >= 1
    assert ip in all_ips


def test_discovery_service_lifecycle():
    service = DiscoveryService(port=5003, service_name="CyberShield-Test")
    service.start()
    assert service.running is True

    # Test UDP discovery ping
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2.0)
    sock.sendto(b"CYBERSHIELD_DISCOVER\n", ("127.0.0.1", 8888))
    data, _ = sock.recvfrom(2048)
    text = data.decode("utf-8")
    assert "CYBERSHIELD_BACKEND:" in text
    payload = json.loads(text.replace("CYBERSHIELD_BACKEND:", "").strip())
    assert payload["service"] == "cybershield"
    assert payload["port"] == 5003
    sock.close()

    service.stop()
    assert service.running is False


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["status"] == "ONLINE"
    assert data["cases"] >= 1


def test_cases_endpoint_bank_and_police(client):
    res_bank = client.get("/cases?role=BANK")
    assert res_bank.status_code == 200
    cases_bank = res_bank.json()["cases"]
    assert len(cases_bank) >= 1

    res_police = client.get("/cases?role=POLICE")
    assert res_police.status_code == 200
    cases_police = res_police.json()["cases"]
    assert isinstance(cases_police, list)


def test_terminals_and_audit(client):
    t_res = client.get("/terminals")
    assert t_res.status_code == 200
    assert len(t_res.json()["terminals"]) >= 1

    a_res = client.get("/audit")
    assert a_res.status_code == 200
    assert isinstance(a_res.json()["audit"], list)


def test_case_action_escalate_and_hold(client):
    cases = client.get("/cases?role=BANK").json()["cases"]
    target_id = cases[0]["ncrpId"]

    # Act hold
    hold_res = client.post(f"/cases/{target_id}/hold", json={"officer": "Tester"})
    assert hold_res.status_code == 200
    assert hold_res.json()["status"] == "BANK_HOLD"
    assert hold_res.json()["digitalBlockActive"] is True

    # Act escalate
    esc_res = client.post(f"/cases/{target_id}/escalate", json={"officer": "Tester"})
    assert esc_res.status_code == 200
    assert esc_res.json()["status"] == "APPROVED"
    assert esc_res.json()["atmBlockActive"] is True


def test_websocket_connection_and_broadcast(client):
    with client.websocket_connect("/ws") as ws1:
        # Handshake ACK received
        msg = ws1.receive_json()
        assert msg["type"] == "HANDSHAKE_ACK"
        assert msg["server"] == "CyberShield SIH26184"

        # Ping
        ws1.send_json({"action": "PING"})
        pong = ws1.receive_json()
        assert pong["type"] == "PONG"

        # Trigger action and receive broadcast
        cases = client.get("/cases?role=BANK").json()["cases"]
        target_id = cases[0]["ncrpId"]
        client.post(f"/cases/{target_id}/hold", json={"officer": "WS_Tester"})

        update_event = ws1.receive_json()
        assert update_event["type"] == "CASE_UPDATED"
        assert update_event["data"]["ncrpId"] == target_id


def test_multi_client_concurrent_websockets(client):
    """Verify that 3-5 concurrent clients all receive live broadcasts simultaneously."""
    with client.websocket_connect("/ws") as ws1, \
         client.websocket_connect("/ws") as ws2, \
         client.websocket_connect("/ws") as ws3:
        
        # All receive handshakes
        assert ws1.receive_json()["type"] == "HANDSHAKE_ACK"
        assert ws2.receive_json()["type"] == "HANDSHAKE_ACK"
        assert ws3.receive_json()["type"] == "HANDSHAKE_ACK"

        # Trigger live fraud demo alert
        res = client.post("/demo/trigger_fraud")
        assert res.status_code == 200

        # All 3 clients must receive the NEW_ALERT broadcast
        e1 = ws1.receive_json()
        e2 = ws2.receive_json()
        e3 = ws3.receive_json()

        assert e1["type"] == "NEW_ALERT"
        assert e2["type"] == "NEW_ALERT"
        assert e3["type"] == "NEW_ALERT"
        assert e1["data"]["case"]["ncrpId"] == e2["data"]["case"]["ncrpId"] == e3["data"]["case"]["ncrpId"]
