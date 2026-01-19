"""
Pydantic models for type-safe YAML configuration.
Provides validation, type checking, and schema generation.
"""

from pydantic import BaseModel, Field, validator, root_validator
from enum import Enum
from typing import Optional, List, Dict, Any
from pathlib import Path


# ═══════════════════════════════════════════════════════════════════════════
# ENUMS - Define valid values for configuration options
# ═══════════════════════════════════════════════════════════════════════════

class TradingMode(str, Enum):
    """Trading environment"""
    DEMO = "demo"
    LIVE = "live"


class GridMode(str, Enum):
    """Grid trading direction"""
    LONG = "LONG"
    SHORT = "SHORT"
    BOTH = "BOTH"


class PostOnlyMode(str, Enum):
    """Post-only order mode"""
    OFF = "off"
    AUTO = "auto"
    ON = "on"


class RungSnapMode(str, Enum):
    """Grid level snapping behavior"""
    BELOW = "below"
    NEAREST = "nearest"
    ABOVE = "above"


class CancelScope(str, Enum):
    """Order cancellation scope"""
    TAGGED = "tagged"
    ALL = "all"


class HeartbeatAction(str, Enum):
    """Action to take when heartbeat fails"""
    CANCEL_BUY_ORDERS = "cancel_buy_orders"
    CANCEL_ALL_ORDERS = "cancel_all_orders"
    NOTIFY_ONLY = "notify_only"


