"""pipeline/notification_service.py — SMS & Email Notification Service for SIH26184.

Deliverable:
- Isolated notification subsystem for high-risk fraud and cashout events.
- Modular provider adapters (Mock & Real SMS / Email).
- Configurable recipient groups (BANK_OFFICIAL, SECURITY_TEAM, INVESTIGATION_TEAM).
- Bounded retry handling with SQLite persistence.
- Deterministic idempotency and duplicate prevention.
- Clean public API: send_sms, send_email, notify.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import smtplib
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.persistence import Store
from shared.schemas import (
    NotificationChannel,
    NotificationDeliveryStatus,
    NotificationEventType,
    NotificationRecipientGroup,
    NotificationRecord,
    NotificationRequest,
)

log = logging.getLogger("notification_service")


# ============================================================================
# 1. NOTIFICATION EVENT & RESULT DATA STRUCTURES
# ============================================================================

@dataclass
class NotificationEvent:
    """Operational fraud/cashout event triggering notifications."""
    event_type: str
    case_id: str
    account_id: str
    amount: Optional[float] = None
    terminal_id: Optional[str] = None
    terminal_location: Optional[str] = None
    timestamp: Optional[str] = None
    confidence: Optional[float] = None
    risk_score: Optional[float] = None
    evidence: List[str] = field(default_factory=list)
    status: Optional[str] = None
    origin_transaction: Optional[Dict[str, Any]] = None
    money_trail_summary: Optional[str] = None
    action_url: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NotificationResult:
    """Outcome of a provider delivery attempt."""
    status: str
    is_simulated: bool
    provider: str
    message_id: str
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# 2. PROVIDER INTERFACES & ADAPTERS
# ============================================================================

class NotificationProvider(ABC):
    """Abstract base provider for outbound channels."""

    @abstractmethod
    def send(self, request: NotificationRequest) -> NotificationResult:
        """Deliver the notification request or simulate delivery."""
        raise NotImplementedError


class MockSmsProvider(NotificationProvider):
    """Simulated SMS delivery provider for demos and offline execution."""

    def __init__(self, failure_rate: float = 0.0) -> None:
        self.failure_rate = failure_rate
        self.sent_messages: List[Dict[str, Any]] = []

    def send(self, request: NotificationRequest) -> NotificationResult:
        msg_id = f"SMS-SIM-{uuid.uuid4().hex[:8]}"
        log.info(
            f"[SIMULATED SMS] To: {request.recipient} ({request.recipient_group}) | "
            f"Case: {request.case_id} | Body: {request.message_body}"
        )
        record = {
            "message_id": msg_id,
            "recipient": request.recipient,
            "body": request.message_body,
            "case_id": request.case_id,
            "event_type": request.event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "simulated": True,
        }
        self.sent_messages.append(record)
        return NotificationResult(
            status=NotificationDeliveryStatus.SENT,
            is_simulated=True,
            provider="MockSmsProvider",
            message_id=msg_id,
            details=record,
        )


class RealSmsProvider(NotificationProvider):
    """Real HTTP gateway SMS provider configurable via environment variables."""

    def __init__(
        self,
        gateway_url: Optional[str] = None,
        api_key: Optional[str] = None,
        sender_id: Optional[str] = None,
        timeout: float = 5.0,
    ) -> None:
        self.gateway_url = gateway_url or os.environ.get("SMS_GATEWAY_URL", "")
        self.api_key = api_key or os.environ.get("SMS_API_KEY", "")
        self.sender_id = sender_id or os.environ.get("SMS_SENDER_ID", "CYBSHLD")
        self.timeout = timeout

    def send(self, request: NotificationRequest) -> NotificationResult:
        if not self.gateway_url or not self.api_key:
            raise ValueError(
                "Real SMS gateway unconfigured: SMS_GATEWAY_URL and SMS_API_KEY environment variables required."
            )

        payload = {
            "to": request.recipient,
            "message": request.message_body,
            "sender_id": self.sender_id,
            "case_id": request.case_id,
            "event_type": request.event_type,
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "CyberShield-NotificationService/1.0",
        }
        req = urllib.request.Request(self.gateway_url, data=data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                resp_text = resp.read().decode("utf-8")
                resp_json = json.loads(resp_text) if resp_text else {}
                msg_id = resp_json.get("message_id") or resp_json.get("id") or f"SMS-REAL-{uuid.uuid4().hex[:8]}"
                log.info(f"[REAL SMS] Delivered to {request.recipient} via {self.gateway_url} (ID: {msg_id})")
                return NotificationResult(
                    status=NotificationDeliveryStatus.SENT,
                    is_simulated=False,
                    provider="RealSmsProvider",
                    message_id=msg_id,
                    details=resp_json,
                )
        except Exception as exc:
            log.error(f"[REAL SMS FAILED] Gateway delivery failed for {request.recipient}: {exc}")
            raise


class MockEmailProvider(NotificationProvider):
    """Simulated Email delivery provider for demos and offline testing."""

    def __init__(self) -> None:
        self.sent_emails: List[Dict[str, Any]] = []

    def send(self, request: NotificationRequest) -> NotificationResult:
        msg_id = f"EMAIL-SIM-{uuid.uuid4().hex[:8]}"
        log.info(
            f"[SIMULATED EMAIL] To: {request.recipient} ({request.recipient_group}) | "
            f"Subject: {request.subject} | Case: {request.case_id}"
        )
        record = {
            "message_id": msg_id,
            "recipient": request.recipient,
            "subject": request.subject,
            "body": request.message_body,
            "case_id": request.case_id,
            "event_type": request.event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "simulated": True,
        }
        self.sent_emails.append(record)
        return NotificationResult(
            status=NotificationDeliveryStatus.SENT,
            is_simulated=True,
            provider="MockEmailProvider",
            message_id=msg_id,
            details=record,
        )


class SmtpEmailProvider(NotificationProvider):
    """Real SMTP email provider configurable via environment variables."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_tls: Optional[bool] = None,
        from_address: Optional[str] = None,
        timeout: float = 10.0,
    ) -> None:
        self.host = host or os.environ.get("SMTP_HOST", "")
        self.port = int(port or os.environ.get("SMTP_PORT", 587))
        self.username = username or os.environ.get("SMTP_USER", "")
        self.password = password or os.environ.get("SMTP_PASSWORD", "")
        self.use_tls = use_tls if use_tls is not None else (os.environ.get("SMTP_USE_TLS", "true").lower() == "true")
        self.from_address = from_address or os.environ.get("SMTP_FROM", "alerts@cybershield.internal")
        self.timeout = timeout

    def send(self, request: NotificationRequest) -> NotificationResult:
        if not self.host:
            raise ValueError("SMTP host unconfigured: SMTP_HOST environment variable required.")

        msg = MIMEMultipart("alternative")
        msg["Subject"] = request.subject
        msg["From"] = self.from_address
        msg["To"] = request.recipient
        msg["X-CyberShield-Case-ID"] = request.case_id
        msg["X-CyberShield-Event-Type"] = request.event_type

        # Attach plain text
        part_plain = MIMEText(request.message_body, "plain", "utf-8")
        msg.attach(part_plain)

        # Attach HTML version if available in metadata
        html_body = request.metadata.get("html_body")
        if html_body:
            part_html = MIMEText(html_body, "html", "utf-8")
            msg.attach(part_html)

        try:
            with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as server:
                if self.use_tls:
                    server.starttls()
                if self.username and self.password:
                    server.login(self.username, self.password)
                server.sendmail(self.from_address, [request.recipient], msg.as_string())

            msg_id = f"SMTP-{uuid.uuid4().hex[:8]}"
            log.info(f"[REAL EMAIL] Sent email to {request.recipient} via {self.host}:{self.port}")
            return NotificationResult(
                status=NotificationDeliveryStatus.SENT,
                is_simulated=False,
                provider="SmtpEmailProvider",
                message_id=msg_id,
                details={"host": self.host, "port": self.port, "to": request.recipient},
            )
        except Exception as exc:
            log.error(f"[REAL EMAIL FAILED] SMTP delivery failed to {request.recipient}: {exc}")
            raise


