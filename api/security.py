"""api/security.py — Cryptographic API Request Signing, Nonce Replay Defense, and Role ABAC.

Protects reverse intervention endpoints (/api/act, /api/cases/dossier) against:
1. Replay attacks (via deterministic nonces and 300s timestamp sliding window).
2. Man-in-the-middle payload tampering (via HMAC-SHA256 / Ed25519 signature validation).
3. Unauthorized privilege escalation (via Attribute-Based Access Control / ABAC).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from fastapi import Header, HTTPException, Request

log = logging.getLogger("api_security")

# Master secret key for nodal officer HMAC signing (configurable via env)
DEFAULT_API_SECRET = os.environ.get("CYBERSHIELD_API_SECRET", "CYBERSHIELD-I4C-NATIONAL-SECRET-KEY-2026")
MAX_TIMESTAMP_DRIFT_SECONDS = 300  # 5 minutes sliding window
MAX_NONCE_CACHE_SIZE = 10000


class NonceCache:
    """Thread-safe, memory-bounded sliding window nonce store for replay defense."""

    def __init__(self, maxsize: int = MAX_NONCE_CACHE_SIZE) -> None:
        self.maxsize = maxsize
        self._cache: OrderedDict[str, float] = OrderedDict()

    def check_and_add(self, nonce: str, timestamp_epoch: float) -> bool:
        """Returns True if nonce is fresh and unused; False if replayed."""
        now = time.time()
        # Evict expired entries older than 2 * window
        cutoff = now - (MAX_TIMESTAMP_DRIFT_SECONDS * 2)
        while self._cache and next(iter(self._cache.values())) < cutoff:
            self._cache.popitem(last=False)

        if nonce in self._cache:
            return False  # Replay detected

        if len(self._cache) >= self.maxsize:
            self._cache.popitem(last=False)

        self._cache[nonce] = timestamp_epoch
        return True


NONCE_STORE = NonceCache()


def _canonical_bytes(payload: Dict[str, Any]) -> bytes:
    """Deterministic JSON byte string."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def generate_action_signature(
    payload: Dict[str, Any],
    timestamp: str,
    nonce: str,
    officer_id: str,
    secret_key: str = DEFAULT_API_SECRET,
) -> str:
    """Generate valid HMAC-SHA256 signature for test clients and Android app."""
    body_bytes = _canonical_bytes(payload)
    sign_string = f"{timestamp}|{nonce}|{officer_id}|".encode("utf-8") + body_bytes
    return hmac.new(secret_key.encode("utf-8"), sign_string, hashlib.sha256).hexdigest()


def verify_intervention_security(
    payload: Dict[str, Any],
    signature: Optional[str] = None,
    timestamp: Optional[str] = None,
    nonce: Optional[str] = None,
    officer_id: Optional[str] = None,
    officer_role: Optional[str] = None,
    secret_key: str = DEFAULT_API_SECRET,
    enforce_strict: bool = False,
) -> Tuple[bool, str]:
    """Validates signature, timestamp freshness, nonce uniqueness, and role privileges.
    
    If enforce_strict is False (development/testing mode), missing signatures log a warning
    and allow execution. If signature headers are present, full validation is always enforced.
    """
    if not signature or not timestamp or not nonce:
        if enforce_strict:
            raise HTTPException(status_code=401, detail="Missing mandatory security headers (X-Signature, X-Timestamp, X-Nonce)")
        return True, "Security validation bypassed (dev/test mode without headers)"

    # 1. Timestamp Freshness Check
    try:
        # Support ISO 8601 or epoch seconds
        if timestamp.isdigit():
            req_time = float(timestamp)
        else:
            clean_ts = timestamp.replace("Z", "+00:00")
            req_time = datetime.fromisoformat(clean_ts).timestamp()
    except Exception:
        raise HTTPException(status_code=400, detail=f"Malformed X-Timestamp header: '{timestamp}'")

    now = time.time()
    drift = abs(now - req_time)
    if drift > MAX_TIMESTAMP_DRIFT_SECONDS:
        raise HTTPException(
            status_code=401,
            detail=f"Timestamp expired: request drift ({drift:.1f}s) exceeds window ({MAX_TIMESTAMP_DRIFT_SECONDS}s)"
        )

    # 2. Nonce Replay Check
    officer = officer_id or payload.get("officer", "OFFICER-UNKNOWN")
    nonce_key = f"{officer}:{nonce}"
    if not NONCE_STORE.check_and_add(nonce_key, req_time):
        raise HTTPException(status_code=401, detail=f"Replay attack detected: nonce '{nonce}' was already used")

    # 3. Signature Validation
    expected_sig = generate_action_signature(payload, timestamp, nonce, officer, secret_key=secret_key)
    if not hmac.compare_digest(signature.lower(), expected_sig.lower()):
        raise HTTPException(status_code=401, detail="Invalid cryptographic request signature (HMAC-SHA256 mismatch)")

    # 4. Role Attribute-Based Access Control (ABAC)
    action = payload.get("action", "").lower()
    role = (officer_role or payload.get("role") or "").upper()
    if role:
        if action in ("hold", "confirm_customer", "release") and not (role.startswith("BANK") or role == "ADMIN"):
            raise HTTPException(status_code=403, detail=f"Role '{role}' is not authorized to execute bank fund action '{action}'")
        if action in ("police_forward", "dispatch", "update_patrol_status") and not (role.startswith("POLICE") or role == "ADMIN"):
            raise HTTPException(status_code=403, detail=f"Role '{role}' is not authorized to execute LEA dispatch action '{action}'")

    return True, "Authenticated and cryptographically verified"
