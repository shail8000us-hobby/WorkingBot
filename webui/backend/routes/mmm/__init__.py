"""
MMM — Money Mind & Method

BTC 0DTE Options Selling Algorithm with auto-adjustment, strike shifting,
close-at-5, and reversal handling.

Logic reference: MONEY_POWER_CALCULATION_LOGIC.md
Development plan: MMM_DEVELOPMENT_PLAN.md

Created: February 15, 2026
"""

from .mmm_api import mmm_bp
from .mmm_websocket import init_websocket
from .mmm_initializer import get_initializer
from .mmm_executor import get_executor
from .mmm_engine import get_engine
from .mmm_safety import get_safety
from .mmm_monitor import (
    start_session_monitor, stop_session_monitor,
    pause_session_monitor, resume_session_monitor,
    get_monitor, get_all_monitors,
)

__all__ = [
    'mmm_bp',
    'init_mmm',
    'init_websocket',
    'get_initializer',
    'get_executor',
    'get_engine',
    'get_safety',
    'start_session_monitor',
    'stop_session_monitor',
    'pause_session_monitor',
    'resume_session_monitor',
    'get_monitor',
    'get_all_monitors',
]


def init_mmm():
    """
    Initialize MMM module on backend startup.

    - Initializes the position sub-ledger (mmm_ledger.py)
    - Restores active sessions from storage
    - Logs session summary
    - Auto-restores heartbeat monitors for RUNNING/PAUSED sessions

    Call this after registering the blueprint in app.py.
    """
    import logging
    log = logging.getLogger('mmm')

    # Initialize the persistent position sub-ledger (creates schema if needed)
    try:
        from .mmm_ledger import init_ledger
        init_ledger()
    except Exception as _ledger_err:
        log.error(f"MMM ledger init failed (non-critical): {_ledger_err}")

    # Start authenticated WebSocket executions channel (real-time fill ledger source)
    try:
        from .mmm_ws_executions import get_executions_ws
        get_executions_ws().start()
        print("[MMM] Executions WS started")
        log.info("MMM Executions WS started")
    except Exception as _exec_ws_err:
        print(f"[MMM] ⚠️ Executions WS failed to start: {_exec_ws_err}")
        log.warning(f"MMM Executions WS failed to start: {_exec_ws_err}")

    try:
        from .mmm_storage import get_storage

        storage = get_storage()
        active_ids = storage.get_active_session_ids()
        total_count = storage.get_session_count()

        print(f"[MMM] Initializing: {total_count} session(s) in storage, {len(active_ids)} active")
        log.info(f"MMM initializing: {total_count} session(s) in storage, {len(active_ids)} active")

        if active_ids:
            log.info(f"Active session IDs: {active_ids}")
            # Restore heartbeat monitors for RUNNING/PAUSED sessions
            restored_count = 0
            for sid in active_ids:
                try:
                    session = storage.get_session(sid)
                    if not session:
                        log.warning(f"  Session {sid} listed as active but not found in storage, skipping")
                        continue
                    
                    status = session.get('strategy_status', 'UNKNOWN')
                    
                    # Restore monitors for RUNNING, PAUSED, or mid-exit sessions
                    if status in ('RUNNING', 'PAUSED', 'BOTH_SIDES_UP', 'PARTIAL_ENTRY', 'EXITING'):
                        print(f"[MMM] Restoring monitor for session {sid} (status={status})")
                        log.info(f"  Restoring monitor for session {sid} (status={status})")
                        start_session_monitor(sid, session, context='monitor_restore')
                        restored_count += 1
                        log.info(f"  ✅ Successfully restored monitor for {sid}")
                    else:
                        log.info(f"  Skipping {sid}: status={status} (not active)")
                        
                except Exception as e:
                    print(f"[MMM] ❌ Failed to restore monitor for {sid}: {e}")
                    log.exception(f"  Failed to restore monitor for {sid}: {e}")
            
            print(f"[MMM] Initialization complete: {restored_count}/{len(active_ids)} monitors restored")
            log.info(f"MMM initialization complete: {restored_count}/{len(active_ids)} monitors restored")
        else:
            print(f"[MMM] No active sessions to restore")
            log.info(f"MMM initialized: No active sessions to restore")

        # Start the watchdog supervisor (watches all monitors for thread death / beat timeout)
        try:
            from .mmm_watchdog import MMMWatchdog
            watchdog = MMMWatchdog.get_instance()
            watchdog.start()
            print("[MMM] Watchdog supervisor started")
            log.info("MMM Watchdog started")
        except Exception as we:
            print(f"[MMM] ⚠️ Watchdog failed to start: {we}")
            log.warning(f"MMM Watchdog failed to start: {we}")

    except Exception as e:
        error_msg = f"MMM initialization FAILED: {e}"
        print(f"[MMM] ❌ {error_msg}")
        log.exception(error_msg)
