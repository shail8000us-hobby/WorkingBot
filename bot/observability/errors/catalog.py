"""
Error Catalog - Known error patterns and their remediation actions
This is the knowledge base for error classification and fixes.
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from .schema import ErrorSeverity, ErrorSource, ErrorAction


@dataclass
class ErrorPattern:
    """Pattern matcher for known errors"""
    code: str
    regex: str
    severity: ErrorSeverity
    title: str
    explanation: str
    likely_causes: List[str]
    suggested_actions: List[str]
    available_fixes: List[ErrorAction]
    can_auto_fix: bool = False
    applies_to_sources: Optional[List[ErrorSource]] = None
    
    def matches(self, message: str, source: ErrorSource) -> bool:
        """Check if this pattern matches the message"""
        if self.applies_to_sources and source not in self.applies_to_sources:
            return False
        return bool(re.search(self.regex, message, re.IGNORECASE))


class ErrorCatalog:
    """Central catalog of known error patterns"""
    
    def __init__(self):
        self.patterns: List[ErrorPattern] = []
        self._initialize_catalog()
    
    def _initialize_catalog(self):
        """Load all known error patterns"""
        
        # ========== API & Authentication Errors ==========
        self.patterns.append(ErrorPattern(
            code="API_AUTH_FAILED",
            regex=r"(authentication failed|invalid api key|unauthorized|401)",
            severity=ErrorSeverity.CRITICAL,
            title="API Authentication Failed",
            explanation="The bot cannot authenticate with the exchange API. This blocks all trading operations.",
            likely_causes=[
                "API key expired or revoked",
                "API key not whitelisted for current IP",
                "Wrong API credentials in secrets/api_keys.env",
                "API key permissions insufficient (need trading enabled)"
            ],
            suggested_actions=[
                "Verify API keys in secrets/api_keys.env",
                "Check IP whitelist on Delta Exchange",
                "Regenerate API keys if compromised",
                "Ensure trading permissions are enabled for the API key"
            ],
            available_fixes=[
                ErrorAction(
                    id="refresh_api_keys",
                    title="Refresh API Keys from File",
                    description="Reload API credentials from secrets/api_keys.env without restarting bot",
                    requires_confirmation=True,
                    is_destructive=False,
                    is_dry_runnable=False,
                    preconditions=["API keys file must exist", "Bot must be running"],
                    side_effects=["Active connections will be re-established"]
                )
            ],
            can_auto_fix=False
        ))
        
        # ========== Rate Limiting ==========
        self.patterns.append(ErrorPattern(
            code="API_RATE_LIMIT",
            regex=r"(rate limit|too many requests|429|throttle)",
            severity=ErrorSeverity.HIGH,
            title="API Rate Limit Exceeded",
            explanation="The bot is making too many API requests and is being throttled by the exchange.",
            likely_causes=[
                "Too many orders placed in short time",
                "Multiple bot instances running (check for duplicates)",
                "API limits changed by exchange",
                "Overly aggressive polling intervals"
            ],
            suggested_actions=[
                "Check for duplicate bot processes (ps aux | grep gridbot)",
                "Increase API_CALL_DELAY in config",
                "Reduce grid density (fewer orders)",
                "Wait 60 seconds for rate limit to reset"
            ],
            available_fixes=[
                ErrorAction(
                    id="pause_trading_15m",
                    title="Pause Trading for 15 Minutes",
                    description="Temporarily stop new order placement to let rate limits reset",
                    requires_confirmation=True,
                    is_destructive=False,
                    is_dry_runnable=False,
                    preconditions=["Bot is running"],
                    side_effects=["No new orders for 15 minutes", "Existing orders remain active"]
                ),
                ErrorAction(
                    id="increase_api_delay",
                    title="Increase API Call Delay",
                    description="Set API_CALL_DELAY to 1.0 second (from current value)",
                    requires_confirmation=True,
                    is_destructive=False,
                    is_dry_runnable=True,
                    preconditions=["config.yaml is writable"],
                    side_effects=["Slower order updates", "Reduced API calls"]
                )
            ],
            can_auto_fix=False
        ))
        
        # ========== Margin & Liquidation ==========
        self.patterns.append(ErrorPattern(
            code="INSUFFICIENT_MARGIN",
            regex=r"(insufficient.*margin|margin.*low|not enough.*collateral|balance.*low)",
            severity=ErrorSeverity.CRITICAL,
            title="Insufficient Margin",
            explanation="Account margin is too low to place new orders or maintain positions. Risk of liquidation.",
            likely_causes=[
                "Account balance depleted by losses",
                "Position size too large for available margin",
                "Multiple positions consuming margin",
                "Unrealized losses reducing available margin"
            ],
            suggested_actions=[
                "Add funds to account immediately",
                "Close losing positions to free margin",
                "Reduce position sizes (GRIDBOT_MAX_OPEN)",
                "Check Guardian bot settings (should have prevented this)"
            ],
            available_fixes=[
                ErrorAction(
                    id="reduce_position_size",
                    title="Reduce Maximum Position Size by 50%",
                    description="Update GRIDBOT_MAX_OPEN to half current value",
                    requires_confirmation=True,
                    is_destructive=False,
                    is_dry_runnable=True,
                    preconditions=["Bot is running", "config.yaml is writable"],
                    side_effects=["Smaller positions", "Lower risk", "Lower potential profit"]
                ),
                ErrorAction(
                    id="emergency_stop_entries",
                    title="Stop New Entries (Keep Exits)",
                    description="Set EXECUTE_ORDERS=False to prevent new positions",
                    requires_confirmation=True,
                    is_destructive=False,
                    is_dry_runnable=False,
                    preconditions=["Bot is running"],
                    side_effects=["No new BUY orders", "Existing positions can still close"]
                )
            ],
            can_auto_fix=False
        ))
        
        # Startup Error Patterns - Safety Gatekeeper
        self.patterns.append(ErrorPattern(
            code="SAFETY_GATEKEEPER_BLOCK",
            regex=r"Safety gatekeeper blocked (BUY|SELL) order",
            severity=ErrorSeverity.MEDIUM,
            title="Safety Gatekeeper Blocked Order",
            explanation="The safety gatekeeper prevented an order from being placed due to risk limits or safety checks.",
            likely_causes=[
                "EXECUTE_ORDERS is set to False",
                "Margin utilization exceeds maximum allowed",
                "Order confirmation guard is active (waiting for previous fill)",
                "Volatility limits exceeded",
                "Emergency stop flag is set",
                "Equity floor breached",
                "Drawdown protective mode active"
            ],
            suggested_actions=[
                "Check safety gatekeeper status in the Robustness panel",
                "Review current margin utilization",
                "Verify EXECUTE_ORDERS setting in configuration",
                "Check if order confirmation guard is blocking (review recent fills)",
                "Review volatility limits if applicable",
                "Check Guardian bot status and equity floor settings"
            ],
            available_fixes=[
                ErrorAction(
                    id="check_execute_orders",
                    title="Check EXECUTE_ORDERS Setting",
                    description="Verify if EXECUTE_ORDERS is enabled in configuration",
                    requires_confirmation=False,
                    is_destructive=False,
                    is_dry_runnable=False,
                    preconditions=[],
                    side_effects=[]
                ),
                ErrorAction(
                    id="check_safety_status",
                    title="Check Safety Gatekeeper Status",
                    description="Review all safety gatekeeper checks and their current status",
                    requires_confirmation=False,
                    is_destructive=False,
                    is_dry_runnable=False,
                    preconditions=[],
                    side_effects=[]
                )
            ],
            can_auto_fix=False
        ))
        
        # Configuration Change Detection
        self.patterns.append(ErrorPattern(
            code="CONFIG_CHANGE_DETECTED",
            regex=r"CONFIGURATION CHANGES DETECTED|config.*change|hot.*reload",
            severity=ErrorSeverity.LOW,
            title="Configuration Changes Detected",
            explanation="The bot detected changes to config.yaml and will apply them via hot reload.",
            likely_causes=[
                "User edited config.yaml file",
                "Configuration was updated via WebUI",
                "Automated configuration adjustment"
            ],
            suggested_actions=[
                "Verify the configuration changes are intentional",
                "Review the new settings in the Configuration panel",
                "Monitor bot behavior after the reload",
                "Check that grid parameters are correct"
            ],
            available_fixes=[
                ErrorAction(
                    id="verify_config",
                    title="Verify Configuration",
                    description="Review current configuration settings",
                    requires_confirmation=False,
                    is_destructive=False,
                    is_dry_runnable=False,
                    preconditions=[],
                    side_effects=[]
                )
            ],
            can_auto_fix=False
        ))
        
        # Log Formatting False Positives
        self.patterns.append(ErrorPattern(
            code="LOG_FORMATTING_FALSE_POSITIVE",
            regex=r"^[━═\-─]{50,}$",
            severity=ErrorSeverity.LOW,
            title="Log Formatting (Not an Error)",
            explanation="This is a log formatting line (decorative separator), not an actual error.",
            likely_causes=[
                "Log formatting for visual clarity",
                "Section separators in logs"
            ],
            suggested_actions=[
                "No action needed - this is not a real error",
                "Can be safely ignored or marked as resolved"
            ],
            available_fixes=[
                ErrorAction(
                    id="mark_resolved",
                    title="Mark as Resolved",
                    description="Mark this false positive as resolved",
                    requires_confirmation=False,
                    is_destructive=False,
                    is_dry_runnable=False,
                    preconditions=[],
                    side_effects=[]
                )
            ],
            can_auto_fix=True
        ))
        
        self.patterns.append(ErrorPattern(
            code="LIQUIDATION_RISK",
            regex=r"(liquidation.*risk|close to liquidation|margin.*critical|bankruptcy price)",
            severity=ErrorSeverity.CRITICAL,
            title="Liquidation Risk Detected",
            explanation="Position is dangerously close to liquidation price. Immediate action required.",
            likely_causes=[
                "Large adverse price movement",
                "Excessive leverage",
                "Guardian bot not running or configured incorrectly",
                "Insufficient margin buffer"
            ],
            suggested_actions=[
                "Add margin to account IMMEDIATELY",
                "Close positions manually to reduce risk",
                "Check Guardian bot status (should auto-close)",
                "Verify GUARDIAN_MAX_ACCOUNT_LOSS_INR is set correctly"
            ],
            available_fixes=[
                ErrorAction(
                    id="close_all_positions",
                    title="Close All Positions (Market Orders)",
                    description="Emergency liquidation of all open positions at market price",
                    requires_confirmation=True,
                    is_destructive=True,
                    is_dry_runnable=False,
                    preconditions=["User confirmed understanding of slippage"],
                    side_effects=["All positions closed", "May incur slippage losses", "Preserves remaining capital"]
                )
            ],
            can_auto_fix=False
        ))
        
        # ========== Network & Connectivity ==========
        self.patterns.append(ErrorPattern(
            code="NETWORK_UNREACHABLE",
            regex=r"(network.*unreachable|connection refused|timed out|EHOSTUNREACH|ECONNREFUSED)",
            severity=ErrorSeverity.HIGH,
            title="Network Connection Lost",
            explanation="Cannot reach the exchange API. Trading operations suspended.",
            likely_causes=[
                "Internet connection down",
                "Exchange API outage",
                "Firewall blocking connection",
                "DNS resolution failure"
            ],
            suggested_actions=[
                "Check internet connectivity (ping 8.8.8.8)",
                "Verify exchange status (status.delta.exchange)",
                "Check firewall rules",
                "Wait for connectivity to restore (bot will auto-reconnect)"
            ],
            available_fixes=[
                ErrorAction(
                    id="test_connectivity",
                    title="Test Exchange Connectivity",
                    description="Attempt to ping exchange API and report results",
                    requires_confirmation=False,
                    is_destructive=False,
                    is_dry_runnable=False,
                    preconditions=[],
                    side_effects=["No side effects, read-only test"]
                )
            ],
            can_auto_fix=False
        ))
        
        # ========== Configuration Errors ==========
        self.patterns.append(ErrorPattern(
            code="CONFIG_PARAM_DRIFT",
            regex=r"(param.*mismatch|config.*drift|GRIDBOT_.*not.*sync|legacy param)",
            severity=ErrorSeverity.MEDIUM,
            title="Configuration Parameter Drift",
            explanation="New GRIDBOT_* parameters don't match legacy parameters. Hot reload may fail.",
            likely_causes=[
                "Manual edit of config.yaml without updating both sets",
                "Migration to new param names incomplete",
                "Hot reload picked up only one set of changes"
            ],
            suggested_actions=[
                "Use Configuration panel to update both GRIDBOT_* and legacy params together",
                "Run parameter sync utility",
                "Check PARAMETER_SYNC_COMPLETE.md for details"
            ],
            available_fixes=[
                ErrorAction(
                    id="sync_gridbot_params",
                    title="Sync GRIDBOT_* → Legacy Parameters",
                    description="Copy GRIDBOT_MAX_OPEN → MAX_OPEN, GRIDBOT_GRID_* → GRID_*, etc.",
                    requires_confirmation=True,
                    is_destructive=False,
                    is_dry_runnable=True,
                    preconditions=["config.yaml is writable"],
                    side_effects=["Legacy params will match GRIDBOT_* values", "Hot reload will use new values"]
                )
            ],
            can_auto_fix=True
        ))
        
        self.patterns.append(ErrorPattern(
            code="CONFIG_MISSING",
            regex=r"(config.*not found|missing.*parameter|keyerror.*env|required.*setting)",
            severity=ErrorSeverity.HIGH,
            title="Required Configuration Missing",
            explanation="A required configuration parameter is missing or invalid.",
            likely_causes=[
                "config.yaml incomplete",
                "Typo in parameter name",
                "File permissions preventing read",
                "Parameter added in new version but not documented"
            ],
            suggested_actions=[
                "Check config.yaml for missing parameters",
                "Compare with config.yaml.example",
                "Check file permissions (should be readable)",
                "Review CONFIGURATION_PANEL_GUIDE.md"
            ],
            available_fixes=[
                ErrorAction(
                    id="restore_default_config",
                    title="Restore Missing Parameters to Defaults",
                    description="Add any missing required parameters with safe default values",
                    requires_confirmation=True,
                    is_destructive=False,
                    is_dry_runnable=True,
                    preconditions=["config.yaml exists and is writable"],
                    side_effects=["Missing parameters will be added with defaults"]
                )
            ],
            can_auto_fix=False
        ))
        
        # ========== Exchange Errors ==========
        self.patterns.append(ErrorPattern(
            code="EXCHANGE_DOWNTIME",
            regex=r"(exchange.*down|maintenance.*mode|service unavailable|503|exchange.*offline)",
            severity=ErrorSeverity.HIGH,
            title="Exchange Downtime/Maintenance",
            explanation="The exchange is temporarily unavailable (maintenance or outage).",
            likely_causes=[
                "Scheduled maintenance",
                "Unexpected exchange outage",
                "DDoS protection active"
            ],
            suggested_actions=[
                "Check exchange status page",
                "Wait for exchange to come back online",
                "Bot will auto-reconnect when available",
                "Consider setting EXECUTE_ORDERS=False until stable"
            ],
            available_fixes=[],
            can_auto_fix=False
        ))
        
        # ========== Order Execution Errors ==========
        self.patterns.append(ErrorPattern(
            code="ORDER_REJECTED",
            regex=r"(order.*reject|invalid.*order|order.*failed|post.*only.*fail)",
            severity=ErrorSeverity.MEDIUM,
            title="Order Rejected by Exchange",
            explanation="The exchange rejected an order placement request.",
            likely_causes=[
                "Post-only order would have matched immediately",
                "Price too far from market (exchange limits)",
                "Order size violates exchange minimums",
                "Duplicate order detected"
            ],
            suggested_actions=[
                "Check order parameters (price, size)",
                "Verify POST_ONLY_MODE setting matches strategy",
                "Review exchange order rules",
                "Check for duplicate bot processes"
            ],
            available_fixes=[
                ErrorAction(
                    id="disable_post_only",
                    title="Disable Post-Only Mode",
                    description="Set POST_ONLY_MODE=False to allow taker orders",
                    requires_confirmation=True,
                    is_destructive=False,
                    is_dry_runnable=True,
                    preconditions=["config.yaml is writable"],
                    side_effects=["Orders may cross spread", "Pay taker fees instead of maker rebates"]
                )
            ],
            can_auto_fix=False
        ))
        
        # ========== Bot Health & Process Errors ==========
        self.patterns.append(ErrorPattern(
            code="BOT_PROCESS_DUPLICATE",
            regex=r"(duplicate.*process|multiple.*instances|already.*running|process.*conflict)",
            severity=ErrorSeverity.CRITICAL,
            title="Duplicate Bot Process Detected",
            explanation="Multiple instances of the bot are running, which can cause double-trading and conflicts.",
            likely_causes=[
                "Bot started multiple times without stopping previous instance",
                "PM2 or supervisor started duplicate processes",
                "Manual start while PM2 already running"
            ],
            suggested_actions=[
                "Stop all bot instances: pm2 stop all",
                "Check running processes: ps aux | grep gridbot",
                "Kill duplicates manually if needed",
                "Start fresh with single instance"
            ],
            available_fixes=[
                ErrorAction(
                    id="kill_duplicate_processes",
                    title="Kill Duplicate Bot Processes",
                    description="Identify and terminate duplicate bot PIDs, keeping only the oldest",
                    requires_confirmation=True,
                    is_destructive=True,
                    is_dry_runnable=False,
                    preconditions=["Multiple bot processes detected"],
                    side_effects=["Only one bot instance will remain running"]
                )
            ],
            can_auto_fix=False
        ))
        
        self.patterns.append(ErrorPattern(
            code="HOT_RELOAD_FAILED",
            regex=r"(hot.*reload.*fail|config.*reload.*error|failed.*to.*apply|hash.*mismatch)",
            severity=ErrorSeverity.MEDIUM,
            title="Hot Reload Failed",
            explanation="The bot detected configuration changes but failed to apply them without restart.",
            likely_causes=[
                "Invalid parameter values",
                "Config file syntax error",
                "Parameter sync mismatch (GRIDBOT_* vs legacy)",
                "File locked by another process"
            ],
            suggested_actions=[
                "Check config file syntax",
                "Verify parameter values are valid",
                "Use Configuration panel instead of manual edit",
                "Restart bot if hot reload continues to fail"
            ],
            available_fixes=[
                ErrorAction(
                    id="force_config_reload",
                    title="Force Configuration Reload",
                    description="Restart config watcher and re-apply current settings",
                    requires_confirmation=True,
                    is_destructive=False,
                    is_dry_runnable=False,
                    preconditions=["Bot is running"],
                    side_effects=["Brief interruption in config monitoring"]
                )
            ],
            can_auto_fix=False
        ))
        
        # ========== Python/System Errors ==========
        self.patterns.append(ErrorPattern(
            code="UNHANDLED_EXCEPTION",
            regex=r"(traceback|exception|error:|unhandled|crash)",
            severity=ErrorSeverity.HIGH,
            title="Unhandled Exception",
            explanation="The bot encountered an unexpected error. This may indicate a bug or edge case.",
            likely_causes=[
                "Bug in bot code",
                "Unexpected API response format",
                "Data type mismatch",
                "Edge case not handled"
            ],
            suggested_actions=[
                "Check full stack trace in logs",
                "Report to developers with reproduction steps",
                "Check if similar error reported in GitHub issues",
                "Restart bot if it's stuck"
            ],
            available_fixes=[],
            can_auto_fix=False
        ))
        
        self.patterns.append(ErrorPattern(
            code="JSON_PARSE_ERROR",
            regex=r"(json.*decode.*error|invalid.*json|parse.*error|unexpected.*token)",
            severity=ErrorSeverity.MEDIUM,
            title="JSON Parsing Error",
            explanation="Failed to parse JSON response from exchange or config file.",
            likely_causes=[
                "Malformed exchange API response",
                "Config file has syntax errors",
                "Incomplete response (timeout mid-transfer)",
                "Encoding issues"
            ],
            suggested_actions=[
                "Check logs for exact parsing error",
                "Verify config file JSON syntax",
                "If exchange response, retry request",
                "Check network stability"
            ],
            available_fixes=[],
            can_auto_fix=False
        ))

        # ========== Startup & Safety Gatekeeper Issues ==========
        self.patterns.append(ErrorPattern(
            code="SAFETY_GATEKEEPER_BLOCK",
            regex=r"(safety gatekeeper blocked|gatekeeper blocked)",
            severity=ErrorSeverity.MEDIUM,
            title="Safety Gatekeeper Blocking Orders",
            explanation="The safety gatekeeper is preventing order placement due to safety checks.",
            likely_causes=[
                "EXECUTE_ORDERS disabled in configuration",
                "Margin utilization limits exceeded",
                "Order confirmation guard waiting for previous order",
                "Emergency stop flag exists",
                "Drawdown protective mode active"
            ],
            suggested_actions=[
                "Check safety gatekeeper status in WebUI",
                "Verify EXECUTE_ORDERS=true in config.yaml",
                "Review margin utilization limits",
                "Check for emergency stop flags",
                "Wait for order confirmation if applicable"
            ],
            available_fixes=[
                ErrorAction(
                    id="check_gatekeeper_status",
                    title="Check Gatekeeper Status",
                    description="View current safety gatekeeper configuration and blocking reasons",
                    requires_confirmation=False,
                    is_destructive=False,
                    is_dry_runnable=True,
                    preconditions=["Bot must be running"],
                    side_effects=["None - read-only operation"]
                ),
                ErrorAction(
                    id="enable_execute_orders",
                    title="Enable Execute Orders",
                    description="Set EXECUTE_ORDERS=true in configuration (if safe to do so)",
                    requires_confirmation=True,
                    is_destructive=False,
                    is_dry_runnable=True,
                    preconditions=["Configuration file must exist"],
                    side_effects=["Bot will be able to place real orders"]
                )
            ],
            can_auto_fix=True
        ))

        self.patterns.append(ErrorPattern(
            code="CONFIG_CHANGE_DETECTED",
            regex=r"(configuration changes detected|config changes detected|hot reload)",
            severity=ErrorSeverity.LOW,
            title="Configuration Changes Detected",
            explanation="The bot detected configuration changes during startup. This is normal behavior.",
            likely_causes=[
                "Configuration file was modified",
                "Hot reload system activated",
                "Environment variables changed",
                "Settings updated via WebUI"
            ],
            suggested_actions=[
                "Verify configuration changes are correct",
                "Check that all required settings are present",
                "Restart bot if configuration changes are significant",
                "Review configuration for any errors"
            ],
            available_fixes=[
                ErrorAction(
                    id="verify_config_integrity",
                    title="Verify Configuration Integrity",
                    description="Check configuration file for missing or invalid settings",
                    requires_confirmation=False,
                    is_destructive=False,
                    is_dry_runnable=True,
                    preconditions=["Configuration file must exist"],
                    side_effects=["None - read-only operation"]
                ),
                ErrorAction(
                    id="apply_config_changes",
                    title="Apply Configuration Changes",
                    description="Apply pending configuration changes to running bot",
                    requires_confirmation=False,
                    is_destructive=False,
                    is_dry_runnable=True,
                    preconditions=["Bot must be running"],
                    side_effects=["Bot will use updated configuration"]
                )
            ],
            can_auto_fix=True
        ))

        self.patterns.append(ErrorPattern(
            code="LOG_FORMATTING_FALSE_POSITIVE",
            regex=r"^[━─═]+$",
            severity=ErrorSeverity.LOW,
            title="Log Formatting (False Positive)",
            explanation="This is a visual separator line in logs, not an actual error.",
            likely_causes=[
                "Log formatting with Unicode box-drawing characters",
                "Visual separators in log output",
                "Cosmetic log elements"
            ],
            suggested_actions=[
                "This is not an actual error - can be safely ignored",
                "Mark as resolved if it appears in error list",
                "Consider filtering out in error detection"
            ],
            available_fixes=[
                ErrorAction(
                    id="mark_as_false_positive",
                    title="Mark as False Positive",
                    description="Mark this error as resolved since it's just log formatting",
                    requires_confirmation=False,
                    is_destructive=False,
                    is_dry_runnable=False,
                    preconditions=["Error must be in database"],
                    side_effects=["Error will be marked as resolved"]
                )
            ],
            can_auto_fix=True
        ))
        
    def classify(self, message: str, source: ErrorSource) -> Optional[ErrorPattern]:
        """
        Classify a log message against known patterns.
        Returns the first matching pattern, or None if unknown.
        """
        for pattern in self.patterns:
            if pattern.matches(message, source):
                return pattern
        return None
    
    def get_pattern_by_code(self, code: str) -> Optional[ErrorPattern]:
        """Get pattern by error code"""
        for pattern in self.patterns:
            if pattern.code == code:
                return pattern
        return None
    
    def get_all_codes(self) -> List[str]:
        """Get list of all known error codes"""
        return [p.code for p in self.patterns]
