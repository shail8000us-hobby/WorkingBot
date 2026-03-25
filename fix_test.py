import pytest
from webui.backend.routes.mmm.tests.test_mmm_state import TestRecomputeSideLots, _recompute

def test_manual():
    print("Testing original_lots_derived")
    tester = TestRecomputeSideLots()
    side = tester._make_side_with_positions()
    print("BEFORE_RECOMPUTE:", [p for p in side['positions'] if p['id'] == 'ce_orig'])
    _recompute(side)
    print("AFTER_RECOMPUTE:", [p for p in side['positions'] if p['id'] == 'ce_orig'])
    
test_manual()
