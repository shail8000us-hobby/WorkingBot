"""
MMMX Hedger — Deferred Hedge Execution After Tr5+ Deployment

Spec: MMMX_COMPLETE.md Section 7 (Hedger), MMMX_IMPLEMENTATION_PLAN.md Phase 7.

Hedging activates only after tranches_deployed >= 5 (>= 50 lots deployed).
Hedge execution is deferred by hedge_execution_delay_minutes (default 15).

Key functions:
  schedule_post_deploy(session, tranche_id, deployed_at) — schedule a hedge after Tr5+ deploy
  tick(session, executor, audit) → List[dict]            — execute PENDING hedges when due
  update_hedge_pnl(session, live_quotes)                 — refresh unrealized P&L each beat
  detect_displacement(session, repositioned_parent_id)   — mark hedge ORPHANED on parent reposition

Invariants (DO NOT BREAK):
  - Hedger uses smart_execute (NOT emergency_execute).
  - Hedges are NOT closed by hard stop or parent reposition — they are marked ORPHANED and left open.
  - Hedges are only scheduled for tranches_deployed >= 5.
  - Tr1–Tr4 deployments do NOT produce hedges.
  - All timestamps: datetime.now(timezone.utc).isoformat() — never naive utcnow().
  - Isolation: ZERO imports from routes.mmm.* in this file.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from .mmmx_constants import (
    LOT_SIZE_BTC,
    HEDGE_CAPACITY_THRESHOLD_LOTS,
    HedgeStatus,
)
from .mmmx_state import make_hedge

log = logging.getLogger('mmmx_hedger')


# ── Scheduling ─────────────────────────────────────────────────────────────────

def schedule_post_deploy(
    session: Dict[str, Any],
    tranche_id: Any,
    deployed_at: str,
) -> Optional[Dict[str, Any]]:
    """
    Schedule a hedge entry after a tranche deployment.

    Only schedules when tranches_deployed >= 5 (HEDGE_CAPACITY_THRESHOLD_LOTS / 10
    tranches = 50 lots minimum) AND hedging_enabled is True.

    Args:
        session:     Live session dict (will be mutated).
        tranche_id:  ID of the tranche just deployed.
        deployed_at: ISO UTC timestamp of the deployment.

    Returns:
        The schedule entry dict if one was created, else None.
    """
    if not session.get('params', {}).get('hedging_enabled', True):
        return None

    tranches_deployed = session.get('tranches_deployed', 0)
    if tranches_deployed < 5:
        # Below capacity threshold — no hedge
        return None

    params = session.get('params', {})
    delay_mins = float(params.get('hedge_execution_delay_minutes', 15))

    try:
        deploy_dt = datetime.fromisoformat(deployed_at)
        if deploy_dt.tzinfo is None:
            deploy_dt = deploy_dt.replace(tzinfo=timezone.utc)
    except Exception:
        deploy_dt = datetime.now(timezone.utc)

    execute_after = (deploy_dt + timedelta(minutes=delay_mins)).isoformat()

    # Derive lots from the parent tranche
    lots = 10  # default (1 tranche = 10 lots)
    for t in session.get('tranches', []):
        if t.get('tranche_id') == tranche_id:
            lots = t['ce'].get('lots', 10)
            break

    entry = {
        'tranche_id':    tranche_id,
        'execute_after': execute_after,
        'lots':          lots,
        'status':        'PENDING',
    }

    session.setdefault('_hedge_schedule', []).append(entry)
    log.info(
        f"[Hedger] Tr{tranche_id}: hedge scheduled for "
        f"{execute_after} ({lots} lots)"
    )
    return entry


# ── Execution ──────────────────────────────────────────────────────────────────

async def tick(
    session: Dict[str, Any],
    executor,
    audit,
) -> List[Dict[str, Any]]:
    """
    Execute PENDING hedge schedule entries whose execute_after time has passed.

    For each eligible entry:
      1. Calls smart_execute to buy CE and PE hedge options.
      2. On success: creates hedge via make_hedge(), appends to session['hedges'].
      3. Marks schedule entry as EXECUTED.

    Args:
        session:  Live session dict.
        executor: MMMXExecutor instance (must have smart_execute).
        audit:    MMMXAuditLog instance.

    Returns:
        List of hedge dicts that were newly executed.
    """
    schedule = session.get('_hedge_schedule', [])
    if not schedule:
        return []

    now = datetime.now(timezone.utc)
    executed: List[Dict[str, Any]] = []

    for entry in schedule:
        if entry.get('status') != 'PENDING':
            continue

        # Check if it is time to execute
        try:
            exec_after_dt = datetime.fromisoformat(entry['execute_after'])
            if exec_after_dt.tzinfo is None:
                exec_after_dt = exec_after_dt.replace(tzinfo=timezone.utc)
        except Exception as exc:
            log.error(f"[Hedger] Bad execute_after in schedule: {exc}")
            continue

        if now < exec_after_dt:
            continue

        tranche_id = entry['tranche_id']
        lots = entry.get('lots', 10)
        parent = _find_tranche(session, tranche_id)

        if parent is None:
            log.warning(f"[Hedger] Tr{tranche_id}: parent tranche not found — skipping hedge")
            entry['status'] = 'SKIPPED'
            continue

        ce_leg = parent['ce']
        pe_leg = parent['pe']

        # Execute CE hedge buy (buy further OTM call as protection)
        ce_result = await executor.smart_execute(
            symbol=ce_leg['symbol'],
            side='buy',
            size=lots,
            action=f'HEDGE_CE_Tr{tranche_id}',
            session_id=session.get('session_id', ''),
            tranche_id=tranche_id,
        )

        # Execute PE hedge buy (buy further OTM put as protection)
        pe_result = await executor.smart_execute(
            symbol=pe_leg['symbol'],
            side='buy',
            size=lots,
            action=f'HEDGE_PE_Tr{tranche_id}',
            session_id=session.get('session_id', ''),
            tranche_id=tranche_id,
        )

        if not (ce_result.success and pe_result.success):
            log.warning(
                f"[Hedger] Tr{tranche_id}: hedge execution partial/failed — "
                f"CE={ce_result.success}, PE={pe_result.success}"
            )
            entry['status'] = 'FAILED'
            continue

        # Build hedge dict
        hedge = make_hedge(
            parent_tranche_id=tranche_id,
            entry_spot=session.get('last_deployment_spot') or 0.0,
            hedge_distance_pct=session.get('params', {}).get('hedge_distance_pct', 20.0),
            ce_symbol=ce_leg['symbol'],
            ce_strike=ce_leg.get('strike', 0.0),
            ce_lots=lots,
            ce_premium=float(ce_result.avg_price or ce_leg.get('entry_premium', 0.0)),
            ce_delta=ce_leg.get('entry_delta', 0.0),
            pe_symbol=pe_leg['symbol'],
            pe_strike=pe_leg.get('strike', 0.0),
            pe_lots=lots,
            pe_premium=float(pe_result.avg_price or pe_leg.get('entry_premium', 0.0)),
            pe_delta=pe_leg.get('entry_delta', 0.0),
            ce_spread_width=0.0,
            pe_spread_width=0.0,
        )
        hedge['hedge_executed_at'] = now.isoformat()

        # Append to session
        session.setdefault('hedges', []).append(hedge)
        session.setdefault('hedges_by_parent', {})[str(tranche_id)] = hedge['hedge_id']
        session['active_hedges'] = session.get('active_hedges', 0) + 1
        hedge_premium_paid = hedge.get('hedge_premium_paid', 0.0)
        session['total_hedge_cost_paid'] = (
            session.get('total_hedge_cost_paid', 0.0) + hedge_premium_paid
        )

        # Mark schedule entry as executed
        entry['status'] = 'EXECUTED'

        executed.append(hedge)
        log.info(
            f"[Hedger] Tr{tranche_id}: hedge H-Tr{tranche_id} executed "
            f"({lots} lots, premium_paid={hedge_premium_paid:.2f})"
        )

        # Audit log
        try:
            audit.enqueue_event(
                session_id=session.get('session_id', ''),
                category='HEDGE',
                message=f"Hedge H-Tr{tranche_id} executed: {lots} lots",
                data={'hedge_id': hedge['hedge_id'], 'tranche_id': tranche_id},
            )
        except Exception:
            pass

    return executed


# ── P&L update ─────────────────────────────────────────────────────────────────

def update_hedge_pnl(
    session: Dict[str, Any],
    live_quotes: Dict[str, Any],
) -> None:
    """
    Recompute unrealized P&L for every ACTIVE hedge using live_quotes.

    live_quotes: {symbol -> tick_dict with 'mark_price' or 'bid'/'ask'}

    Mutates hedge['ce']['unrealized_pnl'], hedge['pe']['unrealized_pnl'],
    and hedge['ce']['current_premium'], hedge['pe']['current_premium'].
    """
    for hedge in session.get('hedges', []):
        if hedge.get('status') != HedgeStatus.ACTIVE:
            continue

        for side in ('ce', 'pe'):
            leg = hedge[side]
            symbol = leg.get('symbol', '')
            tick = live_quotes.get(symbol)
            if tick is None:
                continue

            current_price = (
                tick.get('mark_price')
                or tick.get('mid')
                or ((tick.get('bid', 0.0) + tick.get('ask', 0.0)) / 2)
                or 0.0
            )
            if current_price <= 0:
                continue

            leg['current_premium'] = current_price
            entry_premium = leg.get('entry_premium', 0.0)
            lots = leg.get('lots', 0)
            # LONG position: pnl = (current - entry) * lots * LOT_SIZE_BTC
            leg['unrealized_pnl'] = (current_price - entry_premium) * lots * LOT_SIZE_BTC


# ── Displacement detection ─────────────────────────────────────────────────────

def detect_displacement(
    session: Dict[str, Any],
    repositioned_parent_id: Any,
) -> Optional[Dict[str, Any]]:
    """
    Mark the hedge for the repositioned parent tranche as ORPHANED.

    Does NOT close the hedge — orphaned hedges are left open per spec.
    Sends a Telegram alert and logs.

    Returns the affected hedge dict, or None if no hedge found.
    """
    affected = None

    for hedge in session.get('hedges', []):
        if hedge.get('parent_tranche_id') == repositioned_parent_id:
            if hedge.get('status') == HedgeStatus.ACTIVE:
                hedge['status'] = HedgeStatus.ORPHANED
                hedge['displaced_from_parent_at'] = datetime.now(timezone.utc).isoformat()
                session['active_hedges'] = max(0, session.get('active_hedges', 0) - 1)
                affected = hedge
                log.warning(
                    f"[Hedger] Hedge {hedge['hedge_id']} marked ORPHANED "
                    f"(parent Tr{repositioned_parent_id} repositioned). "
                    "Hedge NOT closed — stays open."
                )
                try:
                    from .mmmx_telegram import send_alert
                    send_alert(
                        f"⚠️ Hedge {hedge['hedge_id']} ORPHANED — "
                        f"parent Tr{repositioned_parent_id} repositioned. "
                        "Hedge remains open.",
                        alert_type=f'hedge_orphaned_{repositioned_parent_id}',
                        session_id=session.get('session_id'),
                        dedup_ttl=120,
                    )
                except Exception:
                    pass
                break

    return affected


# ── Helpers ────────────────────────────────────────────────────────────────────

def _find_tranche(session: Dict[str, Any], tranche_id: Any) -> Optional[Dict[str, Any]]:
    for t in session.get('tranches', []):
        if t.get('tranche_id') == tranche_id:
            return t
    return None
