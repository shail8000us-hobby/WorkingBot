"""
Contract tests for MMM Adopter — T3-9

SEALED — v1.0.0 — March 21, 2026
Do not modify without UNSEAL command in AI_SEAL.md

No bugs found during audit.

Functions covered:
  classify_positions(selected_positions, spot_price) -> Dict
  validate_adoptable(classified, session_id, max_lots_per_side) -> Dict
  build_adopted_session_state(session, classified, trigger_mode, expiry) -> Dict

File: webui/backend/routes/mmm/mmm_adopter.py

--- classify_positions contracts ---
C-CP-1: single CE + single PE → each side has active, frozen=[]
C-CP-2: explicit role='active' respected over ATM proximity
C-CP-3: multiple CE no role → closest to ATM is active, others frozen
C-CP-4: empty selected_positions → active=None for both sides

--- validate_adoptable contracts ---
C-VA-1: no CE → error with description
C-VA-2: no PE → error with description
C-VA-3: valid symmetric positions → valid=True
C-VA-4: asymmetric lots → valid=True with warning
C-VA-5: CE active with 0 lots → error

--- build_adopted_session_state contracts ---
C-BASS-1: CE and PE side states populated from classified data
C-BASS-2: frozen positions appended to positions[] (unified ledger)
C-BASS-3: expiry mismatch raises ValueError
C-BASS-4: total_premium_collected computed from active + frozen entry prices
C-BASS-5: trigger_snapshot uses canonical strike_key for active strike
"""

import pytest
from unittest.mock import patch, MagicMock


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _pos(side, strike, lots, entry_price=100.0, symbol=None, role=None):
    p = {
        'side': side,
        'strike': float(strike),
        'lots': lots,
        'entry_price': float(entry_price),
        'symbol': symbol or f'{side[0]}-BTC-{int(strike)}-210326',
    }
    if role is not None:
        p['role'] = role
    return p


def _make_classified(ce_strike=90000, pe_strike=88000, ce_lots=5, pe_lots=5,
                     ce_prem=200.0, pe_prem=200.0):
    return {
        'ce': {
            'active': {'strike': float(ce_strike), 'lots': ce_lots,
                       'entry_price': ce_prem, 'symbol': f'C-BTC-{ce_strike}-210326'},
            'frozen': [],
        },
        'pe': {
            'active': {'strike': float(pe_strike), 'lots': pe_lots,
                       'entry_price': pe_prem, 'symbol': f'P-BTC-{pe_strike}-210326'},
            'frozen': [],
        },
    }


def _make_session_for_adopt(expiry='21032026'):
    """Create a minimal session dict for build_adopted_session_state."""
    from unittest.mock import MagicMock
    with patch('webui.backend.routes.mmm.mmm_storage.get_storage',
               return_value=MagicMock(get_session=MagicMock(return_value=None),
                                      list_sessions=MagicMock(return_value=[]))):
        from webui.backend.routes.mmm.mmm_state import create_session
        return create_session(params={
            'expiry': expiry,
            'initial_lots': 5,
        })


def _mock_storage():
    storage = MagicMock()
    storage.list_sessions.return_value = []
    return storage


# =============================================================================
# classify_positions
# =============================================================================

class TestClassifyPositions:

    @pytest.mark.sealed
    def test_c_cp_1_single_ce_and_pe_classified(self):
        from webui.backend.routes.mmm.mmm_adopter import classify_positions
        positions = [
            _pos('CE', 90000, 5),
            _pos('PE', 88000, 5),
        ]
        result = classify_positions(positions, spot_price=89000)
        assert result['ce']['active'] is not None
        assert result['ce']['active']['strike'] == 90000.0
        assert result['ce']['frozen'] == []
        assert result['pe']['active'] is not None
        assert result['pe']['active']['strike'] == 88000.0

    @pytest.mark.sealed
    def test_c_cp_2_explicit_role_respected_over_atm(self):
        from webui.backend.routes.mmm.mmm_adopter import classify_positions
        # Two CE positions: ATM would pick 90000 (closer to spot=89000),
        # but role='active' on 91000 forces it to be active.
        positions = [
            _pos('CE', 90000, 5, role='frozen'),
            _pos('CE', 91000, 3, role='active'),  # marked active explicitly
            _pos('PE', 88000, 5),
        ]
        result = classify_positions(positions, spot_price=89000)
        assert result['ce']['active']['strike'] == 91000.0
        assert len(result['ce']['frozen']) == 1
        assert result['ce']['frozen'][0]['strike'] == 90000.0

    @pytest.mark.sealed
    def test_c_cp_3_auto_classify_atm_becomes_active(self):
        from webui.backend.routes.mmm.mmm_adopter import classify_positions
        positions = [
            _pos('CE', 90000, 5),   # closer to spot=89000
            _pos('CE', 95000, 3),   # further away → frozen
            _pos('PE', 88000, 5),
        ]
        result = classify_positions(positions, spot_price=89000)
        assert result['ce']['active']['strike'] == 90000.0
        assert len(result['ce']['frozen']) == 1
        assert result['ce']['frozen'][0]['strike'] == 95000.0

    @pytest.mark.sealed
    def test_c_cp_4_empty_positions_returns_none_active(self):
        from webui.backend.routes.mmm.mmm_adopter import classify_positions
        result = classify_positions([])
        assert result['ce']['active'] is None
        assert result['pe']['active'] is None


# =============================================================================
# validate_adoptable
# =============================================================================