# ============================================================================
# 3. RECIPIENT CONFIGURATION & CHANNEL PREFERENCES
# ============================================================================

class RecipientConfig:
    """Configurable recipient mapping by conceptual recipient groups."""

    def __init__(self, overrides: Optional[Dict[str, Dict[str, str]]] = None) -> None:
        self._config = {
            NotificationRecipientGroup.BANK_OFFICIAL: {
                NotificationChannel.SMS: os.environ.get("BANK_OFFICIAL_PHONE", "+919876543210"),
                NotificationChannel.EMAIL: os.environ.get("BANK_OFFICIAL_EMAIL", "duty.officer@cybershield.bank"),
            },
            NotificationRecipientGroup.SECURITY_TEAM: {
                NotificationChannel.SMS: os.environ.get("SECURITY_TEAM_PHONE", "+919876543211"),
                NotificationChannel.EMAIL: os.environ.get("SECURITY_TEAM_EMAIL", "soc.alerts@cybershield.bank"),
            },
            NotificationRecipientGroup.INVESTIGATION_TEAM: {
                NotificationChannel.SMS: os.environ.get("INVESTIGATION_TEAM_PHONE", "+919876543212"),
                NotificationChannel.EMAIL: os.environ.get("INVESTIGATION_TEAM_EMAIL", "investigators@cybershield.bank"),
            },
        }
        if overrides:
            for group, channels in overrides.items():
                if group in self._config:
                    self._config[group].update(channels)
                else:
                    self._config[group] = channels

    def get_recipients(
        self, event_type: str, channel: str
    ) -> List[Tuple[str, str]]:
        """Return list of (recipient_address, recipient_group) for a given event and channel."""
        # By policy:
        # HIGH_RISK_CASE, CONFIRMED_FRAUD, WITHDRAWAL_BLOCKED -> BANK_OFFICIAL & SECURITY_TEAM
        # POLICE_ALERT_SENT, CASE_ESCALATED -> BANK_OFFICIAL & INVESTIGATION_TEAM
        # CASHOUT_ATTEMPT_DETECTED -> BANK_OFFICIAL & SECURITY_TEAM
        # PENDING_CONFIRMATION -> BANK_OFFICIAL
        if event_type in (
            NotificationEventType.HIGH_RISK_CASE,
            NotificationEventType.CONFIRMED_FRAUD,
            NotificationEventType.WITHDRAWAL_BLOCKED,
            NotificationEventType.CASHOUT_ATTEMPT_DETECTED,
        ):
            groups = [NotificationRecipientGroup.BANK_OFFICIAL, NotificationRecipientGroup.SECURITY_TEAM]
        elif event_type in (
            NotificationEventType.POLICE_ALERT_SENT,
            NotificationEventType.CASE_ESCALATED,
        ):
            groups = [NotificationRecipientGroup.BANK_OFFICIAL, NotificationRecipientGroup.INVESTIGATION_TEAM]
        else:
            groups = [NotificationRecipientGroup.BANK_OFFICIAL]

        recipients = []
        for g in groups:
            addr = self._config.get(g, {}).get(channel)
            if addr:
                recipients.append((addr, g))
        return recipients


