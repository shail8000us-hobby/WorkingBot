#!/usr/bin/env python3
"""
WSGI entry point for Gunicorn.

Usage:
    gunicorn -k eventlet -w 1 -b 0.0.0.0:5555 webui.backend.wsgi:app

This module:
1. Monkey-patches eventlet before any other imports
2. Sets the correct async mode for Flask-SocketIO
3. Imports the Flask app
4. Starts deferred monitor initialization
"""
import os
import sys

# Ensure project root is on path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

# Monkey-patch BEFORE any other imports (required for eventlet)
import eventlet
eventlet.monkey_patch()

# Tell Flask-SocketIO to use eventlet
os.environ['SOCKETIO_ASYNC_MODE'] = 'eventlet'

# Now import the Flask app
from webui.backend.app import app, socketio, get_api_credentials
import time


def _deferred_monitor_init():
    """Start all monitors after the server is accepting connections."""
    import urllib.request

    # Wait for server to be ready
    print("\n⏳ [Gunicorn] Waiting for server before starting monitors...")
    for _ in range(60):
        try:
            urllib.request.urlopen('http://127.0.0.1:5555/api/health', timeout=2)
            break
        except Exception:
            eventlet.sleep(0.5)
    else:
        print("⚠️  Server not ready in 30s — starting monitors anyway")

    print("\n" + "=" * 60)
    print("📡 [Gunicorn] Starting background monitors...")
    print("=" * 60)

    # --- Health Checker ---
    try:
        print("\n💊 Starting Health Checker...")
        from webui.backend.utils.lightweight_health import start_health_checker
        from webui.backend.utils.process_helpers import (
            check_bot_running, check_guardian_running
        )

        def safe_check_bot():
            try: return check_bot_running()
            except Exception: return False

        def safe_check_guardian():
            try: return check_guardian_running()
            except Exception: return False

        def safe_check_telegram():
            try:
                from config.loader import get_config
                _cfg = get_config()
                bt = _cfg.telegram.live_bot_token if _cfg.trading_mode == 'live' else _cfg.telegram.demo_bot_token
                if not bt: bt = _cfg.telegram.bot_token
                return bool(bt and bt != '***REDACTED***')
            except Exception: return False

        start_health_checker(
            bot_check=safe_check_bot,
            monitor_check=lambda: False,
            guardian_check=safe_check_guardian,
            telegram_check=safe_check_telegram
        )
        print("✅ Health checker started")
    except Exception as e:
        print(f"⚠️  Health checker failed: {e}")

    # --- Volatility Collector ---
    try:
        print("📊 Starting Volatility Collector...")
        from bot.volatility.delta_volatility_collector import get_collector
        collector = get_collector()
        collector.start()
        print("✅ Volatility Collector started")
    except Exception as e:
        print(f"⚠️  Volatility Collector failed: {e}")

    # --- SL/TP Monitor ---
    api_client = None
    try:
        print("🎯 Starting SL/TP Monitor...")
        from webui.backend.options_strategy.sl_tp_monitor import init_sl_tp_monitoring
        from webui.backend.options_strategy.sl_tp_manager import get_sl_tp_manager
        from bot.api.unified_api_client import UnifiedAPIClient

        creds = get_api_credentials()
        api_client = UnifiedAPIClient(
            api_key=creds['api_key'], api_secret=creds['api_secret'],
            symbol='BTCUSD', enable_websocket=False
        )
        sl_tp_manager = get_sl_tp_manager()
        init_sl_tp_monitoring(api_client, sl_tp_manager, auto_start=True)
        print("✅ SL/TP Monitor started")
    except Exception as e:
        print(f"⚠️  SL/TP Monitor failed: {e}")

    # --- Max Loss Monitor ---
    try:
        print("🛑 Starting Max Loss Monitor...")
        from webui.backend.options_strategy.max_loss_manager import init_max_loss_monitoring, get_max_loss_manager
        max_loss_manager = get_max_loss_manager()
        # Each monitor needs its own UnifiedAPIClient so their httpx.AsyncClient
        # instances are each bound to their own event loop (no "attached to different loop" errors)
        max_loss_api_client = UnifiedAPIClient(
            api_key=creds['api_key'], api_secret=creds['api_secret'],
            symbol='BTCUSD', enable_websocket=False
        )
        init_max_loss_monitoring(max_loss_api_client, max_loss_manager, auto_start=True)
        print("✅ Max Loss Monitor started")
    except Exception as e:
        print(f"⚠️  Max Loss Monitor failed: {e}")

    eventlet.sleep(2)  # Stagger to prevent API rate limits

    # --- IV Background Recorder ---
    try:
        from webui.backend.db.iv_history_db import start_iv_background_recorder
        start_iv_background_recorder(interval=300)
        print("✅ IV Background Recorder started")
    except Exception as e:
        print(f"⚠️  IV Recorder failed: {e}")

    # --- Take Profit Monitor ---
    try:
        print("🎯 Starting Take Profit Monitor...")
        from webui.backend.options_strategy.take_profit_manager import (
            init_take_profit_monitoring, get_take_profit_manager,
            init_socketio as init_tp_socketio
        )
        init_tp_socketio(socketio)
        take_profit_manager = get_take_profit_manager()
        # Each monitor gets its own client to avoid event loop binding conflicts
        tp_api_client = UnifiedAPIClient(
            api_key=creds['api_key'], api_secret=creds['api_secret'],
            symbol='BTCUSD', enable_websocket=False
        )
        init_take_profit_monitoring(tp_api_client, take_profit_manager, auto_start=True)
        print("✅ Take Profit Monitor started")
    except Exception as e:
        print(f"⚠️  Take Profit Monitor failed: {e}")

    # --- Price WebSocket ---
    try:
        print("💹 Starting Delta Price WebSocket...")
        from webui.backend.services import start_price_service
        start_price_service(socketio)
        print("✅ Price WebSocket started")
    except Exception as e:
        print(f"⚠️  Price WebSocket failed: {e}")

    print("\n" + "=" * 60)
    print("✅ [Gunicorn] All monitors initialized")
    print("=" * 60 + "\n")


# Start deferred monitor init in a green thread
eventlet.spawn(_deferred_monitor_init)
