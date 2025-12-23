"""
Narrator Integration Layer
Glue between NarratorCore and HumanLogger for runtime narration.

Thread-safe, async-safe, low overhead, optional.
"""

import asyncio
import time
import inspect
from typing import Optional, Callable, Any
from functools import wraps
from concurrent.futures import ThreadPoolExecutor

# Import core components
from bot.utils.narrator_core import NarratorCore, ExplanationMode, FunctionInfo
from bot.config.narration_config import (
    ENABLE_CODE_NARRATION,
    CODE_NARRATION_MODE,
    NARRATION_RATE_LIMIT,
    MAX_NARRATION_LENGTH,
    NARRATION_WHITELIST,
    NARRATION_BLACKLIST,
    ASYNC_SAFE_MODE,
    RESPECT_SYSTEM_LOAD,
    DEBUG_NARRATION,
    EXPLAIN_SAGA_FLOWS,
    EXPLAIN_ACTOR_ROUTING
)


class NarratorIntegration:
    """
    Runtime code narration integration.
    
    Provides safe, optional, low-overhead code explanation at runtime.
    Can explain what functions do when they're called.
    
    100% safe:
    - Never blocks async event loop
    - Respects rate limits
    - Skips narration if system busy
    - Thread-safe
    - Actor-safe
    """
    
    def __init__(self):
        # Map mode string to enum
        mode_map = {
            'tech': ExplanationMode.TECH,
            'trader': ExplanationMode.TRADER,
            'simple': ExplanationMode.SIMPLE
        }
        
        self.narrator = NarratorCore(mode=mode_map.get(CODE_NARRATION_MODE, ExplanationMode.TRADER))
        self.enabled = ENABLE_CODE_NARRATION
        self._last_narration_times = {}
        
        # Thread pool for async-safe execution
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="narrator")
        
        # Cache for analyzed functions (avoid re-parsing)
        self._function_cache = {}
    
    def should_narrate(self, event_type: str) -> bool:
        """
        Check if we should narrate this event.
        
        Args:
            event_type: Type of event (e.g., 'order_placed')
            
        Returns:
            True if narration allowed
        """
        if not self.enabled:
            return False
        
        # Check blacklist
        if event_type in NARRATION_BLACKLIST:
            return False
        
        # Check whitelist (if configured)
        if NARRATION_WHITELIST and event_type not in NARRATION_WHITELIST:
            return False
        
        # Check rate limit
        current_time = time.time()
        last_time = self._last_narration_times.get(event_type, 0)
        
        if current_time - last_time < NARRATION_RATE_LIMIT:
            return False
        
        # Check system load (if configured)
        if RESPECT_SYSTEM_LOAD:
            if self._is_system_busy():
                if DEBUG_NARRATION:
                    print("[Narrator] Skipping narration - system busy")
                return False
        
        # Update last narration time
        self._last_narration_times[event_type] = current_time
        return True
    
    def _is_system_busy(self) -> bool:
        """
        Check if system is under stress.
        
        Returns:
            True if system too busy for narration
        """
        try:
            import psutil
            
            # Check CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            if cpu_percent > 80:
                return True
            
            # Check memory usage
            memory = psutil.virtual_memory()
            if memory.percent > 85:
                return True
            
            return False
        except ImportError:
            # psutil not available, assume not busy
            return False
        except:
            # Any error, assume not busy
            return False
    
    def explain_function_call(self, func: Callable, context: str = "") -> Optional[str]:
        """
        Generate explanation for a function call.
        
        Args:
            func: Function being called
            context: Additional context (e.g., "after order filled")
            
        Returns:
            Human explanation or None if narration disabled
        """
        if not self.enabled:
            return None
        
        # Check cache
        func_name = func.__name__
        if func_name in self._function_cache:
            explanation = self._function_cache[func_name]
        else:
            # Analyze function
            try:
                source = inspect.getsource(func)
                func_info = self._parse_function(func)
                explanation = self.narrator.explain_function(func_info)
                
                # Cache it
                self._function_cache[func_name] = explanation
            except:
                explanation = f"Function '{func_name}' executing"
        
        # Add context if provided
        if context:
            explanation = f"{explanation}\n🔍 Context: {context}"
        
        # Truncate if too long
        if len(explanation) > MAX_NARRATION_LENGTH:
            explanation = explanation[:MAX_NARRATION_LENGTH] + "..."
        
        return explanation
    
    def _parse_function(self, func: Callable) -> FunctionInfo:
        """
        Extract FunctionInfo from a callable.
        
        Args:
            func: Function to analyze
            
        Returns:
            FunctionInfo object
        """
        import ast
        
        # Get function signature
        sig = inspect.signature(func)
        args = [param.name for param in sig.parameters.values() if param.name != 'self']
        
        # Get source and parse
        source = inspect.getsource(func)
        tree = ast.parse(source)
        
        # Find function node
        func_node = None
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == func.__name__:
                    func_node = node
                    break
        
        if not func_node:
            # Fallback
            return FunctionInfo(
                name=func.__name__,
                args=args,
                returns=None,
                is_async=inspect.iscoroutinefunction(func),
                docstring=func.__doc__,
                complexity=1,
                line_start=0,
                line_end=0
            )
        
        # Use narrator's analysis
        return self.narrator._analyze_function(func_node)
    
    def explain_saga_step(self, saga_name: str, step_name: str, step_description: str) -> Optional[str]:
        """
        Explain a saga step execution.
        
        Args:
            saga_name: Name of the saga
            step_name: Name of the step
            step_description: What the step does
            
        Returns:
            Human explanation
        """
        if not self.enabled or not EXPLAIN_SAGA_FLOWS:
            return None
        
        if self.narrator.mode == ExplanationMode.TRADER:
            return f"📖 Saga '{saga_name}' → Step '{step_name}': {step_description}"
        elif self.narrator.mode == ExplanationMode.SIMPLE:
            return f"The bot is doing step '{step_name}' in the '{saga_name}' sequence."
        else:
            return f"Saga: {saga_name}, Step: {step_name}"
    
    def explain_actor_message(self, actor_name: str, message_type: str, handler: str) -> Optional[str]:
        """
        Explain actor message routing.
        
        Args:
            actor_name: Name of the actor
            message_type: Type of message
            handler: Handler function name
            
        Returns:
            Human explanation
        """
        if not self.enabled or not EXPLAIN_ACTOR_ROUTING:
            return None
        
        if self.narrator.mode == ExplanationMode.TRADER:
            return f"🎯 Actor '{actor_name}' received '{message_type}' → routing to '{handler}()'"
        elif self.narrator.mode == ExplanationMode.SIMPLE:
            return f"The '{actor_name}' worker got a '{message_type}' message and knows what to do."
        else:
            return f"Actor: {actor_name}, Message: {message_type}, Handler: {handler}"
    
    async def explain_function_call_async(self, func: Callable, context: str = "") -> Optional[str]:
        """
        Async-safe function explanation.
        
        Runs explanation in thread pool to never block event loop.
        
        Args:
            func: Function being called
            context: Additional context
            
        Returns:
            Human explanation or None
        """
        if not ASYNC_SAFE_MODE:
            # Direct execution
            return self.explain_function_call(func, context)
        
        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        try:
            explanation = await loop.run_in_executor(
                self._executor,
                self.explain_function_call,
                func,
                context
            )
            return explanation
        except:
            return None
    
    def clear_cache(self):
        """Clear function analysis cache"""
        self._function_cache.clear()
    
    def shutdown(self):
        """Clean shutdown of executor"""
        self._executor.shutdown(wait=False)