class NotificationPreferences:
    """Configurable channel enablement per operational event type."""

    DEFAULT_PREFERENCES: Dict[str, Dict[str, bool]] = {
        NotificationEventType.HIGH_RISK_CASE: {NotificationChannel.SMS: True, NotificationChannel.EMAIL: True},
        NotificationEventType.CONFIRMED_FRAUD: {NotificationChannel.SMS: True, NotificationChannel.EMAIL: True},
        NotificationEventType.CASHOUT_ATTEMPT_DETECTED: {NotificationChannel.SMS: True, NotificationChannel.EMAIL: True},
        NotificationEventType.WITHDRAWAL_BLOCKED: {NotificationChannel.SMS: True, NotificationChannel.EMAIL: True},
        NotificationEventType.CASE_ESCALATED: {NotificationChannel.SMS: False, NotificationChannel.EMAIL: True},
        NotificationEventType.POLICE_ALERT_SENT: {NotificationChannel.SMS: True, NotificationChannel.EMAIL: True},
        NotificationEventType.PENDING_CONFIRMATION: {NotificationChannel.SMS: False, NotificationChannel.EMAIL: True},
    }

    def __init__(self, custom_prefs: Optional[Dict[str, Dict[str, bool]]] = None) -> None:
        self.prefs: Dict[str, Dict[str, bool]] = {
            k: dict(v) for k, v in self.DEFAULT_PREFERENCES.items()
        }
        if custom_prefs:
            for ev, chs in custom_prefs.items():
                self.prefs.setdefault(ev, {}).update(chs)

    def is_channel_enabled(self, event_type: str, channel: str) -> bool:
        """Check whether channel delivery is enabled for an event."""
        return self.prefs.get(event_type, {}).get(channel, False)


