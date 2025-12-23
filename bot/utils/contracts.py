"""
Design by Contract (DbC) Implementation for GridBot

Provides runtime verification of:
- Preconditions (requirements before function execution)
- Postconditions (guarantees after function execution)  
- Class invariants (properties that must always hold)

Usage:
    from bot.utils.contracts import require, ensure, invariant
    
    @require(lambda self, price: price > 0, "Price must be positive")
    @ensure(lambda self, result: result is not None, "Must return order ID")
    def place_order(self, price):
        ...

This is a lightweight custom implementation (no external dependencies).
"""

import functools
import logging
from typing import Callable, Any, Optional

log = logging.getLogger("contracts")

# Global flag to enable/disable contracts (can disable in production for performance)
CONTRACTS_ENABLED = True


class ContractViolation(Exception):
    """Raised when a contract is violated"""
    pass


def require(condition: Callable, message: str = "Precondition violated"):
    """
    Precondition decorator - verifies condition BEFORE function executes
    
    Args:
        condition: Lambda function that takes same args as decorated function
        message: Error message if condition fails
        
    Example:
        @require(lambda self, price: price > 0, "Price must be positive")
        def place_order(self, price):
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not CONTRACTS_ENABLED:
                return func(*args, **kwargs)
            
            try:
                # Check precondition
                if not condition(*args, **kwargs):
                    error_msg = f"PRECONDITION FAILED in {func.__name__}: {message}"
                    log.error(error_msg)
                    raise ContractViolation(error_msg)
            except ContractViolation:
                raise
            except Exception as e:
                # Error evaluating condition itself
                log.warning(f"Error checking precondition in {func.__name__}: {e}")
            
            # Execute function
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def ensure(condition: Callable, message: str = "Postcondition violated"):
    """
    Postcondition decorator - verifies condition AFTER function executes
    
    Args:
        condition: Lambda that takes (self, result) or (result,)
        message: Error message if condition fails
        
    Example:
        @ensure(lambda self, result: result > 0, "Must return positive value")
        def calculate_profit(self, entry, exit):
            return exit - entry
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Execute function
            result = func(*args, **kwargs)
            
            if not CONTRACTS_ENABLED:
                return result
            
            try:
                # Check postcondition
                # Try with self + result first, then just result
                try:
                    check_passed = condition(args[0] if args else None, result)
                except TypeError:
                    check_passed = condition(result)
                
                if not check_passed:
                    error_msg = f"POSTCONDITION FAILED in {func.__name__}: {message}"
                    log.error(error_msg)
                    log.error(f"  Result was: {result}")
                    raise ContractViolation(error_msg)
            except ContractViolation:
                raise
            except Exception as e:
                # Error evaluating condition
                log.warning(f"Error checking postcondition in {func.__name__}: {e}")
            
            return result
        
        return wrapper
    return decorator


def invariant(condition: Callable, message: str = "Class invariant violated"):
    """
    Class invariant decorator - verifies condition holds for ALL methods
    
    Applied to a class method, checks condition before AND after method execution.
    
    Args:
        condition: Lambda that takes self
        message: Error message if condition fails
        
    Example:
        @invariant(lambda self: len(self.positions) <= self.max_open)
        def add_position(self, position):
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not CONTRACTS_ENABLED:
                return func(*args, **kwargs)
            
            self_obj = args[0] if args else None
            
            # Check invariant BEFORE
            try:
                if self_obj and not condition(self_obj):
                    error_msg = f"INVARIANT VIOLATED (before {func.__name__}): {message}"
                    log.error(error_msg)
                    raise ContractViolation(error_msg)
            except ContractViolation:
                raise
            except Exception as e:
                log.warning(f"Error checking invariant before {func.__name__}: {e}")
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Check invariant AFTER
            try:
                if self_obj and not condition(self_obj):
                    error_msg = f"INVARIANT VIOLATED (after {func.__name__}): {message}"
                    log.error(error_msg)
                    log.error(f"  Check that {func.__name__} maintains class invariants")
                    raise ContractViolation(error_msg)
            except ContractViolation:
                raise
            except Exception as e:
                log.warning(f"Error checking invariant after {func.__name__}: {e}")
            
            return result
        
        return wrapper
    return decorator


def enable_contracts():
    """Enable contract checking (default)"""
    global CONTRACTS_ENABLED
    CONTRACTS_ENABLED = True
    log.info("✅ Contracts ENABLED - Runtime verification active")


def disable_contracts():
    """Disable contract checking (for production performance)"""
    global CONTRACTS_ENABLED
    CONTRACTS_ENABLED = False
    log.warning("⚠️ Contracts DISABLED - Runtime verification inactive")


def are_contracts_enabled() -> bool:
    """Check if contracts are currently enabled"""
    return CONTRACTS_ENABLED

