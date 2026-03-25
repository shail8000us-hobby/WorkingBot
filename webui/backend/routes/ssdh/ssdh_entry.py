"""
SSDH Entry — Atomic Entry Orchestrator

Places all 4 SSDH legs simultaneously via asyncio.gather.
Any single leg failure → rollback (cancel unfilled + market-close filled).
Never creates a partial structure.

Entry state machine: ENTRY_IDLE → ENTRY_PLACING → ENTRY_COMPLETE | ENTRY_ABORTED

Checkpoint persistence after each fill — crash recovery reads entry_fills
to determine what was already placed.

Created: March 21, 2026
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import List, Dict, Optional

log = logging.getLogger('ssdh_entry')


class AtomicEntryOrchestrator:
    """
    Executes all 4 legs in parallel. Rolls back on any failure.

    LegSpec dict:
    {
        'leg_id':         str,   # LEG_SHORT_CE | LEG_SHORT_PE | LEG_LONG_CE | LEG_LONG_PE
        'symbol':         str,   # Delta Exchange symbol e.g. 'C-BTC-100000-210326'
        'side':           str,   # 'CE' | 'PE'
        'direction':      str,   # DIR_SHORT | DIR_LONG
        'pos_type':       str,   # TYPE_CORE | TYPE_HEDGE
        'strike':         float,
        'lots':           int,
        'order_side':     str,   # 'sell' (shorts) | 'buy' (longs)
        'client_order_id':str,
    }
    """

    async def execute_entry(
        self,
        session: dict,
        executor,
        legs: List[dict],
    ) -> dict:
        """
        Places all legs simultaneously via asyncio.gather.

        Returns:
          {'success': True,  'positions': [position_dicts]}
          {'success': False, 'error': str, 'rollback_ok': bool}
        """
        from .ssdh_state import (
            create_position, persist_session,
            ENTRY_PLACING, ENTRY_COMPLETE, ENTRY_ABORTED,
            DIR_SHORT, TYPE_CORE,
        )
        from .ssdh_activity import log_activity

        # Set entry checkpoint state
        session['entry_state']      = ENTRY_PLACING
        session['entry_started_at'] = datetime.now(timezone.utc).isoformat()
        persist_session(session)

        log_activity('entry_starting',
            f"Placing {len(legs)} legs in parallel",
            session_id=session['session_id'], severity='progress')

        # Launch all legs simultaneously
        timeout = int(session['params'].get('entry_timeout_seconds', 180))
        tasks   = [self._place_leg(executor, session, leg) for leg in legs]

        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            log_activity('entry_failed', 'Entry timed out — rolling back all fills',
                session_id=session['session_id'], severity='error')
            return await self._rollback(session, executor,
                fills=[], failures=[{'leg': None, 'error': 'entry_timeout'}])

        # Categorise results
        fills    = []
        failures = []
        for leg, result in zip(legs, results):
            if isinstance(result, Exception):
                failures.append({'leg': leg, 'error': str(result)})
            elif not (result or {}).get('success'):
                failures.append({'leg': leg, 'error': (result or {}).get('error', 'unknown')})
            else:
                fills.append({'leg': leg, 'result': result})
                session['entry_fills'][leg['leg_id']] = result
                persist_session(session)   # checkpoint after each fill

                log_activity('entry_leg_filled',
                    f"{leg['direction'].upper()} {leg['side']} @ {result.get('fill_price', 0):.2f}",
                    session_id=session['session_id'], severity='success')

        if failures:
            err_summary = '; '.join(f["error"] for f in failures)
            log_activity('entry_failed',
                f"Entry failed ({len(failures)}/{len(legs)} legs): {err_summary}",
                session_id=session['session_id'], severity='error')
            return await self._rollback(session, executor, fills, failures)

        # Build position objects from fills
        positions = []
        for item in fills:
            leg    = item['leg']
            result = item['result']
            pos    = create_position(
                pos_id            = leg['leg_id'],
                side              = leg['side'],
                direction         = leg['direction'],
                pos_type          = leg['pos_type'],
                strike            = leg['strike'],
                lots              = leg['lots'],
                entry_premium     = result['fill_price'],
                order_id          = result['order_id'],
                client_order_id   = result['client_order_id'],
                fill_confirmed_at = result['fill_confirmed_at'],
                symbol            = leg.get('symbol', ''),
            )
            positions.append(pos)
            session['positions'].append(pos)

            # Accumulate entry fees
            session['total_fees'] = float(
                session.get('total_fees', 0.0) + result.get('fees', 0.0)
            )

        session['entry_state'] = ENTRY_COMPLETE
        persist_session(session)

        log_activity('entry_complete',
            f"All {len(legs)} legs filled",
            session_id=session['session_id'], severity='success')

        return {'success': True, 'positions': positions}

    async def _place_leg(self, executor, session: dict, leg: dict) -> dict:
        """Place a single leg using the executor."""
        session_id = session['session_id']
        params     = session['params']

        if leg['order_side'] == 'sell':
            return await executor.sell_option(
                session_id       = session_id,
                symbol           = leg['symbol'],
                strike           = leg['strike'],
                lots             = leg['lots'],
                client_order_id  = leg['client_order_id'],
                session_params   = params,
            )
        else:
            return await executor.buy_option(
                session_id       = session_id,
                symbol           = leg['symbol'],
                strike           = leg['strike'],
                lots             = leg['lots'],
                client_order_id  = leg['client_order_id'],
                session_params   = params,
            )

    async def _rollback(
        self, session: dict, executor, fills: list, failures: list
    ) -> dict:
        """
        Close all filled legs at market immediately.
        Set entry_state = ENTRY_ABORTED.
        Returns {'success': False, 'error': ..., 'rollback_ok': bool}
        """
        from .ssdh_state import persist_session, ENTRY_ABORTED
        from .ssdh_activity import log_activity

        log_activity('entry_rollback',
            f"Rolling back {len(fills)} filled leg(s)",
            session_id=session['session_id'], severity='warning')

        rollback_errors = []
        close_tasks = []
        for item in fills:
            leg    = item['leg']
            result = item['result']
            close_tasks.append(
                executor.emergency_execute(
                    position={
                        'pos_id':    leg['leg_id'],
                        'direction': leg['direction'],
                        'side':      leg['side'],
                        'lots':      leg['lots'],
                    },
                    session_id = session['session_id'],
                    symbol     = leg['symbol'],
                )
            )

        if close_tasks:
            close_results = await asyncio.gather(*close_tasks, return_exceptions=True)
            for i, r in enumerate(close_results):
                if isinstance(r, Exception) or not (r or {}).get('success'):
                    rollback_errors.append(str(r))
                    log_activity('entry_rollback_failed',
                        f"Rollback leg {i} failed: {r}",
                        session_id=session['session_id'], severity='error')

        rollback_ok = len(rollback_errors) == 0
        session['entry_state'] = ENTRY_ABORTED
        persist_session(session)

        if rollback_ok:
            log_activity('entry_rollback_ok', 'All rollback closes confirmed',
                session_id=session['session_id'], severity='success')
        else:
            log_activity('entry_rollback_failed',
                f"Rollback partial: {rollback_errors}",
                session_id=session['session_id'], severity='error')

        err_msgs = '; '.join(f['error'] for f in failures)
        return {
            'success':     False,
            'error':       err_msgs,
            'rollback_ok': rollback_ok,
        }

    def resume_from_checkpoint(self, session: dict, executor) -> str:
        """
        Called on monitor startup if entry_state != ENTRY_COMPLETE.
        Determines whether to resume (try remaining legs) or rollback (timeout elapsed).

        Returns: 'resuming' | 'rolling_back' | 'already_complete' | 'aborted'
        """
        from .ssdh_state import ENTRY_COMPLETE, ENTRY_ABORTED, ENTRY_IDLE

        state = session.get('entry_state', ENTRY_IDLE)

        if state == ENTRY_COMPLETE:
            return 'already_complete'
        if state == ENTRY_ABORTED:
            return 'aborted'

        started = session.get('entry_started_at')
        if not started:
            return 'rolling_back'

        try:
            started_ts = datetime.fromisoformat(started.replace('Z', '+00:00'))
            elapsed    = (datetime.now(timezone.utc) - started_ts).total_seconds()
            timeout    = int(session['params'].get('entry_timeout_seconds', 180))

            if elapsed < timeout:
                log.info("resume_from_checkpoint: %ds elapsed of %ds — resuming", int(elapsed), timeout)
                return 'resuming'
            else:
                log.warning("resume_from_checkpoint: %ds elapsed > %ds timeout — rolling back", int(elapsed), timeout)
                return 'rolling_back'
        except Exception as e:
            log.error("resume_from_checkpoint error: %s", e)
            return 'rolling_back'