class LogLevel(str, Enum):
    """Logging level"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class GapFillOrderType(str, Enum):
    """Order type for gap filling"""
    MAKER = "maker"
    TAKER = "taker"
    AUTO = "auto"


class EmergencyCloseOrderType(str, Enum):
    """Order type for emergency closes"""
    MARKET = "market"
    LIMIT = "limit"


# ═══════════════════════════════════════════════════════════════════════════
# BOT CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

class BotConfig(BaseModel):
    """Core bot trading configuration"""
    symbol: str = Field("BTCUSD", description="Trading symbol")
    mode: GridMode = Field(GridMode.LONG, description="Grid trading direction")
    trading_enabled: bool = Field(True, description="Enable/disable trading")
    heartbeat_seconds: int = Field(20, gt=0, le=300, description="Heartbeat interval")


# ═══════════════════════════════════════════════════════════════════════════
# GRID CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

class GridGeometry(BaseModel):
    """Grid price range and spacing"""
    lower: int = Field(90000, gt=0, description="Grid lower boundary")
    upper: int = Field(110000, gt=0, description="Grid upper boundary")
    step: int = Field(500, gt=0, le=10000, description="Grid step size")
    reference: int = Field(95500, gt=0, description="Reference price for starting")
    
    @validator('upper')
    def upper_must_exceed_lower(cls, v, values):
        if 'lower' in values and v <= values['lower']:
            raise ValueError(f"upper ({v}) must be > lower ({values['lower']})")
        return v
    
    @validator('reference')
    def reference_in_range(cls, v, values):
        if 'lower' in values and 'upper' in values:
            if not (values['lower'] <= v <= values['upper']):
                raise ValueError(f"reference ({v}) must be between lower ({values['lower']}) and upper ({values['upper']})")
        return v


class GridLimits(BaseModel):
    """Grid position and size limits"""
    max_open_positions: int = Field(10, gt=0, le=100, description="Max open positions")
    lot_size: int = Field(2, gt=0, description="Contracts per order (LONG mode)")
    short_lot_multiplier: float = Field(0.5, gt=0, le=1.0, description="SHORT lot size multiplier (0.5 = half of lot_size)")
    max_open_orders: int = Field(20, gt=0, description="Max open orders")
    max_qty_per_order: int = Field(1, gt=0, description="Max quantity per order")


class GridBehavior(BaseModel):
    """Grid behavior and strictness"""
    strict_grid: bool = Field(True, description="Enforce strict grid alignment")
    rung_snap_mode: RungSnapMode = Field(RungSnapMode.BELOW, description="How to snap to grid levels")
    tick_size: float = Field(0.5, gt=0, description="Price tick size")
    dynamic_tick_size: bool = Field(True, description="Use dynamic tick sizing")
    seed_initial_count: int = Field(0, ge=0, description="Number of orders to seed at startup")


class SmartGapFill(BaseModel):
    """Smart gap fill configuration"""
    enabled: bool = Field(False, description="Enable smart gap fill")
    order_type: GapFillOrderType = Field(GapFillOrderType.MAKER, description="Order type for gap fills")
    max_levels: int = Field(0, ge=0, le=20, description="Max gap levels to fill")


class GridConfig(BaseModel):
    """Complete grid configuration"""
    geometry: GridGeometry
    limits: GridLimits
    behavior: GridBehavior
    smart_gap_fill: SmartGapFill


# ═══════════════════════════════════════════════════════════════════════════
# CAPITAL PROTECTION
# ═══════════════════════════════════════════════════════════════════════════

class EquityFloor(BaseModel):
    """Equity floor protection"""
    enabled: bool = Field(True, description="Enable equity floor")
    floor_inr: int = Field(70000, gt=0, description="Minimum equity in INR")
    check_interval: int = Field(60, gt=0, le=3600, description="Check interval in seconds")
    require_acknowledgment: bool = Field(True, description="Require manual ack to resume")


class DrawdownCap(BaseModel):
    """Drawdown cap protection"""
    enabled: bool = Field(True, description="Enable drawdown cap")
    max_pct: float = Field(30.0, gt=0, le=100, description="Max drawdown percentage")
    window_days: int = Field(30, gt=0, le=365, description="Rolling window in days")
    hysteresis_pct: float = Field(15.0, ge=0, le=50, description="Hysteresis buffer")
    check_interval: int = Field(3600, gt=0, description="Check interval in seconds")


class TwoManRule(BaseModel):
    """Configuration change confirmation"""
    enabled: bool = Field(True, description="Enable two-man rule")
    timeout_seconds: int = Field(600, gt=0, description="Confirmation timeout")
    auto_revert: bool = Field(True, description="Auto-revert if not confirmed")


class ExposureGrowth(BaseModel):
    """Position accumulation rate limits"""
    enabled: bool = Field(True, description="Enable exposure growth limits")
    max_tranches_per_minute: int = Field(2, gt=0, description="Max new positions per minute")
    max_notional_inr_per_minute: int = Field(999999999, gt=0, description="Max notional per minute")
    queue_enabled: bool = Field(True, description="Queue excess orders")


class PendingBudget(BaseModel):
    """Pending order budget limits"""
    max_notional_inr: int = Field(2000000000000, gt=0, description="Max notional in pending orders")
    buffer_pct: float = Field(10.0, ge=0, le=100, description="Safety buffer percentage")


class CapitalProtection(BaseModel):
    """Complete capital protection configuration"""
    equity_floor: EquityFloor
    drawdown_cap: DrawdownCap
    two_man_rule: TwoManRule
    exposure_growth: ExposureGrowth
    pending_budget: PendingBudget
    
    # Backward compatibility for legacy code
    max_loss_inr: float = Field(10000.0, gt=0, description="Max account loss INR (backward compat)")


# ═══════════════════════════════════════════════════════════════════════════
# SAFETY SYSTEMS
# ═══════════════════════════════════════════════════════════════════════════

class FlashMoveGuard(BaseModel):
    """Flash move protection"""
    enabled: bool = Field(True, description="Enable flash move guard")
    threshold_pct: float = Field(0.75, gt=0, le=100, description="Price move threshold %")
    window_seconds: int = Field(30, gt=0, le=3600, description="Time window for detection")
    cooldown_seconds: int = Field(120, gt=0, description="Cooldown after trigger")


class SpreadGuard(BaseModel):
    """Spread explosion protection"""
    enabled: bool = Field(True, description="Enable spread guard")
    explosion_multiplier: float = Field(5.0, gt=1.0, le=100.0, description="Normal spread multiplier threshold")


class VolatilitySafety(BaseModel):
    """Volatility-based trading safety"""
    enabled: bool = Field(True, description="Enable volatility safety")
    max_iv: float = Field(55.0, gt=0, le=200, description="Max implied volatility %")
    max_rv: float = Field(60.0, gt=0, le=200, description="Max realized volatility %")
    max_spread: float = Field(15.0, gt=0, le=100, description="Max IV-RV spread %")
    check_interval: int = Field(300, gt=0, description="Check interval seconds")
    auto_resume: bool = Field(True, description="Auto-resume when safe")
    resume_buffer: float = Field(5.0, ge=0, le=50, description="Resume buffer %")
    
    # Real-Time Monitoring
    monitor_enabled: bool = Field(True, description="Enable real-time volatility monitoring")
    update_interval: int = Field(60, gt=0, le=3600, description="Update interval seconds")
    
    # Volatility Thresholds
    threshold_elevated: float = Field(40.0, gt=0, le=200, description="Elevated volatility threshold %")
    threshold_high: float = Field(60.0, gt=0, le=200, description="High volatility threshold %")
    threshold_extreme: float = Field(80.0, gt=0, le=200, description="Extreme volatility threshold %")
    halt_threshold: float = Field(100.0, gt=0, le=200, description="Halt trading threshold %")
    
    # Realized Volatility Configuration
    rv_window: int = Field(24, gt=0, le=168, description="RV calculation window (hours)")
    
    # Opportunistic Recovery Configuration
    opportunistic_recovery: 'OpportunisticRecoveryConfig' = Field(
        default_factory=lambda: OpportunisticRecoveryConfig(),
        description="Opportunistic recovery settings"
    )


class RecoveryConfig(BaseModel):
    """
    Standalone Recovery Engine Configuration (Nov 20, 2025).
    
    CRITICAL FIX: max_grids is now CONFIGURABLE (was hardcoded to 3).
    Can be adjusted via WebUI for different market conditions.
    """
    enabled: bool = Field(True, description="Enable recovery engine")
    max_grids: int = Field(3, gt=0, le=10, description="Max grids to recover (CONFIGURABLE)")
    cooldown_minutes: int = Field(60, gt=0, le=1440, description="Cooldown between recovery runs")
    execution_delay_seconds: int = Field(2, gt=0, le=10, description="Delay between recovery orders")


class OpportunisticRecoveryConfig(BaseModel):
    """
    DEPRECATED: Use RecoveryConfig instead.
    Kept for backward compatibility.
    """
    enabled: bool = Field(True, description="Enable opportunistic recovery")
    iv_threshold: float = Field(35.0, gt=0, le=100, description="Max implied volatility %")
    rv_threshold: float = Field(40.0, gt=0, le=100, description="Max realized volatility %")
    spread_threshold: float = Field(10.0, gt=0, le=1000, description="Bid-ask spread halt threshold INR")
    
    # Recovery Limits
    max_orders_volatility: int = Field(5, gt=0, le=20, description="Max orders per volatility recovery")
    max_orders_startup: int = Field(2, gt=0, le=10, description="Max orders per startup recovery")
    
    # Execution Settings
    execution_delay_ms: int = Field(300, gt=0, le=5000, description="Delay between recovery orders (ms)")
    min_profit_margin: float = Field(500.0, gt=0, description="Minimum profit margin required (INR)")
    cooldown_seconds: int = Field(60, gt=0, le=3600, description="Cooldown between recoveries (seconds)")


class CircuitBreaker(BaseModel):
    """API circuit breaker"""
    enabled: bool = Field(True, description="Enable circuit breaker")
    failure_threshold: int = Field(3, gt=0, description="Failures before opening")
    timeout_seconds: int = Field(60, gt=0, description="Timeout before retry")
    half_open_calls: int = Field(2, gt=0, description="Test calls in half-open state")


class ConfirmationGuard(BaseModel):
    """Order confirmation guard"""
    enabled: bool = Field(True, description="Enable confirmation guard")
    poll_interval: int = Field(10, gt=0, description="Poll interval seconds")
    chaos_threshold: int = Field(60, gt=0, description="Chaos threshold seconds")


class RSIConfig(BaseModel):
    """RSI-based trading safety (Layer 6)"""
    enabled: bool = Field(True, description="Enable RSI monitoring")
    period: int = Field(14, ge=2, le=50, description="RSI calculation period")
    overbought_threshold: float = Field(70.0, ge=50, le=100, description="RSI overbought threshold (legacy)")
    oversold_threshold: float = Field(30.0, ge=0, le=50, description="RSI oversold threshold (legacy)")
    long_threshold: float = Field(30.0, ge=0, le=100, description="LONG mode: STOP when RSI <= this value (oversold - market too weak)")
    short_threshold: float = Field(70.0, ge=0, le=100, description="SHORT mode: STOP when RSI >= this value (overbought - market too strong)")
    hysteresis_seconds: int = Field(60, ge=0, le=300, description="Hysteresis delay in seconds when RSI is exactly at threshold")
    timeframe: str = Field("1h", description="OHLCV timeframe for RSI calculation")
    check_interval: int = Field(300, ge=60, description="RSI check interval in seconds")
    cache_ttl: int = Field(60, ge=10, description="RSI cache TTL in seconds")


class SafetyConfig(BaseModel):
    """Complete safety configuration"""
    # Core Trading Controls
    execute_orders: bool = Field(True, description="Enable real order placement (dry-run if False)")
    live_acknowledgment: str = Field("", description="Must be 'YES' to trade in live mode")
    
    # Guardian Layer 3 & 4 Limits
    max_position_size: Optional[int] = Field(None, gt=0, description="Max total position size in contracts")
    min_liquidation_distance_pct: Optional[float] = Field(None, gt=0, description="Min liquidation distance percentage")
    
    # Safety Modules
    flash_move: FlashMoveGuard
    spread_guard: SpreadGuard
    volatility: VolatilitySafety
    circuit_breaker: CircuitBreaker
    confirmation_guard: ConfirmationGuard
    rsi: Optional[RSIConfig] = Field(None, description="RSI monitoring configuration (Layer 6)")


# ═══════════════════════════════════════════════════════════════════════════
# GUARDIAN BOT
# ═══════════════════════════════════════════════════════════════════════════

class HealthCheckConfig(BaseModel):
    """Guardian Layer 5 health monitoring configuration"""
    enabled: bool = Field(True, description="Enable system health monitoring")
    api_timeout_seconds: int = Field(30, gt=0, description="API timeout threshold")
    websocket_timeout_seconds: int = Field(60, gt=0, description="WebSocket timeout threshold")
    data_stale_threshold_seconds: int = Field(120, gt=0, description="Data stale threshold")


class GuardianConfig(BaseModel):
    """Guardian bot configuration"""
    enabled: bool = Field(True, description="Enable guardian bot")
    check_interval: int = Field(10, gt=0, le=300, description="Check interval seconds")
    max_account_loss_inr: int = Field(5000, gt=0, description="Max account loss in INR")
    usd_to_inr_rate: float = Field(85.0, gt=0, description="USD to INR conversion rate")
    liquidation_critical: float = Field(0.01, gt=0, le=1.0, description="Critical liquidation distance")
    auto_close_positions: bool = Field(True, description="Auto-close on emergency")
    close_order_type: EmergencyCloseOrderType = Field(EmergencyCloseOrderType.MARKET, description="Emergency close order type")
    cancel_orders_on_emergency: bool = Field(True, description="Cancel orders on emergency")
    alert_threshold_80: bool = Field(True, description="Alert at 80% threshold")
    alert_threshold_90: bool = Field(True, description="Alert at 90% threshold")
    daily_summary: bool = Field(True, description="Send daily summary")
    cooldown: int = Field(60, gt=0, description="Cooldown between actions")
    
    # Layer 5: Health monitoring
    health_check: Optional[HealthCheckConfig] = Field(None, description="Health check configuration")
    
    # Hysteresis Configuration
    hysteresis_80_trigger: float = Field(80.0, gt=0, description="80% alert trigger threshold (can exceed 100%)")
    hysteresis_80_reset: float = Field(75.0, gt=0, description="80% alert reset threshold (can exceed 100%)")
    hysteresis_90_trigger: float = Field(90.0, gt=0, description="90% alert trigger threshold (can exceed 100%)")
    hysteresis_90_reset: float = Field(85.0, gt=0, description="90% alert reset threshold (can exceed 100%)")
    hysteresis_100_trigger: float = Field(100.0, gt=0, description="100% alert trigger threshold (can exceed 100%)")
    hysteresis_100_reset: float = Field(95.0, gt=0, description="100% alert reset threshold (can exceed 100%)")
    
    # File Paths
    bot_log: str = Field("logs/guardian.log", description="Guardian log file path")
    pid_file: str = Field(".guardian.pid", description="PID file path")
    health_file: str = Field(".guardian_health", description="Health status file")
    emergency_flag: str = Field(".guardian_emergency_stop", description="Emergency stop flag file")
    
    # Logging Configuration
    log_file: bool = Field(True, description="Enable file logging")
    log_level: LogLevel = Field(LogLevel.INFO, description="Guardian log level")
    
    # Auto Margin Management
    auto_margin_topup: bool = Field(False, description="Enable auto margin top-up")
    auto_topup_amount_inr: int = Field(1000, gt=0, description="Auto top-up amount INR")
    max_loss: int = Field(3000, gt=0, description="Max allowed loss INR")


# ═══════════════════════════════════════════════════════════════════════════
# LIQUIDATION PROTECTION
# ═══════════════════════════════════════════════════════════════════════════

class LiquidationProtection(BaseModel):
    """Liquidation monitoring and protection"""
    enabled: bool = Field(True, description="Enable liquidation protection")
    margin_utilization_max: float = Field(40.0, gt=0, description="Max margin utilization % (can exceed 100% in cross margin)")
    margin_utilization_warning_1: float = Field(50.0, gt=0, description="Warning threshold 1 (can exceed 100%)")
    margin_utilization_warning_2: float = Field(70.0, gt=0, description="Warning threshold 2 (can exceed 100%)")
    margin_emergency_reserve: float = Field(60.0, gt=0, le=100, description="Emergency reserve %")
    reduce_only_at_utilization: float = Field(200.0, gt=0, description="Enter reduce-only mode at % (can exceed 100%)")
    liquidation_distance_min: float = Field(60.0, gt=0, description="Min distance from liquidation %")
    liquidation_distance_target: float = Field(70.0, gt=0, description="Target distance %")
    liquidation_distance_critical: float = Field(50.0, gt=0, description="Critical distance %")
    real_time_monitoring: bool = Field(True, description="Enable real-time monitoring")
    websocket_margin_updates: bool = Field(True, description="Subscribe to margin WebSocket")
    websocket_portfolio_updates: bool = Field(True, description="Subscribe to portfolio WebSocket")
    margin_utilization_critical: float = Field(80.0, gt=0, description="Critical utilization threshold (can exceed 100%)")
    margin_utilization_warning: float = Field(60.0, gt=0, description="Warning utilization threshold (can exceed 100%)")
    liquidation_distance_warning: float = Field(10.0, gt=0, description="Warning distance threshold")
    auto_margin_topup: bool = Field(False, description="Auto top-up margin")
    auto_topup_amount_inr: int = Field(1000, gt=0, description="Auto top-up amount")
    
    # MTM (Mark-to-Market) Monitoring
    mtm_monitoring_enabled: bool = Field(True, description="Enable MTM monitoring")
    mtm_check_interval: int = Field(2, gt=0, le=300, description="MTM check interval seconds")
    mtm_alert_threshold: int = Field(-1000, description="MTM alert threshold INR")
    mtm_critical_threshold: int = Field(-3000, description="MTM critical threshold INR")
    
    # WebSocket Subscriptions
    mark_price_websocket_enabled: bool = Field(True, description="Subscribe to mark price WebSocket")
    portfolio_margin_websocket_enabled: bool = Field(True, description="Subscribe to portfolio margin WebSocket")
    positions_websocket_enabled: bool = Field(True, description="Subscribe to positions WebSocket")
    
    # ADL (Auto-Deleveraging) Protection
    adl_monitoring_enabled: bool = Field(True, description="Monitor ADL queue rank")
    adl_warning_level: int = Field(4, ge=1, le=5, description="ADL warning level (1-5)")
    adl_auto_reduce_level: int = Field(5, ge=1, le=5, description="ADL auto-reduce level")
    adl_reduce_percentage: float = Field(30.0, gt=0, le=100, description="ADL reduce percentage")
    
    # Funding Rate Monitoring
    funding_rate_monitoring: bool = Field(True, description="Monitor funding rates")
    funding_rate_alert_threshold: float = Field(0.5, gt=0, description="Funding rate alert threshold %")
    funding_rate_critical_threshold: float = Field(1.0, gt=0, description="Funding rate critical threshold %")
    funding_pre_payment_check: bool = Field(True, description="Check funding before payment")
    funding_pre_payment_minutes: int = Field(60, gt=0, description="Minutes before funding payment to check")
    
    # Alert Configuration
    liquidation_alert_telegram: bool = Field(True, description="Send Telegram alerts")
    liquidation_alert_sound: bool = Field(True, description="Play sound alerts")
    liquidation_alert_email: bool = Field(False, description="Send email alerts")
    liquidation_alert_throttle: int = Field(3600, gt=0, description="Alert throttle seconds")
    liquidation_check_interval: int = Field(5, gt=0, description="Liquidation check interval seconds")
    liquidation_distance_check_interval: bool = Field(True, description="Enable distance check interval")
    liquidation_log_level: LogLevel = Field(LogLevel.INFO, description="Liquidation log level")
    
    # Auto Actions
    auto_reduce_positions_enabled: bool = Field(False, description="Auto-reduce positions on high utilization")
    auto_reduce_at_utilization: float = Field(80.0, gt=0, description="Auto-reduce trigger utilization % (can exceed 100%)")
    auto_reduce_percentage: float = Field(30.0, gt=0, le=100, description="Auto-reduce position percentage")
    auto_add_margin_enabled: bool = Field(False, description="Auto-add margin when needed")
    auto_margin_topup_enabled: bool = Field(False, description="Auto top-up margin")
    auto_topup_threshold: float = Field(60.0, gt=0, description="Auto top-up trigger threshold % (can exceed 100%)")
    auto_topup_target: float = Field(90.0, gt=0, description="Auto top-up target % (can exceed 100%)")
    max_topups_per_position: int = Field(3, gt=0, description="Max top-ups per position")
    min_balance_reserve_percent: float = Field(20.0, gt=0, le=100, description="Min balance reserve %")
    
    # Emergency Actions
    emergency_close_all_at_utilization: float = Field(90.0, gt=0, description="Emergency close all at utilization % (can exceed 100%)")
    emergency_close_all_at_distance: float = Field(30.0, gt=0, description="Emergency close all at distance %")
    emergency_close_percentage: float = Field(100.0, gt=0, le=100, description="Emergency close percentage")
    emergency_cancel_all_orders: bool = Field(True, description="Cancel all orders in emergency")
    auto_emergency_on_websocket_alert: bool = Field(False, description="Auto-emergency on WebSocket alert")
    auto_cancel_orders_at_yellow: bool = Field(True, description="Auto-cancel orders at yellow threshold")
    
    # Dynamic Margin Management
    dynamic_utilization_enabled: bool = Field(False, description="Enable dynamic utilization management")
    dynamic_utilization_mtm_threshold: float = Field(20.0, gt=0, description="MTM threshold for dynamic adjustment")
    dynamic_utilization_reduction: float = Field(10.0, gt=0, le=100, description="Utilization reduction %")
    dynamic_utilization_volatility_factor: bool = Field(True, description="Apply volatility factor")
    
    # Margin Thresholds
    margin_warning_threshold: float = Field(80.0, gt=0, description="Margin warning threshold % (can exceed 100%)")
    margin_danger_threshold: float = Field(50.0, gt=0, description="Margin danger threshold % (can exceed 100%)")
    margin_critical_threshold: float = Field(20.0, gt=0, description="Margin critical threshold % (can exceed 100%)")
    maintenance_margin_percent: float = Field(2.5, gt=0, le=100, description="Maintenance margin percentage")
    
    # Distance to Liquidation
    distance_to_liq_warning: float = Field(3.0, gt=0, description="Distance to liquidation warning %")


# ═══════════════════════════════════════════════════════════════════════════
# STARTUP & SHUTDOWN
# ═══════════════════════════════════════════════════════════════════════════

class StartupBehavior(BaseModel):
    """Bot startup behavior"""
    sync_duration: int = Field(60, ge=0, description="Sync duration at startup (seconds)")
    strict_start: bool = Field(True, description="Use strict start mode")
    forget_exchange_on_start: bool = Field(True, description="Forget existing exchange orders")
    enable_smart_recovery: bool = Field(True, description="Enable smart position recovery")
    cancel_all_on_start: bool = Field(False, description="Cancel all orders on start")
    cancel_scope: CancelScope = Field(CancelScope.TAGGED, description="Order cancellation scope")


class ShutdownBehavior(BaseModel):
    """Bot shutdown behavior"""
    shutdown_duration: int = Field(60, ge=0, description="Graceful shutdown duration (seconds)")
    cancel_buy_orders: bool = Field(True, description="Cancel BUY orders on shutdown")
    keep_tp_orders: bool = Field(True, description="Keep TP orders on shutdown")


# ═══════════════════════════════════════════════════════════════════════════
# ORDER EXECUTION
# ═══════════════════════════════════════════════════════════════════════════

class OrderExecution(BaseModel):
    """Order execution configuration"""
    post_only_mode: PostOnlyMode = Field(PostOnlyMode.AUTO, description="Post-only mode")
    price_buffer_pct: float = Field(0.1, ge=0, le=10, description="Price buffer for post-only %")
    fill_threshold: float = Field(0.98, gt=0, le=1.0, description="Fill confirmation threshold")
    max_retries: int = Field(3, gt=0, le=10, description="Max retry attempts")
    retry_delay: float = Field(2.0, gt=0, le=60, description="Retry delay seconds")
    cooldown_seconds: int = Field(30, gt=0, le=300, description="Cooldown between orders")
    tag_prefix: str = Field("GBOT_", description="Order tag prefix")
    adopt_untagged: bool = Field(False, description="Adopt untagged orders")


# ═══════════════════════════════════════════════════════════════════════════
# HEARTBEAT & MONITORING
# ═══════════════════════════════════════════════════════════════════════════

class Heartbeat(BaseModel):
    """Heartbeat / dead man's switch"""
    enabled: bool = Field(True, description="Enable heartbeat")
    timeout: int = Field(15, gt=0, description="Heartbeat timeout seconds")
    update_interval: int = Field(5, gt=0, description="Update interval seconds")
    monitor_interval: int = Field(10, gt=0, description="Monitor check interval")
    file: str = Field(".heartbeat", description="Heartbeat file path")
    action: HeartbeatAction = Field(HeartbeatAction.CANCEL_BUY_ORDERS, description="Action on failure")