# ==================== DECORATOR FOR AUTOMATIC NARRATION ====================

def narrate(event_type: str = "function_call", context: str = ""):
    """
    Decorator to automatically narrate function calls.
    
    Usage:
        @narrate(event_type="order_placed", context="after fill processing")
        async def place_order(self, side, price):
            ...
    
    Args:
        event_type: Type of event for rate limiting
        context: Context description
    
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Check if we should narrate
            if narrator_integration.should_narrate(event_type):
                # Get explanation
                explanation = await narrator_integration.explain_function_call_async(func, context)
                
                if explanation:
                    # Import human_log here to avoid circular imports
                    from bot.utils.human_logger import human_log
                    human_log.code_narration_event(explanation)
            
            # Execute the actual function
            return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Check if we should narrate
            if narrator_integration.should_narrate(event_type):
                # Get explanation
                explanation = narrator_integration.explain_function_call(func, context)
                
                if explanation:
                    # Import human_log here to avoid circular imports
                    from bot.utils.human_logger import human_log
                    human_log.code_narration_event(explanation)
            
            # Execute the actual function
            return func(*args, **kwargs)
        
        # Return appropriate wrapper based on function type
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# Global singleton
narrator_integration = NarratorIntegration()


# ==================== CONVENIENCE FUNCTIONS ====================

def explain_code_event(event_type: str, description: str):
    """
    Manually trigger a code narration event.
    
    Args:
        event_type: Event type for rate limiting
        description: What's happening
    """
    if narrator_integration.should_narrate(event_type):
        from bot.utils.human_logger import human_log
        human_log.code_narration_event(description)


def explain_this_function(context: str = ""):
    """
    Explain the calling function.
    
    Call this inside any function to get runtime narration:
        def my_function():
            explain_this_function("processing order fill")
            # ... rest of code
    
    Args:
        context: Additional context
    """
    # Get calling function
    frame = inspect.currentframe().f_back
    func_name = frame.f_code.co_name
    
    # Try to get the actual function object
    try:
        func = frame.f_globals.get(func_name)
        if func and callable(func):
            if narrator_integration.should_narrate("function_call"):
                explanation = narrator_integration.explain_function_call(func, context)
                if explanation:
                    from bot.utils.human_logger import human_log
                    human_log.code_narration_event(explanation)
    except:
        pass


def narrate_saga_step(saga_name: str, step_name: str, description: str):
    """
    Narrate a saga step.
    
    Args:
        saga_name: Name of saga
        step_name: Step name
        description: What the step does
    """
    if narrator_integration.should_narrate(f"saga_{saga_name}"):
        explanation = narrator_integration.explain_saga_step(saga_name, step_name, description)
        if explanation:
            from bot.utils.human_logger import human_log
            human_log.code_narration_event(explanation)


def narrate_actor_message(actor_name: str, message_type: str, handler: str):
    """
    Narrate actor message routing.
    
    Args:
        actor_name: Actor name
        message_type: Message type
        handler: Handler function
    """
    if narrator_integration.should_narrate(f"actor_{actor_name}"):
        explanation = narrator_integration.explain_actor_message(actor_name, message_type, handler)
        if explanation:
            from bot.utils.human_logger import human_log
            human_log.code_narration_event(explanation)