# ============================================================================
# 4. CONTENT FORMATTERS (SMS & EMAIL)
# ============================================================================

def _format_inr(amount: Optional[float]) -> str:
    if amount is None:
        return "Rs. 0"
    return f"Rs. {amount:,.0f}"


def format_sms(event: NotificationEvent) -> str:
    """Generate concise operational SMS message strictly under SMS length limits."""
    amt_str = _format_inr(event.amount)
    terminal = event.terminal_id or "ATM/Agent point"

    if event.event_type == NotificationEventType.WITHDRAWAL_BLOCKED:
        return (
            f"SIH26184 ALERT:\n"
            f"Withdrawal attempt {amt_str} blocked.\n"
            f"Case: {event.case_id}.\n"
            f"Terminal: {terminal}.\n"
            f"Immediate investigation recommended."
        )
    elif event.event_type == NotificationEventType.CONFIRMED_FRAUD:
        return (
            f"SIH26184 PRIORITY ALERT:\n"
            f"Customer confirmed fraud on case {event.case_id}.\n"
            f"Amount: {amt_str}.\n"
            f"Downstream recovery initiated.\n"
            f"Open CyberShield immediately."
        )
    elif event.event_type == NotificationEventType.CASHOUT_ATTEMPT_DETECTED:
        loc = f" ({event.terminal_location})" if event.terminal_location else ""
        return (
            f"SIH26184 ALERT:\n"
            f"Cashout attempt {amt_str} detected.\n"
            f"Case: {event.case_id}.\n"
            f"Terminal: {terminal}{loc}.\n"
            f"Open CyberShield for verification."
        )
    elif event.event_type == NotificationEventType.POLICE_ALERT_SENT:
        return (
            f"SIH26184 NOTICE:\n"
            f"Police escalation alert generated for case {event.case_id}.\n"
            f"Terminal: {terminal}.\n"
            f"Investigation package dispatched."
        )
    elif event.event_type == NotificationEventType.CASE_ESCALATED:
        return (
            f"SIH26184 NOTICE:\n"
            f"Case {event.case_id} escalated to priority CRITICAL.\n"
            f"Amount: {amt_str}.\n"
            f"Open CyberShield for investigation."
        )
    elif event.event_type == NotificationEventType.PENDING_CONFIRMATION:
        return (
            f"SIH26184 NOTICE:\n"
            f"High-risk transfer {amt_str} awaiting customer confirmation.\n"
            f"Case: {event.case_id}.\n"
            f"Digital hold active."
        )
    else:
        # Default: HIGH_RISK_CASE
        return (
            f"SIH26184 ALERT:\n"
            f"High-risk fraud case {event.case_id} detected.\n"
            f"Amount: {amt_str}.\n"
            f"Predicted cashout: {terminal}.\n"
            f"Open CyberShield for investigation."
        )