class HealthCheck(BaseModel):
    """Health check configuration"""
    enabled: bool = Field(True, description="Enable health checks")
    interval: int = Field(300, gt=0, description="Check interval seconds")


class PerformanceLogging(BaseModel):
    """Performance logging configuration"""
    enabled: bool = Field(True, description="Enable performance logging")
    interval: int = Field(3600, gt=0, description="Log interval seconds")


# ═══════════════════════════════════════════════════════════════════════════
# API CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

class APIDemo(BaseModel):
    """Demo API configuration"""
    public_url: str = Field("https://cdn-ind.testnet.deltaex.org", description="Demo public API URL")
    private_url: str = Field("https://cdn-ind.testnet.deltaex.org", description="Demo private API URL")
    websocket_url: str = Field("wss://testnet-api.delta.exchange", description="Demo WebSocket URL")
    base_url: str = Field("https://testnet-api.delta.exchange", description="Demo base API URL")
    product_id: int = Field(27, description="Demo product ID")
    testnet: bool = Field(True, description="Is testnet")


class APILive(BaseModel):
    """Live API configuration"""
    public_url: str = Field("https://api.india.delta.exchange", description="Live public API URL")
    private_url: str = Field("https://api.india.delta.exchange", description="Live private API URL")
    websocket_url: str = Field("wss://socket.india.delta.exchange", description="Live WebSocket URL")
    base_url: str = Field("https://api.india.delta.exchange", description="Live base API URL")
    product_id: int = Field(139, description="Live product ID")
    testnet: bool = Field(False, description="Is testnet")


