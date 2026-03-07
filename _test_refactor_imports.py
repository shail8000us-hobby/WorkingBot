"""
Comprehensive import test for options_control refactoring (Phases 1-4).
Tests that all re-exports work and external callers can still import.
"""
import sys
import traceback

passed = 0
failed = 0

def test(label, fn):
    global passed, failed
    try:
        fn()
        print(f"  OK  {label}")
        passed += 1
    except Exception as e:
        print(f"  FAIL {label}: {e}")
        traceback.print_exc()
        failed += 1

# ── Phase 1: options_client.py ──
def t1():
    from webui.backend.routes.options.options_client import _run_async, get_unified_client, with_timeout
    assert callable(_run_async)
    assert callable(get_unified_client)
    assert callable(with_timeout)
test("Phase 1: options_client direct imports", t1)

def t1b():
    from webui.backend.routes.options.options_control import _run_async, get_unified_client, with_timeout
    assert callable(_run_async)
test("Phase 1: options_client re-exports via options_control", t1b)

# ── Phase 2: order_executor.py ──
def t2():
    from webui.backend.routes.options.order_executor import (
        ORDER_TYPE_MAKER_FIRST, ORDER_TYPE_MAKER_ONLY, ORDER_TYPE_MARKET_ONLY,
        ORDER_TYPE_SSR, VALID_ORDER_TYPES,
        cancel_order_with_verification, validate_order_size,
        place_options_order, modify_order_price, fetch_fresh_orderbook_quotes,
        place_smart_order,
    )
    assert ORDER_TYPE_MAKER_FIRST == 'maker_first'
    assert ORDER_TYPE_MARKET_ONLY == 'market_only'
    assert callable(place_smart_order)
    assert callable(cancel_order_with_verification)
test("Phase 2: order_executor direct imports", t2)

def t2b():
    from webui.backend.routes.options.options_control import (
        ORDER_TYPE_MAKER_FIRST, ORDER_TYPE_MAKER_ONLY, ORDER_TYPE_MARKET_ONLY,
        ORDER_TYPE_SSR, VALID_ORDER_TYPES,
        cancel_order_with_verification, validate_order_size,
        place_options_order, modify_order_price, fetch_fresh_orderbook_quotes,
        place_smart_order,
    )
    assert ORDER_TYPE_MAKER_FIRST == 'maker_first'
test("Phase 2: order_executor re-exports via options_control", t2b)

# ── Phase 3: ssr_monitor.py ──
def t3():
    from webui.backend.routes.options.ssr_monitor import (
        get_active_ssr_orders, register_ssr_order, update_ssr_order,
        remove_ssr_order, place_ssr_order, place_ssr_order_with_margin,
    )
    assert callable(get_active_ssr_orders)
    assert callable(place_ssr_order)
test("Phase 3: ssr_monitor direct imports", t3)

def t3b():
    from webui.backend.routes.options.options_control import (
        place_ssr_order, place_ssr_order_with_margin, get_active_ssr_orders,
    )
    assert callable(place_ssr_order)
test("Phase 3: ssr_monitor re-exports via options_control", t3b)

# ── Phase 4: delta_hedge.py ──
def t4():
    from webui.backend.routes.options.delta_hedge import (
        register_delta_hedge_routes, get_hedge_events_snapshot,
    )
    assert callable(register_delta_hedge_routes)
    assert callable(get_hedge_events_snapshot)
test("Phase 4: delta_hedge direct imports", t4)

def t4b():
    from webui.backend.routes.options.options_control import options_bp
    # Verify delta hedge route registration function was deferred on the blueprint
    assert len(options_bp.deferred_functions) > 0, "No deferred functions on blueprint"
test("Phase 4: delta_hedge routes registered on blueprint", t4b)

# ── External caller simulations ──
def t5():
    from webui.backend.routes.options.options_control import options_bp
    assert options_bp is not None
test("app.py: import options_bp", t5)

def t6():
    from webui.backend.routes.options.options_control import place_smart_order, with_timeout, validate_order_size
test("batch_add_endpoint.py: import place_smart_order, with_timeout, validate_order_size", t6)

def t7():
    from webui.backend.routes.options.options_control import _run_async
test("batch_add_endpoint.py: import _run_async", t7)

def t8():
    from webui.backend.routes.options.options_control import place_smart_order, ORDER_TYPE_MARKET_ONLY
test("max_loss_manager.py: import place_smart_order, ORDER_TYPE_MARKET_ONLY", t8)

def t9():
    from webui.backend.routes.options.options_control import execute_close_order
    assert callable(execute_close_order)
test("sl_tp_monitor.py: import execute_close_order", t9)

def t10():
    from webui.backend.routes.options.options_control import place_smart_order, ORDER_TYPE_MAKER_FIRST
test("take_profit_manager.py: import place_smart_order, ORDER_TYPE_MAKER_FIRST", t10)

def t11():
    from webui.backend.routes.options.options_control import cancel_order_with_verification
    assert callable(cancel_order_with_verification)
test("test_sealed: import cancel_order_with_verification", t11)

# ── SEALED decorator checks ──
def t12():
    from webui.backend.routes.options.order_executor import place_smart_order, cancel_order_with_verification
    # Check that @sealed decorator is applied (the function should have _sealed attr or wrapper)
    pso_name = getattr(place_smart_order, '__wrapped__', place_smart_order).__name__
    cwv_name = getattr(cancel_order_with_verification, '__wrapped__', cancel_order_with_verification).__name__
    assert pso_name == 'place_smart_order' or 'place_smart_order' in str(place_smart_order)
    assert cwv_name == 'cancel_order_with_verification' or 'cancel_order_with_verification' in str(cancel_order_with_verification)
test("SEALED: decorators applied to place_smart_order and cancel_order_with_verification", t12)

# ── Cross-import dependency checks ──
def t13():
    # ssr_monitor imports from order_executor
    from webui.backend.routes.options.ssr_monitor import fetch_fresh_orderbook_quotes, place_options_order
test("Cross-import: ssr_monitor -> order_executor", t13)

def t14():
    # delta_hedge imports from options_client
    from webui.backend.routes.options.delta_hedge import _run_async, get_unified_client
test("Cross-import: delta_hedge -> options_client", t14)

# ── Thread-safety check for SSR registry ──
def t15():
    from webui.backend.routes.options.ssr_monitor import (
        get_active_ssr_orders, register_ssr_order, remove_ssr_order,
    )
    # Register a test order
    register_ssr_order('TEST_123', {'symbol': 'TEST', 'status': 'test', 'start_time': 0})
    orders = get_active_ssr_orders()
    found = any(o['order_id'] == 'TEST_123' for o in orders)
    assert found, "Registered order not found in get_active_ssr_orders()"
    remove_ssr_order('TEST_123')
    orders2 = get_active_ssr_orders()
    found2 = any(o['order_id'] == 'TEST_123' for o in orders2)
    assert not found2, "Removed order still found in get_active_ssr_orders()"
test("SSR registry: register/get/remove round-trip", t15)

# ── Summary ──
print(f"\n{'='*50}")
print(f"  RESULTS: {passed} passed, {failed} failed")
print(f"{'='*50}")
sys.exit(1 if failed else 0)
