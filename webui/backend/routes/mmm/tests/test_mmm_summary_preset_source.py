import os
import tempfile

from webui.backend.routes.mmm.mmm_state import get_session_summary
from webui.backend.routes.mmm.mmm_storage import MMMStorage


def _build_session(session_id: str = 'mmm-test-1'):
    return {
        'session_id': session_id,
        'strategy_status': 'IDLE',
        'mode': 'fresh',
        'params': {
            'expiry': '21032026',
            'dte_category': '5DTE',
            '_preset_source': 'STRADDLE_ROLL',
            'adjustment_interval': 300,
        },
        'ce': {
            'positions': [],
            'active_strike': 0,
            'original_lots': 0,
            'active_lots': 0,
            'total_lots': 0,
            'frozen_total_lots': 0,
            'entry_fill_price': 0,
        },
        'pe': {
            'positions': [],
            'active_strike': 0,
            'original_lots': 0,
            'active_lots': 0,
            'total_lots': 0,
            'frozen_total_lots': 0,
            'entry_fill_price': 0,
        },
        'adjustment_history': [],
        'adjustment_count': 0,
        'reversal_count': 0,
        'shift_count': 0,
        'close_at_5_count': 0,
        'total_premium_collected': 0.0,
        'ce_premium_collected': 0.0,
        'pe_premium_collected': 0.0,
        'realized_pnl': 0.0,
        'unrealized_pnl': 0.0,
        'total_fees': 0.0,
        'peak_pnl': 0.0,
        'last_heartbeat': None,
        'next_heartbeat': None,
        'expiry_time': None,
        'perp_hedge': {'realized_pnl': 0.0, 'unrealized_pnl': 0.0},
        '_reverse': {'net_pnl': 0.0},
    }


def test_get_session_summary_exposes_preset_source_and_dte_category():
    session = _build_session()

    summary = get_session_summary(session)

    assert summary['dte_category'] == '5DTE'
    assert summary['_preset_source'] == 'STRADDLE_ROLL'


def test_list_session_summaries_exposes_preset_source_and_dte_category_from_sql():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'mmm_sessions.db')
        storage = MMMStorage(db_path=db_path)
        storage.save_session(_build_session('mmm-test-sql'))

        summaries = storage.list_session_summaries()

    assert len(summaries) == 1
    assert summaries[0]['dte_category'] == '5DTE'
    assert summaries[0]['_preset_source'] == 'STRADDLE_ROLL'


def test_row_to_summary_fallback_keeps_preset_source_and_dte_category():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'mmm_sessions.db')
        storage = MMMStorage(db_path=db_path)

        summary = storage._row_to_summary_fallback(_build_session('mmm-test-fallback'))

    assert summary['dte_category'] == '5DTE'
    assert summary['_preset_source'] == 'STRADDLE_ROLL'