class APICredentials(BaseModel):
    """API credentials configuration"""
    use_env: bool = Field(True, description="Load credentials from environment")


class APIEndpoints(BaseModel):
    """API endpoint configuration"""
    demo: APIDemo = Field(default_factory=APIDemo, description="Demo API settings")
    live: APILive = Field(default_factory=APILive, description="Live API settings")
    credentials: APICredentials = Field(default_factory=APICredentials, description="Credential settings")
    reference_level: float = Field(109800, description="Default reference price level")
    
    # Legacy compatibility fields
    @property
    def demo_public_url(self) -> str:
        return self.demo.public_url
    
    @property
    def demo_private_url(self) -> str:
        return self.demo.private_url
    
    @property
    def demo_ws_url(self) -> str:
        return self.demo.websocket_url
    
    @property
    def live_public_url(self) -> str:
        return self.live.public_url
    
    @property
    def live_private_url(self) -> str:
        return self.live.private_url
    
    @property
    def live_ws_url(self) -> str:
        return self.live.websocket_url


# ═══════════════════════════════════════════════════════════════════════════
# REFACTOR COMPATIBILITY
# ═══════════════════════════════════════════════════════════════════════════

class RefactorCompat(BaseModel):
    """Refactor compatibility layer configuration"""
    enabled: bool = Field(True, description="Enable compatibility layer")
    warn_threshold: int = Field(1, description="Warning after N accesses")
    fail_threshold: int = Field(2, description="Error after N accesses")


# ═══════════════════════════════════════════════════════════════════════════
# TELEGRAM NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════════════════

class TelegramConfig(BaseModel):
    """Telegram notification configuration"""
    enabled: bool = Field(True, description="Enable Telegram notifications")
    bot_token: Optional[str] = Field(None, description="Telegram bot token")
    chat_id: Optional[str] = Field(None, description="Telegram chat ID")
    live_bot_token: Optional[str] = Field(None, description="Live mode bot token")
    live_chat_id: Optional[str] = Field(None, description="Live mode chat ID")
    demo_bot_token: Optional[str] = Field(None, description="Demo mode bot token")
    demo_chat_id: Optional[str] = Field(None, description="Demo mode chat ID")
    # Options trading bot (separate from grid/guardian)
    options_bot_token: Optional[str] = Field(None, description="Options trading bot token")
    options_chat_id: Optional[str] = Field(None, description="Options trading chat ID")


# ═══════════════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════════════

class LoggingConfig(BaseModel):
    """Logging configuration"""
    level: LogLevel = Field(LogLevel.INFO, description="Log level")
    format: str = Field("%(asctime)s - %(name)s - %(levelname)s - %(message)s", description="Log format")
    guardian_log_file: str = Field("guardian.log", description="Guardian bot log file")
    guardian_log_level: LogLevel = Field(LogLevel.INFO, description="Guardian log level")


# ═══════════════════════════════════════════════════════════════════════════
# RISK LIMITS
# ═══════════════════════════════════════════════════════════════════════════

class RiskLimits(BaseModel):
    """Risk limits and safety thresholds"""
    max_account_loss_inr: int = Field(25000, gt=0, description="Max account loss in INR")
    usd_to_inr_rate: float = Field(85.0, gt=0, description="USD to INR conversion rate")
    max_drift_alerts: int = Field(10, gt=0, description="Max drift alerts")
    max_disruption_events: int = Field(5, gt=0, description="Max disruption events")
    emergency_price_buffer: float = Field(0.2, gt=0, description="Emergency price buffer")
    market_disruption_cooldown: int = Field(300, gt=0, description="Market disruption cooldown seconds")


# ═══════════════════════════════════════════════════════════════════════════
# EXECUTION SAFETY
# ═══════════════════════════════════════════════════════════════════════════

class ExecutionSafety(BaseModel):
    """Execution safety confirmation"""
    i_understand_live: str = Field("NO", description="Live trading acknowledgment (YES/NO)")
    execute_orders: bool = Field(False, description="Actually execute orders")
    require_live_password: bool = Field(True, description="Require password for live trading")
    live_trading_password: Optional[str] = Field(None, description="Live trading password")
    allow_destructive_fixes: bool = Field(False, description="Allow destructive fixes")
    
    @validator('execute_orders')
    def validate_execution(cls, v, values):
        """Prevent accidental live trading"""
        if v and values.get('i_understand_live') != 'YES':
            raise ValueError("Cannot enable execute_orders without setting i_understand_live=YES")
        return v


# ═══════════════════════════════════════════════════════════════════════════
# WEBUI CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

