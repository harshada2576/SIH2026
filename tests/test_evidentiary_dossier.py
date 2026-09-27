"""tests/test_evidentiary_dossier.py

Tests for Section 63 BSA / 65B IEA Electronic Evidence Dossier generation and validation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from export.evidentiary_dossier import generate_evidentiary_dossier


def test_evidentiary_dossier_generation_and_integrity(tmp_path):
    sample_case = {
        "ncrpId": "CMP-2026-981240",
        "flaggedAccountId": "ACC-MULE-88",
        "status": "BANK_HOLD",
        "suspiciousExposure": 185000.0,
        "protected_amount": 185000.0,
        "legitimateBalance": 24000.0,
        "risk_score": 0.88,
        "confidence": 0.92,
        "evidence": [
            "Smurfing: 4 structured transfers totaling ₹1,85,000",
            "Impossible travel: Mumbai to Hyderabad in 40m",
        ],
        "moneyTrail": [
            {"source_account_id": "ACC-VICTIM", "target_account_id": "ACC-MID1", "amount_inr": 92500.0, "payment_channel": "UPI", "transaction_id": "TXN-01"},
            {"source_account_id": "ACC-MID1", "target_account_id": "ACC-MULE-88", "amount_inr": 92500.0, "payment_channel": "IMPS", "transaction_id": "TXN-02"},
        ],
        "targetTerminal": {
            "id": "ATM-HDFC-BKC-001",
            "type": "ATM_KIOSK",
            "lat": 19.0760,
            "lon": 72.8777,
            "cash_status": "ONLINE_DISPENSING",
            "operating_hours": "24x7",
        },
        "corridor": {
            "corridor_id": "CORR-01",
            "waypoints": [
                {"terminal_id": "ATM-HDFC-BKC-001", "order": 1, "latitude": 19.0760, "longitude": 72.8777},
                {"terminal_id": "ATM-SBI-BKC-002", "order": 2, "latitude": 19.0810, "longitude": 72.8810},
            ]
        }
    }

    dossier = generate_evidentiary_dossier(sample_case, nodal_officer_id="NODAL-OFFICER-007")

    assert dossier.header.nodal_officer_id == "NODAL-OFFICER-007"
    assert "Section 63, Bharatiya Sakshya Adhiniyam" in dossier.header.legal_framework
    assert dossier.attribution.ncrp_complaint_id == "CMP-2026-981240"
    assert dossier.attribution.reported_loss_inr == 185000.0
    assert len(dossier.money_trail) == 2
    assert dossier.money_trail[0].transaction_id == "TXN-01"
    assert len(dossier.egress_forensics.corridor_route) == 2
    assert dossier.crypto_proof.merkle_root_hash is not None
    assert dossier.crypto_proof.digital_signature_hex is not None

    # Verify mathematical authenticity of the dossier
    assert dossier.verify_authenticity() is True