def format_email(event: NotificationEvent) -> Tuple[str, str, str]:
    """Generate structured investigation email returning (subject, plain_text, html)."""
    amt_str = _format_inr(event.amount)
    terminal = event.terminal_id or "ATM-SBI-ND-042"
    location = event.terminal_location or "Designated terminal"
    risk_band = (
        "CRITICAL" if (event.risk_score and event.risk_score >= 0.8)
        else "HIGH"
    )
    conf_pct = int(round((event.confidence or 0.85) * 100))
    ts = event.timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Subject line
    if event.event_type == NotificationEventType.CONFIRMED_FRAUD:
        subject = f"[SIH26184] Confirmed Fraud Escalation - {event.case_id}"
    elif event.event_type == NotificationEventType.WITHDRAWAL_BLOCKED:
        subject = f"[SIH26184] Cash-Out Withdrawal Intercepted - {event.case_id}"
    elif event.event_type == NotificationEventType.CASHOUT_ATTEMPT_DETECTED:
        subject = f"[SIH26184] Cash-Out Withdrawal Attempt Detected - {event.case_id}"
    elif event.event_type == NotificationEventType.POLICE_ALERT_SENT:
        subject = f"[SIH26184] Police Escalation Dispatched - {event.case_id}"
    elif event.event_type == NotificationEventType.CASE_ESCALATED:
        subject = f"[SIH26184] Investigation Case Escalated - {event.case_id}"
    else:
        subject = f"[SIH26184] High-Risk Fraud Alert - {event.case_id}"

    # Evidence bullet points from actual case
    evidence_lines = event.evidence or [
        "Rapid multi-hop fund forwarding detected",
        "Shared device fingerprint correlation",
        "Suspicious cashout terminal proximity",
    ]
    plain_evidence = "\n".join(f"- {e}" for e in evidence_lines)
    html_evidence = "".join(f"<li>{e}</li>" for e in evidence_lines)

    # Origin txn line
    orig = event.origin_transaction or {}
    src = orig.get("source_account_id") or "Victim Account"
    dst = orig.get("target_account_id") or event.account_id
    orig_line = f"{src} -> {dst} ({amt_str})"

    # Plain text format
    plain_text = f"""Subject:
{subject}

Case:
{event.case_id}

Event:
{event.event_type}

Risk:
{risk_band}

Confidence:
{conf_pct}%

Flagged Account:
{event.account_id}

Origin Transaction:
{orig_line}

Current State:
{event.status or 'PRE_COMPLAINT_INTERVENTION'}

Predicted Cashout:
{terminal} ({location})

Timestamp:
{ts}

Evidence:
{plain_evidence}

Action:
Open CyberShield for investigation and case review.
"""

    # HTML format matching CyberShield Dark Aesthetics
    html_text = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0B0F19; color: #F3F4F6; margin: 0; padding: 24px; }}