class FlaskConfig(BaseModel):
    """Flask server configuration"""
    debug: bool = Field(False, description="Flask debug mode")
    host: str = Field("127.0.0.1", description="Flask server host")
    port: int = Field(5001, gt=1000, le=65535, description="Flask backend port")
    env: str = Field("production", description="Flask environment")


class ErrorsConfig(BaseModel):
    """Error collection configuration"""
    collector_enabled: bool = Field(True, description="Enable error collector")
    db_path: str = Field("data/errors.db", description="Error database path")
    rate_limit_window: int = Field(60, gt=0, description="Rate limit window (seconds)")
    rate_limit_max: int = Field(100, gt=0, description="Max errors per window")
    burst_threshold: int = Field(10, gt=0, description="Burst detection threshold")
    allow_destructive: bool = Field(False, description="Allow destructive fixes")
    push_websocket: bool = Field(True, description="Push errors via WebSocket")


class LogsConfig(BaseModel):
    """Log file paths"""
    trading_bot: str = Field("bot.log", description="Trading bot log file")
    guardian_bot: str = Field("logs/guardian.log", description="Guardian bot log file")
    health_bot: str = Field("logs/health.log", description="Health bot log file")


class AuthConfig(BaseModel):
    """WebUI authentication configuration"""
    enabled: bool = Field(False, description="Enable authentication")
    user: str = Field("admin", description="Admin username")
    # Note: password should be in secrets/.env for security


class PM2Config(BaseModel):
    """PM2 process manager configuration"""
    enabled: bool = Field(False, description="Enable PM2 integration")


class URLConfig(BaseModel):
    """WebUI URL configuration"""
    default: str = Field("http://localhost:5555", description="Default WebUI URL")


class WebUIConfig(BaseModel):
    """Web UI configuration"""
    enabled: bool = Field(True, description="Enable Web UI")
    port: int = Field(5555, gt=1000, le=65535, description="Web UI port")
    allowed_origins: str = Field(
        "http://localhost:*,http://127.0.0.1:*,http://100.107.230.67:*,http://mymac.tail289dc3.ts.net:*,http://*.ts.net:*,http://100.*.*.*:*",
        description="Allowed CORS origins"
    )
    auth_enabled: bool = Field(False, description="Enable authentication")
    flask: FlaskConfig = Field(default_factory=FlaskConfig, description="Flask configuration")
    errors: ErrorsConfig = Field(default_factory=ErrorsConfig, description="Error management")
    logs: LogsConfig = Field(default_factory=LogsConfig, description="Log file paths")
    auth: AuthConfig = Field(default_factory=AuthConfig, description="Authentication settings")
    pm2: PM2Config = Field(default_factory=PM2Config, description="PM2 configuration")
    url: URLConfig = Field(default_factory=URLConfig, description="URL configuration")


# ═══════════════════════════════════════════════════════════════════════════
# RISK ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════

class RiskAnalyticsConfig(BaseModel):
    """Risk analytics configuration"""
    enabled: bool = Field(True, description="Enable risk analytics")
    cache_ttl: int = Field(60, gt=0, le=3600, description="Cache TTL seconds")


# ═══════════════════════════════════════════════════════════════════════════
# IP MONITORING
# ═══════════════════════════════════════════════════════════════════════════

class IPMonitorConfig(BaseModel):
    """IP monitoring configuration"""
    enabled: bool = Field(True, description="Enable IP monitoring")
    interval: int = Field(300, gt=0, le=3600, description="Check interval seconds")


# ═══════════════════════════════════════════════════════════════════════════
# HOT RELOAD
# ═══════════════════════════════════════════════════════════════════════════

class HotReloadConfig(BaseModel):
    """Hot reload configuration"""
    enabled: bool = Field(True, description="Enable hot reload")


# ═══════════════════════════════════════════════════════════════════════════
# PM2 CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

class PM2DetailedConfig(BaseModel):
    """Detailed PM2 configuration"""
    enabled: bool = Field(True, description="Enable PM2 integration")


# ═══════════════════════════════════════════════════════════════════════════
# EMERGENCY CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

class EmergencyConfig(BaseModel):
    """Emergency stop configuration"""
    price_buffer: float = Field(0.2, gt=0, le=1.0, description="Emergency price buffer")


# ═══════════════════════════════════════════════════════════════════════════
# WEBSOCKET CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

class WebSocketConfig(BaseModel):
    """WebSocket configuration"""
    heartbeat_interval: int = Field(30, gt=0, le=300, description="Heartbeat interval seconds")
    timeout: int = Field(30, gt=0, le=300, description="WebSocket timeout seconds")
    reconnect_delay: int = Field(5, gt=0, le=60, description="Reconnect delay seconds")
    reconnect_interval: int = Field(5, gt=0, le=60, description="Reconnect interval seconds")
    max_reconnect_attempts: int = Field(100, gt=0, description="Max reconnection attempts")
    
    # Exponential Backoff Configuration
    base_reconnect_delay: float = Field(1.0, gt=0, le=60, description="Base reconnect delay seconds")
    max_reconnect_delay: float = Field(60.0, gt=0, description="Max reconnect delay seconds")
    jitter_ratio: float = Field(0.20, ge=0, le=1.0, description="Jitter ratio for reconnect delay")
    
    # Connection Timeouts
    connection_timeout: int = Field(15, gt=0, le=120, description="Connection timeout seconds")
    auth_timeout: int = Field(10, gt=0, le=60, description="Authentication timeout seconds")
    
    # Health Monitoring
    dead_threshold: int = Field(35, gt=0, le=300, description="Dead connection threshold seconds")
    quiet_ping_at: int = Field(30, gt=0, le=300, description="Send quiet ping at seconds")
    
    # Debug Mode
    debug_mode: bool = Field(False, description="Enable WebSocket debug logging")


# ═══════════════════════════════════════════════════════════════════════════
# ALERT THROTTLING
# ═══════════════════════════════════════════════════════════════════════════

class AlertThrottleConfig(BaseModel):
    """Alert throttling configuration"""
    green: int = Field(0, ge=0, description="Green alert throttle seconds (0 = no throttle)")
    yellow: int = Field(3600, ge=0, description="Yellow alert throttle seconds")
    orange: int = Field(3600, ge=0, description="Orange alert throttle seconds")
    red: int = Field(0, ge=0, description="Red alert throttle seconds (0 = no throttle)")


# ═══════════════════════════════════════════════════════════════════════════
# STRATEGY OVERRIDE (for multi-strategy)
# ═══════════════════════════════════════════════════════════════════════════

class StrategyOverride(BaseModel):
    """Strategy-specific overrides"""
    name: str = Field(..., description="Strategy name")
    description: Optional[str] = Field(None, description="Strategy description")
    extends: Optional[str] = Field(None, description="Inherit from base strategy")
    overrides: Dict[str, Any] = Field(default_factory=dict, description="Configuration overrides")
    enabled: bool = Field(True, description="Strategy enabled")


# ═══════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════
# MONITORING SYSTEM CONFIGURATION (Nov 19, 2025)
# ═══════════════════════════════════════════════════════════════════════════

class FillMonitorConfig(BaseModel):
    """Fill monitor configuration (Phase 1)"""
    enabled: bool = Field(True, description="Enable fill monitor")
    check_interval: int = Field(30, gt=0, le=300, description="Check interval in seconds")
    verification_delay: int = Field(30, gt=0, le=300, description="Delay before first verification")
    max_age: int = Field(86400, gt=0, description="Max age for tracked orders")


class DualChannelConfig(BaseModel):
    """Dual-channel monitor configuration (Phase 2)"""
    enabled: bool = Field(False, description="Enable dual-channel monitoring")
    rest_poll_interval: int = Field(10, gt=0, le=60, description="REST poll interval in seconds")
    max_fill_history: int = Field(1000, gt=0, description="Max fills to track")
    alert_on_websocket_miss: bool = Field(True, description="Alert when WebSocket misses fill")


class OrderTrackerConfig(BaseModel):
    """Order tracker configuration (Phase 2)"""
    enabled: bool = Field(False, description="Enable order tracker")
    pending_timeout: int = Field(86400, gt=0, description="Pending order timeout in seconds")
    fill_timeout: int = Field(10, gt=0, description="Fill timeout in seconds")
    check_interval: int = Field(30, gt=0, le=300, description="Check interval in seconds")
    alert_on_timeout: bool = Field(True, description="Alert on timeout")


