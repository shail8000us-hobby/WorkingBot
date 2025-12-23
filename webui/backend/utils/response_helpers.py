"""
Shared Response Formatting Utilities

Used by: pnl, orders, positions blueprints (anywhere using numpy)

Extracted from app.py to avoid duplication across blueprints.
"""

from typing import Any
import math

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


def convert_numpy_types(obj: Any) -> Any:
    """
    Recursively convert numpy types to native Python types for JSON serialization.
    Also handles NaN, Infinity, and -Infinity values.
    
    Args:
        obj: Object to convert (dict, list, numpy type, or other)
        
    Returns:
        Object with numpy types converted to Python native types
    
    Example:
        >>> data = {'value': np.int64(42), 'array': np.array([1, 2, 3])}
        >>> convert_numpy_types(data)
        {'value': 42, 'array': [1, 2, 3]}
    """
    if not NUMPY_AVAILABLE:
        return obj
    
    if isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        value = float(obj)
        # Handle NaN and Infinity
        if math.isnan(value):
            return 0.0
        elif math.isinf(value):
            return 0.0 if value < 0 else 0.0
        return value
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, float):
        # Handle Python float NaN and Infinity
        if math.isnan(obj):
            return 0.0
        elif math.isinf(obj):
            return 0.0
        return obj
    else:
        return obj
