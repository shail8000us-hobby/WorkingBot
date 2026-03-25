"""
SSDH Integrity — Structure Integrity Check

Verifies all 4 SSDH legs are present and active every heartbeat.
If any leg is missing → emergency exit.

Rule: only runs after ENTRY_COMPLETE.
During entry: always returns (True, 'Entry not complete — skipping check').

Created: March 21, 2026
"""

import logging
from typing import Tuple

log = logging.getLogger('ssdh_integrity')


def check_structure_integrity(session: dict) -> Tuple[bool, str]:
    """
    Verifies all 4 leg types are present and active.
    Only runs if entry_state == ENTRY_COMPLETE.

    Checks:
    - At least 1 active short CE  (TYPE_CORE,  DIR_SHORT, side='CE')
    - At least 1 active short PE  (TYPE_CORE,  DIR_SHORT, side='PE')
    - At least 1 active long  CE  (TYPE_HEDGE, DIR_LONG,  side='CE')
    - At least 1 active long  PE  (TYPE_HEDGE, DIR_LONG,  side='PE')

    Returns (ok, reason).
    If ok=False: reason names the missing leg.
    e.g.: (False, 'CE short leg missing — possible liquidation or manual close')
    """
    from .ssdh_state import ENTRY_COMPLETE, get_positions_by_type, DIR_SHORT, DIR_LONG

    if not session.get('params', {}).get('structure_integrity_check', True):
        return True, 'integrity check disabled'

    entry_state = session.get('entry_state')
    if entry_state != ENTRY_COMPLETE:
        return True, 'Entry not complete — skipping check'

    checks = [
        (DIR_SHORT, 'CE', 'CE short leg missing — possible liquidation or manual close'),
        (DIR_SHORT, 'PE', 'PE short leg missing — possible liquidation or manual close'),
        (DIR_LONG,  'CE', 'CE long hedge missing — structure incomplete'),
        (DIR_LONG,  'PE', 'PE long hedge missing — structure incomplete'),
    ]

    for direction, side, error_msg in checks:
        positions = get_positions_by_type(session, direction, side)
        if not positions:
            log.critical("SSDH structure break: %s", error_msg)
            return False, error_msg

    return True, 'structure intact'