class StateComparatorConfig(BaseModel):
    """State comparator configuration (Phase 3)"""
    enabled: bool = Field(False, description="Enable state comparator")
    check_interval: int = Field(60, gt=0, le=300, description="Check interval in seconds")
    auto_reconcile: bool = Field(True, description="Auto-reconcile discrepancies")
    alert_threshold: int = Field(3, gt=0, description="Alert after N discrepancies")


class EnhancedReconciliationConfig(BaseModel):
    """Enhanced reconciliation configuration (Phase 3)"""
    enabled: bool = Field(False, description="Enable enhanced reconciliation")
    check_interval: int = Field(120, gt=0, le=600, description="Check interval in seconds")
    alert_on_issue: bool = Field(True, description="Alert on issue detected")


class HeartbeatConfig(BaseModel):
    """Heartbeat monitor configuration"""
    enabled: bool = Field(True, description="Enable heartbeat monitor")
    file: str = Field(".heartbeat", description="Heartbeat file path")
    timeout: int = Field(60, gt=0, le=300, description="Heartbeat timeout in seconds")
    check_interval: int = Field(10, gt=0, le=60, description="Check interval in seconds")
    action: str = Field("cancel_buy_orders", description="Action on timeout (cancel_buy_orders, cancel_all_orders, notify_only)")


class MonitoringConfig(BaseModel):
    """Complete monitoring system configuration"""
    heartbeat: HeartbeatConfig = Field(default_factory=HeartbeatConfig)
    fill_monitor: FillMonitorConfig = Field(default_factory=FillMonitorConfig)
    dual_channel: DualChannelConfig = Field(default_factory=DualChannelConfig)
    order_tracker: OrderTrackerConfig = Field(default_factory=OrderTrackerConfig)
    state_comparator: StateComparatorConfig = Field(default_factory=StateComparatorConfig)
    enhanced_reconciliation: EnhancedReconciliationConfig = Field(default_factory=EnhancedReconciliationConfig)


# ═══════════════════════════════════════════════════════════════════════════
# RECOVERY SYSTEM CONFIGURATION (Nov 20, 2025)
# ═══════════════════════════════════════════════════════════════════════════

class RecoveryConfig(BaseModel):
    """Recovery engine configuration"""
    enabled: bool = Field(True, description="Enable recovery system")
    max_retries: int = Field(3, gt=0, le=10, description="Max retries per grid")
    retry_delay: int = Field(5, gt=0, le=60, description="Delay between retries (seconds)")
    recovery_cooldown: int = Field(300, gt=0, description="Cooldown between sessions (seconds)")
    recovery_failure_threshold: int = Field(3, gt=0, description="Circuit breaker failure threshold")
    recovery_circuit_timeout: int = Field(60, gt=0, description="Circuit breaker timeout (seconds)")
    recovery_max_concurrent: int = Field(5, gt=0, description="Max concurrent recoveries")
    recovery_rate_limit: float = Field(0.5, gt=0, description="Recovery rate limit (orders/sec)")


# ═══════════════════════════════════════════════════════════════════════════
# EXCHANGE MAINTENANCE PROTECTION (Dec 23, 2025)
# ═══════════════════════════════════════════════════════════════════════════

class FillMonitorMaintenanceConfig(BaseModel):
    """Fill monitor for exchange maintenance protection"""
    enabled: bool = Field(True, description="Enable fill monitor")
    check_interval: int = Field(30, gt=0, le=300, description="Check interval in seconds")
    max_detection_delay: int = Field(60, gt=0, le=600, description="Max acceptable detection delay")


class PostOrderVerificationConfig(BaseModel):
    """Post-order verification for immediate fill detection"""
    enabled: bool = Field(True, description="Enable post-order verification")
    initial_delay: int = Field(1, gt=0, le=10, description="Initial delay before first check (seconds)")
    retry_count: int = Field(3, gt=0, le=10, description="Number of retries")
    retry_interval: int = Field(2, gt=0, le=30, description="Interval between retries (seconds)")


class ExchangeStateDetectionConfig(BaseModel):
    """Exchange maintenance state detection"""
    enabled: bool = Field(True, description="Enable exchange state detection")
    maintenance_poll_interval: int = Field(60, gt=0, le=300, description="Maintenance detection poll interval")
    post_maintenance_sync_delay: int = Field(10, gt=0, le=120, description="Delay before sync after maintenance")
    require_grid_coverage: bool = Field(True, description="Require grid coverage during sync")


class ExchangeMaintenanceConfig(BaseModel):
    """Complete exchange maintenance protection configuration"""
    fill_monitor: FillMonitorMaintenanceConfig = Field(default_factory=FillMonitorMaintenanceConfig)
    post_order_verification: PostOrderVerificationConfig = Field(default_factory=PostOrderVerificationConfig)
    exchange_state_detection: ExchangeStateDetectionConfig = Field(default_factory=ExchangeStateDetectionConfig)


# ═══════════════════════════════════════════════════════════════════════════
# MULTI-INSTANCE SUPPORT (v6.0) - Instance = Symbol + Mode
# ═══════════════════════════════════════════════════════════════════════════

class InstanceRSIConfig(BaseModel):
    """Per-instance RSI thresholds
    
    CRITICAL: LONG and SHORT modes have OPPOSITE RSI logic:
    - LONG mode: Stop when RSI <= stop_threshold (oversold = market too weak to buy)
    - SHORT mode: Stop when RSI >= stop_threshold (overbought = market too strong to short)
    """
    enabled: bool = Field(True, description="Enable RSI monitoring for this instance")
    period: int = Field(14, ge=2, le=50, description="RSI calculation period")
    stop_threshold: float = Field(
        description="RSI threshold to stop trading. "
        "LONG: stop when RSI <= this (default 30). "
        "SHORT: stop when RSI >= this (default 70)."
    )
    resume_threshold: float = Field(
        description="RSI threshold to resume trading. "
        "LONG: resume when RSI >= this (default 40). "
        "SHORT: resume when RSI <= this (default 60)."
    )
    hysteresis_seconds: int = Field(60, ge=0, le=300, description="Delay when RSI at threshold")
    timeframe: str = Field("1h", description="OHLCV timeframe for RSI")
    check_interval: int = Field(300, ge=60, description="RSI check interval seconds")
    
    @classmethod
    def for_long_mode(cls) -> "InstanceRSIConfig":
        """Create RSI config for LONG mode (stop at oversold)"""
        return cls(
            enabled=True,
            stop_threshold=30.0,  # Stop when RSI <= 30 (oversold)
            resume_threshold=40.0  # Resume when RSI >= 40
        )
    
    @classmethod
    def for_short_mode(cls) -> "InstanceRSIConfig":
        """Create RSI config for SHORT mode (stop at overbought)"""
        return cls(
            enabled=True,
            stop_threshold=70.0,  # Stop when RSI >= 70 (overbought)
            resume_threshold=60.0  # Resume when RSI <= 60
        )


class InstanceSafetyConfig(BaseModel):
    """Per-instance safety configuration"""
    max_account_loss_inr: float = Field(gt=0, description="Maximum account loss for this instance in INR")
    min_liquidation_distance_pct: float = Field(gt=0, description="Minimum liquidation distance %")
    rsi: Optional[InstanceRSIConfig] = Field(None, description="Instance-specific RSI thresholds")
    
    # Optional overrides
    max_position_size: Optional[int] = Field(None, gt=0, description="Max total position size in contracts")
    execute_orders: bool = Field(True, description="Enable real order placement (dry-run if False)")


class InstanceGridGeometry(BaseModel):
    """Instance-specific grid geometry"""
    lower: str = Field(description="Grid lower boundary")
    upper: str = Field(description="Grid upper boundary")
    step: str = Field(description="Grid step size")
    reference: str = Field(description="Reference price for starting")


class InstanceGridLimits(BaseModel):
    """Instance-specific position limits"""
    max_open_positions: str = Field(description="Maximum open positions")
    lot_size: str = Field(description="Lot size for trades")
    max_open_orders: int = Field(description="Maximum open orders")
    max_qty_per_order: str = Field(description="Maximum quantity per order")


