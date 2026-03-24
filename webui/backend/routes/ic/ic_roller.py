"""
IC Roller — Iron Condor Roll Execution

Executes roll adjustments:
  1. Close old spread (2 legs)
  2. Open new spread (2 legs) at new strikes
  3. Track roll credit/debit
  4. Update cycle state

From IC_ALGO_PLAN.md §9.3.

Created: 2026-03-24
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from .ic_constants import (
    LEG_SP, LEG_LP, LEG_SC, LEG_LC,
    LEG_CLOSED, LEG_ROLLED,
    ADJ_ROLL_CALL_UP, ADJ_ROLL_PUT_DOWN, ADJ_ROLL_BOTH,
)
from .ic_state import create_leg_state, compute_cycle_strikes
from .ic_engine import compute_roll_credit
from .ic_adjuster import (
    create_adjustment_event, record_adjustment, estimate_roll_credit_viable,
)

log = logging.getLogger('ic_roller')


def execute_roll_call_up(
    cycle: Dict,
    session: Dict,
    executor,
    new_sc_data: Dict,
    new_lc_data: Dict,
    spot: float,
) -> bool:
    """
    Roll the call spread up (market moved up, call side threatened).

    §9.3 Steps:
      1. Close SC + LC at market
      2. Open new SC' + LC' at higher strikes
      3. Update leg state and cumulative roll credit

    Returns:
        True if roll succeeded
    """
    legs = cycle.get('legs', {})
    params = session.get('params', {})
    lots = params.get('lots', 10)
    simulate = params.get('simulate', False)

    old_sc = legs.get(LEG_SC, {})
    old_lc = legs.get(LEG_LC, {})

    # Step 1: Close old call spread
    old_close_premiums = {
        LEG_SC: old_sc.get('mark_premium', 0),
        LEG_LC: old_lc.get('mark_premium', 0),
    }

    if simulate:
        log.info(
            f"[SIMULATE] Roll call up: close SC@{old_sc.get('strike')} + "
            f"LC@{old_lc.get('strike')}"
        )
    else:
        # TODO: Real close via executor
        pass

    # Mark old legs as rolled
    old_sc['status'] = LEG_ROLLED
    old_sc['close_premium'] = old_close_premiums[LEG_SC]
    old_sc['close_time'] = datetime.now(timezone.utc).isoformat()

    old_lc['status'] = LEG_ROLLED
    old_lc['close_premium'] = old_close_premiums[LEG_LC]
    old_lc['close_time'] = datetime.now(timezone.utc).isoformat()

    # Step 2: Open new call spread
    new_sc_premium = new_sc_data.get('bid', new_sc_data.get('premium', 0))
    new_lc_premium = new_lc_data.get('ask', new_lc_data.get('premium', 0))

    new_entry_premiums = {
        LEG_SC: new_sc_premium,
        LEG_LC: new_lc_premium,
    }

    new_sc_leg = create_leg_state(
        leg_key=LEG_SC, strike=new_sc_data['strike'], lots=lots,
        side='call', action='sell', entry_premium=new_sc_premium,
    )
    new_lc_leg = create_leg_state(
        leg_key=LEG_LC, strike=new_lc_data['strike'], lots=lots,
        side='call', action='buy', entry_premium=new_lc_premium,
    )

    if 'symbol' in new_sc_data:
        new_sc_leg['product_symbol'] = new_sc_data['symbol']
    if 'symbol' in new_lc_data:
        new_lc_leg['product_symbol'] = new_lc_data['symbol']

    if simulate:
        log.info(
            f"[SIMULATE] Open new SC@{new_sc_data['strike']} + "
            f"LC@{new_lc_data['strike']}"
        )

    # Replace legs in cycle
    legs[LEG_SC] = new_sc_leg
    legs[LEG_LC] = new_lc_leg

    # Step 3: Compute roll credit
    new_legs = {LEG_SC: new_sc_leg, LEG_LC: new_lc_leg}
    old_legs = {LEG_SC: old_sc, LEG_LC: old_lc}

    roll_credit = compute_roll_credit(
        old_close_premiums, new_entry_premiums, old_legs, new_legs
    )

    cycle['cumulative_roll_credit'] = round(
        cycle.get('cumulative_roll_credit', 0) + roll_credit, 4
    )

    # Update strikes
    compute_cycle_strikes(cycle)

    # Record adjustment event
    adj_event = create_adjustment_event(
        adj_type=ADJ_ROLL_CALL_UP,
        trigger='breach_call',
        spot=spot,
        old_strikes={'SC': old_sc.get('strike', 0), 'LC': old_lc.get('strike', 0)},
        new_strikes={'SC': new_sc_data['strike'], 'LC': new_lc_data['strike']},
        roll_credit=roll_credit,
        cumulative_roll_credit=cycle['cumulative_roll_credit'],
    )
    record_adjustment(session, cycle, adj_event)

    log.info(
        f"[{session.get('session_id', '?')}] Roll call up complete: "
        f"SC {old_sc.get('strike')} → {new_sc_data['strike']}, "
        f"roll credit ${roll_credit:.4f}/BTC"
    )

    return True


def execute_roll_put_down(
    cycle: Dict,
    session: Dict,
    executor,
    new_sp_data: Dict,
    new_lp_data: Dict,
    spot: float,
) -> bool:
    """
    Roll the put spread down (market moved down, put side threatened).

    Symmetric to execute_roll_call_up but for the put side.
    """
    legs = cycle.get('legs', {})
    params = session.get('params', {})
    lots = params.get('lots', 10)
    simulate = params.get('simulate', False)

    old_sp = legs.get(LEG_SP, {})
    old_lp = legs.get(LEG_LP, {})

    # Close old put spread
    old_close_premiums = {
        LEG_SP: old_sp.get('mark_premium', 0),
        LEG_LP: old_lp.get('mark_premium', 0),
    }

    if simulate:
        log.info(
            f"[SIMULATE] Roll put down: close SP@{old_sp.get('strike')} + "
            f"LP@{old_lp.get('strike')}"
        )

    old_sp['status'] = LEG_ROLLED
    old_sp['close_premium'] = old_close_premiums[LEG_SP]
    old_sp['close_time'] = datetime.now(timezone.utc).isoformat()

    old_lp['status'] = LEG_ROLLED
    old_lp['close_premium'] = old_close_premiums[LEG_LP]
    old_lp['close_time'] = datetime.now(timezone.utc).isoformat()

    # Open new put spread
    new_sp_premium = new_sp_data.get('bid', new_sp_data.get('premium', 0))
    new_lp_premium = new_lp_data.get('ask', new_lp_data.get('premium', 0))

    new_entry_premiums = {
        LEG_SP: new_sp_premium,
        LEG_LP: new_lp_premium,
    }

    new_sp_leg = create_leg_state(
        leg_key=LEG_SP, strike=new_sp_data['strike'], lots=lots,
        side='put', action='sell', entry_premium=new_sp_premium,
    )
    new_lp_leg = create_leg_state(
        leg_key=LEG_LP, strike=new_lp_data['strike'], lots=lots,
        side='put', action='buy', entry_premium=new_lp_premium,
    )

    if 'symbol' in new_sp_data:
        new_sp_leg['product_symbol'] = new_sp_data['symbol']
    if 'symbol' in new_lp_data:
        new_lp_leg['product_symbol'] = new_lp_data['symbol']

    if simulate:
        log.info(
            f"[SIMULATE] Open new SP@{new_sp_data['strike']} + "
            f"LP@{new_lp_data['strike']}"
        )

    legs[LEG_SP] = new_sp_leg
    legs[LEG_LP] = new_lp_leg

    # Compute roll credit
    new_legs = {LEG_SP: new_sp_leg, LEG_LP: new_lp_leg}
    old_legs = {LEG_SP: old_sp, LEG_LP: old_lp}

    roll_credit = compute_roll_credit(
        old_close_premiums, new_entry_premiums, old_legs, new_legs
    )

    cycle['cumulative_roll_credit'] = round(
        cycle.get('cumulative_roll_credit', 0) + roll_credit, 4
    )

    compute_cycle_strikes(cycle)

    adj_event = create_adjustment_event(
        adj_type=ADJ_ROLL_PUT_DOWN,
        trigger='breach_put',
        spot=spot,
        old_strikes={'SP': old_sp.get('strike', 0), 'LP': old_lp.get('strike', 0)},
        new_strikes={'SP': new_sp_data['strike'], 'LP': new_lp_data['strike']},
        roll_credit=roll_credit,
        cumulative_roll_credit=cycle['cumulative_roll_credit'],
    )
    record_adjustment(session, cycle, adj_event)

    log.info(
        f"[{session.get('session_id', '?')}] Roll put down complete: "
        f"SP {old_sp.get('strike')} → {new_sp_data['strike']}, "
        f"roll credit ${roll_credit:.4f}/BTC"
    )

    return True
