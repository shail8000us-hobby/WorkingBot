"""
Prometheus Metric Definitions

All metrics are defined here with proper naming conventions:
- Prefix: gridbot_
- Naming: snake_case
- Units: always in suffix (_seconds, _bytes, _percent, etc.)

Metric Types:
- Counter: Monotonically increasing (orders_placed_total)
- Gauge: Can go up/down (open_positions_count)
- Histogram: Distribution of values (api_call_duration_seconds)
- Summary: Similar to histogram with quantiles

References:
- https://prometheus.io/docs/practices/naming/
- https://prometheus.io/docs/concepts/metric_types/
"""

from prometheus_client import (
    Counter, Gauge, Histogram, Summary, Info,
    CollectorRegistry
)

# Create isolated registry (don't pollute global namespace)
REGISTRY = CollectorRegistry()

# ============================================================================
# APPLICATION INFO
# ============================================================================

app_info = Info(
    'gridbot_app',
    'WorkingBot application information',
    registry=REGISTRY
)

# ============================================================================
# TRADING METRICS - Orders
# ============================================================================

orders_placed_total = Counter(
    'gridbot_orders_placed_total',
    'Total number of orders placed',
    ['side', 'status', 'symbol', 'instance', 'order_type'],
    registry=REGISTRY
)

orders_filled_total = Counter(
    'gridbot_orders_filled_total',
    'Total number of orders filled',
    ['side', 'symbol', 'instance'],
    registry=REGISTRY
)

orders_cancelled_total = Counter(
    'gridbot_orders_cancelled_total',
    'Total number of orders cancelled',
    ['reason', 'symbol', 'instance'],
    registry=REGISTRY
)

orders_failed_total = Counter(
    'gridbot_orders_failed_total',
    'Total number of orders that failed',
    ['error_type', 'symbol', 'instance'],
    registry=REGISTRY
)

# Order timing
order_placement_latency_seconds = Histogram(
    'gridbot_order_placement_latency_seconds',
    'Time taken to place an order',
    ['side', 'symbol', 'instance'],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    registry=REGISTRY
)

fill_latency_seconds = Histogram(
    'gridbot_fill_latency_seconds',
    'Time from order placement to fill',
    ['side', 'symbol', 'instance'],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600, 1800],
    registry=REGISTRY
)

# ============================================================================
# TRADING METRICS - Positions
# ============================================================================

open_positions_count = Gauge(
    'gridbot_open_positions_count',
    'Number of currently open positions',
    ['symbol', 'instance', 'side'],
    registry=REGISTRY
)

position_value_usd = Gauge(
    'gridbot_position_value_usd',
    'Total position value in USD',
    ['symbol', 'instance'],
    registry=REGISTRY
)

position_size_contracts = Gauge(
    'gridbot_position_size_contracts',
    'Total position size in contracts',
    ['symbol', 'instance', 'side'],
    registry=REGISTRY
)

# ============================================================================
# TRADING METRICS - P&L
# ============================================================================

unrealized_pnl_usd = Gauge(
    'gridbot_unrealized_pnl_usd',
    'Current unrealized profit/loss in USD',
    ['symbol', 'instance'],
    registry=REGISTRY
)

realized_pnl_usd = Counter(
    'gridbot_realized_pnl_usd_total',
    'Cumulative realized profit/loss in USD (use increase() for deltas)',
    ['symbol', 'instance'],
    registry=REGISTRY
)

daily_pnl_usd = Gauge(
    'gridbot_daily_pnl_usd',
    'Daily profit/loss in USD (resets at midnight)',
    ['symbol', 'instance'],
    registry=REGISTRY
)

# ============================================================================
# TRADING METRICS - Grid Performance
# ============================================================================

grid_level_fills_total = Counter(
    'gridbot_grid_level_fills_total',
    'Number of fills per grid level',
    ['level', 'side', 'symbol', 'instance'],
    registry=REGISTRY
)

