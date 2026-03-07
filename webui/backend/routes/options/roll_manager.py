"""
Roll Manager Blueprint  (Feature 9 — Roll Management Tool)
===========================================================
Independent module for rolling option positions to a further expiry.

A "roll" = buy back existing short position + sell new position at same
strike / different expiry.  Net roll cost = new_bid - close_ask.

Routes:
  GET  /api/options/roll/quotes?symbol=C-BTC-90000-260328&target_expiry=260404
  POST /api/options/roll/execute
"""

import logging
from flask import Blueprint, jsonify, request

try:
    from .options_client import _run_async, get_unified_client, with_timeout
    from .order_executor import fetch_fresh_orderbook_quotes, place_smart_order
except ImportError:
    from webui.backend.routes.options.options_client import _run_async, get_unified_client, with_timeout
    from webui.backend.routes.options.order_executor import fetch_fresh_orderbook_quotes, place_smart_order

logger = logging.getLogger(__name__)

roll_manager_bp = Blueprint('roll_manager', __name__)


def _build_target_symbol(source_symbol: str, target_expiry: str) -> str:
    """
    Swap the expiry component of a symbol string.

    source_symbol:  C-BTC-90000-260328
    target_expiry:  260404
    Returns:        C-BTC-90000-260404
    """
    parts = source_symbol.split('-')
    if len(parts) < 4:
        raise ValueError(f"Cannot parse symbol: {source_symbol}")
    parts[-1] = target_expiry
    return '-'.join(parts)


# ---------------------------------------------------------------------------
# GET /api/options/roll/expiries — available expiry dates after current
# ---------------------------------------------------------------------------

