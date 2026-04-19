"""
Phase 3 — TokenBudget arithmetic tests.
"""

import pytest
from webui.backend.routes.mmm.mmm_whipsaw_smart import TokenBudget, _load_budget, _save_budget


def _budget(remaining=10.0, per_session=10.0):
    return TokenBudget(tokens_remaining=remaining, tokens_per_session=per_session)


# ── spend ────────────────────────────────────────────────────────────────────

def test_spend_success():
    b = _budget(10.0)
    assert b.spend(1.0) is True
    assert abs(b.tokens_remaining - 9.0) < 1e-9


def test_spend_exact():
    b = _budget(2.0)
    assert b.spend(2.0) is True
    assert b.tokens_remaining == 0.0


def test_spend_insufficient():
    b = _budget(0.5)
    assert b.spend(1.0) is False
    assert b.tokens_remaining == 0.5  # unchanged


def test_spend_zero():
    b = _budget(0.0)
    assert b.spend(1.0) is False


# ── credit_patience ───────────────────────────────────────────────────────────

def test_credit_patience_normal():
    b = _budget(remaining=8.0, per_session=10.0)
    b.credit_patience(0.5)
    assert abs(b.tokens_remaining - 8.5) < 1e-9


def test_credit_patience_capped():
    # Can't exceed tokens_per_session
    b = _budget(remaining=9.8, per_session=10.0)
    b.credit_patience(0.5)
    assert b.tokens_remaining == 10.0


def test_credit_patience_default_amount():
    b = _budget(remaining=5.0)
    b.credit_patience()
    assert abs(b.tokens_remaining - 5.5) < 1e-9


# ── cost_for_mode ─────────────────────────────────────────────────────────────

def test_cost_normal_no_flip():
    b = _budget()
    assert b.cost_for_mode('NORMAL', is_flip=False) == 1.0


def test_cost_normal_flip():
    b = _budget()
    assert b.cost_for_mode('NORMAL', is_flip=True) == 2.0


def test_cost_defensive_no_flip():
    b = _budget()
    assert abs(b.cost_for_mode('DEFENSIVE', is_flip=False) - 1.5) < 1e-9


def test_cost_defensive_flip():
    b = _budget()
    assert abs(b.cost_for_mode('DEFENSIVE', is_flip=True) - 2.5) < 1e-9


# ── session load / save ───────────────────────────────────────────────────────

def test_load_budget_initial():
    session = {}
    b = _load_budget(session, tokens_per_session=10.0)
    assert b.tokens_remaining == 10.0


def test_load_budget_from_session():
    session = {'_smart_ws_tokens': 7.5}
    b = _load_budget(session, tokens_per_session=10.0)
    assert b.tokens_remaining == 7.5


def test_save_budget():
    session = {}
    b = _budget(remaining=6.25)
    _save_budget(session, b)
    assert session['_smart_ws_tokens'] == 6.25


def test_round_trip():
    session = {}
    b = _load_budget(session, 10.0)
    b.spend(3.5)
    _save_budget(session, b)
    b2 = _load_budget(session, 10.0)
    assert abs(b2.tokens_remaining - 6.5) < 1e-9