grid_efficiency_ratio = Gauge(
    'gridbot_grid_efficiency_ratio',
    'Grid efficiency (active_levels / total_levels)',
    ['symbol', 'instance'],
    registry=REGISTRY
)

grid_coverage_percent = Gauge(
    'gridbot_grid_coverage_percent',
    'Percentage of grid covered by current positions',
    ['symbol', 'instance'],
    registry=REGISTRY
)

current_price_usd = Gauge(
    'gridbot_current_price_usd',
    'Current market price in USD',
    ['symbol'],
    registry=REGISTRY
)

grid_reference_price_usd = Gauge(
    'gridbot_grid_reference_price_usd',
    'Grid reference price in USD',
    ['symbol', 'instance'],
    registry=REGISTRY
)

# ============================================================================
# TRADING METRICS - Slippage
# ============================================================================

slippage_percent = Histogram(
    'gridbot_slippage_percent',
    'Order slippage as percentage of expected price',
    ['side', 'symbol', 'instance'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
    registry=REGISTRY
)

# ============================================================================
# SYSTEM METRICS
# ============================================================================

system_cpu_percent = Gauge(
    'gridbot_system_cpu_percent',
    'System CPU usage percentage',
    registry=REGISTRY
)

system_memory_percent = Gauge(
    'gridbot_system_memory_percent',
    'System memory usage percentage',
    registry=REGISTRY
)

system_memory_used_mb = Gauge(
    'gridbot_system_memory_used_mb',
    'System memory used in MB',
    registry=REGISTRY
)

system_disk_percent = Gauge(
    'gridbot_system_disk_percent',
    'System disk usage percentage',
    registry=REGISTRY
)

system_disk_used_gb = Gauge(
    'gridbot_system_disk_used_gb',
    'System disk used in GB',
    registry=REGISTRY
)

system_load_average = Gauge(
    'gridbot_system_load_average',
    'System load average',
    ['period'],  # 1m, 5m, 15m
    registry=REGISTRY
)

# ============================================================================
# BOT PROCESS METRICS
# ============================================================================

bot_memory_mb = Gauge(
    'gridbot_bot_memory_mb',
    'Bot process memory usage in MB',
    ['process_name', 'symbol', 'instance'],
    registry=REGISTRY
)

bot_uptime_seconds = Gauge(
    'gridbot_bot_uptime_seconds',
    'Bot process uptime in seconds',
    ['symbol', 'instance'],
    registry=REGISTRY
)

bot_restart_count = Counter(
    'gridbot_bot_restart_count_total',
    'Number of bot restarts',
    ['symbol', 'instance', 'reason'],
    registry=REGISTRY
)

bot_state = Gauge(
    'gridbot_bot_state',
    'Bot state (1=running, 0=stopped)',
    ['symbol', 'instance'],
    registry=REGISTRY
)

# ============================================================================
# GUARDIAN METRICS
# ============================================================================

guardian_signal = Gauge(
    'gridbot_guardian_signal',
    'Guardian trading signal (1=GO, 0=STOP)',
    ['symbol', 'instance'],
    registry=REGISTRY
)

guardian_risk_level = Gauge(
    'gridbot_guardian_risk_level',
    'Guardian calculated risk level (0-100)',
    ['symbol', 'instance'],
    registry=REGISTRY
)

guardian_interventions_total = Counter(
    'gridbot_guardian_interventions_total',
    'Number of Guardian interventions',
    ['action', 'reason', 'symbol', 'instance'],
    registry=REGISTRY
)

guardian_checks_total = Counter(
    'gridbot_guardian_checks_total',
    'Number of Guardian health checks',
    ['symbol', 'instance'],
    registry=REGISTRY
)

guardian_uptime_seconds = Gauge(
    'gridbot_guardian_uptime_seconds',
    'Guardian process uptime in seconds',
    ['symbol', 'instance'],
    registry=REGISTRY
)

# ============================================================================
# RISK METRICS
# ============================================================================

total_loss_inr = Gauge(
    'gridbot_total_loss_inr',
    'Total accumulated loss in INR',
    ['symbol', 'instance'],
    registry=REGISTRY
)

daily_loss_inr = Gauge(
    'gridbot_daily_loss_inr',
    'Daily loss in INR (resets at midnight)',
    ['symbol', 'instance'],
    registry=REGISTRY
)

liquidation_distance_percent = Gauge(
    'gridbot_liquidation_distance_percent',
    'Distance to liquidation price as percentage',
    ['symbol', 'instance'],
    registry=REGISTRY
)

margin_used_percent = Gauge(
    'gridbot_margin_used_percent',
    'Percentage of available margin used',
    ['symbol', 'instance'],
    registry=REGISTRY
)

drawdown_percent = Gauge(
    'gridbot_drawdown_percent',
    'Current drawdown from peak as percentage',
    ['symbol', 'instance'],
    registry=REGISTRY
)

# RSI metrics
rsi_value = Gauge(
    'gridbot_rsi_value',
    'Current RSI indicator value',
    ['symbol', 'timeframe'],
    registry=REGISTRY
)

rsi_trading_allowed = Gauge(
    'gridbot_rsi_trading_allowed',
    'RSI allows trading (1=yes, 0=no)',
    ['symbol', 'instance'],
    registry=REGISTRY
)

# ============================================================================
# API METRICS
# ============================================================================

api_call_duration_seconds = Histogram(
    'gridbot_api_call_duration_seconds',
    'API call duration in seconds',
    ['endpoint', 'method', 'status_code'],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
    registry=REGISTRY
)

api_calls_total = Counter(
    'gridbot_api_calls_total',
    'Total API calls made',
    ['endpoint', 'method', 'status_code'],
    registry=REGISTRY
)

api_rate_limit_hits = Counter(
    'gridbot_api_rate_limit_hits_total',
    'Number of rate limit hits (preemptive)',
    ['endpoint'],
    registry=REGISTRY
)

api_429_errors = Counter(
    'gridbot_api_429_errors_total',
    'Number of 429 rate limit errors received',
    ['endpoint'],
    registry=REGISTRY
)

api_errors_total = Counter(
    'gridbot_api_errors_total',
    'Total API errors',
    ['endpoint', 'error_type'],
    registry=REGISTRY
)

api_requests_in_flight = Gauge(
    'gridbot_api_requests_in_flight',
    'Current number of API requests in flight',
    registry=REGISTRY
)

# WebSocket metrics
websocket_connected = Gauge(
    'gridbot_websocket_connected',
    'WebSocket connection status (1=connected, 0=disconnected)',
    ['channel'],
    registry=REGISTRY
)

websocket_messages_received_total = Counter(
    'gridbot_websocket_messages_received_total',
    'Total WebSocket messages received',
    ['channel', 'message_type'],
    registry=REGISTRY
)

websocket_reconnects_total = Counter(
    'gridbot_websocket_reconnects_total',
    'Total WebSocket reconnection attempts',
    ['channel'],
    registry=REGISTRY
)

# ============================================================================
# RECOVERY METRICS
# ============================================================================

recovery_sessions_total = Counter(
    'gridbot_recovery_sessions_total',
    'Number of recovery sessions',
    ['engine', 'status', 'symbol', 'instance'],
    registry=REGISTRY
)

recovery_duration_seconds = Histogram(
    'gridbot_recovery_duration_seconds',
    'Recovery session duration',
    ['engine', 'symbol', 'instance'],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600],
    registry=REGISTRY
)

