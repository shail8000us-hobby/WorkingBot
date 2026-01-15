"""
Pydantic schemas for Zero DTE configuration validation
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any
from datetime import time


class PremiumRange(BaseModel):
    min: float = Field(15, ge=1, description="Minimum premium for entry")
    max: float = Field(30, le=100, description="Maximum premium for entry")
    
    @field_validator('max')
    @classmethod
    def max_greater_than_min(cls, v, info):
        # Note: In Pydantic v2, we can't easily access other fields in field_validator
        # This validation happens at model level
        return v


class EntryConfig(BaseModel):
    default_underlying: str = Field("BTC", pattern="^(BTC|ETH)$")
    initial_lots: int = Field(5, ge=1, le=50)
    strike_offset_pct: float = Field(2.5, ge=0.5, le=10)
    premium_range: PremiumRange = Field(default_factory=PremiumRange)
    max_spread_pct: float = Field(2.0, ge=0.1, le=5)
    earliest_entry_time: str = Field("09:30")
    latest_entry_time: str = Field("14:00")


class LotAdjustment(BaseModel):
    min_lot_adjustment: int = Field(1, ge=1, le=5)
    max_lot_adjustment: int = Field(10, ge=1, le=20)
    max_lots_per_leg: int = Field(20, ge=5, le=100)


class OrderConfig(BaseModel):
    preference: str = Field("maker_first", pattern="^(maker_first|market)$")
    timeout_seconds: int = Field(2, ge=1, le=10)
    max_slippage_pct: float = Field(0.5, ge=0.1, le=2)


class RebalancingConfig(BaseModel):
    imbalance_threshold_pct: float = Field(20, ge=5, le=50)
    min_premium_diff: float = Field(5, ge=1, le=20)
    adjustment: LotAdjustment = Field(default_factory=LotAdjustment)
    orders: OrderConfig = Field(default_factory=OrderConfig)


class TargetPremium(BaseModel):
    min: float = Field(20, ge=5)
    max: float = Field(25, le=50)


class RolloverConfig(BaseModel):
    min_premium_threshold: float = Field(5, ge=1, le=20)
    target_premium: TargetPremium = Field(default_factory=TargetPremium)
    max_strike_search: int = Field(5, ge=2, le=10)
    cooldown_seconds: int = Field(300, ge=60, le=600)


class ExitConfig(BaseModel):
    both_legs_below: float = Field(5, ge=1, le=20, 
        description="Exit when BOTH legs premium below this")
    forced_exit_time: str = Field("17:15")
    settlement_time: str = Field("17:30")
    stop_loss_amount: float = Field(5000, ge=1000, le=50000)
    profit_target_pct: float = Field(0, ge=0, le=100)


class GreeksLimits(BaseModel):
    max_delta: float = Field(0.5, ge=0.1, le=1)
    max_gamma: float = Field(0.1, ge=0.01, le=0.5)
    max_vega: float = Field(100, ge=10, le=500)


class MonitoringConfig(BaseModel):
    poll_interval_seconds: int = Field(30, ge=10, le=120)
    snapshot_interval_seconds: int = Field(60, ge=30, le=300)
    greeks_limits: GreeksLimits = Field(default_factory=GreeksLimits)
    margin_warning_threshold_pct: float = Field(75, ge=50, le=95)


class EmergencyConfig(BaseModel):
    close_on_guardian_stop: bool = True
    close_on_margin_breach: bool = True


class RiskConfig(BaseModel):
    guardian_enabled: bool = True
    guardian_signal_file: str = "guardian_signal.txt"
    max_margin_utilization_pct: float = Field(80, ge=50, le=95)
    min_margin_buffer: float = Field(50000, ge=10000)
    emergency: EmergencyConfig = Field(default_factory=EmergencyConfig)


class AlertEvents(BaseModel):
    session_start: bool = True
    session_end: bool = True
    rebalance: bool = True
    rollover: bool = True
    stop_loss_warning: bool = True
    profit_milestone: bool = True


class AlertConfig(BaseModel):
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    events: AlertEvents = Field(default_factory=AlertEvents)


class DatabaseConfig(BaseModel):
    directory: str = "database"
    sessions_db: str = "zero_dte_sessions.db"
    trades_db: str = "zero_dte_trades.db"
    rebalances_db: str = "zero_dte_rebalances.db"
    retention_days: int = Field(30, ge=7, le=365)


class LoggingConfig(BaseModel):
    level: str = Field("INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    file: str = "logs/zero_dte_engine.log"
    rotation: str = "50 MB"
    retention: str = "7 days"
    compression: str = "gz"


class ContractSpec(BaseModel):
    contract_size: float
    tick_size: float
    symbol_format: str


class ContractsConfig(BaseModel):
    BTC: ContractSpec = Field(default_factory=lambda: ContractSpec(
        contract_size=0.001, tick_size=0.5, 
        symbol_format="{type}-BTC-{strike}-{expiry}"
    ))
    ETH: ContractSpec = Field(default_factory=lambda: ContractSpec(
        contract_size=0.01, tick_size=0.05,
        symbol_format="{type}-ETH-{strike}-{expiry}"
    ))


class StrategyInfo(BaseModel):
    name: str = "0DTE Premium Balancer"
    version: str = "1.0.0"
    description: str = "Autonomous 0DTE strangle with premium rebalancing"


class ZeroDTEConfig(BaseModel):
    """Complete configuration schema for 0DTE bot"""
    strategy: StrategyInfo = Field(default_factory=StrategyInfo)
    entry: EntryConfig = Field(default_factory=EntryConfig)
    rebalancing: RebalancingConfig = Field(default_factory=RebalancingConfig)
    rollover: RolloverConfig = Field(default_factory=RolloverConfig)
    exit: ExitConfig = Field(default_factory=ExitConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    alerts: AlertConfig = Field(default_factory=AlertConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    contracts: ContractsConfig = Field(default_factory=ContractsConfig)
    
    class Config:
        extra = "allow"