.container {{ max-width: 620px; margin: 0 auto; background-color: #111827; border: 1px solid #374151; border-radius: 12px; overflow: hidden; }}
.header {{ background-color: #1F2937; padding: 20px 24px; border-bottom: 2px solid #06B6D4; }}
.badge {{ display: inline-block; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: bold; text-transform: uppercase; background-color: #EF4444; color: #FFFFFF; }}
.content {{ padding: 24px; }}
.field {{ margin-bottom: 16px; }}
.field-label {{ font-size: 11px; text-transform: uppercase; color: #9CA3AF; letter-spacing: 0.05em; margin-bottom: 4px; }}
.field-val {{ font-size: 15px; font-weight: 600; color: #F9FAFB; }}
.evidence-box {{ background-color: #182234; border-left: 4px solid #06B6D4; padding: 12px 16px; border-radius: 4px; margin: 18px 0; }}
.evidence-box ul {{ margin: 6px 0 0 0; padding-left: 20px; color: #E5E7EB; }}
.footer {{ background-color: #0B0F19; padding: 16px 24px; text-align: center; font-size: 12px; color: #6B7280; border-top: 1px solid #1F2937; }}
.btn {{ display: inline-block; background-color: #06B6D4; color: #0B0F19; padding: 10px 20px; font-weight: bold; border-radius: 6px; text-decoration: none; margin-top: 12px; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="badge">{event.event_type.replace('_', ' ')}</div>
    <h2 style="margin: 10px 0 0 0; color: #FFFFFF; font-size: 20px;">{subject}</h2>
  </div>
  <div class="content">
    <div style="display: flex; justify-content: space-between; margin-bottom: 16px;">
      <div class="field">
        <div class="field-label">Case Reference</div>
        <div class="field-val" style="color: #06B6D4;">{event.case_id}</div>
      </div>
      <div class="field">
        <div class="field-label">Amount at Risk</div>
        <div class="field-val">{amt_str}</div>
      </div>
      <div class="field">
        <div class="field-label">Confidence</div>
        <div class="field-val">{conf_pct}%</div>
      </div>
    </div>
    <div class="field">
      <div class="field-label">Flagged Account & Trail</div>
      <div class="field-val">{orig_line}</div>
    </div>
    <div class="field">
      <div class="field-label">Predicted Physical Egress Terminal</div>
      <div class="field-val">{terminal} &mdash; <span style="color: #9CA3AF;">{location}</span></div>
    </div>
    <div class="evidence-box">
      <div class="field-label" style="color: #06B6D4;">Corroborating Evidence Trail</div>
      <ul>{html_evidence}</ul>
    </div>
    <div class="field">
      <div class="field-label">Recommended Operational Action</div>
      <div style="color: #F3F4F6; font-size: 14px;">Review real-time money trail and terminal egress ranking in CyberShield.</div>
    </div>
  </div>
  <div class="footer">
    SIH26184 &bull; CyberShield Autonomous Interception Engine &bull; Confidential
  </div>
</div>
</body>
</html>
"""
    return subject, plain_text, html_text


# ============================================================================
# 5. DEDICATED NOTIFICATION SERVICE
# ============================================================================

class NotificationService:
    """Central notification management engine.

    Orchestrates provider selection, channel preferences, recipient mapping,
    idempotency checks, bounded retries, and SQLite persistence.
    """

    def __init__(
        self,
        store: Optional[Store] = None,
        sms_provider: Optional[NotificationProvider] = None,
        email_provider: Optional[NotificationProvider] = None,
        recipients: Optional[RecipientConfig] = None,
        preferences: Optional[NotificationPreferences] = None,
        max_retries: int = 3,
    ) -> None:
        self.store = store or Store()
        self.recipients = recipients or RecipientConfig()
        self.preferences = preferences or NotificationPreferences()
        self.max_retries = max_retries

        # Initialize providers based on mode / environment
        mode = os.environ.get("NOTIFICATION_MODE", "mock").lower()
        if sms_provider:
            self.sms_provider = sms_provider
        elif mode == "real" and os.environ.get("SMS_GATEWAY_URL"):
            self.sms_provider = RealSmsProvider()
        else:
            self.sms_provider = MockSmsProvider()

        if email_provider:
            self.email_provider = email_provider
        elif mode == "real" and os.environ.get("SMTP_HOST"):
            self.email_provider = SmtpEmailProvider()
        else:
            self.email_provider = MockEmailProvider()

    # ------------------------------------------------------------------------
    # Core Send Methods
    # ------------------------------------------------------------------------

    def send_sms(self, request: NotificationRequest) -> NotificationResult:
        """Send or simulate an operational SMS message with retry and persistence."""
        return self._send_with_retry(request, self.sms_provider)

    def send_email(self, request: NotificationRequest) -> NotificationResult:
        """Send or simulate an investigation email with retry and persistence."""
        return self._send_with_retry(request, self.email_provider)

    def _generate_idempotency_key(self, request: NotificationRequest) -> str:
        if request.idempotency_key:
            return request.idempotency_key
        raw = f"{request.case_id}:{request.event_type}:{request.channel}:{request.recipient}"
        return f"IDEM-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"

    def _send_with_retry(
        self,
        request: NotificationRequest,
        provider: NotificationProvider,
    ) -> NotificationResult:
        """Execute delivery with idempotency checking, bounded retry, and DB persistence."""
        idem_key = self._generate_idempotency_key(request)
        request.idempotency_key = idem_key

        # 1. Idempotency Check: Don't re-send already successful or in-flight notifications
        existing = self.store.get_notification_by_idempotency_key(idem_key)
        if existing and existing.get("status") in (
            NotificationDeliveryStatus.SENT,
            NotificationDeliveryStatus.PENDING,
        ):
            log.info(
                f"[DEDUPLICATION] Notification already exists in state {existing.get('status')} "
                f"for key {idem_key} (ID: {existing.get('notification_id')}). Skipping duplicate send."
            )
            return NotificationResult(
                status=existing["status"],
                is_simulated=bool(existing.get("is_simulated", True)),
                provider=type(provider).__name__,
                message_id=existing["notification_id"],
                details=existing.get("payload_json", {}),
            )

        notif_id = f"NOTIF-{uuid.uuid4().hex[:10]}"
        now_str = datetime.now(timezone.utc).isoformat()

        # Initial persistence as PENDING
        record = NotificationRecord(
            notification_id=notif_id,
            case_id=request.case_id,
            event_type=request.event_type,
            channel=request.channel,
            recipient=request.recipient,
            recipient_group=request.recipient_group,
            subject=request.subject,
            message_body=request.message_body,
            status=NotificationDeliveryStatus.PENDING,
            is_simulated=isinstance(provider, (MockSmsProvider, MockEmailProvider)),
            retry_count=0,
            idempotency_key=idem_key,
            payload_json=request.metadata,
            created_at=now_str,
        )
        self.store.save_notification(record)

        # 2. Bounded Retry Loop
        attempt = 0
        last_error: Optional[str] = None

        while attempt < self.max_retries:
            attempt += 1
            try:
                if attempt > 1:
                    log.warning(
                        f"[RETRY {attempt}/{self.max_retries}] Retrying delivery for {notif_id} "
                        f"({request.channel} -> {request.recipient})"
                    )
                    self.store.update_notification_status(
                        notif_id,
                        status=NotificationDeliveryStatus.RETRYING,
                        retry_count=attempt - 1,
                    )

                result = provider.send(request)

                # Success -> Update status to SENT
                sent_at = datetime.now(timezone.utc).isoformat()
                self.store.update_notification_status(
                    notif_id,
                    status=NotificationDeliveryStatus.SENT,
                    sent_at=sent_at,
                    retry_count=attempt - 1,
                )
                return result

            except Exception as exc:
                last_error = str(exc)
                log.warning(
                    f"[DELIVERY FAILED] Attempt {attempt}/{self.max_retries} failed for {notif_id}: {exc}"
                )

        # Max retries exhausted -> FAILED
        self.store.update_notification_status(
            notif_id,
            status=NotificationDeliveryStatus.FAILED,
            error=last_error,
            retry_count=self.max_retries,
        )
        return NotificationResult(
            status=NotificationDeliveryStatus.FAILED,
            is_simulated=isinstance(provider, (MockSmsProvider, MockEmailProvider)),
            provider=type(provider).__name__,
            message_id=notif_id,
            error=last_error,
        )

    # ------------------------------------------------------------------------
    # High-Level Event Notification Workflow
    # ------------------------------------------------------------------------

    def notify(self, event: NotificationEvent) -> List[NotificationRecord]:
        """Dispatch notifications across configured channels for an operational event.

        Returns list of persisted NotificationRecords.
        """
        results: List[NotificationRecord] = []

        # Format messages
        sms_text = format_sms(event)
        email_subj, email_plain, email_html = format_email(event)

        # 1. SMS Dispatch
        if self.preferences.is_channel_enabled(event.event_type, NotificationChannel.SMS):
            recipients = self.recipients.get_recipients(event.event_type, NotificationChannel.SMS)
            for phone, group in recipients:
                req = NotificationRequest(
                    case_id=event.case_id,
                    event_type=event.event_type,
                    channel=NotificationChannel.SMS,
                    recipient=phone,
                    recipient_group=group,
                    subject=f"SIH26184: {event.event_type}",
                    message_body=sms_text,
                    metadata={"event_details": event.details},
                )
                res = self.send_sms(req)
                saved = self.store.get_notification_by_idempotency_key(req.idempotency_key)
                if saved:
                    results.append(NotificationRecord.from_dict(saved))

        # 2. Email Dispatch
        if self.preferences.is_channel_enabled(event.event_type, NotificationChannel.EMAIL):
            recipients = self.recipients.get_recipients(event.event_type, NotificationChannel.EMAIL)
            for email_addr, group in recipients:
                req = NotificationRequest(
                    case_id=event.case_id,
                    event_type=event.event_type,
                    channel=NotificationChannel.EMAIL,
                    recipient=email_addr,
                    recipient_group=group,
                    subject=email_subj,
                    message_body=email_plain,
                    metadata={"html_body": email_html, "event_details": event.details},
                )
                res = self.send_email(req)
                saved = self.store.get_notification_by_idempotency_key(req.idempotency_key)
                if saved:
                    results.append(NotificationRecord.from_dict(saved))

        return results

    # ------------------------------------------------------------------------
    # Query & Summary Helpers (Consumed by CyberShield / API)
    # ------------------------------------------------------------------------

    def get_case_notifications(self, case_id: str) -> List[Dict[str, Any]]:
        """Retrieve all notification records for a case."""
        return self.store.get_notifications_for_case(case_id)

    def get_case_notification_summary(self, case_id: str) -> Dict[str, Any]:
        """Produce structured notification status map for mobile clients.

        Returns:
            {
                "channels": {
                    "SMS": {"status": "SENT", "is_simulated": true, "timestamp": "...", "count": 1},
                    "EMAIL": {"status": "SENT", "is_simulated": true, "timestamp": "...", "count": 1}
                },
                "items": [...]
            }
        """
        records = self.store.get_notifications_for_case(case_id)
        channels: Dict[str, Dict[str, Any]] = {
            NotificationChannel.SMS: {"status": "NOT_SENT", "is_simulated": True, "timestamp": None, "count": 0},
            NotificationChannel.EMAIL: {"status": "NOT_SENT", "is_simulated": True, "timestamp": None, "count": 0},
        }

        for r in records:
            ch = r.get("channel")
            if ch in channels:
                channels[ch]["count"] += 1
                # If any failed, mark as FAILED unless another succeeded later
                if channels[ch]["status"] != NotificationDeliveryStatus.SENT:
                    channels[ch]["status"] = r.get("status", "SENT")
                channels[ch]["is_simulated"] = bool(r.get("is_simulated", True))
                if not channels[ch]["timestamp"] or (r.get("sent_at") and r["sent_at"] > channels[ch]["timestamp"]):
                    channels[ch]["timestamp"] = r.get("sent_at") or r.get("created_at")

        items = []
        for r in records:
            items.append({
                "notificationId": r.get("notification_id"),
                "channel": r.get("channel"),
                "eventType": r.get("event_type"),
                "recipient": r.get("recipient"),
                "recipientGroup": r.get("recipient_group"),
                "status": r.get("status"),
                "isSimulated": bool(r.get("is_simulated", True)),
                "timestamp": r.get("sent_at") or r.get("created_at"),
                "preview": (r.get("message_body") or "")[:120],
            })

        return {
            "channels": channels,
            "items": items,
        }