missed_grids_recovered_total = Counter(
    'gridbot_missed_grids_recovered_total',
    'Number of missed grid levels recovered',
    ['symbol', 'instance'],
    registry=REGISTRY
)

reconciliation_runs_total = Counter(
    'gridbot_reconciliation_runs_total',
    'Number of reconciliation runs',
    ['status', 'symbol', 'instance'],
    registry=REGISTRY
)

reconciliation_discrepancies_total = Counter(
    'gridbot_reconciliation_discrepancies_total',
    'Number of discrepancies found during reconciliation',
    ['type', 'symbol', 'instance'],
    registry=REGISTRY
)

# ============================================================================
# ANOMALY DETECTION METRICS
# ============================================================================

anomalies_detected_total = Counter(
    'gridbot_anomalies_detected_total',
    'Number of anomalies detected',
    ['category', 'severity', 'symbol', 'instance'],
    registry=REGISTRY
)

price_deviation_percent = Gauge(
    'gridbot_price_deviation_percent',
    'Price deviation from expected value as percentage',
    ['symbol', 'instance'],
    registry=REGISTRY
)

# ============================================================================
# OPTIONS TRADING METRICS
# ============================================================================

options_positions_count = Gauge(
    'gridbot_options_positions_count',
    'Number of open options positions',
    ['option_type', 'symbol'],  # option_type: call, put
    registry=REGISTRY
)

