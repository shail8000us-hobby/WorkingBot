import { z } from 'zod';

export const StateSchema = z.record(z.string(), z.any());
export type StateResponse = z.infer<typeof StateSchema>;

export const ConfigEntrySchema = z
  .object({
    value: z.any().optional(),
    description: z.string().optional(),
    source_key: z.string().optional(),
    legacy_sources: z.array(z.string()).optional(),
    deprecated: z.boolean().optional(),
    category: z.string().optional(),
    group: z.string().optional(),
  })
  .passthrough();

export const ConfigResponseSchema = z.record(z.string(), ConfigEntrySchema);
export type ConfigResponse = z.infer<typeof ConfigResponseSchema>;

export const PositionSchema = z
  .object({
    id: z.union([z.string(), z.number()]).optional(),
    symbol: z.string().optional(),
    entry_price: z.number().optional(),
    entry_time: z.string().optional(),
    current_price: z.number().optional(),
    mark_price: z.number().optional(),
    size: z.number().optional(),
    status: z.string().optional(),
    pnl_usd: z.number().optional(),
    pnl_inr: z.number().optional(),
    notional: z.number().optional(),
    notional_deployed: z.number().optional(),
    liquidation: z
      .object({
        risk_level: z.string().optional(),
        liquidation_price: z.number().optional(),
        distance_percent: z.number().optional(),
      })
      .partial()
      .optional(),
  })
  .passthrough();

export const PositionsResponseSchema = z
  .object({
    positions: z.array(PositionSchema),
    summary: z.record(z.string(), z.any()).optional(),
    source: z.string().optional(),
  })
  .passthrough();
export type PositionsResponse = z.infer<typeof PositionsResponseSchema>;

export const ReconciliationRecordSchema = z
  .object({
    order_id: z.string().optional(),
    client_order_id: z.string().optional(),
    symbol: z.string().optional(),
    source: z.string().optional(),
    discrepancy: z.record(z.string(), z.any()).optional(),
    acknowledged: z.boolean().optional(),
  })
  .passthrough();

export const ReconciliationTableResponseSchema = z
  .object({
    status: z.string(),
    records: z.array(ReconciliationRecordSchema),
    counters: z.record(z.string(), z.any()).optional(),
    pagination: z
      .object({
        page: z.number(),
        per_page: z.number(),
        total: z.number(),
        total_pages: z.number(),
      })
      .optional(),
    timestamp: z.string().optional(),
  })
  .passthrough();
export type ReconciliationTableResponse = z.infer<typeof ReconciliationTableResponseSchema>;

export const ReconciliationStatusSchema = z
  .object({
    status: z.string().optional(),
    enabled: z.boolean().optional(),
    is_running: z.boolean().optional(),
    last_run: z.union([z.string(), z.number()]).optional(),
    last_success: z.union([z.string(), z.number()]).optional(),
    last_error: z.string().optional(),
    counters: z.record(z.string(), z.any()).optional(),
    summary: z.record(z.string(), z.any()).optional(),
  })
  .passthrough();
export type ReconciliationStatus = z.infer<typeof ReconciliationStatusSchema>;

export const ReconciliationOrdersStatusSchema = z
  .object({
    status: z.string().optional(),
    order_count: z.number().optional(),
    trading_active: z.boolean().optional(),
    bot_running: z.boolean().optional(),
    mode: z.string().optional(),
    meta: z.record(z.string(), z.any()).optional(),
  })
  .passthrough();
export type ReconciliationOrdersStatus = z.infer<typeof ReconciliationOrdersStatusSchema>;

export const ReconciliationActionResponseSchema = z
  .object({
    status: z.string().optional(),
    success: z.boolean().optional(),
    results: z.record(z.string(), z.any()).optional(),
    error: z.string().optional(),
  })
  .passthrough();
export type ReconciliationActionResponse = z.infer<typeof ReconciliationActionResponseSchema>;

export const TradingBlockerSchema = z
  .object({
    id: z.string().optional(),
    category: z.string().optional(),
    name: z.string().optional(),
    severity: z.string().optional(),
    active: z.boolean().optional(),
    message: z.string().optional(),
    deep_link: z
      .object({
        tab: z.string().optional(),
        section: z.string().optional(),
        field: z.string().optional(),
      })
      .partial()
      .optional(),
  })
  .passthrough();

export const TradingStatusResponseSchema = z
  .object({
    success: z.boolean(),
    trading_allowed: z.boolean().optional(),
    total_blockers: z.number().optional(),
    blockers: z.array(TradingBlockerSchema).optional(),
    status: z
      .object({
        trading_status: z.string().optional(),
        bot_running: z.boolean().optional(),
        bot_start_time: z.string().nullable().optional(),
        trading_allowed: z.boolean().optional(),
      })
      .partial()
      .optional(),
  })
  .passthrough();
export type TradingStatusResponse = z.infer<typeof TradingStatusResponseSchema>;

export const TradingStatusCommandResponseSchema = z
  .object({
    success: z.boolean(),
    message: z.string().optional(),
    error: z.string().optional(),
  })
  .passthrough();
export type TradingStatusCommandResponse = z.infer<typeof TradingStatusCommandResponseSchema>;
