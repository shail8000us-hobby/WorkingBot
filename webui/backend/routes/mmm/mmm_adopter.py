"""
MMM Adopter — Money Mind & Method

Logic for adopting already-existing exchange positions into MMM sessions.

Components:
  - fetch_exchange_btc_options()     — Fetch open short BTC options from Delta Exchange
  - classify_positions()            — Map selected positions to active/frozen per side
  - validate_adoptable()            — Sanity-check before committing
  - build_adopted_session_state()   — Produce the full session state dict

Design principles:
  - Zero changes to runtime modules (monitor, engine, trigger, safety)
  - Once state is built, adopted sessions behave identically to import sessions
  - Trigger snapshots default to current prices ("take over from NOW")

Created: February 18, 2026
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

from .mmm_constants import LOT_SIZE_BTC, strike_key as _strike_key

log = logging.getLogger('mmm_adopter')


# =============================================================================
# 1. Fetch exchange positions
# =============================================================================

def fetch_exchange_btc_options(expiry_filter: str = None) -> Dict[str, Any]:
    """
    Fetch all open SHORT BTC options positions from Delta Exchange.

    Returns structured data ready for the adopt UI.

    Args:
        expiry_filter: Optional DDMMYYYY expiry to filter by

    Returns:
        {
            success: bool,
            positions: [ {symbol, side, strike, expiry, lots, entry_price,
                          mark_price, unrealized_pnl, iv, delta, theta, product_id} ],
            spot_price: float,
            expiries_with_positions: [str],
            error: str (if not success)
        }
    """
    try:
        from bot.api.delta_client import DeltaClient

        delta_client = DeltaClient()

        # Fetch all margined positions
        response = delta_client._req('GET', '/v2/positions/margined')
        if not response.get('success'):
            return {'success': False, 'error': 'Delta API returned unsuccessful response', 'positions': []}

        pos_list = response.get('result', [])
        log.info(f"[Adopter] Fetched {len(pos_list)} total positions from Delta Exchange")

        # Fetch spot price
        spot_price = 0.0
        try:
            from .mmm_initializer import get_initializer
            initializer = get_initializer()
            spot_price = initializer.get_spot_price('BTC')
        except Exception as e:
            log.warning(f"[Adopter] Could not fetch spot price: {e}")

        positions = []
        expiries_seen = set()

        for pos_data in pos_list:
            size = int(pos_data.get('size', 0))
            if size >= 0:
                # Skip LONG positions and empty — MMM only manages short options
                continue

            product_symbol = pos_data.get('product_symbol', '')
            product_id = int(pos_data.get('product_id', 0))

            # Only BTC options (symbol starts with C-BTC or P-BTC)
            if not (product_symbol.startswith('C-BTC') or product_symbol.startswith('P-BTC')):
                continue

            # Parse symbol: C-BTC-98000-180226 or P-BTC-92000-180226
            parts = product_symbol.split('-')
            if len(parts) < 4:
                log.warning(f"[Adopter] Cannot parse symbol: {product_symbol}")
                continue

            option_type = parts[0]  # 'C' or 'P'
            try:
                strike = float(parts[2])
            except (ValueError, IndexError):
                log.warning(f"[Adopter] Cannot parse strike from: {product_symbol}")
                continue

            expiry_str = parts[3]  # e.g., '180226' (DDMMYY)
            # Normalize to DDMMYYYY
            if len(expiry_str) == 6:
                expiry_full = expiry_str[:4] + '20' + expiry_str[4:]
            elif len(expiry_str) == 8:
                expiry_full = expiry_str
            else:
                log.warning(f"[Adopter] Cannot parse expiry from: {product_symbol}")
                continue

            # Apply expiry filter
            if expiry_filter and expiry_full != expiry_filter:
                continue

            expiries_seen.add(expiry_full)

            entry_price = float(pos_data.get('entry_price', 0))
            mark_price = float(pos_data.get('mark_price', 0))
            lots = abs(size)

            # Calculate unrealized PnL for SHORT: (entry - mark) × lots × LOT_SIZE_BTC
            unrealized_pnl = (entry_price - mark_price) * lots * LOT_SIZE_BTC

            # Fetch Greeks from ticker if available
            iv = 0.0
            delta_val = 0.0
            theta_val = 0.0
            try:
                ticker_resp = delta_client._req('GET', f'/v2/tickers/{product_symbol}')
                if ticker_resp.get('success'):
                    ticker_data = ticker_resp.get('result', {})
                    greeks = ticker_data.get('greeks', {})
                    iv = float(greeks.get('iv', 0))
                    delta_val = float(greeks.get('delta', 0))
                    theta_val = float(greeks.get('theta', 0))
                    # Use live mark_price from ticker if available
                    live_mark = float(ticker_data.get('mark_price', 0))
                    if live_mark > 0:
                        mark_price = live_mark
                        unrealized_pnl = (entry_price - mark_price) * lots * LOT_SIZE_BTC
            except Exception as e:
                # BATCH-D FIX BUG-3: Log instead of silently swallowing — ticker failure
                # also loses live mark_price, making unrealized_pnl stale.
                log.debug(f"[Adopter] Ticker fetch failed for {product_symbol}: {e}")

            side = 'CE' if option_type == 'C' else 'PE'

            positions.append({
                'symbol': product_symbol,
                'product_id': product_id,
                'side': side,
                'strike': strike,
                'expiry': expiry_full,
                'size': size,
                'lots': lots,
                'entry_price': round(entry_price, 2),
                'mark_price': round(mark_price, 2),
                'unrealized_pnl': round(unrealized_pnl, 4),
                'iv': round(iv, 4),
                'delta': round(delta_val, 4),
                'theta': round(theta_val, 4),
            })

        # Sort by expiry → side → strike
        positions.sort(key=lambda p: (p['expiry'], p['side'], p['strike']))

        return {
            'success': True,
            'positions': positions,
            'spot_price': spot_price,
            'expiries_with_positions': sorted(expiries_seen),
            'total_found': len(positions),
        }

    except Exception as e:
        log.exception("[Adopter] Failed to fetch exchange positions")
        return {'success': False, 'error': str(e), 'positions': []}


# =============================================================================
# 2. Classify positions into active/frozen per side
# =============================================================================

def classify_positions(
    selected_positions: List[Dict],
    spot_price: float = 0,
) -> Dict[str, Any]:
    """
    Classify selected positions into active and frozen per side.

    For each side (CE/PE):
      - Exactly one strike is "active" (the one MMM monitors for triggers)
      - All other strikes become "frozen"

    If the user provides role='active'/'frozen' on each position, use that.
    Otherwise auto-classify: closest to ATM = active.

    Args:
        selected_positions: List of position dicts, each with:
            symbol, side (CE/PE), strike, lots, entry_price, role (optional)
        spot_price: Current BTC spot for auto-classification

    Returns:
        {
            ce: { active: {strike, lots, entry_price, symbol}, frozen: [...] },
            pe: { active: {...}, frozen: [...] },
        }
    """
    ce_positions = [p for p in selected_positions if p['side'].upper() == 'CE']
    pe_positions = [p for p in selected_positions if p['side'].upper() == 'PE']

    result = {
        'ce': _classify_side(ce_positions, spot_price, 'CE'),
        'pe': _classify_side(pe_positions, spot_price, 'PE'),
    }

    return result


def _classify_side(
    positions: List[Dict],
    spot_price: float,
    side: str,
) -> Dict[str, Any]:
    """Classify positions on one side into active + frozen."""
    if not positions:
        return {'active': None, 'frozen': []}

    # Check if user explicitly assigned roles
    explicit_actives = [p for p in positions if p.get('role', '').lower() == 'active']

    if len(explicit_actives) == 1:
        active = explicit_actives[0]
    elif len(explicit_actives) > 1:
        # Multiple marked as active — pick closest to ATM
        active = min(explicit_actives, key=lambda p: abs(p['strike'] - spot_price)) if spot_price > 0 else explicit_actives[0]
    else:
        # No explicit roles — auto-classify: closest to ATM = active
        if spot_price > 0:
            active = min(positions, key=lambda p: abs(p['strike'] - spot_price))
        else:
            # Fallback: most lots = active
            active = max(positions, key=lambda p: p.get('lots', 0))

    # H-8 fix: use value equality, not identity check (breaks after JSON round-trip)
    frozen = [p for p in positions if p != active]

    return {
        'active': {
            'strike': active['strike'],
            'lots': active['lots'],
            'entry_price': active['entry_price'],
            'symbol': active['symbol'],
        },
        'frozen': [
            {
                'strike': f['strike'],
                'lots': f['lots'],
                'entry_price': f['entry_price'],
                'symbol': f['symbol'],
            }
            for f in frozen
        ],
    }


# =============================================================================
# 3. Validate adoptable
# =============================================================================

def validate_adoptable(
    classified: Dict,
    session_id: str = None,
    max_lots_per_side: int = 100,
) -> Dict[str, Any]:
    """
    Run sanity checks before allowing adoption.

    Args:
        classified: Output of classify_positions()
        session_id: Session ID being adopted into (for overlap check)
        max_lots_per_side: Maximum lots per side from params

    Returns:
        {
            valid: bool,
            warnings: [str],
            errors: [str],
            summary: { ce_total_lots, pe_total_lots, ce_strikes, pe_strikes,
                       total_premium_collected }
        }
    """
    warnings = []
    errors = []

    ce = classified.get('ce', {})
    pe = classified.get('pe', {})

    # --- Require both sides ---
    if not ce.get('active'):
        errors.append('No CE (Call) position selected. MMM requires both CE and PE sides.')
    if not pe.get('active'):
        errors.append('No PE (Put) position selected. MMM requires both CE and PE sides.')

    if errors:
        return {'valid': False, 'errors': errors, 'warnings': warnings, 'summary': {}}

    # --- Compute totals ---
    ce_active_lots = ce['active']['lots']
    ce_frozen_lots = sum(f['lots'] for f in ce.get('frozen', []))
    ce_total = ce_active_lots + ce_frozen_lots

    pe_active_lots = pe['active']['lots']
    pe_frozen_lots = sum(f['lots'] for f in pe.get('frozen', []))
    pe_total = pe_active_lots + pe_frozen_lots

    ce_strikes = [ce['active']['strike']] + [f['strike'] for f in ce.get('frozen', [])]
    pe_strikes = [pe['active']['strike']] + [f['strike'] for f in pe.get('frozen', [])]

    # --- Warnings ---
    if ce_total != pe_total:
        warnings.append(
            f"CE lots ({ce_total}) ≠ PE lots ({pe_total}) — asymmetric position. "
            f"This is allowed but may affect P&L balance."
        )

    if ce_total > max_lots_per_side:
        warnings.append(
            f"CE total lots ({ce_total}) exceeds max_lots_per_side ({max_lots_per_side}). "
            f"Safety cap will still apply."
        )

    if pe_total > max_lots_per_side:
        warnings.append(
            f"PE total lots ({pe_total}) exceeds max_lots_per_side ({max_lots_per_side}). "
            f"Safety cap will still apply."
        )

    if ce_active_lots == 0:
        errors.append('CE active strike has 0 lots. Must have at least 1 lot.')
    if pe_active_lots == 0:
        errors.append('PE active strike has 0 lots. Must have at least 1 lot.')

    # --- Cross-session overlap check ---
    try:
        from .mmm_storage import get_storage
        storage = get_storage()
        all_sessions = storage.list_sessions()

        all_symbols_to_adopt = set()
        if ce.get('active'):
            all_symbols_to_adopt.add(ce['active']['symbol'])
        for f in ce.get('frozen', []):
            all_symbols_to_adopt.add(f['symbol'])
        if pe.get('active'):
            all_symbols_to_adopt.add(pe['active']['symbol'])
        for f in pe.get('frozen', []):
            all_symbols_to_adopt.add(f['symbol'])

        for s in all_sessions:
            sid = s.get('session_id', '')
            if sid == session_id:
                continue
            s_status = s.get('strategy_status', 'IDLE')
            if s_status in ('STOPPED',):
                continue

            # Collect managed symbols for this other session
            managed_symbols = set()
            for side_key in ('ce', 'pe'):
                side_data = s.get(side_key, {})
                sym = side_data.get('symbol', '')
                if sym:
                    managed_symbols.add(sym)
                for fp in side_data.get('frozen_positions', []):
                    fsym = fp.get('symbol', '')
                    if fsym:
                        managed_symbols.add(fsym)

            overlap = all_symbols_to_adopt & managed_symbols
            if overlap:
                errors.append(
                    f"Position(s) {', '.join(overlap)} already managed by session '{sid}' "
                    f"(status: {s_status}). Cannot adopt."
                )
    except Exception as e:
        warnings.append(f"Could not check cross-session overlap: {e}")

    # --- Total premium sketch ---
    total_prem = 0.0
    for side_data in (ce, pe):
        active = side_data.get('active', {})
        total_prem += active.get('entry_price', 0) * active.get('lots', 0) * LOT_SIZE_BTC
        for fp in side_data.get('frozen', []):
            total_prem += fp.get('entry_price', 0) * fp.get('lots', 0) * LOT_SIZE_BTC

    summary = {
        'ce_active_lots': ce_active_lots,
        'ce_frozen_lots': ce_frozen_lots,
        'ce_total_lots': ce_total,
        'pe_active_lots': pe_active_lots,
        'pe_frozen_lots': pe_frozen_lots,
        'pe_total_lots': pe_total,
        'ce_strikes': ce_strikes,
        'pe_strikes': pe_strikes,
        'total_premium_collected': round(total_prem, 4),
    }

    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings,
        'summary': summary,
    }


# =============================================================================
# 4. Build adopted session state
# =============================================================================

def build_adopted_session_state(
    session: Dict,
    classified: Dict,
    trigger_mode: str = 'current_prices',
    expiry: str = '',
) -> Dict:
    """
    Populate session state from classified adopted positions.

    This produces a session state dict that is indistinguishable from one
    that was created via import mode + adjustments. Once built, all runtime 
    modules (monitor, engine, trigger, safety) work unchanged.

    Args:
        session: The session dict to populate (already created via create_session)
        classified: Output of classify_positions()
        trigger_mode: 'current_prices' | 'entry_prices'
        expiry: DDMMYYYY expiry string

    Returns:
        Updated session dict (mutated in place)
    """
    from .mmm_state import create_side_state, recompute_side_lots

    for side_key in ('ce', 'pe'):
        side_data = classified.get(side_key, {})
        active = side_data.get('active')

        if not active:
            continue

        side_label = side_key.upper()

        # Create base side state (Fix #23: positions[] initialized with original entry)
        side_state = create_side_state(
            side=side_label,
            original_lots=active['lots'],
            original_premium=active['entry_price'],
            original_strike=active['strike'],
        )

        # Set active strike
        side_state['active_strike'] = active['strike']
        side_state['symbol'] = active['symbol']

        # Fix #23: Add adopted frozen positions directly to positions[] (Unified Ledger)
        # Do NOT set frozen_positions directly — it is a computed view from positions[].
        frozen_list = side_data.get('frozen', [])
        now = datetime.now(timezone.utc).isoformat()
        # C-7 fix: ensure 'positions' key exists before appending
        if 'positions' not in side_state or side_state['positions'] is None:
            log.warning(f"[Adopter] 'positions' missing from {side_label} state — initializing empty")
            side_state['positions'] = []
        for i, fp in enumerate(frozen_list, start=1):
            counter = side_state.get('_pos_counter', 0) + 1
            side_state['_pos_counter'] = counter
            side_state['positions'].append({
                'id': f"{side_key}_frozen_{counter:03d}",
                'strike': fp.get('strike', 0),
                'lots': fp.get('lots', 0),
                'entry_premium': fp.get('entry_price', 0),
                'premium': fp.get('entry_price', 0),
                'type': fp.get('type', 'adjustment'),
                'status': 'shifted',
                'created_at': now,
                'shifted_at': now,
                'closed_at': None,
                'realized_pnl': None,
                'timestamp': now,
                'source': 'adopt',
                'symbol': fp.get('symbol', ''),
            })

        # Set trigger snapshot
        # Robust v2 Fix #13: Use canonical strike_key() for consistent keys
        if trigger_mode == 'entry_prices':
            side_state['trigger_snapshot'] = {
                _strike_key(active['strike']): active['entry_price'],
            }
        else:
            # Default: current_prices — will be set by caller after fetching live prices
            # For now set entry_price as fallback, caller will override
            side_state['trigger_snapshot'] = {
                _strike_key(active['strike']): active['entry_price'],
            }

        # Recompute lots (rebuilds frozen_positions view + all derived scalars)
        side_state = recompute_side_lots(side_state)

        session[side_key] = side_state

    # Set entry metadata
    session['entry_mode'] = 'adopt'
    session['entry_time'] = datetime.now(timezone.utc).isoformat()
    session['adopted_at'] = datetime.now(timezone.utc).isoformat()

    # Set lots (max of both sides for session-level, used by start_session)
    ce_lots = session.get('ce', {}).get('original_lots', 0)
    pe_lots = session.get('pe', {}).get('original_lots', 0)
    session['lots'] = max(ce_lots, pe_lots)

    # Set expiry on session
    # SAFETY: Validate expiry matches session creation expiry
    creation_expiry = session.get('params', {}).get('expiry', '')
    if expiry:
        if creation_expiry and creation_expiry != expiry:
            raise ValueError(
                f"Expiry mismatch: session was created with expiry {creation_expiry} "
                f"but adopt specifies {expiry}. This would route trades to wrong contracts."
            )
        # M-20 fix: warn when session has no creation expiry
        elif not creation_expiry:
            log.warning(f"[Adopter] Session has no creation_expiry; adopting with {expiry}")
        session['expiry'] = expiry

    # Calculate total premium collected across all positions
    total_premium = 0.0
    ce_premium = 0.0
    pe_premium = 0.0
    for side_key in ('ce', 'pe'):
        s = session.get(side_key, {})
        side_prem = s.get('original_premium', 0) * s.get('original_lots', 0) * LOT_SIZE_BTC
        for fp in s.get('frozen_positions', []):
            side_prem += fp.get('entry_premium', 0) * fp.get('lots', 0) * LOT_SIZE_BTC
        total_premium += side_prem
        if side_key == 'ce':
            ce_premium = side_prem
        else:
            pe_premium = side_prem

    session['initial_total_premium'] = round(total_premium, 6)
    session['total_premium_collected'] = round(total_premium, 6)
    session['ce_premium_collected'] = round(ce_premium, 6)
    session['pe_premium_collected'] = round(pe_premium, 6)

    # Store adoption snapshot for audit
    session['adoption_snapshot'] = {
        'classified': classified,
        'trigger_mode': trigger_mode,
        'adopted_at': datetime.now(timezone.utc).isoformat(),
        'expiry': expiry,
    }

    # Set expiry
    if expiry:
        session['params']['expiry'] = expiry
        try:
            from .mmm_initializer import expiry_to_utc_datetime
            session['expiry_time'] = expiry_to_utc_datetime(expiry)
        except Exception as e:
            log.warning(f"[Adopter] Could not compute expiry_time: {e}")

    session['updated_at'] = datetime.now(timezone.utc).isoformat()

    # Update analytics with initial adoption data
    analytics = session.get('analytics', {})
    ce = session.get('ce', {})
    pe = session.get('pe', {})
    analytics['initial_ce_lots'] = ce.get('total_lots', 0)
    analytics['initial_pe_lots'] = pe.get('total_lots', 0)
    analytics['max_ce_lots'] = ce.get('total_lots', 0)
    analytics['max_pe_lots'] = pe.get('total_lots', 0)
    analytics['max_combined_lots'] = ce.get('total_lots', 0) + pe.get('total_lots', 0)
    analytics['session_start_time'] = datetime.now(timezone.utc).isoformat()
    session['analytics'] = analytics

    log.info(
        f"[Adopter] Built session state: "
        f"CE active={ce.get('active_strike')}×{ce.get('active_lots')} + "
        f"{ce.get('frozen_total_lots')} frozen, "
        f"PE active={pe.get('active_strike')}×{pe.get('active_lots')} + "
        f"{pe.get('frozen_total_lots')} frozen, "
        f"total_premium={total_premium:.4f} BTC"
    )

    return session
