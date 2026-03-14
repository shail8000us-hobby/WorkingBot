"""
Contract tests for check_side_fully_closed + check_both_sides_closed

SEALED — v1.0.0 — March 14, 2026
Do not modify without UNSEAL command in AI_SEAL.md

Functions: check_side_fully_closed(), check_both_sides_closed()
File: webui/backend/routes/mmm/mmm_close_at_5.py

Contracts:
  C1. check_side_fully_closed: returns True when side has total_lots=0
  C2. check_side_fully_closed: returns False when side has total_lots>0
  C3. check_side_fully_closed: returns True when side key is absent from session (default=0)
  C4. check_side_fully_closed: works for both 'ce' and 'pe' sides
  C5. check_both_sides_closed: returns True only when both CE and PE total_lots=0
  C6. check_both_sides_closed: returns False when CE has lots (PE=0)
  C7. check_both_sides_closed: returns False when PE has lots (CE=0)
  C8. check_both_sides_closed: returns False when both sides have lots
"""

import pytest

pytestmark = pytest.mark.sealed

from webui.backend.routes.mmm.mmm_close_at_5 import (
    check_side_fully_closed,
    check_both_sides_closed,
)


def _session(ce_lots=0, pe_lots=0):
    """Build minimal session dict with total_lots for both sides."""
    return {
        'ce': {'total_lots': ce_lots},
        'pe': {'total_lots': pe_lots},
    }


# ─── C1: True when total_lots=0 ────────────────────────────────────────────

def test_c1_check_side_fully_closed_returns_true_when_zero_lots():
    session = _session(ce_lots=0, pe_lots=5)
    assert check_side_fully_closed(session, 'ce') is True


# ─── C2: False when total_lots > 0 ─────────────────────────────────────────

def test_c2_check_side_fully_closed_returns_false_when_has_lots():
    session = _session(ce_lots=10, pe_lots=0)
    assert check_side_fully_closed(session, 'ce') is False


def test_c2b_exact_lot_count_returns_false():
    session = _session(ce_lots=1, pe_lots=0)
    assert check_side_fully_closed(session, 'ce') is False


# ─── C3: Absent side → defaults to 0 → True ────────────────────────────────

def test_c3_absent_side_key_returns_true():
    session = {}  # no 'ce' or 'pe' keys
    assert check_side_fully_closed(session, 'ce') is True


def test_c3b_side_without_total_lots_field_returns_true():
    session = {'ce': {}}  # no total_lots field
    assert check_side_fully_closed(session, 'ce') is True


# ─── C4: Works for both sides ──────────────────────────────────────────────

def test_c4_pe_side_with_lots():
    session = _session(ce_lots=0, pe_lots=7)
    assert check_side_fully_closed(session, 'pe') is False


def test_c4b_pe_side_zero():
    session = _session(ce_lots=3, pe_lots=0)
    assert check_side_fully_closed(session, 'pe') is True


# ─── C5: check_both_sides_closed: True only when BOTH are zero ─────────────

def test_c5_both_zero_returns_true():
    session = _session(ce_lots=0, pe_lots=0)
    assert check_both_sides_closed(session) is True


# ─── C6: False when CE has lots, PE is zero ────────────────────────────────

def test_c6_ce_has_lots_pe_empty():
    session = _session(ce_lots=5, pe_lots=0)
    assert check_both_sides_closed(session) is False


# ─── C7: False when PE has lots, CE is zero ────────────────────────────────

def test_c7_pe_has_lots_ce_empty():
    session = _session(ce_lots=0, pe_lots=3)
    assert check_both_sides_closed(session) is False


# ─── C8: False when both sides have lots ───────────────────────────────────

def test_c8_both_have_lots():
    session = _session(ce_lots=10, pe_lots=10)
    assert check_both_sides_closed(session) is False