@roll_manager_bp.route('/api/options/roll/expiries', methods=['GET'])
def roll_expiries():
    """
    Return available Delta Exchange expiry dates that are strictly after the
    position's current expiry.  Uses the options chain expirations endpoint.

    Query params:
      current_expiry — DDMMYY from the position symbol (e.g. 130326)
    """
    current_raw = request.args.get('current_expiry', '').strip()
    if not current_raw or len(current_raw) != 6:
        return jsonify({'success': False, 'error': 'current_expiry (DDMMYY) required'}), 400

    try:
        from datetime import date as Date
        dd, mm, yy = int(current_raw[0:2]), int(current_raw[2:4]), int(current_raw[4:6])
        current_date = Date(2000 + yy, mm, dd)
    except Exception:
        return jsonify({'success': False, 'error': f'Cannot parse expiry: {current_raw}'}), 400

    try:
        from webui.backend.options_chain.chain_service import OptionsChainService
        svc = OptionsChainService()
        all_expiries = svc.get_expirations('BTC')  # returns ['06032026', '13032026', ...]

        future_expiries = []
        for exp_str in all_expiries:
            try:
                # Format: DDMMYYYY
                d = int(exp_str[0:2])
                m = int(exp_str[2:4])
                y = int(exp_str[4:8])
                exp_date = Date(y, m, d)
                if exp_date > current_date:
                    # Convert to DDMMYY for symbol building
                    ddmmyy = f"{d:02d}{m:02d}{y % 100:02d}"
                    future_expiries.append({
                        'ddmmyy': ddmmyy,
                        'label': exp_date.strftime('%d %b %Y'),
                        'date': exp_date.isoformat(),
                    })
            except Exception:
                continue

        return jsonify({
            'success': True,
            'expiries': future_expiries,
            'current_expiry': current_date.isoformat(),
        })

    except Exception as e:
        logger.error("roll_expiries error: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


# ---------------------------------------------------------------------------
# GET /api/options/roll/quotes
# ---------------------------------------------------------------------------

def _fetch_quote_via_chain(symbol: str) -> dict:
    """
    Fetch live bid/ask for an options symbol using the proven bulk-tickers path
    (/v2/tickers?contract_types=call_options,put_options).  Falls back to the
    async L2-orderbook path when chain_service returns nothing (unlisted symbol).
    Returns a normalised dict: {bid, ask, mid, mark_price}.
    """
    try:
        from webui.backend.options_chain.chain_service import OptionsChainService
        svc = OptionsChainService()
        data = svc.get_option_ticker(symbol)
        if data and (data.get('bid') or data.get('ask') or data.get('mark_price')):
            bid = data['bid'] or None        # convert 0.0 (no market) → None
            ask = data['ask'] or None
            mark = data.get('mark_price') or None
            mid = round((bid + ask) / 2, 4) if bid and ask else mark
            return {'bid': bid, 'ask': ask, 'mid': mid, 'mark_price': mark, 'source': 'chain'}
    except Exception as e:
        logger.warning("chain_service quote failed for %s: %s", symbol, e)

    # Fallback: async orderbook / ticker (for newly-listed symbols not yet in chain cache)
    try:
        client = get_unified_client()

        async def _async_fallback():
            q = {}
            try:
                ob = await with_timeout(client.rest_client.get_orderbook(symbol), timeout_seconds=10)
                buys = ob.get('buy', [])
                sells = ob.get('sell', [])
                if buys and sells:
                    q['bid'] = float(buys[0].get('price', 0)) or None
                    q['ask'] = float(sells[0].get('price', 0)) or None
            except Exception:
                pass

            if not q.get('bid') or not q.get('ask'):
                try:
                    tk = await with_timeout(client.get_option_ticker(symbol), timeout_seconds=10)
                    q['bid'] = tk.get('bid') or None
                    q['ask'] = tk.get('ask') or None
                    q['mark_price'] = tk.get('mark_price')
                except Exception:
                    pass
            return q

        q = _run_async(_async_fallback())
        bid = q.get('bid')
        ask = q.get('ask')
        mid = round((bid + ask) / 2, 4) if bid and ask else q.get('mark_price')
        return {'bid': bid, 'ask': ask, 'mid': mid, 'mark_price': q.get('mark_price'), 'source': 'async'}
    except Exception as e:
        logger.error("async quote fallback also failed for %s: %s", symbol, e)
        return {'bid': None, 'ask': None, 'mid': None, 'mark_price': None, 'source': 'none'}


@roll_manager_bp.route('/api/options/roll/quotes', methods=['GET'])
def roll_quotes():
    """
    Return live bid/ask for both legs of a roll.
    Query params:
      symbol         — current position symbol  (e.g. C-BTC-90000-260328)
      target_expiry  — YYMMDD of target expiry  (e.g. 260404)
      size           — lots to roll (default 1)
    """
    symbol = request.args.get('symbol', '').strip()
    target_expiry = request.args.get('target_expiry', '').strip()
    size = int(request.args.get('size', 1))

    if not symbol or not target_expiry:
        return jsonify({'success': False, 'error': 'symbol and target_expiry are required'}), 400

    try:
        target_symbol = _build_target_symbol(symbol, target_expiry)
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400

    try:
        # Fetch both legs concurrently using threading (chain_service is synchronous)
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as pool:
            close_future = pool.submit(_fetch_quote_via_chain, symbol)
            new_future   = pool.submit(_fetch_quote_via_chain, target_symbol)
            close_q = close_future.result(timeout=20)
            new_q   = new_future.result(timeout=20)

        close_bid = close_q.get('bid')
        close_ask = close_q.get('ask')
        new_bid   = new_q.get('bid')
        new_ask   = new_q.get('ask')

        def _mid(b, a):
            if b and a:
                return round((b + a) / 2, 4)
            return None

        net_debit = None
        if close_ask is not None and new_bid is not None:
            net_debit = round((close_ask - new_bid) * size * _contract_multiplier(symbol), 4)

        logger.info(
            "roll_quotes %s→%s  close bid/ask=%s/%s  new bid/ask=%s/%s  net=%s",
            symbol, target_symbol,
            close_bid, close_ask, new_bid, new_ask, net_debit
        )

        return jsonify({
            'success': True,
            'source': {
                'symbol': symbol,
                'bid': close_bid,
                'ask': close_ask,
                'mid': _mid(close_bid, close_ask) or close_q.get('mark_price'),
            },
            'target': {
                'symbol': target_symbol,
                'bid': new_bid,
                'ask': new_ask,
                'mid': _mid(new_bid, new_ask) or new_q.get('mark_price'),
            },
            'net_debit': net_debit,
            'size': size,
        })
    except Exception as e:
        logger.error("roll_quotes error: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


# ---------------------------------------------------------------------------
# POST /api/options/roll/execute
# ---------------------------------------------------------------------------

@roll_manager_bp.route('/api/options/roll/execute', methods=['POST'])
def roll_execute():
    """
    Execute a roll: close existing position then open new position.
    Body:
      symbol         — current position symbol
      target_expiry  — YYMMDD of target expiry
      size           — lots (must be ≤ current position size)
      order_preference — 'smart' | 'market' (default: 'smart')
    """
    data = request.get_json() or {}
    symbol = data.get('symbol', '').strip()
    target_expiry = data.get('target_expiry', '').strip()
    size = int(data.get('size', 1))
    order_preference = data.get('order_preference', 'smart')

    if not symbol or not target_expiry:
        return jsonify({'success': False, 'error': 'symbol and target_expiry are required'}), 400

    try:
        target_symbol = _build_target_symbol(symbol, target_expiry)
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400

    try:
        client = get_unified_client()
        close_side = 'buy'   # closing a short = buy

        # Step 1: Close existing position
        async def _close():
            return await with_timeout(
                place_smart_order(
                    client=client,
                    symbol=symbol,
                    size=size,
                    side=close_side,
                    order_preference=order_preference,
                    reduce_only=True,
                ),
                timeout_seconds=30,
            )

        close_result = _run_async(_close())
        if close_result.get('success') is False:
            return jsonify({
                'success': False,
                'error': f"Close leg failed: {close_result.get('error', 'unknown')}",
                'closed': close_result,
            }), 400
        logger.info("[Roll] Closed %s x%d — %s", symbol, size, close_result.get('execution_type'))

        # Step 2: Open new position (sell)
        async def _open():
            return await with_timeout(
                place_smart_order(
                    client=client,
                    symbol=target_symbol,
                    size=size,
                    side='sell',
                    order_preference=order_preference,
                    reduce_only=False,
                ),
                timeout_seconds=30,
            )

        open_result = _run_async(_open())
        logger.info("[Roll] Opened %s x%d — %s", target_symbol, size, open_result.get('execution_type'))

        return jsonify({
            'success': True,
            'closed': {
                'symbol': symbol,
                'size': size,
                'execution_type': close_result.get('execution_type'),
                'fill_price': close_result.get('fill_price') or close_result.get('average_fill_price'),
            },
            'opened': {
                'symbol': target_symbol,
                'size': size,
                'execution_type': open_result.get('execution_type'),
                'fill_price': open_result.get('fill_price') or open_result.get('average_fill_price'),
            },
        })

    except Exception as e:
        logger.error("roll_execute error: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _parallel_quotes(client, symbol_a: str, symbol_b: str):
    """Fetch orderbook quotes for two symbols concurrently."""
    import asyncio
    results = await asyncio.gather(
        fetch_fresh_orderbook_quotes(client, symbol_a),
        fetch_fresh_orderbook_quotes(client, symbol_b),
        return_exceptions=True,
    )
    q_a = results[0] if not isinstance(results[0], Exception) else {}
    q_b = results[1] if not isinstance(results[1], Exception) else {}
    return q_a, q_b


def _contract_multiplier(symbol: str) -> float:
    upper = symbol.upper()
    if 'ETH' in upper:
        return 0.01
    return 0.001   # BTC default
