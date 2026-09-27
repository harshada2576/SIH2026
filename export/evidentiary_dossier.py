"""export/evidentiary_dossier.py — Section 63 BSA / 65B IEA Compliant Electronic Evidence Dossier.

Generates mathematically verifiable, tamper-evident legal dossiers for LEA charge-sheeting,
prosecutorial filing, and judicial presentation under Bharatiya Sakshya Adhiniyam, 2023 (Section 63)
and Indian Evidence Act, 1872 (Section 65B).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from audit.merkle_ledger import MerkleAuditLedger, MerkleAuditProof, _canonical_json, _sha256
from shared.schemas import CaseRecord, RiskAlert


@dataclass
class DossierHeader:
    dossier_id: str
    legal_framework: str = "Section 63, Bharatiya Sakshya Adhiniyam (BSA), 2023 & Section 65B, Indian Evidence Act, 1872"
    generated_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    issuing_authority: str = "Indian Cyber Crime Coordination Centre (I4C) / MHA"
    nodal_officer_id: str = "OFFICER-I4C-CYBERSHIELD"
    system_identifier: str = "CyberShield Predictive Egress Analytics Engine v2.0"


@dataclass
class CaseAttribution:
    ncrp_complaint_id: str
    flagged_account_id: str
    risk_score_percent: float
    confidence_percent: float
    risk_band: str
    reported_loss_inr: float
    protected_amount_inr: float
    legitimate_balance_inr: float


@dataclass
class ForensicHop:
    hop_index: int
    transaction_id: str
    source_account: str
    target_account: str
    amount_inr: float
    channel: str
    timestamp: str
    leg_sha256: str


@dataclass
class EgressForensics:
    primary_terminal_id: str
    terminal_type: str
    latitude: float
    longitude: float
    predicted_window_start: str
    predicted_window_end: str
    corridor_route: List[Dict[str, Any]] = field(default_factory=list)
    operational_telemetry: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CryptographicProofBundle:
    merkle_root_hash: str
    leaf_sha256: str
    merkle_inclusion_proof: Optional[Dict[str, Any]]
    dossier_sha256_digest: str
    digital_signature_hex: str
    signing_algorithm: str = "Ed25519 / SHA-256"


@dataclass
class EvidentiaryDossier:
    """Complete, self-contained electronic evidence certificate for judicial scrutiny."""
    header: DossierHeader
    attribution: CaseAttribution
    evidence_signals: List[str]
    money_trail: List[ForensicHop]
    egress_forensics: EgressForensics
    crypto_proof: CryptographicProofBundle

    def to_dict(self) -> Dict[str, Any]:
        return {
            "header": asdict(self.header),
            "attribution": asdict(self.attribution),
            "evidence_signals": list(self.evidence_signals),
            "money_trail": [asdict(h) for h in self.money_trail],
            "egress_forensics": asdict(self.egress_forensics),
            "crypto_proof": asdict(self.crypto_proof),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def verify_authenticity(self) -> bool:
        """Mathematically verifies the internal digest and Merkle proof integrity."""
        content = {
            "header": asdict(self.header),
            "attribution": asdict(self.attribution),
            "evidence_signals": self.evidence_signals,
            "money_trail": [asdict(h) for h in self.money_trail],
            "egress_forensics": asdict(self.egress_forensics),
        }
        computed_digest = _sha256(_canonical_json(content))
        if computed_digest != self.crypto_proof.dossier_sha256_digest:
            return False

        if self.crypto_proof.merkle_inclusion_proof:
            proof = MerkleAuditProof.from_dict(self.crypto_proof.merkle_inclusion_proof)
            return proof.verify()
        return True


def generate_evidentiary_dossier(
    case_data: Dict[str, Any] | CaseRecord,
    merkle_ledger: Optional[MerkleAuditLedger] = None,
    nodal_officer_id: str = "OFFICER-I4C-CYBERSHIELD",
) -> EvidentiaryDossier:
    """Constructs a Section 63 BSA / 65B Electronic Evidence Dossier."""
    if hasattr(case_data, "to_dict"):
        data = case_data.to_dict()
    else:
        data = dict(case_data)

    case_id = data.get("ncrpId") or data.get("case_id") or data.get("complaint_id", "CASE-UNKNOWN")
    now_utc = datetime.now(timezone.utc).isoformat()

    header = DossierHeader(
        dossier_id=f"BSA-DOSSIER-{case_id}-{int(datetime.now(timezone.utc).timestamp())}",
        generated_at_utc=now_utc,
        nodal_officer_id=nodal_officer_id,
    )

    loss_val = data.get("suspiciousExposure") or data.get("suspicious_amount", 0.0)
    prot_val = data.get("protected_amount", loss_val)
    legit_val = data.get("legitimateBalance") or data.get("existing_balance", 0.0)
    risk_score = data.get("risk_score") or (data.get("riskBreakdown", {}).get("totalPercent", 80) / 100.0)
    conf_score = data.get("confidence") or (data.get("confidencePercent", 85) / 100.0)

    attribution = CaseAttribution(
        ncrp_complaint_id=case_id,
        flagged_account_id=data.get("flaggedAccountId") or data.get("flagged_account_id", ""),
        risk_score_percent=round(risk_score * 100.0, 1),
        confidence_percent=round(conf_score * 100.0, 1),
        risk_band=data.get("band") or data.get("priority", "HIGH"),
        reported_loss_inr=float(loss_val),
        protected_amount_inr=float(prot_val),
        legitimate_balance_inr=float(legit_val),
    )

    raw_trail = data.get("moneyTrail") or data.get("money_trail", [])
    trail_hops: List[ForensicHop] = []
    if isinstance(raw_trail, list):
        for idx, leg in enumerate(raw_trail):
            if isinstance(leg, dict):
                src = leg.get("source_account_id") or leg.get("source", "UNKNOWN")
                tgt = leg.get("target_account_id") or leg.get("target", "UNKNOWN")
                amt = float(leg.get("amount_inr") or leg.get("amount", 0.0))
                chn = leg.get("payment_channel") or leg.get("channel", "UPI")
                ts = leg.get("timestamp", now_utc)
                tx_id = leg.get("transaction_id") or f"TXN-{idx}"
            else:
                src, tgt, amt, chn, ts, tx_id = "ACC-A", "ACC-B", 0.0, "UPI", now_utc, f"TXN-{idx}"

            leg_hash = _sha256(f"{tx_id}|{src}|{tgt}|{amt}|{chn}|{ts}")
            trail_hops.append(
                ForensicHop(
                    hop_index=idx + 1,
                    transaction_id=tx_id,
                    source_account=src,
                    target_account=tgt,
                    amount_inr=amt,
                    channel=chn,
                    timestamp=ts,
                    leg_sha256=leg_hash,
                )
            )

    target_term = data.get("targetTerminal") or (data.get("predicted_terminals", [{}])[0] if data.get("predicted_terminals") else {})
    corridor_data = data.get("corridor") or {}
    waypoints = corridor_data.get("waypoints", []) if isinstance(corridor_data, dict) else []

    egress = EgressForensics(
        primary_terminal_id=target_term.get("id") or target_term.get("terminal_id", "ATM-UNKNOWN"),
        terminal_type=target_term.get("type") or target_term.get("terminal_type", "ATM_KIOSK"),
        latitude=float(target_term.get("lat") or target_term.get("latitude", 0.0)),
        longitude=float(target_term.get("lon") or target_term.get("longitude", 0.0)),
        predicted_window_start=data.get("predicted_window_start", now_utc),
        predicted_window_end=data.get("predicted_window_end", now_utc),
        corridor_route=waypoints,
        operational_telemetry={
            "cash_status": target_term.get("cash_status", "ONLINE_DISPENSING"),
            "operating_hours": target_term.get("operating_hours", "24x7"),
        },
    )

    evidence_signals = data.get("evidence", [])

    # Calculate deterministic digest of the factual content
    core_content = {
        "header": asdict(header),
        "attribution": asdict(attribution),
        "evidence_signals": evidence_signals,
        "money_trail": [asdict(h) for h in trail_hops],
        "egress_forensics": asdict(egress),
    }
    dossier_digest = _sha256(_canonical_json(core_content))

    # Retrieve or generate Merkle inclusion proof
    ledger = merkle_ledger or MerkleAuditLedger()
    proof_tuple = ledger.get_proof_for_case(case_id)

    if proof_tuple:
        merkle_block, merkle_proof = proof_tuple
        root_hash = merkle_block.merkle_root
        proof_dict = merkle_proof.to_dict()
    else:
        # Commit current dossier digest to Merkle ledger to anchor it
        committed_block = ledger.commit_batch([{"case_id": case_id, "dossier_digest": dossier_digest, "timestamp": now_utc}])
        tree = MerkleAuditLedger()
        root_hash = committed_block.merkle_root
        proof_dict = {
            "leaf_hash": _sha256(_canonical_json({"case_id": case_id, "dossier_digest": dossier_digest, "timestamp": now_utc})),
            "leaf_index": 0,
            "root_hash": root_hash,
            "tree_size": 1,
            "steps": [],
            "timestamp": now_utc,
        }

    # Generate cryptographic signature over dossier digest
    sig_hex = ledger._private_key.sign(dossier_digest.encode("utf-8")).hex()

    crypto = CryptographicProofBundle(
        merkle_root_hash=root_hash,
        leaf_sha256=dossier_digest,
        merkle_inclusion_proof=proof_dict,
        dossier_sha256_digest=dossier_digest,
        digital_signature_hex=sig_hex,
    )

    return EvidentiaryDossier(
        header=header,
        attribution=attribution,
        evidence_signals=evidence_signals,
        money_trail=trail_hops,
        egress_forensics=egress,
        crypto_proof=crypto,
    )
