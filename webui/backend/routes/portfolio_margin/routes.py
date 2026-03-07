"""
Portfolio Margin Flask Routes

REST endpoints for portfolio margin monitoring, management, and risk analysis.
All routes are prefixed with /api/portfolio-margin/.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import threading
import time
from datetime import datetime
from typing import Dict, List

from flask import Blueprint, jsonify, request, Response

from .models import (
    PortfolioMargin, WalletBalance, Position, RiskMetrics, MarginHistoryEntry,
)
from .api_client import DeltaPortfolioMarginClient
from .websocket_client import PortfolioMarginWebSocket
from .margin_calculator import (
    calculate_initial_margin, calculate_maintenance_margin,
    calculate_utilization, analyze_portfolio_risk, compare_margin_modes,
    run_stress_test,
)

log = logging.getLogger(__name__)

portfolio_margin_bp = Blueprint('portfolio_margin', __name__)

# ---------------------------------------------------------------------------
# Module-level singletons (lazy-initialised)
# ---------------------------------------------------------------------------
_client: DeltaPortfolioMarginClient | None = None
_ws_client: PortfolioMarginWebSocket | None = None
_history: List[Dict] = []  # In-memory margin history
_history_lock = threading.Lock()
MAX_HISTORY = 1000  # Keep last N entries
_tickers_cache: Dict = {}
_tickers_ts: float = 0
TICKERS_TTL = 30  # Cache tickers for 30 seconds


def _get_client() -> DeltaPortfolioMarginClient:
    global _client
    if _client is None:
        _client = DeltaPortfolioMarginClient()
    return _client


def _get_ws() -> PortfolioMarginWebSocket:
    global _ws_client
    if _ws_client is None:
        client = _get_client()
        _ws_client = PortfolioMarginWebSocket(auth_payload_fn=client.generate_ws_auth)
        _ws_client.on_portfolio_margin(_on_portfolio_margin_update)
    return _ws_client


def _on_portfolio_margin_update(data: Dict):
    """Callback: store margin snapshot in history from WS."""
    entry = {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'risk_margin': float(data.get('risk_margin', 0)),
        'margin_floor': float(data.get('margin_floor', 0)),
        'liquidation_risk': bool(data.get('liquidation_risk', False)),
        'source': 'websocket',
    }
    _append_history(entry)


def _append_history(entry: Dict):
    """Thread-safe append to margin history buffer."""
    with _history_lock:
        _history.append(entry)
        if len(_history) > MAX_HISTORY:
            _history[:] = _history[-MAX_HISTORY:]


def _record_rest_snapshot(wallet: WalletBalance):
    """Record a history snapshot from REST data on every refresh."""
    utilization = calculate_utilization(wallet.blocked_margin, wallet.balance)
    entry = {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'balance': round(wallet.balance, 4),
        'blocked_margin': round(wallet.blocked_margin, 4),
        'available_balance': round(wallet.available_balance, 4),
        'margin_utilization': round(utilization, 2),
        'risk_margin': round(wallet.portfolio_margin, 4),
        'source': 'rest',
    }
    _append_history(entry)


def _get_cached_tickers():
    """Get tickers with TTL caching."""
    global _tickers_cache, _tickers_ts
    now = time.time()
    if now - _tickers_ts > TICKERS_TTL:
        client = _get_client()
        raw = client.get_tickers()
        _tickers_cache = {}
        for t in raw:
            sym = t.get('symbol', '')
            if sym:
                _tickers_cache[sym] = t
        _tickers_ts = now
        log.info('Tickers cache refreshed: %d symbols', len(_tickers_cache))
    return _tickers_cache


# ============================================================================
# Routes
# ============================================================================

@portfolio_margin_bp.route('/api/portfolio-margin/status', methods=['GET'])
def pm_status():
    """Full status: margin mode, wallet snapshot, computed utilization."""
    try:
        client = _get_client()
        ws = _get_ws()

        mode = client.get_margin_mode()
        balances_raw = client.get_wallet_balances()
        wallets = [WalletBalance.from_api_data(b) for b in balances_raw]
        wallets_dict = [w.to_dict() for w in wallets]

        primary = next((w for w in wallets if w.balance > 0), WalletBalance())
        utilization = calculate_utilization(primary.blocked_margin, primary.balance)

        if primary.balance > 0:
            _record_rest_snapshot(primary)

        return jsonify({
            'success': True,
            'margin_mode': mode,
            'wallets': wallets_dict,
            'utilization': round(utilization, 2),
            'portfolio_margin_ws': ws.latest_portfolio_margin,
            'wallet_margin_ws': ws.latest_wallet_margin,
            'websocket': ws.status(),
        })
    except Exception as exc:
        log.error('portfolio-margin/status error: %s', exc)
        return jsonify({'success': False, 'error': str(exc)}), 500


@portfolio_margin_bp.route('/api/portfolio-margin/mode', methods=['PUT'])
def pm_set_mode():
    """Switch margin mode (isolated ↔ portfolio)."""
    try:
        body = request.get_json(force=True) or {}
        mode = body.get('margin_mode', '').strip()
        if mode not in ('isolated', 'portfolio'):
            return jsonify({'success': False, 'error': 'margin_mode must be "isolated" or "portfolio"'}), 400
        subaccount = body.get('subaccount_user_id')
        client = _get_client()
        result = client.set_margin_mode(mode, subaccount)
        return jsonify({'success': True, 'result': result})
    except Exception as exc:
        log.error('portfolio-margin/mode error: %s', exc)
        return jsonify({'success': False, 'error': str(exc)}), 500


@portfolio_margin_bp.route('/api/portfolio-margin/wallet', methods=['GET'])
def pm_wallet():
    """Wallet balances with margin breakdown."""
    try:
        client = _get_client()
        raw = client.get_wallet_balances()
        wallets = [WalletBalance.from_api_data(b) for b in raw]
        return jsonify({
            'success': True,
            'wallets': [w.to_dict() for w in wallets],
        })
    except Exception as exc:
        log.error('portfolio-margin/wallet error: %s', exc)
        return jsonify({'success': False, 'error': str(exc)}), 500


@portfolio_margin_bp.route('/api/portfolio-margin/positions', methods=['GET'])
def pm_positions():
    """Open positions with margin details."""
    try:
        client = _get_client()
        ct_param = request.args.get('contract_types', '')
        contract_types = [c.strip() for c in ct_param.split(',') if c.strip()] or None
        raw = client.get_positions(contract_types)
        positions = [Position.from_api_data(p) for p in raw]
        return jsonify({
            'success': True,
            'positions': [p.to_dict() for p in positions],
            'count': len(positions),
        })
    except Exception as exc:
        log.error('portfolio-margin/positions error: %s', exc)
        return jsonify({'success': False, 'error': str(exc)}), 500


@portfolio_margin_bp.route('/api/portfolio-margin/risk', methods=['GET'])
def pm_risk():
    """Risk analysis — uses wallet data for IM/MM when PM data unavailable."""
    try:
        client = _get_client()
        ws = _get_ws()

        # Wallet
        raw_wallets = client.get_wallet_balances()
        wallet = WalletBalance.from_api_data(raw_wallets[0]) if raw_wallets else WalletBalance()

        # Positions
        raw_positions = client.get_positions()
        positions = [Position.from_api_data(p) for p in raw_positions]

        # Try WS data first
        pm_data = ws.latest_portfolio_margin
        pm = PortfolioMargin.from_ws_data(pm_data) if pm_data else PortfolioMargin()

        metrics = analyze_portfolio_risk(wallet, positions, pm)
        return jsonify({
            'success': True,
            'risk': metrics.to_dict(),
            'wallet': wallet.to_dict(),
            'portfolio_margin': pm.to_dict(),
        })
    except Exception as exc:
        log.error('portfolio-margin/risk error: %s', exc)
        return jsonify({'success': False, 'error': str(exc)}), 500


@portfolio_margin_bp.route('/api/portfolio-margin/tickers', methods=['GET'])
def pm_tickers():
    """Proxy tickers from Delta Exchange CDN — returns greeks for options."""
    try:
        tickers = _get_cached_tickers()
        # Only return options/futures tickers (filter out spot, etc.)
        filtered = {}
        for sym, data in tickers.items():
            if any(sym.startswith(p) for p in ('C-', 'P-', 'BTCUSD', 'ETHUSD')):
                filtered[sym] = {
                    'symbol': sym,
                    'mark_price': data.get('mark_price'),
                    'spot_price': data.get('spot_price'),
                    'greeks': data.get('greeks'),
                    'product_id': data.get('product_id'),
                }
        return jsonify({'success': True, 'tickers': filtered, 'count': len(filtered)})
    except Exception as exc:
        log.error('portfolio-margin/tickers error: %s', exc)
        return jsonify({'success': False, 'error': str(exc)}), 500


@portfolio_margin_bp.route('/api/portfolio-margin/risk-matrix', methods=['GET'])
def pm_risk_matrix():
    """Latest risk matrix from WebSocket."""
    try:
        ws = _get_ws()
        pm_data = ws.latest_portfolio_margin
        risk_matrix = pm_data.get('risk_matrix', {}) if pm_data else {}
        return jsonify({'success': True, 'risk_matrix': risk_matrix})
    except Exception as exc:
        log.error('portfolio-margin/risk-matrix error: %s', exc)
        return jsonify({'success': False, 'error': str(exc)}), 500


# ---------------------------------------------------------------------------
# Stress Testing
# ---------------------------------------------------------------------------

@portfolio_margin_bp.route('/api/portfolio-margin/stress-test', methods=['POST'])
def pm_stress_test():
    """Run stress test scenarios on current portfolio."""
    try:
        body = request.get_json(force=True) or {}
        pct_moves = body.get('pct_moves', [-30, -20, -10, -5, 5, 10])

        client = _get_client()
        raw_wallets = client.get_wallet_balances()
        wallet = WalletBalance.from_api_data(raw_wallets[0]) if raw_wallets else WalletBalance()
        raw_positions = client.get_positions()
        positions = [Position.from_api_data(p) for p in raw_positions]

        results = run_stress_test(positions, wallet, pct_moves)
        return jsonify({
            'success': True,
            'scenarios': results,
            'position_count': len(positions),
            'current_balance': round(wallet.balance, 4),
        })
    except Exception as exc:
        log.error('portfolio-margin/stress-test error: %s', exc)
        return jsonify({'success': False, 'error': str(exc)}), 500


# ---------------------------------------------------------------------------
# WebSocket management
# ---------------------------------------------------------------------------

@portfolio_margin_bp.route('/api/portfolio-margin/websocket/start', methods=['POST'])
def pm_ws_start():
    try:
        ws = _get_ws()
        ws.start()
        return jsonify({'success': True, 'status': ws.status()})
    except Exception as exc:
        log.error('portfolio-margin/websocket/start error: %s', exc)
        return jsonify({'success': False, 'error': str(exc)}), 500


@portfolio_margin_bp.route('/api/portfolio-margin/websocket/stop', methods=['POST'])
def pm_ws_stop():
    try:
        ws = _get_ws()
        ws.stop()
        return jsonify({'success': True, 'status': ws.status()})
    except Exception as exc:
        log.error('portfolio-margin/websocket/stop error: %s', exc)
        return jsonify({'success': False, 'error': str(exc)}), 500


@portfolio_margin_bp.route('/api/portfolio-margin/websocket/status', methods=['GET'])
def pm_ws_status():
    try:
        ws = _get_ws()
        return jsonify({'success': True, **ws.status()})
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


# ---------------------------------------------------------------------------
# History & Export
# ---------------------------------------------------------------------------

@portfolio_margin_bp.route('/api/portfolio-margin/history', methods=['GET'])
def pm_history():
    try:
        limit = int(request.args.get('limit', 100))
        with _history_lock:
            data = list(_history[-limit:])
        return jsonify({'success': True, 'history': data, 'count': len(data)})
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@portfolio_margin_bp.route('/api/portfolio-margin/export', methods=['POST'])
def pm_export():
    """Export current data as JSON or CSV."""
    try:
        body = request.get_json(force=True) or {}
        fmt = body.get('format', 'json')
        client = _get_client()
        ws = _get_ws()

        raw_wallets = client.get_wallet_balances()
        raw_positions = client.get_positions()
        now_str = datetime.utcnow().strftime('%Y%m%d_%H%M%S')

        if fmt == 'csv':
            si = io.StringIO()
            writer = csv.writer(si)
            writer.writerow([
                'symbol', 'type', 'side', 'size', 'entry_price', 'mark_price',
                'initial_margin', 'unrealized_pnl', 'liquidation_price',
            ])
            for p in raw_positions:
                writer.writerow([
                    p.get('product_symbol', ''),
                    p.get('contract_type', ''),
                    p.get('side', ''),
                    p.get('size', 0),
                    p.get('entry_price', 0),
                    p.get('mark_price', 0),
                    p.get('initial_margin', p.get('margin', 0)),
                    p.get('unrealized_pnl', 0),
                    p.get('liquidation_price', ''),
                ])
            output = si.getvalue()
            filename = f'portfolio_margin_{now_str}.csv'
            return Response(output, mimetype='text/csv',
                            headers={'Content-Disposition': f'attachment; filename={filename}'})

        export_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'wallets': raw_wallets,
            'positions': raw_positions,
            'portfolio_margin': ws.latest_portfolio_margin,
            'wallet_margin': ws.latest_wallet_margin,
        }
        return jsonify({'success': True, 'data': export_data})
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@portfolio_margin_bp.route('/api/portfolio-margin/compare', methods=['GET'])
def pm_compare():
    try:
        client = _get_client()
        raw_positions = client.get_positions()
        isolated_total = sum(float(p.get('initial_margin', 0) or p.get('margin', 0)) for p in raw_positions)
        raw_wallets = client.get_wallet_balances()
        portfolio_total = sum(float(w.get('portfolio_margin', 0)) for w in raw_wallets)
        comparison = compare_margin_modes(isolated_total, portfolio_total)
        return jsonify({'success': True, **comparison})
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500
