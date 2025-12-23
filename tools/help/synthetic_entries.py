"""
Synthetic Help Entries for Frontend Actions
These are manually defined help entries for frontend actions that don't have dedicated backend routes
but share common endpoints (like /api/config or /api/capital/update-config)
"""

SYNTHETIC_HELP_ENTRIES = [
    {
        "action_id": "capital.equity-floor.save",
        "title": "Save Equity Floor Settings",
        "summary": "Updates equity floor capital protection settings",
        "effects": [
            "Saves EQUITY_FLOOR threshold to config",
            "Updates EQUITY_FLOOR_CHECK_INTERVAL",
            "Sets EQUITY_FLOOR_REQUIRE_ACK if enabled",
            "Hot reload applies changes immediately to running bot",
            "Guardian will enforce new equity floor limit"
        ],
        "risks": [
            "Setting floor too high may trigger immediate stop",
            "Setting floor too low reduces protection"
        ],
        "related_config": ["EQUITY_FLOOR", "EQUITY_FLOOR_CHECK_INTERVAL", "EQUITY_FLOOR_REQUIRE_ACK"],
        "api": {"method": "POST", "endpoint": "/api/capital/update-config"},
        "category": "capital-protection"
    },
    {
        "action_id": "capital.drawdown-cap.save",
        "title": "Save Drawdown Cap Settings",
        "summary": "Updates maximum drawdown limits for capital protection",
        "effects": [
            "Saves MAX_DRAWDOWN_PERCENT to config",
            "Updates DRAWDOWN_CHECK_INTERVAL",
            "Sets DRAWDOWN_HYSTERESIS_PCT and DRAWDOWN_WINDOW_DAYS",
            "Hot reload applies changes immediately",
            "Guardian enforces new drawdown limits"
        ],
        "risks": [
            "Tighter limits may trigger stops during normal volatility",
            "Looser limits reduce downside protection"
        ],
        "related_config": ["MAX_DRAWDOWN_PERCENT", "DRAWDOWN_CHECK_INTERVAL", "DRAWDOWN_HYSTERESIS_PCT", "DRAWDOWN_WINDOW_DAYS"],
        "api": {"method": "POST", "endpoint": "/api/capital/update-config"},
        "category": "capital-protection"
    },
    {
        "action_id": "liquidation.save-settings",
        "title": "Save Liquidation Protection Settings",
        "summary": "Updates liquidation protection configuration to prevent margin calls",
        "effects": [
            "Saves liquidation distance thresholds",
            "Updates margin buffer requirements",
            "Sets auto-liquidation triggers",
            "Applies to running bot via hot reload",
            "Liquidation monitor enforces new limits"
        ],
        "risks": [
            "Too aggressive settings may close positions prematurely",
            "Too loose settings increase liquidation risk"
        ],
        "related_config": ["LIQUIDATION_DISTANCE_THRESHOLD", "MARGIN_BUFFER_PERCENT", "AUTO_LIQUIDATE_ENABLED"],
        "api": {"method": "POST", "endpoint": "/api/liquidation/config"},
        "category": "liquidation-protection"
    },
    {
        "action_id": "monitoring.save-safety-limits",
        "title": "Save Safety Limits",
        "summary": "Updates core trading safety limits (loss limits, position size, order quantity)",
        "effects": [
            "Saves MAX_ACCOUNT_LOSS_INR to config",
            "Updates MAX_POSITION_NOTIONAL_INR",
            "Sets MAX_QTY_PER_ORDER",
            "Hot reload applies immediately to running bot",
            "Gatekeeper enforces new limits on next order"
        ],
        "risks": [
            "Increasing limits reduces protection",
            "Decreasing limits may block legitimate trades",
            "Changes apply immediately to running bot"
        ],
        "related_config": ["MAX_ACCOUNT_LOSS_INR", "MAX_POSITION_NOTIONAL_INR", "MAX_QTY_PER_ORDER"],
        "api": {"method": "POST", "endpoint": "/api/config"},
        "category": "safety"
    },
    {
        "action_id": "reconciliation.resync",
        "title": "Resync Order Status",
        "summary": "Resyncs selected orders with exchange to fix discrepancies",
        "effects": [
            "Fetches latest order status from exchange API",
            "Updates local bot_state.json with current status",
            "Fixes PENDING_ACK, FILLED, CANCELLED status mismatches",
            "Resolves ghost order issues",
            "Updates order reconciliation log"
        ],
        "use_cases": [
            "When orders show as pending but are filled on exchange",
            "To fix ghost orders that don't exist on exchange",
            "After network issues caused status desync"
        ],
        "related_config": ["RECONCILIATION_ENABLED", "RECONCILIATION_INTERVAL"],
        "api": {"method": "POST", "endpoint": "/api/reconciliation/resync"},
        "category": "reconciliation"
    },
    {
        "action_id": "reconciliation.acknowledge",
        "title": "Acknowledge Discrepancy",
        "summary": "Marks order discrepancies as acknowledged (known/accepted)",
        "effects": [
            "Moves orders from active discrepancies to acknowledged",
            "Stops alerting on these specific orders",
            "Does NOT fix the underlying issue",
            "Records acknowledgment time and user"
        ],
        "use_cases": [
            "When discrepancy is known and being handled manually",
            "To reduce alert noise for non-critical issues",
            "After manual intervention outside the bot"
        ],
        "api": {"method": "POST", "endpoint": "/api/reconciliation/acknowledge"},
        "category": "reconciliation"
    },
    {
        "action_id": "reconciliation.ignore",
        "title": "Ignore Discrepancy (24h)",
        "summary": "Temporarily ignores selected order discrepancies for 24 hours",
        "effects": [
            "Hides discrepancies from active view",
            "Stops alerts for 24 hours",
            "Auto-expires after 24h and reappears if still present",
            "Does NOT fix the issue"
        ],
        "use_cases": [
            "Temporary exchange API issues",
            "Waiting for manual order cancellation",
            "Known transient issues"
        ],
        "api": {"method": "POST", "endpoint": "/api/reconciliation/ignore"},
        "category": "reconciliation"
    },
    {
        "action_id": "robustness.save-loss-limits",
        "title": "Save Loss Limits",
        "summary": "Updates trader and guardian loss limits for robustness protection",
        "effects": [
            "Saves MAX_ACCOUNT_LOSS_INR (trader limit)",
            "Updates GUARDIAN_MAX_ACCOUNT_LOSS_INR (guardian limit)",
            "Hot reload applies changes immediately",
            "Guardian enforces new limits on running bot",
            "Loss tracker resets to use new thresholds"
        ],
        "risks": [
            "Increasing limits allows more losses before stop",
            "Decreasing limits may trigger immediate stop if already exceeded"
        ],
        "related_config": ["MAX_ACCOUNT_LOSS_INR", "GUARDIAN_MAX_ACCOUNT_LOSS_INR"],
        "api": {"method": "POST", "endpoint": "/api/config"},
        "category": "robustness"
    },
    {
        "action_id": "emergency.clear-flag",
        "title": "Clear Emergency Flag",
        "summary": "Clears the emergency flag allowing bot to resume operations",
        "effects": [
            "Removes emergency flag from bot_state.json",
            "Bot can start accepting new orders again",
            "Does NOT automatically restart the bot",
            "Resets gatekeeper if it was blocked"
        ],
        "use_cases": [
            "After resolving issue that triggered emergency mode",
            "To allow bot restart after manual emergency stop",
            "When recovering from critical error"
        ],
        "related_config": ["EMERGENCY_STOP_ENABLED"],
        "api": {"method": "POST", "endpoint": "/api/emergency/clear_flag"},
        "category": "emergency"
    },
    {
        "action_id": "emergency.reset-gatekeeper",
        "title": "Reset Gatekeeper",
        "summary": "Resets Safety Gatekeeper that blocks trading after errors",
        "effects": [
            "Resets gatekeeper blocking state",
            "Clears error counters and violation records",
            "Bot can resume checking for trading opportunities",
            "Does NOT clear emergency flags"
        ],
        "risks": [
            "Bot may resume trading if still running",
            "Underlying issues may not be resolved",
            "Error conditions may recur"
        ],
        "use_cases": [
            "After fixing configuration issues",
            "When error was temporary/resolved",
            "To resume trading after manual intervention"
        ],
        "related_config": ["GATEKEEPER_ENABLED"],
        "api": {"method": "POST", "endpoint": "/api/emergency/reset_gatekeeper"},
        "category": "emergency"
    },
    {
        "action_id": "emergency.force-restart",
        "title": "Force Restart Bot",
        "summary": "Forcefully restarts bot by killing and restarting process",
        "effects": [
            "Kills existing bot process (SIGTERM/SIGKILL)",
            "Starts new bot process",
            "Existing orders remain on exchange (NOT cancelled)",
            "Positions preserved",
            "Bot state reloaded from files"
        ],
        "risks": [
            "Orders in flight may not be tracked immediately",
            "Brief trading interruption (1-2 seconds)",
            "Unresponsive bot may not stop cleanly",
            "State sync issues if bot was mid-operation"
        ],
        "use_cases": [
            "Bot is frozen/unresponsive",
            "After critical configuration change",
            "When normal stop/start doesn't work",
            "Emergency recovery situation"
        ],
        "related_config": ["BOT_SCRIPT_PATH", "PYTHON_EXECUTABLE"],
        "api": {"method": "POST", "endpoint": "/api/emergency/force_restart"},
        "category": "emergency"
    },
    {
        "action_id": "config.save",
        "title": "Save Configuration",
        "summary": "Saves all configuration changes to grid_config.env file",
        "effects": [
            "Writes updated config values to grid_config.env",
            "Validates configuration before saving",
            "Triggers hot reload if bot is running",
            "Changes apply immediately to running bot (no restart needed for most settings)",
            "Creates backup of previous config"
        ],
        "risks": [
            "Invalid values may prevent bot from starting",
            "Some critical settings require bot restart to take effect",
            "Incorrect safety limits could increase risk exposure"
        ],
        "use_cases": [
            "After modifying grid parameters",
            "Updating safety limits or risk settings",
            "Changing Telegram or notification settings",
            "Enabling/disabling features"
        ],
        "post_action": [
            "Check bot logs for hot reload confirmation",
            "Verify changes took effect in bot status",
            "Restart bot if critical settings were changed"
        ],
        "related_config": ["All config keys"],
        "api": {"method": "POST", "endpoint": "/api/config/update"},
        "category": "configuration"
    },
    {
        "action_id": "config.reset",
        "title": "Reset Configuration",
        "summary": "Discards all unsaved configuration changes and reverts to last saved state",
        "effects": [
            "Reloads config from grid_config.env file",
            "Discards all pending changes in UI",
            "Does NOT modify saved config file",
            "No impact on running bot"
        ],
        "use_cases": [
            "Made incorrect changes and want to start over",
            "Accidentally modified wrong settings",
            "Want to abandon all pending changes"
        ],
        "api": {"method": "GET", "endpoint": "/api/config/all"},
        "category": "configuration"
    }
]