class TestValidateAdoptable:

    @pytest.mark.sealed
    def test_c_va_1_no_ce_returns_error(self):
        from webui.backend.routes.mmm.mmm_adopter import validate_adoptable
        classified = {'ce': {'active': None, 'frozen': []}, 'pe': _make_classified()['pe']}
        with patch('webui.backend.routes.mmm.mmm_storage.get_storage',
                   return_value=_mock_storage()):
            result = validate_adoptable(classified)
        assert result['valid'] is False
        assert any('CE' in e for e in result['errors'])

    @pytest.mark.sealed
    def test_c_va_2_no_pe_returns_error(self):
        from webui.backend.routes.mmm.mmm_adopter import validate_adoptable
        classified = {'ce': _make_classified()['ce'], 'pe': {'active': None, 'frozen': []}}
        with patch('webui.backend.routes.mmm.mmm_storage.get_storage',
                   return_value=_mock_storage()):
            result = validate_adoptable(classified)
        assert result['valid'] is False
        assert any('PE' in e for e in result['errors'])

    @pytest.mark.sealed
    def test_c_va_3_valid_symmetric_no_warnings(self):
        from webui.backend.routes.mmm.mmm_adopter import validate_adoptable
        classified = _make_classified(ce_lots=5, pe_lots=5)
        with patch('webui.backend.routes.mmm.mmm_storage.get_storage',
                   return_value=_mock_storage()):
            result = validate_adoptable(classified)
        assert result['valid'] is True
        assert result['errors'] == []
        # No asymmetry warning
        assert not any('asymmetric' in w.lower() for w in result['warnings'])

    @pytest.mark.sealed
    def test_c_va_4_asymmetric_lots_triggers_warning(self):
        from webui.backend.routes.mmm.mmm_adopter import validate_adoptable
        classified = _make_classified(ce_lots=5, pe_lots=3)
        with patch('webui.backend.routes.mmm.mmm_storage.get_storage',
                   return_value=_mock_storage()):
            result = validate_adoptable(classified)
        assert result['valid'] is True  # warning, not error
        assert any('asymmetric' in w.lower() for w in result['warnings'])

    @pytest.mark.sealed
    def test_c_va_5_zero_active_lots_is_error(self):
        from webui.backend.routes.mmm.mmm_adopter import validate_adoptable
        classified = _make_classified(ce_lots=0, pe_lots=5)
        with patch('webui.backend.routes.mmm.mmm_storage.get_storage',
                   return_value=_mock_storage()):
            result = validate_adoptable(classified)
        assert result['valid'] is False
        assert any('CE active' in e for e in result['errors'])


# =============================================================================
# build_adopted_session_state
# =============================================================================

class TestBuildAdoptedSessionState:

    @pytest.mark.sealed
    def test_c_bass_1_side_states_populated_from_classified(self):
        from webui.backend.routes.mmm.mmm_adopter import build_adopted_session_state
        session = _make_session_for_adopt('21032026')
        classified = _make_classified(ce_strike=90000, pe_strike=88000,
                                      ce_lots=5, pe_lots=5)
        result = build_adopted_session_state(session, classified, expiry='21032026')
        assert result['ce']['active_strike'] == 90000.0
        assert result['pe']['active_strike'] == 88000.0
        assert result['ce']['original_lots'] == 5
        assert result['pe']['original_lots'] == 5

    @pytest.mark.sealed
    def test_c_bass_2_frozen_positions_in_positions_list(self):
        from webui.backend.routes.mmm.mmm_adopter import build_adopted_session_state
        session = _make_session_for_adopt('21032026')
        classified = {
            'ce': {
                'active': {'strike': 90000.0, 'lots': 5, 'entry_price': 200.0,
                           'symbol': 'C-BTC-90000-210326'},
                'frozen': [
                    {'strike': 89000.0, 'lots': 3, 'entry_price': 150.0,
                     'symbol': 'C-BTC-89000-210326'}
                ],
            },
            'pe': {
                'active': {'strike': 88000.0, 'lots': 5, 'entry_price': 180.0,
                           'symbol': 'P-BTC-88000-210326'},
                'frozen': [],
            },
        }
        result = build_adopted_session_state(session, classified, expiry='21032026')
        # frozen_positions is a computed view from positions[] — must contain frozen entry
        assert len(result['ce']['frozen_positions']) == 1
        assert result['ce']['frozen_positions'][0]['strike'] == 89000.0

    @pytest.mark.sealed
    def test_c_bass_3_expiry_mismatch_raises_value_error(self):
        from webui.backend.routes.mmm.mmm_adopter import build_adopted_session_state
        session = _make_session_for_adopt('21032026')
        classified = _make_classified()
        with pytest.raises(ValueError, match='mismatch'):
            build_adopted_session_state(session, classified, expiry='25032026')

    @pytest.mark.sealed
    def test_c_bass_4_total_premium_collected_computed(self):
        from webui.backend.routes.mmm.mmm_adopter import build_adopted_session_state
        session = _make_session_for_adopt('21032026')
        # CE: 5 lots × 200 prem × 0.001, PE: 5 lots × 180 prem × 0.001
        # total = (5*200 + 5*180) * 0.001 = 1900 * 0.001 = 1.9
        classified = _make_classified(ce_lots=5, pe_lots=5, ce_prem=200.0, pe_prem=180.0)
        result = build_adopted_session_state(session, classified, expiry='21032026')
        assert abs(result['total_premium_collected'] - 1.9) < 0.001

    @pytest.mark.sealed
    def test_c_bass_5_trigger_snapshot_uses_canonical_strike_key(self):
        from webui.backend.routes.mmm.mmm_adopter import build_adopted_session_state
        from webui.backend.routes.mmm.mmm_constants import strike_key
        session = _make_session_for_adopt('21032026')
        classified = _make_classified(ce_strike=90000)
        result = build_adopted_session_state(session, classified, expiry='21032026')
        key = strike_key(90000.0)
        assert key in result['ce']['trigger_snapshot']