class InstanceGridBehavior(BaseModel):
    """Instance-specific grid behavior"""
    strict_grid: str = Field(default="true", description="Enforce strict grid levels")
    rung_snap_mode: RungSnapMode = Field(default=RungSnapMode.BELOW, description="Grid level snapping")
    tick_size: str = Field(description="Tick size for price rounding")
    dynamic_tick_size: Optional[str] = Field(default="false", description="Enable dynamic tick size")
    seed_initial_count: Optional[str] = Field(default="0", description="Seed initial order count")


class InstanceSmartGapFill(BaseModel):
    """Instance-specific smart gap fill config"""
    enabled: str = Field(default="false", description="Enable smart gap fill")
    order_type: str = Field(default="maker", description="Order type for gap fill")
    max_levels: str = Field(default="0", description="Maximum gap levels to fill")


class InstanceGridConfig(BaseModel):
    """Instance-specific grid configuration"""
    geometry: InstanceGridGeometry
    limits: InstanceGridLimits
    behavior: InstanceGridBehavior
    smart_gap_fill: Optional[InstanceSmartGapFill] = Field(default=None)


class InstanceCapitalAllocation(BaseModel):
    """Instance-specific capital allocation"""
    allocated_usd: float = Field(gt=0, description="Allocated capital in USD")
    max_position_value_usd: float = Field(gt=0, description="Maximum position value in USD")


class InstanceConfig(BaseModel):
    """Complete configuration for a trading instance (Symbol + Mode)
    
    V6.0 ARCHITECTURE: Instance = Symbol + Mode
    
    Examples:
    - BTCUSD_LONG: Bitcoin LONG grid
    - BTCUSD_SHORT: Bitcoin SHORT grid (can run simultaneously with BTCUSD_LONG)
    - ETHUSD_LONG: Ethereum LONG grid
    
    This enables running LONG and SHORT on the same symbol at the same time,
    each with their own grid, capital, and RSI thresholds.
    """
    # Core identification
    symbol: str = Field(description="Trading symbol (e.g., BTCUSD, ETHUSD)")
    mode: GridMode = Field(description="Trading mode: LONG or SHORT")
    product_id: int = Field(gt=0, description="Delta Exchange product ID")
    enabled: bool = Field(True, description="Enable/disable this instance")
    
    # Capital allocation
    capital: Optional[InstanceCapitalAllocation] = Field(default=None, description="Capital allocation")
    
    # Grid configuration
    grid: InstanceGridConfig
    
    # Safety configuration (with per-instance RSI thresholds)
    safety: InstanceSafetyConfig
    
    @property
    def instance_name(self) -> str:
        """Generate instance name from symbol + mode"""
        return f"{self.symbol}_{self.mode.value}"
    
    @property
    def database_name(self) -> str:
        """Generate database name for this instance"""
        return f"bot_events_{self.symbol}_{self.mode.value}.db"
    
    @property
    def log_prefix(self) -> str:
        """Generate log prefix for this instance"""
        return f"[{self.symbol}_{self.mode.value}]"
    
    def get_rsi_config(self) -> InstanceRSIConfig:
        """Get RSI config, with mode-appropriate defaults if not specified"""
        if self.safety.rsi:
            return self.safety.rsi
        # Return mode-appropriate defaults
        if self.mode == GridMode.LONG:
            return InstanceRSIConfig.for_long_mode()
        else:
            return InstanceRSIConfig.for_short_mode()


# ═══════════════════════════════════════════════════════════════════════════
# LEGACY MULTI-SYMBOL SUPPORT (v5.0) - Deprecated, use instances (v6.0)
# ═══════════════════════════════════════════════════════════════════════════

class CapitalAllocation(BaseModel):
    """Capital allocation for a specific symbol"""
    allocated_usd: float = Field(gt=0, description="Allocated capital in USD")
    max_position_value_usd: float = Field(gt=0, description="Maximum position value in USD")


class CapitalAllocationConfig(BaseModel):
    """Total capital allocation across symbols"""
    total_capital_usd: float = Field(gt=0, description="Total available capital in USD")
    allocations: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Per-symbol capital allocations")


class SymbolGridGeometry(BaseModel):
    """Symbol-specific grid geometry"""
    lower: str = Field(description="Grid lower boundary")
    upper: str = Field(description="Grid upper boundary")
    step: str = Field(description="Grid step size")
    reference: str = Field(description="Reference price for starting")


class SymbolGridLimits(BaseModel):
    """Symbol-specific position limits"""
    max_open_positions: str = Field(description="Maximum open positions")
    lot_size: str = Field(description="Lot size for LONG trades")
    short_lot_size: Optional[str] = Field(default="1", description="Lot size for SHORT trades")
    max_open_orders: int = Field(description="Maximum open orders")
    max_qty_per_order: str = Field(description="Maximum quantity per order")


class SymbolGridBehavior(BaseModel):
    """Symbol-specific grid behavior"""
    strict_grid: str = Field(default="true", description="Enforce strict grid levels")
    rung_snap_mode: RungSnapMode = Field(default=RungSnapMode.BELOW, description="Grid level snapping")
    tick_size: str = Field(description="Tick size for price rounding")
    dynamic_tick_size: Optional[str] = Field(default="false", description="Enable dynamic tick size")
    seed_initial_count: Optional[str] = Field(default="0", description="Seed initial order count")


class SymbolSmartGapFill(BaseModel):
    """Symbol-specific smart gap fill config"""
    enabled: str = Field(default="false", description="Enable smart gap fill")
    order_type: str = Field(default="maker", description="Order type for gap fill")
    max_levels: str = Field(default="0", description="Maximum gap levels to fill")


class SymbolGridConfig(BaseModel):
    """Symbol-specific grid configuration"""
    geometry: SymbolGridGeometry
    limits: SymbolGridLimits
    behavior: SymbolGridBehavior
    smart_gap_fill: Optional[SymbolSmartGapFill] = Field(default=None)


class SymbolSafety(BaseModel):
    """Symbol-specific safety limits"""
    max_account_loss_inr: str = Field(description="Maximum account loss in INR")
    min_liquidation_distance_pct: float = Field(description="Minimum liquidation distance %")


class SymbolConfig(BaseModel):
    """Complete configuration for a single trading symbol"""
    enabled: bool = Field(True, description="Enable/disable this symbol")
    product_id: int = Field(gt=0, description="Delta Exchange product ID")
    mode: GridMode = Field(description="LONG or SHORT")
    capital: Optional[CapitalAllocation] = Field(default=None, description="Capital allocation")
    grid: SymbolGridConfig
    safety: SymbolSafety


# ═══════════════════════════════════════════════════════════════════════════
# OPTIONS TRADING CONFIGURATION (Added: Jan 4, 2026)
# ═══════════════════════════════════════════════════════════════════════════

class OptionsConfig(BaseModel):
    """Configuration for options trading module (MVP)
    
    This is separate from grid bot - for manual options position management.
    Added: January 4, 2026
    """
    enabled: bool = Field(default=True, description="Enable options trading module")
    polling_interval_seconds: int = Field(default=5, ge=1, le=60, description="Position refresh interval")
    rate_limit_seconds: float = Field(default=2.0, ge=0.5, le=10, description="Minimum time between orders")
    max_spread_pct: float = Field(default=10.0, ge=1, le=50, description="Max acceptable spread percentage")
    guardian_integration: bool = Field(default=True, description="Respect Guardian GO/STOP signals")
    expiry_warning_hours: int = Field(default=24, ge=1, le=168, description="Hours before expiry to warn")
    liquidity_check: bool = Field(default=True, description="Check liquidity before orders")
    default_order_type: str = Field(default="maker_first", description="Default order type: maker_first, maker_only, market_only")


# ═══════════════════════════════════════════════════════════════════════════
# ROOT CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

