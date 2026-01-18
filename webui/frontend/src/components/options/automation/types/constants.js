/**
 * Constants and Enums for Options Automation System
 */

export const ORDER_TYPES = {
  MARKET: 'market',
  LIMIT: 'limit',
  MID_PRICE: 'mid_price',
};

export const MONEYNESS = {
  ITM: 'itm',
  ATM: 'atm',
  OTM: 'otm',
};

export const AUTOMATION_STATUS = {
  INACTIVE: 'inactive', // Not running
  WAITING: 'waiting', // Running but conditions not met
  TRIGGERED: 'triggered', // Conditions met, about to execute
  ACTIVE: 'active', // Position opened, monitoring exit
  PAUSED: 'paused', // Temporarily disabled
  COMPLETED: 'completed', // Exit executed successfully
  ERROR: 'error', // Error occurred
};

export const ACTION_TYPES = {
  BUY: 'buy',
  SELL: 'sell',
};

export const OPERATORS = {
  GREATER_THAN: '>',
  LESS_THAN: '<',
  GREATER_EQUAL: '>=',
  LESS_EQUAL: '<=',
  EQUAL: '=',
};

export const TIME_INTERVALS = {
  ONE_TIME: 'one_time',
  EVERY_1_MIN: 'every_1_min',
  EVERY_5_MIN: 'every_5_min',
  EVERY_15_MIN: 'every_15_min',
  EVERY_30_MIN: 'every_30_min',
  EVERY_1_HOUR: 'every_1_hour',
};

export const EXECUTION_TIMING = {
  IMMEDIATE: 'immediate',
  DELAYED: 'delayed',
  SCHEDULED: 'scheduled',
};

export const POSITION_SIZING = {
  FIXED: 'fixed',
  PERCENTAGE: 'percentage',
  DYNAMIC: 'dynamic',
};

export const TRAILING_STOP_TYPES = {
  PERCENTAGE: 'percentage',
  FIXED: 'fixed',
};

export const EXIT_TYPES = {
  TAKE_PROFIT: 'take_profit',
  STOP_LOSS: 'stop_loss',
  TRAILING_STOP: 'trailing_stop',
  TIME_BASED: 'time_based',
  UNDERLYING_PRICE: 'underlying_price',
};

export const EXIT_LOGIC = {
  OR: 'or', // Exit if ANY condition met
  AND: 'and', // Exit only if ALL conditions met
};

export const NOTIFICATION_TYPES = {
  ENTRY_TRIGGERED: 'entry_triggered',
  EXIT_TRIGGERED: 'exit_triggered',
  ORDER_PLACED: 'order_placed',
  ORDER_FILLED: 'order_filled',
  ORDER_FAILED: 'order_failed',
  RISK_LIMIT_HIT: 'risk_limit_hit',
  ERROR: 'error',
  WARNING: 'warning',
  SUCCESS: 'success',
  INFO: 'info',
};

export const DEFAULT_RULES = {
  entry: {
    action: ACTION_TYPES.BUY,
    quantity: 1,
    ivFilter: {
      enabled: false,
      operator: OPERATORS.GREATER_THAN,
      value: 80,
    },
    moneyness: MONEYNESS.ATM,
    premiumRange: {
      enabled: false,
      min: 0,
      max: 10000,
    },
    timeFilter: {
      enabled: false,
      startTime: '09:30',
      endTime: '15:30',
    },
    underlyingPrice: {
      enabled: false,
      min: 0,
      max: 150000,
    },
  },
  execution: {
    orderType: ORDER_TYPES.MARKET,
    limitPriceOffset: 0,
    orderTimeout: 60,
    timing: EXECUTION_TIMING.IMMEDIATE,
    delaySeconds: 5,
    scheduledTime: '09:30',
    positionSizing: POSITION_SIZING.FIXED,
    quantity: 1,
    capitalPercentage: 5,
    minQuantity: 1,
    maxQuantity: 10,
    staging: {
      enabled: false,
      stages: 3,
      intervalSeconds: 30,
    },
    dryRun: true, // Default to safe mode
  },
  exit: {
    takeProfit: {
      enabled: false,
      percentage: 50,
      fixedValue: 0,
      partial: false,
    },
    stopLoss: {
      enabled: false,
      percentage: 50,
      fixedValue: 0,
    },
    trailingStop: {
      enabled: false,
      type: TRAILING_STOP_TYPES.PERCENTAGE,
      distance: 20,
      activationProfit: 10,
    },
    timeBased: {
      enabled: false,
      exitTime: '15:15',
      duration: 0,
      closeBeforeExpiry: false,
    },
    underlyingExit: {
      enabled: false,
      abovePrice: 0,
      belowPrice: 0,
    },
    logic: EXIT_LOGIC.OR, // Exit if any condition met
  },
  risk: {
    maxPositionSize: 10,
    maxOpenPositions: 5,
    dailyLossLimit: 1000,
    perTradeLossLimit: 200,
    portfolioExposure: 30, // Percentage
    maxOrdersPerMinute: 10,
    orderRetryAttempts: 3,
    alertOnlyMode: true, // Default to alerts only (NO REAL ORDERS)
    autoStopOnError: false,
    closePositionsOnStop: false,
    tradingHoursRestriction: {
      enabled: false,
      startTime: '09:30',
      endTime: '15:15',
    },
    notifications: {
      sound: true,
      browser: true,
      email: false,
      sms: false,
    },
  },
};

export const POLLING_INTERVALS = {
  FAST: 1000, // 1 second
  NORMAL: 5000, // 5 seconds
  SLOW: 10000, // 10 seconds
};

export const STORAGE_KEYS = {
  AUTOMATIONS: 'options_automations',
  HISTORY: 'automation_history',
  DAILY_PNL: 'automation_daily_pnl',
  SETTINGS: 'automation_settings',
};

// Moneyness thresholds (% distance from spot)
export const MONEYNESS_THRESHOLDS = {
  ITM_MIN: -10, // Strike < spot by >10%
  ATM_MIN: -2.5, // Strike within ±2.5% of spot
  ATM_MAX: 2.5,
  OTM_MIN: 2.5, // Strike > spot by >2.5%
};

// UI Colors
export const STATUS_COLORS = {
  [AUTOMATION_STATUS.INACTIVE]: '#6b7280',
  [AUTOMATION_STATUS.WAITING]: '#fbbf24',
  [AUTOMATION_STATUS.TRIGGERED]: '#f59e0b',
  [AUTOMATION_STATUS.ACTIVE]: '#10b981',
  [AUTOMATION_STATUS.PAUSED]: '#8b5cf6',
  [AUTOMATION_STATUS.COMPLETED]: '#3b82f6',
  [AUTOMATION_STATUS.ERROR]: '#ef4444',
};

export const STATUS_ICONS = {
  [AUTOMATION_STATUS.INACTIVE]: '⚪',
  [AUTOMATION_STATUS.WAITING]: '🟡',
  [AUTOMATION_STATUS.TRIGGERED]: '🟠',
  [AUTOMATION_STATUS.ACTIVE]: '🟢',
  [AUTOMATION_STATUS.PAUSED]: '🟣',
  [AUTOMATION_STATUS.COMPLETED]: '🔵',
  [AUTOMATION_STATUS.ERROR]: '🔴',
};
