"""
Patience — Scenario Card Execution Engine for BTC Options.

Flask Blueprint: patience_bp (url_prefix=/api/patience)
Trigger daemon: init_patience() starts the background monitoring thread.

Register in app.py:
    from .routes.patience import patience_bp, init_patience
    app.register_blueprint(patience_bp)
    init_patience()

Created: March 14, 2026
"""

from .patience_api import patience_bp


def init_patience():
    """
    Initialize Patience engine on app startup.
    Starts the trigger daemon, IV collector daemon, wires loop dependencies,
    and recovers in-flight cards.
    """
    from webui.backend.services.patience_trigger import init_patience_trigger
    from webui.backend.services.patience_loop import get_patience_loop_service
    from webui.backend.services.patience_executor import _check_guardian

    trigger = init_patience_trigger()

    # Wire patience_loop dependencies (mirrors _ensure_auto_loop_deps in options_control)
    loop_svc = get_patience_loop_service()
    if loop_svc._api_client_factory is None:
        from webui.backend.routes.options.options_client import get_unified_client
        loop_svc.set_dependencies(
            api_client_factory=get_unified_client,
            check_guardian_fn=_check_guardian,
        )

    # Register execution lock callback (trigger notifies executor when card done)
    from webui.backend.services.patience_executor import register_execution_lock_callback
    register_execution_lock_callback(trigger._on_execution_done)

    # Start IV daemon — isolated so IV failure doesn't prevent trigger daemon from running
    try:
        from webui.backend.services.patience_iv import get_patience_iv
        iv = get_patience_iv()
        if not iv.is_running():
            iv.start()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Patience IV daemon failed to start: {e}")

    return trigger


__all__ = ['patience_bp', 'init_patience']
