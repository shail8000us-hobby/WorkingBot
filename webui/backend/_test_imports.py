#!/usr/bin/env python3
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'webui', 'backend'))
sys.path.insert(0, os.path.dirname(__file__))

def assert_(cond, msg=''):
    if not cond:
        raise AssertionError(msg)

ok = 0
fail = 0

def test(label, fn):
    global ok, fail
    try:
        fn()
        ok += 1
        print(f'  PASS: {label}')
    except Exception as e:
        fail += 1
        print(f'  FAIL: {label} -> {e}')

# Direct file-level imports (bypass routes __init__ which triggers config)
test('ssr_algo_greeks', lambda: __import__('routes.ssr_algo.ssr_algo_greeks', fromlist=['SSRGreeksFetcher']))
test('ssr_algo_exit_manager', lambda: __import__('routes.ssr_algo.ssr_algo_exit_manager', fromlist=['SSRExitManager']))
test('ssr_algo_delta_hedger', lambda: __import__('routes.ssr_algo.ssr_algo_delta_hedger', fromlist=['SSRDeltaHedger']))
test('ssr_algo_vol_analyzer', lambda: __import__('routes.ssr_algo.ssr_algo_vol_analyzer', fromlist=['SSRVolAnalyzer']))
test('ssr_algo_dte_manager', lambda: __import__('routes.ssr_algo.ssr_algo_dte_manager', fromlist=['SSRDTEManager']))
test('ssr_algo_regime', lambda: __import__('routes.ssr_algo.ssr_algo_regime', fromlist=['SSRRegimeAdapter']))
test('ssr_algo_smart_executor', lambda: __import__('routes.ssr_algo.ssr_algo_smart_executor', fromlist=['SSRSmartExecutor']))
test('ssr_algo_rv_tracker', lambda: __import__('routes.ssr_algo.ssr_algo_rv_tracker', fromlist=['SSRRVTracker']))
test('ssr_algo_analytics', lambda: __import__('routes.ssr_algo.ssr_algo_analytics', fromlist=['SSRAnalytics']))

# Check methods
from routes.ssr_algo.ssr_algo_exit_manager import get_exit_manager
em = get_exit_manager()
test('exit_manager.execute_roll', lambda: assert_(hasattr(em, 'execute_roll')))
test('exit_manager.execute_full_exit', lambda: assert_(hasattr(em, 'execute_full_exit')))
test('exit_manager.calculate_dte', lambda: assert_(hasattr(em, 'calculate_dte')))
test('exit_manager.check_exit_conditions', lambda: assert_(hasattr(em, 'check_exit_conditions')))

from routes.ssr_algo.ssr_algo_delta_hedger import get_delta_hedger
dh = get_delta_hedger()
test('hedger.execute_micro_hedge', lambda: assert_(hasattr(dh, 'execute_micro_hedge')))
test('hedger.execute_standard_hedge', lambda: assert_(hasattr(dh, 'execute_standard_hedge')))
test('hedger.execute_emergency_hedge', lambda: assert_(hasattr(dh, 'execute_emergency_hedge')))
test('hedger.execute_surgical_adjustment', lambda: assert_(hasattr(dh, 'execute_surgical_adjustment')))
test('hedger.check_delta_hedge_needed', lambda: assert_(hasattr(dh, 'check_delta_hedge_needed')))

from routes.ssr_algo.ssr_algo_rv_tracker import get_rv_tracker
rv = get_rv_tracker()
test('rv.record_price', lambda: assert_(hasattr(rv, 'record_price')))
test('rv.get_rv_iv_snapshot', lambda: assert_(hasattr(rv, 'get_rv_iv_snapshot')))
test('rv.get_rv_iv_history', lambda: assert_(hasattr(rv, 'get_rv_iv_history')))
test('rv.calculate_realized_vol', lambda: assert_(hasattr(rv, 'calculate_realized_vol')))

from routes.ssr_algo.ssr_algo_analytics import get_analytics
an = get_analytics()
test('analytics.get_session_analytics', lambda: assert_(hasattr(an, 'get_session_analytics')))
test('analytics.get_aggregate_analytics', lambda: assert_(hasattr(an, 'get_aggregate_analytics')))

from routes.ssr_algo.ssr_algo_dte_manager import get_dte_manager
dm = get_dte_manager()
test('dte.get_dte_phase', lambda: assert_(hasattr(dm, 'get_dte_phase')))
test('dte.apply_dte_adjustments', lambda: assert_(hasattr(dm, 'apply_dte_adjustments')))

from routes.ssr_algo.ssr_algo_storage import get_storage
st = get_storage()
test('storage.update_position_leg', lambda: assert_(hasattr(st, 'update_position_leg')))
test('storage.close_position_leg', lambda: assert_(hasattr(st, 'close_position_leg')))

print(f'\nResults: {ok} passed, {fail} failed out of {ok+fail}')
if fail == 0:
    print('ALL CHECKS PASSED')
