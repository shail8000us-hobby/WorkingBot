"""
IC — Iron Condor Strategy Module

Continuous premium-harvesting iron condor algo for BTC 0DTE/weekly options.
4-leg defined-risk strategy with auto-adjustment and cycle management.

Logic reference: IC_ALGO_PLAN.md
Created: 2026-03-24
"""

from .ic_api import ic_bp
from .ic_websocket import init_websocket

__all__ = [
    'ic_bp',
    'init_ic',
    'init_websocket',
]


def init_ic():
    """
    Initialize IC module on backend startup.

    - Restores active sessions from storage
    - Auto-restores heartbeat monitors for RUNNING/PAUSED sessions

    Call this after registering the blueprint in app.py.
    """
    import logging
    log = logging.getLogger('ic')

    try:
        from .ic_storage import get_storage
        from .ic_monitor import ICMonitor
        from .ic_api import _monitors

        storage = get_storage()
        active_ids = storage.get_active_session_ids()
        all_sessions = storage.list_sessions()

        print(f"[IC] Initializing: {len(all_sessions)} session(s) in storage, {len(active_ids)} active")
        log.info(f"IC initializing: {len(all_sessions)} session(s) in storage, {len(active_ids)} active")

        if active_ids:
            restored = 0
            for sid in active_ids:
                try:
                    session = storage.get_session(sid)
                    if not session:
                        continue

                    status = session.get('status', 'IDLE')
                    if status in ('RUNNING', 'PAUSED'):
                        print(f"[IC] Restoring monitor for session {sid} (status={status})")
                        monitor = ICMonitor(sid, session)
                        _monitors[sid] = monitor
                        if status == 'RUNNING':
                            monitor.start()
                        restored += 1
                        log.info(f"  ✅ Restored monitor for {sid}")

                except Exception as e:
                    print(f"[IC] ❌ Failed to restore monitor for {sid}: {e}")
                    log.exception(f"Failed to restore IC monitor for {sid}")

            print(f"[IC] Initialization complete: {restored}/{len(active_ids)} monitors restored")
        else:
            print(f"[IC] No active sessions to restore")

    except Exception as e:
        print(f"[IC] ❌ Initialization FAILED: {e}")
        import logging
        logging.getLogger('ic').exception(f"IC initialization failed: {e}")
