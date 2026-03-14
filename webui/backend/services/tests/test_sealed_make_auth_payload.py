"""
Contract Test: _make_auth_payload
==================================
SEALED — v1.0.0 — March 14, 2026
Protocol: AI_SEAL.md

Locks the known-good behaviour of _make_auth_payload in
_ws_private_worker.py — the HMAC-SHA256 auth payload generator
used to authenticate the private Delta Exchange WebSocket.

Note: @sealed decorator intentionally omitted from source function
because _ws_private_worker.py runs as a standalone subprocess and
adding a parent-package import would break subprocess isolation.

Run with:
    python3 -m pytest webui/backend/services/tests/test_sealed_make_auth_payload.py -v
Or all sealed:
    python3 -m pytest webui/ bot/ -m sealed -v
"""

import hashlib
import hmac
import time

import pytest

from webui.backend.services._ws_private_worker import _make_auth_payload

pytestmark = pytest.mark.sealed


# ---------------------------------------------------------------------------
# CONTRACT 1 — Shape: type='auth', payload has required keys
# ---------------------------------------------------------------------------

def test_returns_correct_shape():
    """Must return dict with type='auth' and payload containing api-key, signature, timestamp."""
    result = _make_auth_payload('any_key', 'any_secret')
    assert result['type'] == 'auth'
    assert 'payload' in result
    for key in ('api-key', 'signature', 'timestamp'):
        assert key in result['payload'], f"Missing payload key: {key}"


# ---------------------------------------------------------------------------
# CONTRACT 2 — api-key matches input exactly
# ---------------------------------------------------------------------------

def test_api_key_passed_through():
    """payload['api-key'] must equal the api_key argument."""
    result = _make_auth_payload('MY_KEY_123', 'any_secret')
    assert result['payload']['api-key'] == 'MY_KEY_123'


# ---------------------------------------------------------------------------
# CONTRACT 3 — Timestamp is a string of a recent Unix epoch second
# ---------------------------------------------------------------------------

def test_timestamp_is_string_integer():
    """payload['timestamp'] must be a string parseable as int and within 10s of now."""
    result = _make_auth_payload('k', 's')
    ts = result['payload']['timestamp']
    assert isinstance(ts, str), "timestamp must be a string"
    ts_int = int(ts)  # must not raise
    assert abs(ts_int - int(time.time())) <= 10, "timestamp must be within 10s of current time"


# ---------------------------------------------------------------------------
# CONTRACT 4 — Signature is valid HMAC-SHA256 of "GET{timestamp}/live"
# ---------------------------------------------------------------------------

def test_signature_is_correct_hmac():
    """signature must equal HMAC-SHA256(secret, 'GET' + timestamp + '/live')."""
    result = _make_auth_payload('key', 'my_secret')
    ts = result['payload']['timestamp']
    sig = result['payload']['signature']
    prehash = 'GET' + ts + '/live'
    expected = hmac.new('my_secret'.encode(), prehash.encode(), hashlib.sha256).hexdigest()
    assert sig == expected


# ---------------------------------------------------------------------------
# CONTRACT 5 — Signature is a 64-character hex string (SHA-256 output)
# ---------------------------------------------------------------------------

def test_signature_is_64_char_hex():
    """SHA-256 hex digest is always exactly 64 hex characters."""
    result = _make_auth_payload('k', 's')
    sig = result['payload']['signature']
    assert len(sig) == 64
    int(sig, 16)  # must be valid hex — raises ValueError if not


# ---------------------------------------------------------------------------
# CONTRACT 6 — Different secrets produce different signatures
# ---------------------------------------------------------------------------

def test_different_secrets_produce_different_signatures():
    """Two different secrets must never produce the same signature."""
    r1 = _make_auth_payload('key', 'secret_A')
    r2 = _make_auth_payload('key', 'secret_B')
    assert r1['payload']['signature'] != r2['payload']['signature']