class RootConfig(BaseModel):
    """Complete bot configuration (supports v4.0, v5.0, and v6.0)
    
    Version History:
    - v4.0: Single-symbol, single-mode (legacy)
    - v5.0: Multi-symbol support (symbols section)
    - v6.0: Multi-instance support (instances section) - Instance = Symbol + Mode
    
    V6.0 allows running BTCUSD_LONG and BTCUSD_SHORT simultaneously.
    """
    version: str = Field("2.0", description="Config schema version")
    trading_mode: TradingMode = Field(TradingMode.DEMO, description="Trading mode (demo/live)")
    
    # V6.0: Multi-instance support (Instance = Symbol + Mode)
    instances: Optional[Dict[str, InstanceConfig]] = Field(
        default=None, 
        description="Instance configurations (v6.0+). Key format: SYMBOL_MODE (e.g., BTCUSD_LONG)"
    )
    
    # V5.0: Multi-symbol support (deprecated, use instances)
    capital_allocation: Optional[CapitalAllocationConfig] = Field(default=None, description="Capital allocation (v5.0+)")
    symbols: Optional[Dict[str, SymbolConfig]] = Field(default=None, description="Symbol configurations (v5.0+, deprecated)")
    
    # Core components (v4.0 - optional for backward compat)
    bot: Optional[BotConfig] = Field(default=None)
    grid: Optional[GridConfig] = Field(default=None)
    capital_protection: CapitalProtection
    safety: SafetyConfig
    guardian: GuardianConfig
    liquidation_protection: Optional[LiquidationProtection] = Field(default=None)
    
    # Behavior
    startup: StartupBehavior
    shutdown: ShutdownBehavior
    order_execution: OrderExecution
    
    # Monitoring
    heartbeat: Heartbeat
    health_check: Optional[HealthCheck] = Field(default=None)
    performance_logging: Optional[PerformanceLogging] = Field(default=None)
    
    # Infrastructure
    api: APIEndpoints
    telegram: TelegramConfig
    logging: LoggingConfig
    webui: WebUIConfig
    refactor_compat: RefactorCompat = Field(default_factory=RefactorCompat, description="Refactor compatibility layer")
    
    # Risk & Safety
    risk_limits: Optional[RiskLimits] = Field(default=None)
    execution_safety: Optional[ExecutionSafety] = Field(default=None)
    
    # New Subsystems
    risk_analytics: RiskAnalyticsConfig = Field(default_factory=RiskAnalyticsConfig, description="Risk analytics configuration")
    ip_monitor: IPMonitorConfig = Field(default_factory=IPMonitorConfig, description="IP monitoring configuration")
    hot_reload: HotReloadConfig = Field(default_factory=HotReloadConfig, description="Hot reload configuration")
    pm2: PM2DetailedConfig = Field(default_factory=PM2DetailedConfig, description="PM2 detailed configuration")
    emergency: EmergencyConfig = Field(default_factory=EmergencyConfig, description="Emergency configuration")
    websocket: WebSocketConfig = Field(default_factory=WebSocketConfig, description="WebSocket configuration")
    alert_throttle: AlertThrottleConfig = Field(default_factory=AlertThrottleConfig, description="Alert throttling")
    
    # Multi-strategy support
    strategies: List[StrategyOverride] = Field(default_factory=list, description="Strategy overrides")
    active_strategies: List[str] = Field(default_factory=list, description="Active strategy names")
    
    # Monitoring system (Nov 19, 2025)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig, description="Monitoring system configuration")
    
    # Recovery system (Nov 20, 2025)
    recovery: RecoveryConfig = Field(default_factory=RecoveryConfig, description="Recovery system configuration")
    
    # Exchange maintenance protection (Dec 23, 2025)
    exchange_maintenance: ExchangeMaintenanceConfig = Field(default_factory=ExchangeMaintenanceConfig, description="Exchange maintenance protection")
    
    # Options trading module (Jan 4, 2026) - Separate from grid bot
    options: OptionsConfig = Field(default_factory=OptionsConfig, description="Options trading configuration")
    
    class Config:
        extra = "forbid"  # Reject unknown fields
        
    def validate_cross_field_constraints(self):
        """Validate cross-field constraints (supports v4.0, v5.0, and v6.0)"""
        
        # V6.0 multi-instance validation (Instance = Symbol + Mode)
        if self.instances:
            for instance_name, instance_config in self.instances.items():
                # Validate instance name format
                expected_name = f"{instance_config.symbol}_{instance_config.mode.value}"
                if instance_name != expected_name:
                    raise ValueError(
                        f"Instance key '{instance_name}' doesn't match symbol+mode '{expected_name}'. "
                        f"Key must be SYMBOL_MODE format."
                    )
                
                # Validate grid geometry
                try:
                    lower = int(instance_config.grid.geometry.lower)
                    upper = int(instance_config.grid.geometry.upper)
                    step = int(instance_config.grid.geometry.step)
                    
                    levels = (upper - lower) / step
                    if levels > 100:
                        raise ValueError(f"{instance_name}: Grid would create {int(levels)} levels (max: 100). Increase step size.")
                    if levels < 5:
                        raise ValueError(f"{instance_name}: Grid would create {int(levels)} levels (min: 5). Decrease step size.")
                except (ValueError, AttributeError) as e:
                    print(f"⚠️  Warning: Could not validate grid levels for {instance_name}: {e}")
                
                # Validate RSI thresholds are appropriate for mode
                if instance_config.safety.rsi:
                    rsi = instance_config.safety.rsi
                    if instance_config.mode == GridMode.LONG:
                        if rsi.stop_threshold > 50:
                            print(f"⚠️  Warning: {instance_name} LONG mode has stop_threshold={rsi.stop_threshold}. "
                                  f"LONG typically stops at oversold (<=30).")
                    elif instance_config.mode == GridMode.SHORT:
                        if rsi.stop_threshold < 50:
                            print(f"⚠️  Warning: {instance_name} SHORT mode has stop_threshold={rsi.stop_threshold}. "
                                  f"SHORT typically stops at overbought (>=70).")
            
            # Common validations
            if self.heartbeat.update_interval >= self.heartbeat.timeout:
                raise ValueError(f"Heartbeat update_interval ({self.heartbeat.update_interval}) must be < timeout ({self.heartbeat.timeout})")
            
            if self.execution_safety and self.execution_safety.execute_orders and self.trading_mode == TradingMode.LIVE:
                if self.execution_safety.i_understand_live != "YES":
                    raise ValueError("Cannot execute live orders without i_understand_live=YES")
            
            return True
        
        # V5.0 multi-symbol validation (deprecated)
        if self.symbols:
            for symbol_name, symbol_config in self.symbols.items():
                # Convert string fields to int for validation
                try:
                    lower = int(symbol_config.grid.geometry.lower)
                    upper = int(symbol_config.grid.geometry.upper)
                    step = int(symbol_config.grid.geometry.step)
                    
                    # Ensure grid step creates reasonable number of levels
                    levels = (upper - lower) / step
                    if levels > 100:
                        raise ValueError(f"{symbol_name}: Grid would create {int(levels)} levels (max: 100). Increase step size.")
                    if levels < 5:
                        raise ValueError(f"{symbol_name}: Grid would create {int(levels)} levels (min: 5). Decrease step size.")
                except (ValueError, AttributeError) as e:
                    print(f"⚠️  Warning: Could not validate grid levels for {symbol_name}: {e}")
            
            # Heartbeat validation
            if self.heartbeat.update_interval >= self.heartbeat.timeout:
                raise ValueError(f"Heartbeat update_interval ({self.heartbeat.update_interval}) must be < timeout ({self.heartbeat.timeout})")
            
            # Execution safety (if present)
            if self.execution_safety and self.execution_safety.execute_orders and self.trading_mode == TradingMode.LIVE:
                if self.execution_safety.i_understand_live != "YES":
                    raise ValueError("Cannot execute live orders without i_understand_live=YES")
            
            return True
        
        # V4.0 single-symbol validation (backward compat)
        if self.grid:
            # Ensure grid step creates reasonable number of levels
            levels = (self.grid.geometry.upper - self.grid.geometry.lower) / self.grid.geometry.step
            if levels > 100:
                raise ValueError(f"Grid would create {int(levels)} levels (max: 100). Increase step size.")
            if levels < 5:
                raise ValueError(f"Grid would create {int(levels)} levels (min: 5). Decrease step size.")
        
        # Validate heartbeat timing
        if self.heartbeat.update_interval >= self.heartbeat.timeout:
            raise ValueError(f"Heartbeat update_interval ({self.heartbeat.update_interval}) must be < timeout ({self.heartbeat.timeout})")
        
        # Validate execution safety
        if self.execution_safety and self.execution_safety.execute_orders and self.trading_mode == TradingMode.LIVE:
            if self.execution_safety.i_understand_live != "YES":
                raise ValueError("Cannot execute live orders without i_understand_live=YES")
        
        return True
