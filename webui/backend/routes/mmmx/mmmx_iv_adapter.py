"""
MMMX IV Adapter — Read-only wrapper for IV rank data.

Spec: MMMX_IMPLEMENTATION_PLAN.md Section 9 Ambiguity A8 (resolved):
  "Acceptable as read-only adapter. Wrap in mmmx_iv_adapter.py exposing only
   get_iv_rank(). No writes to MMM state. Same pattern as mmmx_margin_guardian.py."

Isolation: ZERO imports from routes.mmm.*.
Source: webui/backend/services/patience_iv.py (in services/, not routes.mmm.*).
"""

import logging
from typing import Optional

log = logging.getLogger('mmmx_iv_adapter')

# Default lookback window matching the patience_iv convention.
_DEFAULT_LOOKBACK_DAYS: int = 30


def get_iv_rank(lookback_days: int = _DEFAULT_LOOKBACK_DAYS) -> Optional[float]:
    """
    Return the current IV percentile (0–100) from the patience IV service.

    Returns None if the service is unavailable or has insufficient data.
    Callers must treat None as "unknown" and skip IV-gated logic gracefully.

    Never raises — failures are logged and swallowed.
    """
    try:
        from webui.backend.services.patience_iv import get_current_iv_percentile
        result = get_current_iv_percentile(lookback_days)
        if result is None:
            return None
        return float(result)
    except ImportError:
        try:
            from services.patience_iv import get_current_iv_percentile
            result = get_current_iv_percentile(lookback_days)
            if result is None:
                return None
            return float(result)
        except ImportError:
            log.debug("patience_iv not available — IV rank will be None this beat")
            return None
    except Exception as exc:
        log.warning(f"[MMMX][IVAdapter] get_iv_rank failed: {exc}")
        return None
