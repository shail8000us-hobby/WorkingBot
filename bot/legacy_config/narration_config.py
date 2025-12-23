"""
Code Narration Configuration
Shared settings for both standalone tool and runtime integration.
"""

# ==================== NARRATION SETTINGS ====================

# Enable/disable code narration at runtime
ENABLE_CODE_NARRATION = False  # Set to True to enable runtime narration

# Narration mode: 'tech', 'trader', or 'simple'
CODE_NARRATION_MODE = "trader"

# Rate limiting for code narration events (seconds between narrations)
# Prevents log spam during runtime
NARRATION_RATE_LIMIT = 10.0  # 10 seconds between runtime narrations

# Maximum narration text length (characters)
# Prevents oversized logs
MAX_NARRATION_LENGTH = 500

# ==================== SAFETY SETTINGS ====================

# Only narrate specific event types (if empty, narrate all)
# Examples: ['order_placed', 'order_filled', 'saga_started']
NARRATION_WHITELIST = [
    'order_placed',
    'order_filled',
    'position_updated',
    'saga_started',
    'saga_completed',
    'reconnection_started',
    'grid_updated'
]

# Never narrate these event types
NARRATION_BLACKLIST = [
    'heartbeat',
    'message_routed',  # Too frequent
    'ticker_update'     # Way too frequent
]

# Async-safe: Never block the event loop
# If True, narration runs in thread pool
ASYNC_SAFE_MODE = True

# Performance: Skip narration if system under stress
# Checks CPU and memory before narrating
RESPECT_SYSTEM_LOAD = True

# ==================== STANDALONE TOOL SETTINGS ====================

# Default output format for standalone tool
DEFAULT_OUTPUT_FORMAT = "terminal"  # terminal, md, json

# Default explanation mode for standalone tool
DEFAULT_EXPLANATION_MODE = "trader"  # tech, trader, simple

# Save standalone explanations to this directory
EXPLANATION_OUTPUT_DIR = "code_explanations"

# ==================== ADVANCED SETTINGS ====================

# Enable AST caching (improves performance for repeated analysis)
ENABLE_AST_CACHE = True

# Cache TTL (seconds)
AST_CACHE_TTL = 300  # 5 minutes

# Log narration events to separate file
LOG_NARRATIONS_SEPARATELY = False
NARRATION_LOG_FILE = "code_narrations.log"

# Detect and explain saga flows
EXPLAIN_SAGA_FLOWS = True

# Detect and explain actor message routing
EXPLAIN_ACTOR_ROUTING = True

# ==================== DEBUGGING ====================

# Debug mode: Log narration decisions
DEBUG_NARRATION = False

# Verbose mode: Show AST details
VERBOSE_AST_ANALYSIS = False