options_positions_value_usd = Gauge(
    'gridbot_options_positions_value_usd',
    'Total value of options positions in USD',
    ['option_type', 'symbol'],
    registry=REGISTRY
)

options_unrealized_pnl_usd = Gauge(
    'gridbot_options_unrealized_pnl_usd',
    'Options unrealized P&L in USD',
    ['option_type', 'symbol'],
    registry=REGISTRY
)

options_greeks = Gauge(
    'gridbot_options_greeks',
    'Options portfolio Greeks',
    ['greek', 'symbol'],  # greek: delta, gamma, theta, vega
    registry=REGISTRY
)

options_iv_percentile = Gauge(
    'gridbot_options_iv_percentile',
    'Implied volatility percentile (0-100)',
    ['symbol'],
    registry=REGISTRY
)

options_orders_total = Counter(
    'gridbot_options_orders_total',
    'Total options orders placed',
    ['side', 'option_type', 'symbol', 'status'],
    registry=REGISTRY
)

options_strategies_active = Gauge(
    'gridbot_options_strategies_active',
    'Number of active options strategies',
    ['strategy_type', 'symbol'],
    registry=REGISTRY
)

# ============================================================================
# WEBUI METRICS
# ============================================================================

webui_requests_total = Counter(
    'gridbot_webui_requests_total',
    'Total WebUI API requests',
    ['endpoint', 'method', 'status_code'],
    registry=REGISTRY
)

webui_request_duration_seconds = Histogram(
    'gridbot_webui_request_duration_seconds',
    'WebUI API request duration',
    ['endpoint', 'method'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
    registry=REGISTRY
)

webui_active_sessions = Gauge(
    'gridbot_webui_active_sessions',
    'Number of active WebUI sessions',
    registry=REGISTRY
)

# ============================================================================
# TELEGRAM METRICS
# ============================================================================

telegram_messages_sent_total = Counter(
    'gridbot_telegram_messages_sent_total',
    'Total Telegram messages sent',
    ['message_type'],  # alert, info, daily_report
    registry=REGISTRY
)

telegram_errors_total = Counter(
    'gridbot_telegram_errors_total',
    'Total Telegram errors',
    ['error_type'],
    registry=REGISTRY
)

# ============================================================================
# DATABASE METRICS
# ============================================================================

database_queries_total = Counter(
    'gridbot_database_queries_total',
    'Total database queries executed',
    ['query_type', 'table'],
    registry=REGISTRY
)

database_query_duration_seconds = Histogram(
    'gridbot_database_query_duration_seconds',
    'Database query duration',
    ['query_type'],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
    registry=REGISTRY
)

event_store_events_total = Counter(
    'gridbot_event_store_events_total',
    'Total events stored in event store',
    ['event_type', 'symbol', 'instance'],
    registry=REGISTRY
)
