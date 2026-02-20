#!/usr/bin/env python3
"""Quick test to verify all SSR Algo Phase 1-10 imports work."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'webui', 'backend'))

results = []

def assert_(cond, msg=''):
    if not cond:
        raise AssertionError(msg)

def check(label, fn):
    try:
        fn()
        results.append((label, True, ''))
        print(f'  OK: {label}')
    except Exception as e:
        results.append((label, False, str(e)))
        print(f'  FAIL: {label} -> {e}')

print('=== Phase 1: Greeks ===')
check('SSRGreeksFetcher import', lambda: __import__('webui.backend.routes.ssr_algo.ssr_algo_greeks', fromlist=['SSRGreeksFetcher']))

print('=== Phase 2: Exit Manager ===')
check('SSRExitManager import', lambda: __import__('webui.backend.routes.ssr_algo.ssr_algo_exit_manager', fromlist=['SSRExitManager']))

print('=== Phase 3: Delta Hedger ===')
check('SSRDeltaHedger import', lambda: __import__('webui.backend.routes.ssr_algo.ssr_algo_delta_hedger', fromlist=['SSRDeltaHedger']))

print('=== Phase 4: Vol Analyzer ===')
check('SSRVolAnalyzer import', lambda: __import__('webui.backend.routes.ssr_algo.ssr_algo_vol_analyzer', fromlist=['SSRVolAnalyzer']))

print('=== Phase 6: DTE Manager ===')
check('SSRDTEManager import', lambda: __import__('webui.backend.routes.ssr_algo.ssr_algo_dte_manager', fromlist=['SSRDTEManager']))

print('=== Phase 7: Regime ===')
check('SSRRegimeAdapter import', lambda: __import__('webui.backend.routes.ssr_algo.ssr_algo_regime', fromlist=['SSRRegimeAdapter']))

print('=== Phase 8: Smart Executor ===')
check('SSRSmartExecutor import', lambda: __import__('webui.backend.routes.ssr_algo.ssr_algo_smart_executor', fromlist=['SSRSmartExecutor']))

print('=== Phase 10: RV Tracker ===')
check('SSRRVTracker import', lambda: __import__('webui.backend.routes.ssr_algo.ssr_algo_rv_tracker', fromlist=['SSRRVTracker']))

print('=== Phase 10: Analytics ===')
check('SSRAnalytics import', lambda: __import__('webui.backend.routes.ssr_algo.ssr_algo_analytics', fromlist=['SSRAnalytics']))

# Check key methods exist
print('\n=== Checking key methods ===')
from webui.backend.routes.ssr_algo.ssr_algo_exit_manager import get_exit_manager
em = get_exit_manager()
check('execute_roll method', lambda: assert_(hasattr(em, 'execute_roll'), 'missing execute_roll'))
check('execute_full_exit method', lambda: assert_(hasattr(em, 'execute_full_exit'), 'missing'))
check('calculate_dte method', lambda: assert_(hasattr(em, 'calculate_dte'), 'missing'))

from webui.backend.routes.ssr_algo.ssr_algo_delta_hedger import get_delta_hedger
dh = get_delta_hedger()
check('execute_micro_hedge', lambda: assert_(hasattr(dh, 'execute_micro_hedge'), 'missing'))
check('execute_standard_hedge', lambda: assert_(hasattr(dh, 'execute_standard_hedge'), 'missing'))
check('execute_emergency_hedge', lambda: assert_(hasattr(dh, 'execute_emergency_hedge'), 'missing'))
check('execute_surgical_adjustment', lambda: assert_(hasattr(dh, 'execute_surgical_adjustment'), 'missing'))
check('check_delta_hedge_needed', lambda: assert_(hasattr(dh, 'check_delta_hedge_needed'), 'missing'))

from webui.backend.routes.ssr_algo.ssr_algo_rv_tracker import get_rv_tracker
rv = get_rv_tracker()
check('record_price', lambda: assert_(hasattr(rv, 'record_price'), 'missing'))
check('get_rv_iv_snapshot', lambda: assert_(hasattr(rv, 'get_rv_iv_snapshot'), 'missing'))
check('get_rv_iv_history', lambda: assert_(hasattr(rv, 'get_rv_iv_history'), 'missing'))

from webui.backend.routes.ssr_algo.ssr_algo_analytics import get_analytics
an = get_analytics()
check('get_session_analytics', lambda: assert_(hasattr(an, 'get_session_analytics'), 'missing'))
check('get_aggregate_analytics', lambda: assert_(hasattr(an, 'get_aggregate_analytics'), 'missing'))

# Check __init__ exports
print('\n=== Checking __init__.py exports ===')
from webui.backend.routes.ssr_algo import __all__
expected = ['SSRGreeksFetcher', 'SSRExitManager', 'SSRDeltaHedger', 'SSRVolAnalyzer', 
            'SSRDTEManager', 'SSRRegimeAdapter', 'SSRSmartExecutor', 'SSRRVTracker', 'SSRAnalytics',
            'ssr_algo_bp']
for name in expected:
    check(f'__all__ has {name}', lambda n=name: assert_(n in __all__, f'{n} not in __all__'))

# Summary
print('\n' + '='*50)
fails = [r for r in results if not r[1]]
if fails:
    print(f'FAILURES: {len(fails)}')
    for label, _, err in fails:
        print(f'  - {label}: {err}')
else:
    print(f'ALL {len(results)} CHECKS PASSED')
