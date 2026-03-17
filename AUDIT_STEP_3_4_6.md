# Step 2: Line-by-Line Reading Confirmation
- FULLY READ: mmm_close_at_5.py
- FULLY READ: mmm_recycler.py
- FULLY READ: mmm_reversal.py
- FULLY READ: mmm_watchdog.py
- FULLY READ: mmm_state.py
- FULLY READ: mmm_analytics_aggregator.py
- FULLY READ: mmm_gamma_detector.py
- FULLY READ: mmm_safety.py
- FULLY READ: mmm_monitor.py
- FULLY READ: mmm_heartbeat_health.py
- FULLY READ: mmm_observer.py
- FULLY READ: mmm_initializer.py
- FULLY READ: mmm_circuit_breaker.py
- FULLY READ: mmm_activity.py
- FULLY READ: mmm_dte_presets.py
- FULLY READ: mmm_constants.py
- FULLY READ: __init__.py
- FULLY READ: mmm_margin_guardian.py
- FULLY READ: mmm_telegram.py
- FULLY READ: mmm_api.py
- FULLY READ: mmm_adopter.py
- FULLY READ: mmm_engine.py
- FULLY READ: mmm_strike_shift.py
- FULLY READ: mmm_scaler.py
- FULLY READ: mmm_breakeven_engine.py
- FULLY READ: mmm_wind_down.py
- FULLY READ: mmm_storage.py
- FULLY READ: mmm_perp_hedge.py
- FULLY READ: mmm_walkthrough.py
- FULLY READ: mmm_guardian.py
- FULLY READ: mmm_harvester.py
- FULLY READ: mmm_analytics_storage.py
- FULLY READ: mmm_config.py
- FULLY READ: mmm_regime.py
- FULLY READ: mmm_executor.py
- FULLY READ: mmm_atm_shield.py
- FULLY READ: mmm_pending_orders.py
- FULLY READ: mmm_trigger.py
- FULLY READ: mmm_websocket.py

# Step 3 & 4: Call Graph & State Map
### `mmm_close_at_5.py::_D`
- **Calls:** str, Decimal
### `mmm_close_at_5.py::_check_stale_being_closed`
- **Calls:** warning, get, monotonic, pop
### `mmm_close_at_5.py::scan_closeable_positions`
- **Calls:** get, debug, len
### `mmm_close_at_5.py::close_position`
- **Calls:** build_symbol, isoformat, error, setdefault, float, info, get
- **State Mutations:** session['close_at_5_count'] =, session['realized_pnl'] =, session['updated_at'] =
### `mmm_close_at_5.py::_partial_close_position`
- **Calls:** pop, recompute_side_lots, info, get, max
- **State Mutations:** side_state['original_lots'] =
### `mmm_close_at_5.py::_remove_closed_position`
- **Calls:** warning, pop, recompute_side_lots, isoformat, now, get
- **State Mutations:** side_state['original_lots'] =, side_state['original_premium'] =
### `mmm_close_at_5.py::check_side_fully_closed`
- **Calls:** get
### `mmm_close_at_5.py::check_both_sides_closed`
- **Calls:** check_side_fully_closed
### `mmm_recycler.py::select_recyclable_positions`
- **Calls:** sort, get, append
### `mmm_recycler.py::check_recycle_viability`
- **Calls:** sum, ceil, round, float, get, max
### `mmm_recycler.py::execute_lot_recycling`
- **Calls:** sort, find_new_strike, get, floor, select_recyclable_positions
- **State Mutations:** session['_last_recycle_at'] =, session['pnl_recycle'] =, session['updated_at'] =, session['recycle_count'] =, session['realized_pnl'] =, session['recycle_attempt_count'] =
### `mmm_reversal.py::detect_reversal`
- **Calls:** isinstance, is_wind_down_active, lower, upper, info, get, debug
### `mmm_reversal.py::is_cooldown_active`
- **Calls:** fromisoformat, now, info, replace, get
- **State Mutations:** session['cooldown_until'] =, session['cooldown_active'] =
### `mmm_reversal.py::activate_cooldown`
- **Calls:** isoformat, now, timedelta, info, get, debug
- **State Mutations:** session['cooldown_until'] =, session['cooldown_active'] =
### `mmm_reversal.py::record_reversal`
- **Calls:** len, isoformat, append, setdefault, upper, get, debug
- **State Mutations:** session['reversal_count'] =
### `mmm_reversal.py::handle_reversal_skip_transition`
- **Calls:** update_trigger_snapshots, len, isoformat, now, append, setdefault, upper, info, get
- **State Mutations:** session['last_aggressor'] =
### `mmm_watchdog.py::get_instance`
- **Calls:** MMMWatchdog
### `mmm_watchdog.py::__init__`
- **Calls:** Event, RLock
### `mmm_watchdog.py::start`
- **Calls:** start, clear, Thread, info
### `mmm_watchdog.py::stop`
- **Calls:** set, info
### `mmm_watchdog.py::register`
- **Calls:** debug, getattr
### `mmm_watchdog.py::deregister`
- **Calls:** pop, debug
### `mmm_watchdog.py::_run`
- **Calls:** is_set, _sweep, exception, wait
### `mmm_watchdog.py::_sweep`
- **Calls:** dict, _check_monitor, items, error
### `mmm_watchdog.py::_check_monitor`
- **Calls:** critical, _get_cooldown_remaining, getattr, _check_beat_timeout, _emit_alert, _restart_monitor, save_session, get, debug, deregister
- **State Mutations:** session['strategy_status'] =
### `mmm_watchdog.py::_check_beat_timeout`
- **Calls:** total_seconds, getattr, fromisoformat, now, replace, get
### `mmm_watchdog.py::_restart_monitor`
- **Calls:** pop, start_session_monitor, get_session, get_storage, getattr, register, _record_restart, append, info, save_session, setdefault, sleep, deregister
### `mmm_watchdog.py::_emit_alert`
- **Calls:** warning, emit_safety
### `mmm_watchdog.py::_log_activity`
- **Calls:** warning, log_activity
### `mmm_watchdog.py::_get_cooldown_remaining`
- **Calls:** get, min, max, monotonic
### `mmm_watchdog.py::_record_restart`
- **Calls:** monotonic
### `mmm_watchdog.py::clear_backoff`
- **Calls:** pop, debug
### `mmm_watchdog.py::status`
- **Calls:** round, items, monotonic, len
### `mmm_state.py::_migrate_side_to_positions`
- **Calls:** len, error, lower, append, set, get, isoformat, debug
- **State Mutations:** side_state['positions'] =, side_state['_pos_counter'] =
### `mmm_state.py::create_side_state`
- **Calls:** isoformat, append, lower, now
### `mmm_state.py::recompute_side_lots`
- **Calls:** warning, sum, len, isinstance, _migrate_side_to_positions, isoformat, error, get
- **State Mutations:** side_state['frozen_positions'] =, side_state['adjustment_total_lots'] =, side_state['adjustment_fills'] =, side_state['positions'] =, side_state['total_lots'] =, side_state['adjustment_avg'] =, side_state['frozen_total_lots'] =, side_state['original_lots'] =, side_state['active_lots'] =, side_state['original_premium'] =
### `mmm_state.py::create_session`
- **Calls:** apply_preset, update, get_session, ValueError, isoformat, create_side_state, compute_total_dte_hours, get, max
- **State Mutations:** session['expiry_time'] =
### `mmm_state.py::initialize_side_from_entry`
- **Calls:** warning, recompute_side_lots, create_side_state, lower, strike_key_fn, upper, get
### `mmm_state.py::_backfill_side_premiums`
- **Calls:** get, round, upper
### `mmm_state.py::get_session_summary`
- **Calls:** get, _backfill_side_premiums
### `mmm_analytics_aggregator.py::get_aggregator`
- **Calls:** MMMAnalyticsAggregator
### `mmm_analytics_aggregator.py::_get_conn`
- **Calls:** execute, connect
### `mmm_analytics_aggregator.py::_load_sessions`
- **Calls:** close, _get_conn, execute, error, loads, fetchall
### `mmm_analytics_aggregator.py::get_aggregated_analytics`
- **Calls:** _load_sessions, _distributions, _session_table, _legacy_risk, _empty_analytics, _algo_behavior, _legacy_performance, _risk_profile, error, print_exc, _legacy_capital, _overview, _profitability, _recent_summary, _capital_planning
### `mmm_analytics_aggregator.py::_overview`
- **Calls:** sum, len, round, _expected_value, get
### `mmm_analytics_aggregator.py::_expected_value`
- **Calls:** get, sum, len
### `mmm_analytics_aggregator.py::_capital_planning`
- **Calls:** _empty_capital_planning, _avg_entry_premium, get, _lot_growth_distribution, max, _percentile
### `mmm_analytics_aggregator.py::_avg_entry_premium`
- **Calls:** get, append, len, sum
### `mmm_analytics_aggregator.py::_lot_growth_distribution`
- **Calls:** get, round, items
### `mmm_analytics_aggregator.py::_risk_profile`
- **Calls:** sum, len, round, upper, abs, get, max, _percentile
### `mmm_analytics_aggregator.py::_profitability`
- **Calls:** sum, len, round, _empty_profitability, abs, get, _pnl_distribution
### `mmm_analytics_aggregator.py::_pnl_distribution`
- **Calls:** min, int, len, range, append, round, defaultdict, max
### `mmm_analytics_aggregator.py::_algo_behavior`
- **Calls:** get, round, sum, len
### `mmm_analytics_aggregator.py::_distributions`
- **Calls:** sorted, _histogram, append, round, get
### `mmm_analytics_aggregator.py::_histogram`
- **Calls:** min, int, len, range, append, round, defaultdict, max
### `mmm_analytics_aggregator.py::_session_table`
- **Calls:** get, append, round
### `mmm_analytics_aggregator.py::_data_quality`
- **Calls:** round, get, sum, len
### `mmm_analytics_aggregator.py::_legacy_capital`
- **Calls:** int, len, sum, get, _capital_planning
### `mmm_analytics_aggregator.py::_legacy_risk`
- **Calls:** sum, len, round, abs, get, max
### `mmm_analytics_aggregator.py::_legacy_performance`
- **Calls:** get, _algo_behavior, len
### `mmm_analytics_aggregator.py::_recent_summary`
- **Calls:** get, round
### `mmm_analytics_aggregator.py::_percentile`
- **Calls:** sorted, min, int, len
### `mmm_analytics_aggregator.py::_empty_analytics`
- **Calls:** _empty_capital_planning, isoformat, _empty_profitability, now
### `mmm_gamma_detector.py::get_gamma_detector`
- **Calls:** GammaDetector
### `mmm_gamma_detector.py::__init__`
- **Calls:** Lock
### `mmm_gamma_detector.py::compute_gamma`
- **Calls:** warning, _hash_positions, int, get_breakeven_engine, _empty_result, _build_result, _collect_open_positions, get, _run_boundary_scan
### `mmm_gamma_detector.py::invalidate_cache`
- **Calls:** pop
### `mmm_gamma_detector.py::_run_boundary_scan`
- **Calls:** sum, range, _compute_second_diff, get, max
### `mmm_gamma_detector.py::_compute_second_diff`
- **Calls:** _compute_pnl_at_spot
### `mmm_gamma_detector.py::_classify_zone`
- **Calls:** get
### `mmm_gamma_detector.py::_build_result`
- **Calls:** min, bool, len, isoformat, now, abs, get, _classify_zone
### `mmm_gamma_detector.py::_empty_result`
- **Calls:** isoformat, now
### `mmm_safety.py::update_peak_pnl`
- **Calls:** total_seconds, fromisoformat, isoformat, now, replace, get, max
- **State Mutations:** session['_peak_pnl_set_at'] =, session['peak_pnl'] =
### `mmm_safety.py::reset_peak_pnl_on_reversal`
- **Calls:** get, max, info
- **State Mutations:** session['peak_pnl'] =
### `mmm_safety.py::should_block_adjustment`
- **Calls:** get
### `mmm_safety.py::get_block_action`
- **Calls:** get
### `mmm_safety.py::should_pause`
- **Calls:** get
### `mmm_safety.py::get_safety`
- **Calls:** MMMSafety
### `mmm_safety.py::run_all_checks`
- **Calls:** extend, check_max_loss, check_position_cap, check_total_exposure, check_max_adjustments
### `mmm_safety.py::check_position_cap`
- **Calls:** get, append, upper
### `mmm_safety.py::check_max_adjustments`
- **Calls:** get, append, pop
- **State Mutations:** session['_max_adj_paused'] =
### `mmm_safety.py::check_max_loss`
- **Calls:** get, append, round
### `mmm_safety.py::check_max_loss_sizing`
- **Calls:** get, append, round
- **State Mutations:** session['_max_loss_sizing_warned'] =
### `mmm_safety.py::check_whipsaw`
- **Calls:** get, pop, now
- **State Mutations:** session['_whipsaw_last_noise_at'] =, session['_whipsaw_last_checked_idx'] =, session['_whipsaw_skip_until'] =, session['_whipsaw_score'] =
### `mmm_safety.py::check_total_exposure`
- **Calls:** get, append, upper
### `mmm_safety.py::check_asymmetry`
- **Calls:** pop, min, append, get, max
- **State Mutations:** session['_asymmetry_lot_reduction_pct'] =, session['_asymmetry_heavy_side'] =
### `mmm_safety.py::check_near_expiry`
- **Calls:** get, append
### `mmm_safety.py::check_near_expiry_v2`
- **Calls:** get, append
### `mmm_safety.py::check_pnl_guardrail`
- **Calls:** get, append, round, abs
### `mmm_safety.py::check_margin`
- **Calls:** get, append
### `mmm_safety.py::check_lot_velocity`
- **Calls:** fromisoformat, now, append, timedelta, replace, get
### `mmm_safety.py::check_trailing_stop`
- **Calls:** get, append
### `mmm_monitor.py::start_session_monitor`
- **Calls:** warning, pop, MMMMonitor, stop, start
### `mmm_monitor.py::stop_session_monitor`
- **Calls:** pop, stop
### `mmm_monitor.py::pause_session_monitor`
- **Calls:** pause, get
### `mmm_monitor.py::resume_session_monitor`
- **Calls:** resume, get
### `mmm_monitor.py::get_monitor`
- **Calls:** get
### `mmm_monitor.py::get_all_monitors`
- **Calls:** dict
### `mmm_monitor.py::_save_session`
- **Calls:** warning, extend, get_session, get_storage, error, info, save_session, get
- **State Mutations:** session['params'] =
### `mmm_monitor.py::__init__`
- **Calls:** MMMRegimeEngine, CircuitBreaker, MMMGuardian, HeartbeatHealth, Lock, Event, MarginGuardian, register_guardian, get, get_safety, get_engine
### `mmm_monitor.py::executor`
- **Calls:** get_executor
### `mmm_monitor.py::initializer`
- **Calls:** get_initializer
### `mmm_monitor.py::start`
- **Calls:** warning, isoformat, emit_status_change, _RealThread, clear, items, get, info, start, setdefault, debug, _start_close_watcher
### `mmm_monitor.py::stop`
- **Calls:** warning, pop, _save_my_session, log_activity, isoformat, save_session_analytics, emit_status_change, get_analytics_storage, set, get, setdefault
### `mmm_monitor.py::pause`
- **Calls:** _save_my_session, pop, isoformat, now, emit_status_change, info, get
### `mmm_monitor.py::resume`
- **Calls:** _save_my_session, pop, isoformat, now, emit_status_change, info, get
### `mmm_monitor.py::get_session_snapshot`
- **Calls:** deepcopy
### `mmm_monitor.py::_save_my_session`
- **Calls:** now, summary, get, isoformat, debug, _save_session
### `mmm_monitor.py::_should_stop`
- **Calls:** is_set
### `mmm_monitor.py::force_heartbeat`
- **Calls:** get, pop, set, info
### `mmm_monitor.py::_wait_for_next_cycle`
- **Calls:** min, log_activity, wait, clear, is_set, max, monotonic
### `mmm_monitor.py::_run_loop`
- **Calls:** set_event_loop, critical, close, _get_minutes_to_expiry, get_storage, isoformat, new_event_loop, get, uniform, max, monotonic
### `mmm_monitor.py::_heartbeat`
- **Calls:** warning, _heartbeat_inner
### `mmm_monitor.py::_heartbeat_inner`
- **Calls:** next, _get_minutes_to_expiry, check_both_sides_closed, should_block_adjustment, should_pause, get, compute_unrealized_pnl, run_all_checks, isoformat, monotonic
- **State Mutations:** session['both_sides_up_at'] =, session['_margin_block_sells'] =, session['_circuit_state'] =, session['_effective_min_trigger_move'] =, session['last_heartbeat'] =, session['_breakeven_zone'] =, session['strategy_status'] =, session['both_sides_auto'] =, session['_regime_spot_price'] =, session['_atm_wind_down_triggered'] =, session['_last_trigger_result'] =, session['_margin_wind_down'] =, session['_whipsaw_trigger_widened'] =, session['_breakeven_result'] =, session['_atm_close_triggered'] =, session['pnl_history'] =, session['_gamma_zone_prev'] =, session['_atm_shield_fired'] =, session['_heartbeat_counter'] =, session['_beat_health'] =, session['pnl_perp'] =, session['_breakeven_multiplier'] =, session['_wind_down_mode'] =, session['_regime_action'] =, session['_asymmetry_blocked_side'] =, session['_atm_prev_wind_down_enabled'] =, session['stop_reason'] =, session['_breakeven_zone_prev'] =, session['portfolio_delta'] =, session['error_count'] =, session['_gamma_result'] =, session['both_sides_decided_at'] =, session['adjustment_history'] =, session['unrealized_pnl'] =, session['both_sides_decision'] =, params['wind_down_enabled'] =, session['_beat_deadline'] =, session['_walkthrough_log'] =
### `mmm_monitor.py::_process_proactive_wind_down`
- **Calls:** log_activity, _should_stop, _process_wind_down_buyback, info, upper, compute_wind_down_action, get, debug
### `mmm_monitor.py::_process_wind_down_buyback`
- **Calls:** update_trigger_snapshots, sum, log_activity, isoformat, get_lifo_close_fills, append, defaultdict, compute_wind_down_action, get, items
- **State Mutations:** session['realized_pnl'] =, session['updated_at'] =, session['_wind_down_history'] =
### `mmm_monitor.py::_record_fill_from_pending`
- **Calls:** _save_my_session, len, log_activity, recompute_side_lots, isoformat, append, upper, info, get, setdefault
- **State Mutations:** session['adjustment_count'] =, session['adjustment_history'] =, session['updated_at'] =, side_state['_pos_counter'] =, session['last_aggressor'] =, session['total_premium_collected'] =
### `mmm_monitor.py::_process_adjustment`
- **Calls:** _apply_consecutive_dir_limit, log_activity, record_reversal, detect_reversal, check_shift_needed, calculate_lots_to_sell, get, _create_heartbeat_rest_client
### `mmm_monitor.py::_apply_consecutive_dir_limit`
- **Calls:** int, lower, upper, get, max
- **State Mutations:** session['_consecutive_dir_blocked'] =
### `mmm_monitor.py::_update_consecutive_dir_counter`
- **Calls:** pop, lower, upper, get, debug
- **State Mutations:** session['_consecutive_same_dir_count'] =, session['_consecutive_same_dir_side'] =
### `mmm_monitor.py::_proactive_shift_scan`
- **Calls:** log_activity, _process_strike_shift, upper, info, get
### `mmm_monitor.py::_process_strike_shift`
- **Calls:** pop, build_symbol, freeze_current_positions, find_new_strike, calculate_lots_to_sell, get
- **State Mutations:** session['adjustment_count'] =, session['adjustment_history'] =, session['updated_at'] =, session['last_aggressor'] =, session['_last_shift_time'] =, session['shift_count'] =, session['total_premium_collected'] =, session['_strike_shift_otm_multiplier'] =
### `mmm_monitor.py::_process_shift_fallback`
- **Calls:** log_activity, execute_adjustment, setdefault, calculate_lots_to_sell, get, emit_adjustment
### `mmm_monitor.py::_process_harvest`
- **Calls:** _should_stop, scan_harvestable_positions, set, info, close_position, get, _make_fetch_fn
- **State Mutations:** session['harvest_count'] =, session['harvest_lots_freed'] =
### `mmm_monitor.py::_process_scale_up`
- **Calls:** log_activity, check_scale_eligibility, recompute_side_lots, isoformat, find_scale_strikes, append, info, get
- **State Mutations:** session['ce'] =, ce_state['_pos_counter'] =, session['updated_at'] =, pe_state['_pos_counter'] =, session['pe_premium_collected'] =, session['ce_premium_collected'] =, session['pe'] =, session['total_premium_collected'] =
### `mmm_monitor.py::_process_lot_recycling`
- **Calls:** execute_lot_recycling, log_activity, getattr, info, should_block_sell, emit_recycle, get
### `mmm_monitor.py::_shift_time_recycle`
- **Calls:** int, sum, sort, debug, get, _make_fetch_fn, max
### `mmm_monitor.py::_process_close_at_5`
- **Calls:** sum, get_wind_down_close_threshold, log_activity, join, set, scan_closeable_positions, _make_bid_fetch_fn, get, _make_fetch_fn
### `mmm_monitor.py::_auto_decide_both_sides`
- **Calls:** max, info, get, _make_fetch_fn, _strike_key
- **State Mutations:** session['_last_trigger_result'] =
### `mmm_monitor.py::_auto_close_all`
- **Calls:** extend, _close_one_side, log_activity, _should_stop, gather, stop, error, exception, info, get, close_all_perp, is_perp_hedge_enabled
### `mmm_monitor.py::_close_one_side`
- **Calls:** enumerate, recompute_side_lots, isoformat, range, get
- **State Mutations:** session['realized_pnl'] =
### `mmm_monitor.py::_check_margin_guardian`
- **Calls:** critical, log_activity, emit_safety, stop, get, _create_heartbeat_rest_client, check
### `mmm_monitor.py::_get_other_sessions_lots_at_symbol`
- **Calls:** warning, list_sessions, get_storage, add, items, get, get_all_monitors, _count_session_lots_at_symbol
### `mmm_monitor.py::_count_session_lots_at_symbol`
- **Calls:** build_symbol, get
### `mmm_monitor.py::_auto_correct_missing_positions`
- **Calls:** warning, log_activity, recompute_side_lots, now, get, upper, abs, isoformat
### `mmm_monitor.py::_auto_correct_lot_mismatch`
- **Calls:** warning, sum, log_activity, sort, recompute_side_lots, now, get, upper, abs, isoformat
### `mmm_monitor.py::_auto_correct_frozen_mismatch`
- **Calls:** warning, sum, log_activity, sort, recompute_side_lots, now, get, upper, abs, isoformat
### `mmm_monitor.py::_reconcile_exchange_positions`
- **Calls:** pop, set, get, is_perp_hedge_enabled, _create_heartbeat_rest_client
- **State Mutations:** session['last_reconciliation'] =, session['_exchange_sync_cleaned_v2'] =, session['_orphan_adopted_cleaned'] =, session['_recon_counter'] =
### `mmm_monitor.py::_fetch_premiums`
- **Calls:** build_symbol, error, float, _request_with_retry, get, _create_heartbeat_rest_client
### `mmm_monitor.py::_fetch_premiums_with_fallback`
- **Calls:** warning, pop, allow_request, getattr, record_failure, record_success, float, _fetch_premiums, get, _fetch_premiums_orderbook_fallback
- **State Mutations:** session['_pe_premium_stale'] =, session['_ce_premium_stale'] =
### `mmm_monitor.py::_fetch_premiums_orderbook_fallback`
- **Calls:** warning, getattr, build_symbol, gather, get, _create_heartbeat_rest_client
### `mmm_monitor.py::_create_heartbeat_rest_client`
- **Calls:** get, AsyncDeltaClient, get_api_credentials
### `mmm_monitor.py::_start_close_watcher`
- **Calls:** warning, _ep_original, _RealThread, start, get
### `mmm_monitor.py::_run_close_watcher`
- **Calls:** warning, run, _get_minutes_to_expiry, bool, int, wait, _watcher_check_close_threshold, float, get, is_set
### `mmm_monitor.py::_watcher_check_close_threshold`
- **Calls:** any, gather, add, set, get, _create_heartbeat_rest_client
### `mmm_monitor.py::_prefetch_all_premiums`
- **Calls:** getattr, add, set, get, _create_heartbeat_rest_client
### `mmm_monitor.py::_auto_promote_atm_strike`
- **Calls:** _save_my_session, log_activity, recompute_side_lots, float, upper, info, get, _fetch_spot_price, max
- **State Mutations:** side_state['active_strike'] =
### `mmm_monitor.py::_fetch_spot_price`
- **Calls:** get_spot_price
### `mmm_monitor.py::_make_fetch_fn`
- **Calls:** warning, float, getattr
### `mmm_monitor.py::_make_bid_fetch_fn`
- **Calls:** warning, float, getattr
### `mmm_monitor.py::_get_minutes_to_expiry`
- **Calls:** total_seconds, fromisoformat, now, expiry_to_utc_datetime, replace, get, max
### `mmm_monitor.py::_update_analytics_exposure`
- **Calls:** setdefault, isoformat, get, now
### `mmm_monitor.py::_update_analytics_pnl_milestones`
- **Calls:** total_seconds, fromisoformat, isoformat, now, get, replace, setdefault
### `mmm_monitor.py::_update_analytics_delta`
- **Calls:** isoformat, now, get, abs, setdefault
### `mmm_monitor.py::_calculate_portfolio_delta`
- **Calls:** fetch_all, AsyncDeltaClient, len, isinstance, get_api_credentials, list, get_initializer, get
### `mmm_monitor.py::_emit_heartbeat_data`
- **Calls:** getattr, emit_heartbeat, items, get, _strike_key
- **State Mutations:** session['_premium_map'] =
### `mmm_monitor.py::_execute_close`
- **Calls:** smart_execute, get, emergency_execute
### `mmm_monitor.py::_check_one`
- **Calls:** build_symbol, get, float, _request_with_retry
### `mmm_monitor.py::fetch`
- **Calls:** warning, float
### `mmm_monitor.py::_mid`
- **Calls:** _request_with_retry, get, float
### `mmm_monitor.py::_fetch_one`
- **Calls:** warning, build_symbol, float, _request_with_retry, get
### `mmm_monitor.py::fetch_all`
- **Calls:** build_symbol, zip, gather, list, append, _request_with_retry
### `mmm_monitor.py::_safe_greek`
- **Calls:** isinstance, float
### `mmm_heartbeat_health.py::__init__`
- **Calls:** deque, max, monotonic, RLock
### `mmm_heartbeat_health.py::record_beat`
- **Calls:** warning, _check_stale, BeatRecord, append, monotonic
### `mmm_heartbeat_health.py::record_miss`
- **Calls:** record_beat
### `mmm_heartbeat_health.py::latency_p50`
- **Calls:** list, median
### `mmm_heartbeat_health.py::latency_p95`
- **Calls:** min, int, len, sort, list
### `mmm_heartbeat_health.py::latency_max`
- **Calls:** list, max
### `mmm_heartbeat_health.py::miss_rate_pct`
- **Calls:** list, len, sum
### `mmm_heartbeat_health.py::failure_count_recent`
- **Calls:** list, sum
### `mmm_heartbeat_health.py::seconds_since_last_ok`
- **Calls:** monotonic
### `mmm_heartbeat_health.py::seconds_since_last_beat`
- **Calls:** monotonic
### `mmm_heartbeat_health.py::summary`
- **Calls:** isoformat, now, list, round, get, monotonic, grade
### `mmm_observer.py::get_observer`
- **Calls:** MMMStrategyObserver
### `mmm_observer.py::__init__`
- **Calls:** Lock
### `mmm_observer.py::validate_close`
- **Calls:** _check_price_consistency, warning, upper, get, _check_ledger_integrity, check
### `mmm_observer.py::record_close`
- **Calls:** deque, timestamp, append, now
### `mmm_observer.py::clear_session`
- **Calls:** pop
### `mmm_observer.py::_check_price_consistency`
- **Calls:** warning, get, round, upper
### `mmm_observer.py::_check_ledger_integrity`
- **Calls:** get, upper
### `mmm_initializer.py::expiry_to_utc_datetime`
- **Calls:** get, isoformat, strptime, replace
### `mmm_initializer.py::normalize_expiry`
- **Calls:** len, ValueError, isdigit, strftime, str, strptime, strip
### `mmm_initializer.py::get_initializer`
- **Calls:** MMMInitializer
### `mmm_initializer.py::chain_service`
- **Calls:** OptionsChainService, error
### `mmm_initializer.py::get_spot_price`
- **Calls:** _get_spot_price
### `mmm_initializer.py::get_available_expiries`
- **Calls:** get_expirations
### `mmm_initializer.py::get_full_chain`
- **Calls:** normalize_expiry, len, _get_moneyness, append, exception, _enrich_option, str, get, get_chain_data
### `mmm_initializer.py::preview_strikes`
- **Calls:** normalize_expiry, _rank_strikes, exception, str, get, get_chain_data
### `mmm_initializer.py::validate_manual_selection`
- **Calls:** normalize_expiry, get_option_ticker, len, _extract_ticker_data, get_spot_price, append
### `mmm_initializer.py::build_symbol`
- **Calls:** str, int, expiry_to_symbol_suffix
### `mmm_initializer.py::_rank_strikes`
- **Calls:** sort, build_symbol, append, round, abs, get
### `mmm_initializer.py::_enrich_option`
- **Calls:** get, round
### `mmm_initializer.py::_get_moneyness`
- **Calls:** abs
### `mmm_initializer.py::_extract_ticker_data`
- **Calls:** get, float, round, split
### `mmm_initializer.py::check_liquidity`
- **Calls:** error, get, get_option_ticker
### `mmm_initializer.py::calculate_lots_with_buffer`
- **Calls:** warn, ceil
### `mmm_circuit_breaker.py::__init__`
- **Calls:** deque, RLock
### `mmm_circuit_breaker.py::allow_request`
- **Calls:** info, min, monotonic
### `mmm_circuit_breaker.py::record_success`
- **Calls:** append, monotonic, info
### `mmm_circuit_breaker.py::record_failure`
- **Calls:** _trip, append, max, monotonic
### `mmm_circuit_breaker.py::_trip`
- **Calls:** warning, monotonic
### `mmm_circuit_breaker.py::reset_timeout`
- **Calls:** min
### `mmm_circuit_breaker.py::seconds_until_probe`
- **Calls:** max, monotonic
### `mmm_circuit_breaker.py::_get_window_stats`
- **Calls:** len, sum, lower, get, monotonic
### `mmm_circuit_breaker.py::window_stats`
- **Calls:** _get_window_stats
### `mmm_circuit_breaker.py::reset`
- **Calls:** clear, info, _get_window_stats
### `mmm_circuit_breaker.py::summary`
- **Calls:** _get_window_stats
### `mmm_activity.py::get_activity_log`
- **Calls:** MMMActivityLog
### `mmm_activity.py::log_activity`
- **Calls:** get_activity_log, add
### `mmm_activity.py::resolve_progress_activities`
- **Calls:** resolve_progress, get_activity_log
### `mmm_activity.py::__init__`
- **Calls:** _load_from_disk, makedirs, dirname, deque, RLock
### `mmm_activity.py::_load_from_disk`
- **Calls:** warning, len, open, append, get, info, exists, load
### `mmm_activity.py::_should_persist`
- **Calls:** get
### `mmm_activity.py::_save_to_disk`
- **Calls:** warning, dump, unlink, mkstemp, fdopen, dirname, isoformat, fsync, error, list, fileno, flush, rename, _should_persist, exists
### `mmm_activity.py::add`
- **Calls:** emit_activity, warning, total_seconds, len, getattr, isoformat, now, append, get, strftime, _save_to_disk, items
### `mmm_activity.py::get_recent`
- **Calls:** list, get, reverse
### `mmm_activity.py::clear`
- **Calls:** _save_to_disk, clear, append, get
### `mmm_activity.py::resolve_progress`
- **Calls:** len, emit_activities_updated, append, clear, get, info, _save_to_disk, should_keep
### `mmm_activity.py::should_keep`
- **Calls:** get
### `mmm_dte_presets.py::get_preset`
- **Calls:** get
### `mmm_dte_presets.py::list_presets`
- **Calls:** get, append, items
### `mmm_dte_presets.py::apply_preset`
- **Calls:** warning, get_preset, update
### `mmm_dte_presets.py::compute_total_dte_hours`
- **Calls:** total_seconds, int, now, error, datetime
### `mmm_dte_presets.py::check_aggregate_pnl`
- **Calls:** min, len, round, abs, get
### `mmm_dte_presets.py::check_chain_liquidity`
- **Calls:** get
### `mmm_constants.py::_D`
- **Calls:** str, Decimal
### `mmm_constants.py::strike_key`
- **Calls:** str, round, float, int
### `__init__.py::init_mmm`
- **Calls:** get_storage, get_instance, get_active_session_ids, getLogger, info, get_session_count, start, print
### `mmm_margin_guardian.py::tier_severity`
- **Calls:** index
### `mmm_margin_guardian.py::get_margin_param_defaults`
- **Calls:** dict
### `mmm_margin_guardian.py::fetch_margin_utilization`
- **Calls:** update, isinstance, time, float, upper, hasattr
### `mmm_margin_guardian.py::evaluate_margin_tier`
- **Calls:** get, round, max
### `mmm_margin_guardian.py::estimate_lots_to_close`
- **Calls:** min, sum, ceil, get, max
### `mmm_margin_guardian.py::check`
- **Calls:** warning, estimate_lots_to_close, fetch_margin_utilization, list, error, append, get, evaluate_margin_tier
### `mmm_telegram.py::_get_telegram_credentials`
- **Calls:** str, debug, getattr, get_config
### `mmm_telegram.py::_get_notifier`
- **Calls:** TelegramNotifier, debug, _get_telegram_credentials
### `mmm_telegram.py::_should_send`
- **Calls:** get, time
### `mmm_telegram.py::_send_async`
- **Calls:** warning, _should_send, _send_message, info, _get_notifier, debug
### `mmm_telegram.py::alert_margin_tier_change`
- **Calls:** get, _send_async, now, strftime
### `mmm_telegram.py::alert_emergency_close`
- **Calls:** _send_async, now, strftime
### `mmm_telegram.py::alert_session_stopped`
- **Calls:** _send_async, now, strftime
### `mmm_telegram.py::alert_rapid_check_activated`
- **Calls:** _send_async, now, strftime
### `mmm_telegram.py::alert_max_loss_breach`
- **Calls:** _send_async, now, abs, strftime
### `mmm_telegram.py::alert_both_sides_up`
- **Calls:** _send_async, now, strftime
### `mmm_api.py::_run_async`
- **Calls:** set_event_loop, close, DefaultEventLoopPolicy, new_event_loop, run_until_complete
### `mmm_api.py::_check_guardian_signal`
- **Calls:** get_signal
### `mmm_api.py::get_dte_presets`
- **Calls:** list_presets, jsonify, route, exception, str, items
### `mmm_api.py::get_aggregate_pnl`
- **Calls:** list_sessions, jsonify, check_aggregate_pnl, get_storage, route, exception, str, get
### `mmm_api.py::list_sessions`
- **Calls:** list_sessions, jsonify, len, get_storage, route, lower, exception, str, get, list_session_summaries
### `mmm_api.py::get_session`
- **Calls:** jsonify, get_session, get_storage, get_session_summary, route, lower, exception, str, get
### `mmm_api.py::create_session_endpoint`
- **Calls:** _invalidate_sessions_cache, get_session, get_storage, validate_params, create_session, emit_session_created, get_json, route, info, save_session, get
- **State Mutations:** session['entry_time'] =
### `mmm_api.py::delete_session`
- **Calls:** delete_session, _invalidate_sessions_cache, get_activity_log, emit_session_deleted, jsonify, get_session, get_storage, route, clear, exception, info, get
### `mmm_api.py::start_session`
- **Calls:** _check_pre_entry_conditions, start_session_monitor, get_session, get_storage, log_activity, emit_status_change, route, update_session, info, _check_guardian_signal, get
### `mmm_api.py::_check_pre_entry_conditions`
- **Calls:** len, now, abs, replace, get
### `mmm_api.py::_execute_entry_background`
- **Calls:** get_session, get_storage, isoformat, setdefault, strike_key, get
- **State Mutations:** session['strategy_status'] =, session['last_heartbeat'] =, session['initial_total_premium'] =, session['entry_time'] =, session['pe_premium_collected'] =, session['ce_premium_collected'] =, session['partial_entry'] =, session['total_premium_collected'] =, session['actual_total_premium'] =, session['execution_timestamp'] =
### `mmm_api.py::resolve_partial_entry`
- **Calls:** pop, get_session, get_storage, isoformat, emit_status_change, route, save_session, _check_guardian_signal, strike_key, get
- **State Mutations:** session['strategy_status'] =, session['last_heartbeat'] =, session['entry_time'] =, session['pe_premium_collected'] =, session['ce_premium_collected'] =, session['total_premium_collected'] =, session['actual_total_premium'] =, session['execution_timestamp'] =
### `mmm_api.py::retry_partial_leg`
- **Calls:** jsonify, get_session, get_storage, log_activity, Thread, route, exception, _check_guardian_signal, start, get
### `mmm_api.py::_retry_partial_leg_background`
- **Calls:** pop, get_session, get_storage, log_activity, isoformat, emit_status_change, upper, save_session, strike_key, get
- **State Mutations:** session['strategy_status'] =, session['last_heartbeat'] =, session['entry_time'] =, session['pe_premium_collected'] =, session['ce_premium_collected'] =, session['total_premium_collected'] =, session['actual_total_premium'] =, session['execution_timestamp'] =
### `mmm_api.py::pause_session`
- **Calls:** jsonify, get_session, get_storage, pause_session_monitor, emit_status_change, route, update_session, exception, info, str, get
### `mmm_api.py::resume_session`
- **Calls:** pop, get_session, get_storage, isoformat, get_monitor, emit_status_change, route, info, save_session, _check_guardian_signal, get
- **State Mutations:** session['strategy_status'] =, session['_watchdog_restarts'] =, session['last_heartbeat'] =
### `mmm_api.py::stop_session`
- **Calls:** jsonify, get_session, get_storage, isoformat, get_json, emit_status_change, route, update_session, exception, info, get, stop_session_monitor
### `mmm_api.py::both_sides_decision`
- **Calls:** jsonify, get_session, get_storage, isoformat, get_json, emit_status_change, route, append, update_session, info, get
### `mmm_api.py::get_params_info`
- **Calls:** jsonify, get_hot_reload_params, route, list, exception, str, get_param_info
### `mmm_api.py::get_session_margin_status`
- **Calls:** _run_async, AsyncDeltaClient, jsonify, get_session, get_storage, fetch_margin_utilization, get_monitor, get_api_credentials, route, hasattr, get, evaluate_margin_tier
### `mmm_api.py::get_exchange_margin`
- **Calls:** _run_async, AsyncDeltaClient, jsonify, sort, fetch_margin_utilization, isinstance, get_api_credentials, _fetch_all, route, float, get, get_positions_margined
### `mmm_api.py::get_session_params`
- **Calls:** jsonify, get_session, get_storage, route, exception, str, get
### `mmm_api.py::update_session_params`
- **Calls:** warning, jsonify, get_session, get_storage, dict, emit_params_changed, validate_params, get_json, route, update_session, set, info, get, items
### `mmm_api.py::get_session_history`
- **Calls:** int, jsonify, get_session, get_storage, len, get_session_summary, route, exception, str, get
### `mmm_api.py::get_session_state`
- **Calls:** jsonify, get_session, get_storage, route, exception, get
### `mmm_api.py::health_check`
- **Calls:** jsonify, len, get_storage, get_active_session_ids, now, route, exception, get_session_count, str, isoformat
### `mmm_api.py::get_activities`
- **Calls:** min, get_activity_log, int, jsonify, len, get_recent, route, exception, str, get
### `mmm_api.py::get_expiries`
- **Calls:** jsonify, route, get_available_expiries, exception, get_initializer, str, get
### `mmm_api.py::get_spot_price`
- **Calls:** jsonify, get_spot_price, route, exception, get_initializer, str, get
### `mmm_api.py::preview_strikes`
- **Calls:** jsonify, get_json, route, float, get_initializer, exception, preview_strikes, get
### `mmm_api.py::check_liquidity`
- **Calls:** int, jsonify, get_json, check_liquidity, route, exception, get_initializer, str, get
### `mmm_api.py::init_session_fresh`
- **Calls:** normalize_expiry, initialize_side_from_entry, int, get_session, get_storage, get_json, route, float, expiry_to_utc_datetime, get
- **State Mutations:** session['lots'] =, session['entry_mode'] =, session['initial_total_premium'] =, session['entry_time'] =, session['updated_at'] =, session['expiry'] =, session['expiry_time'] =
### `mmm_api.py::init_session_import`
- **Calls:** normalize_expiry, initialize_side_from_entry, int, get_session, get_storage, get_json, route, float, expiry_to_utc_datetime, get
- **State Mutations:** session['lots'] =, session['entry_mode'] =, session['initial_total_premium'] =, session['entry_time'] =, session['updated_at'] =, session['expiry'] =, session['expiry_time'] =
### `mmm_api.py::get_exchange_positions`
- **Calls:** normalize_expiry, fetch_exchange_btc_options, jsonify, route, exception, str, get
### `mmm_api.py::adopt_positions`
- **Calls:** normalize_expiry, enumerate, build_adopted_session_state, get_session, get_storage, get_json, route, validate_adoptable, classify_positions, save_session, get
### `mmm_api.py::get_chain_data`
- **Calls:** jsonify, route, get_full_chain, exception, get_initializer, str, get
### `mmm_api.py::validate_selection`
- **Calls:** int, jsonify, all, get_json, route, validate_manual_selection, exception, get_initializer, get
### `mmm_api.py::execute_entry`
- **Calls:** _run_async, get_executor, get_session, get_storage, jsonify, execute_entry, route, _check_guardian_signal, get
- **State Mutations:** session['updated_at'] =, session['actual_total_premium'] =, session['execution_timestamp'] =
### `mmm_api.py::get_monitor_status`
- **Calls:** jsonify, get_monitor, route, exception, str, get
### `mmm_api.py::list_monitors`
- **Calls:** jsonify, len, route, exception, str, get_all_monitors, items
### `mmm_api.py::reduce_position`
- **Calls:** _run_async, int, get_executor, get_session, get_storage, jsonify, isoformat, route, lower, get_initializer, info, save_session, get
- **State Mutations:** session['realized_pnl'] =, session['updated_at'] =, session['manual_reduction_pnl'] =
### `mmm_api.py::inject_position`
- **Calls:** int, bool, get_session, get_storage, get_executor, route, lower, float, get_initializer, get
- **State Mutations:** session['adjustment_history'] =, session['updated_at'] =, session['total_premium_collected'] =, side_state['_pos_counter'] =
### `mmm_api.py::set_active_strike`
- **Calls:** sum, get_session, get_storage, get_executor, route, lower, float, get_initializer, get
- **State Mutations:** side_state['active_strike_pinned'] =, side_state['active_strike'] =, session['updated_at'] =
### `mmm_api.py::close_strike_route`
- **Calls:** sum, get_session, get_storage, get_executor, route, lower, float, get_initializer, _check_guardian_signal, get
- **State Mutations:** session['total_realized_pnl'] =, session['updated_at'] =, side_state['active_strike'] =
### `mmm_api.py::reconcile_session`
- **Calls:** _run_async, jsonify, get_session, get_storage, isoformat, get_monitor, route, force_heartbeat, exception, get
- **State Mutations:** session['last_reconciliation'] =
### `mmm_api.py::force_heartbeat`
- **Calls:** jsonify, get_monitor, route, force_heartbeat, exception, str
### `mmm_api.py::get_positions`
- **Calls:** jsonify, get_session, get_storage, route, append, exception, upper, get
### `mmm_api.py::get_exchange_positions_direct`
- **Calls:** _run_async, AsyncDeltaClient, jsonify, fetch, isinstance, get_api_credentials, route, append, float, exception, _request_with_retry, get
### `mmm_api.py::get_exchange_orders`
- **Calls:** _run_async, AsyncDeltaClient, jsonify, len, fetch, isinstance, get_api_credentials, route, append, exception, _request_with_retry, get
### `mmm_api.py::get_triggers`
- **Calls:** jsonify, get_session, get_storage, route, exception, str, get
### `mmm_api.py::get_pnl_timeline`
- **Calls:** jsonify, get_session, get_storage, len, route, exception, get
### `mmm_api.py::get_safety_status`
- **Calls:** jsonify, get_session, get_storage, route, exception, get
### `mmm_api.py::get_breakeven`
- **Calls:** jsonify, get_session, get_storage, route, exception, str, get
### `mmm_api.py::get_gamma`
- **Calls:** jsonify, get_session, get_storage, route, exception, str, get
### `mmm_api.py::get_walkthrough`
- **Calls:** jsonify, build_full_walkthrough, get_storage, get_session, route, exception, str
### `mmm_api.py::get_beat_health`
- **Calls:** jsonify, get_session, get_storage, get_monitor, get_instance, route, summary, get, hasattr, status
### `mmm_api.py::get_regime_status`
- **Calls:** jsonify, get_session, get_storage, route, exception, get, get_regime_status, MMMRegimeEngine
### `mmm_api.py::get_greeks_iv`
- **Calls:** _run_async, AsyncDeltaClient, jsonify, get_session, get_storage, sort, get_api_credentials, route, get_initializer, upper, get
### `mmm_api.py::_safe_float`
- **Calls:** float
### `mmm_api.py::get_session_analytics`
- **Calls:** jsonify, get_session, get_storage, get_analytics_storage, route, get_session_analytics, get
### `mmm_api.py::get_analytics_history`
- **Calls:** min, jsonify, len, get_all_analytics, get_analytics_storage, route, exception, str, get
### `mmm_api.py::get_aggregated_analytics`
- **Calls:** jsonify, get_aggregator, route, exception, str, get_aggregated_analytics
### `mmm_api.py::get_hedge_status`
- **Calls:** jsonify, get_session, get_storage, route, exception, get, get_perp_summary
### `mmm_api.py::toggle_hedge`
- **Calls:** bool, jsonify, get_session, get_storage, emit_params_changed, get_monitor, get_json, route, update_session, info, hasattr, get
- **State Mutations:** params['perp_hedge_enabled'] =
### `mmm_api.py::close_hedge`
- **Calls:** jsonify, get_session, get_storage, getattr, result, get_monitor, get_json, route, is_closed, save_session, get, close_all_perp, run_coroutine_threadsafe
### `mmm_api.py::get_aggregate_metrics`
- **Calls:** list_sessions, jsonify, getattr, get_storage, get_instance, get_monitor, route, append, exception, get, status
### `mmm_api.py::emergency_stop_all`
- **Calls:** list_sessions, jsonify, log_activity, get_storage, len, get_monitor, get_json, route, exception, get
- **State Mutations:** session['strategy_status'] =, session['_emergency_stop'] =
### `mmm_api.py::emergency_health_check`
- **Calls:** active_count, list_sessions, jsonify, all, get_storage, get_ws_health, any, len, get_instance, route, round, exception, memory_info, status, Process
### `mmm_api.py::emergency_pause_all`
- **Calls:** list_sessions, jsonify, log_activity, get_storage, len, get_json, route, append, exception, save_session, get
- **State Mutations:** session['_emergency_pause'] =, session['strategy_status'] =
### `mmm_api.py::emergency_close_all_positions`
- **Calls:** set_event_loop, close, jsonify, log_activity, get_storage, get_json, route, new_event_loop, run_until_complete, get, get_all_monitors, items
### `mmm_api.py::emergency_reset_circuit`
- **Calls:** reset, jsonify, getattr, log_activity, get_monitor, get_json, route, summary, exception, str, get
### `mmm_api.py::clear_session_backoff`
- **Calls:** clear_backoff, jsonify, get_session, get_storage, get_instance, get_json, route, exception, save_session, str, get
- **State Mutations:** session['_watchdog_restarts'] =
### `mmm_api.py::get_audit_trail`
- **Calls:** min, get_activity_log, int, jsonify, len, fromisoformat, get_recent, route, exception, get, split
### `mmm_api.py::export_audit_trail`
- **Calls:** dumps, pop, list_sessions, get_activity_log, len, get_storage, status, get_recent, get_instance, isoformat, route, lower, exception, make_response, get
### `mmm_api.py::get_pnl_curve`
- **Calls:** min, jsonify, get_breakeven_engine, getattr, get_storage, get_monitor, range, route, round, hasattr, _collect_open_positions, get, max, _compute_scan_range
### `mmm_api.py::_fetch_all`
- **Calls:** fetch_margin_utilization, isinstance, gather, str, get_positions_margined
### `mmm_api.py::_do_reduce`
- **Calls:** min, build_symbol, range, get_lifo_close_fills, list, append, float, defaultdict, get, items
- **State Mutations:** session['realized_pnl'] =, session['manual_reduction_pnl'] =
### `mmm_api.py::fetch`
- **Calls:** _request_with_retry, get
### `mmm_api.py::fetch_all`
- **Calls:** build_symbol, zip, gather, list, append, _request_with_retry
### `mmm_api.py::close_session_positions`
- **Calls:** _auto_close_all, error, append, str, get
### `mmm_api.py::_fetch_premiums`
- **Calls:** _ge, build_symbol, _gi, get, get_mid_price
### `mmm_api.py::_fetch_other_mid`
- **Calls:** get_mid_price
### `mmm_api.py::_fetch_both`
- **Calls:** get_mid_price
### `mmm_api.py::_fetch_snap`
- **Calls:** build_symbol, get_mid_price, abs
### `mmm_api.py::run_recon`
- **Calls:** _save_my_session, _reconcile_exchange_positions
### `mmm_adopter.py::fetch_exchange_btc_options`
- **Calls:** _req, int, sort, get_spot_price, add, DeltaClient, float, set, get_initializer, info, get, split
### `mmm_adopter.py::classify_positions`
- **Calls:** upper, _classify_side
### `mmm_adopter.py::_classify_side`
- **Calls:** min, len, lower, abs, get, max
### `mmm_adopter.py::validate_adoptable`
- **Calls:** list_sessions, sum, get_storage, append, get
### `mmm_adopter.py::build_adopted_session_state`
- **Calls:** isoformat, max, round, get
- **State Mutations:** session['lots'] =, session['adopted_at'] =, side_state['trigger_snapshot'] =, session['entry_mode'] =, session['initial_total_premium'] =, session['entry_time'] =, session['updated_at'] =, side_state['positions'] =, side_state['symbol'] =, session['analytics'] =, side_state['active_strike'] =, side_state['_pos_counter'] =, session['pe_premium_collected'] =, session['adoption_snapshot'] =, session['expiry'] =, session['ce_premium_collected'] =, session['total_premium_collected'] =, session['expiry_time'] =
### `mmm_engine.py::_D`
- **Calls:** str, Decimal
### `mmm_engine.py::get_engine`
- **Calls:** MMMEngine
### `mmm_engine.py::executor`
- **Calls:** get_executor
### `mmm_engine.py::initializer`
- **Calls:** get_initializer
### `mmm_engine.py::calculate_standard_loss`
- **Calls:** warning, _D, info, strike_key, get
- **State Mutations:** session['_fetch_error_count'] =
### `mmm_engine.py::calculate_reversal_loss`
- **Calls:** warning, _D, float, info, get
### `mmm_engine.py::calculate_lots_to_sell`
- **Calls:** get, max
- **State Mutations:** session['_trend_boost_mult'] =, session['_trend_boost_active'] =
### `mmm_engine.py::execute_adjustment`
- **Calls:** warning, build_symbol, _update_state_after_adjustment, error, exception, register_pending, info, upper, smart_execute, get
### `mmm_engine.py::_update_state_after_adjustment`
- **Calls:** update_trigger_snapshots, len, recompute_side_lots, isoformat, append, setdefault, upper, info, get
- **State Mutations:** session['adjustment_count'] =, session['adjustment_history'] =, session['updated_at'] =, session['last_aggressor'] =, session['total_premium_collected'] =
### `mmm_engine.py::compute_unrealized_pnl`
- **Calls:** pop, _D, error, float, get
- **State Mutations:** session['_pnl_calculation_incomplete'] =, session['_pnl_fetch_errors'] =
### `mmm_engine.py::compute_total_pnl`
- **Calls:** get, round, compute_unrealized_pnl
### `mmm_engine.py::reconcile_pnl`
- **Calls:** warning, get, abs, compute_total_pnl
- **State Mutations:** session['unrealized_pnl'] =
### `mmm_strike_shift.py::check_shift_needed`
- **Calls:** get, upper, max, info
### `mmm_strike_shift.py::freeze_current_positions`
- **Calls:** pop, recompute_side_lots, isoformat, _migrate_side_to_positions, now, info, get, _strike_key
### `mmm_strike_shift.py::find_new_strike`
- **Calls:** sort, error, get_full_chain, info, get, max
### `mmm_strike_shift.py::activate_new_strike`
- **Calls:** pop, recompute_side_lots, build_symbol, isoformat, append, setdefault, get_initializer, info, get, _strike_key
- **State Mutations:** side_state['_initial_hedge_premium'] =, session['updated_at'] =, side_state['symbol'] =, side_state['_pos_counter'] =, side_state['active_strike'] =
### `mmm_scaler.py::check_scale_eligibility`
- **Calls:** get
### `mmm_scaler.py::find_scale_strikes`
- **Calls:** int, add, get_full_chain, set, get, max
### `mmm_scaler.py::record_scale_event`
- **Calls:** len, now, append, setdefault, get, isoformat
- **State Mutations:** session['scale_count'] =, session['_last_scale_at'] =, session['scale_history'] =
### `mmm_breakeven_engine.py::get_breakeven_engine`
- **Calls:** BreakevenEngine
### `mmm_breakeven_engine.py::__init__`
- **Calls:** Lock
### `mmm_breakeven_engine.py::compute_breakeven`
- **Calls:** _hash_positions, _find_breakeven, _empty_result, _build_result, _collect_open_positions, get, _compute_band_width_pct, _compute_scan_range
### `mmm_breakeven_engine.py::get_aggression_multiplier`
- **Calls:** get
### `mmm_breakeven_engine.py::invalidate_cache`
- **Calls:** pop
### `mmm_breakeven_engine.py::_collect_open_positions`
- **Calls:** get, append
### `mmm_breakeven_engine.py::_compute_pnl_at_spot`
- **Calls:** get, max
### `mmm_breakeven_engine.py::_compute_scan_range`
- **Calls:** get, max, abs
### `mmm_breakeven_engine.py::_find_breakeven`
- **Calls:** int, _compute_pnl_at_spot, range, abs, max
### `mmm_breakeven_engine.py::_classify_zone`
- **Calls:** get
### `mmm_breakeven_engine.py::_compute_multiplier`
- **Calls:** get, max, min
### `mmm_breakeven_engine.py::_build_result`
- **Calls:** _compute_multiplier, bool, sum, _compute_dte_scale, _compute_pnl_at_spot, get, _classify_zone, _compute_band_width_pct
### `mmm_breakeven_engine.py::_empty_result`
- **Calls:** isoformat, now
### `mmm_breakeven_engine.py::_compute_dte_scale`
- **Calls:** min, fromisoformat, isinstance, now, round, replace, get, max, sqrt
### `mmm_breakeven_engine.py::_hash_positions`
- **Calls:** md5, encode, hexdigest, join, sorted, append, get
### `mmm_wind_down.py::is_wind_down_active`
- **Calls:** warning, total_seconds, fromisoformat, now, expiry_to_utc_datetime, replace, get
### `mmm_wind_down.py::get_wind_down_status`
- **Calls:** warning, total_seconds, fromisoformat, now, round, expiry_to_utc_datetime, replace, get, max
### `mmm_wind_down.py::compute_wind_down_action`
- **Calls:** min, upper, info, get, floor, max
### `mmm_wind_down.py::get_lifo_close_fills`
- **Calls:** min, _migrate_side_to_positions, append, get, reversed
### `mmm_wind_down.py::apply_lifo_removals`
- **Calls:** recompute_side_lots, deepcopy, now, error, get, isoformat, max
- **State Mutations:** side_state['positions'] =
### `mmm_wind_down.py::get_wind_down_close_threshold`
- **Calls:** get, is_wind_down_active
### `mmm_storage.py::get_storage`
- **Calls:** MMMStorage
### `mmm_storage.py::__init__`
- **Calls:** _migrate_from_json, makedirs, dirname, _init_db
### `mmm_storage.py::_get_conn`
- **Calls:** execute, connect
### `mmm_storage.py::_init_db`
- **Calls:** close, _get_conn, execute, error, info, commit
### `mmm_storage.py::_migrate_from_json`
- **Calls:** close, _get_conn, open, fetchone, error, get, info, rename, commit, exists, items, load
### `mmm_storage.py::_row_to_session`
- **Calls:** loads, _backfill_session_side_premiums
- **State Mutations:** session['params'] =
### `mmm_storage.py::_backfill_session_side_premiums`
- **Calls:** get, round, upper
### `mmm_storage.py::_calculate_checksum`
- **Calls:** dumps, encode, hexdigest, get, sha256
### `mmm_storage.py::_validate_checksum`
- **Calls:** warning, get, _calculate_checksum
### `mmm_storage.py::save_session`
- **Calls:** dumps, close, _get_conn, ValueError, execute, isoformat, now, error, commit, _calculate_checksum, get, debug
- **State Mutations:** session['updated_at'] =, session['_checksum'] =
### `mmm_storage.py::get_session`
- **Calls:** critical, _row_to_session, pop, close, _get_conn, _validate_checksum, execute, fetchone, error
- **State Mutations:** session['_checksum_warning'] =
### `mmm_storage.py::list_sessions`
- **Calls:** _row_to_session, close, _get_conn, execute, error, fetchall
### `mmm_storage.py::delete_session`
- **Calls:** close, _get_conn, execute, error, info, commit
### `mmm_storage.py::update_session`
- **Calls:** pop, _row_to_session, close, _get_conn, isinstance, execute, fetchone, error, get, commit, _calculate_checksum, isoformat, items
- **State Mutations:** session['updated_at'] =, session['_checksum'] =
### `mmm_storage.py::get_active_session_ids`
- **Calls:** close, _get_conn, execute, error, fetchall
### `mmm_storage.py::list_session_summaries`
- **Calls:** list_sessions, close, _get_conn, execute, error, append, _get_side_premium, _row_to_summary_fallback, fetchall
### `mmm_storage.py::_get_side_premium`
- **Calls:** isinstance, loads, round, upper, get, max
### `mmm_storage.py::_row_to_summary_fallback`
- **Calls:** get
### `mmm_storage.py::get_session_count`
- **Calls:** close, _get_conn, execute, fetchone, error
### `mmm_perp_hedge.py::_D`
- **Calls:** str, Decimal
### `mmm_perp_hedge.py::get_perp_state`
- **Calls:** _init_perp_state
- **State Mutations:** session['perp_hedge'] =
### `mmm_perp_hedge.py::is_perp_hedge_enabled`
- **Calls:** get
### `mmm_perp_hedge.py::compute_required_hedge`
- **Calls:** int, info, abs, get_perp_state, get, debug
### `mmm_perp_hedge.py::_is_cooldown_active`
- **Calls:** warning, total_seconds, fromisoformat, now, replace, get_perp_state, get
### `mmm_perp_hedge.py::update_perp_state_after_fill`
- **Calls:** isoformat, now, float, info, abs, get_perp_state, get
### `mmm_perp_hedge.py::update_perp_mark_pnl`
- **Calls:** get_perp_state, get, float, _D
### `mmm_perp_hedge.py::_execute_hedge_order`
- **Calls:** warning, critical, range, upper, info, smart_execute, get, str, sleep
### `mmm_perp_hedge.py::_check_flip_rate`
- **Calls:** total_seconds, len, fromisoformat, now, setdefault, append, timedelta, replace, get
### `mmm_perp_hedge.py::_record_flip`
- **Calls:** setdefault, append, isoformat, now
### `mmm_perp_hedge.py::run_perp_hedge`
- **Calls:** warning, update_perp_mark_pnl, update_perp_state_after_fill, debug, _is_cooldown_active, is_perp_hedge_enabled, get, _check_flip_rate, compute_required_hedge, _emit_perp_events
### `mmm_perp_hedge.py::close_all_perp`
- **Calls:** critical, update_perp_state_after_fill, emit_safety, _execute_hedge_order, upper, info, abs, get_perp_state, get
### `mmm_perp_hedge.py::get_perp_total_pnl`
- **Calls:** get
### `mmm_perp_hedge.py::get_perp_summary`
- **Calls:** get, is_perp_hedge_enabled
### `mmm_perp_hedge.py::_emit_perp_events`
- **Calls:** emit_perp_hedge_execution, emit_perp_hedge_flip, abs, get_perp_state, get
### `mmm_walkthrough.py::_to_ist`
- **Calls:** fromisoformat, astimezone, strftime, replace
### `mmm_walkthrough.py::_to_ist_short`
- **Calls:** fromisoformat, astimezone, strftime, replace
### `mmm_walkthrough.py::generate_entry_walkthrough`
- **Calls:** get
### `mmm_walkthrough.py::generate_heartbeat_walkthrough`
- **Calls:** get, append, isoformat, max
### `mmm_walkthrough.py::build_full_walkthrough`
- **Calls:** get, generate_entry_walkthrough, append
### `mmm_walkthrough.py::_build_reconstructed_summary`
- **Calls:** append, get, join
### `mmm_walkthrough.py::_ts_diff`
- **Calls:** fromisoformat, total_seconds, abs, replace
### `mmm_guardian.py::get_guardian`
- **Calls:** get
### `mmm_guardian.py::register_guardian`
- **Calls:** debug
### `mmm_guardian.py::deregister_guardian`
- **Calls:** pop, debug
### `mmm_guardian.py::pre_beat_snapshot`
- **Calls:** get, monotonic
### `mmm_guardian.py::check_close_allowed`
- **Calls:** warning, get, upper, check_beat_velocity
### `mmm_guardian.py::record_close`
- **Calls:** get
### `mmm_guardian.py::check_beat_velocity`
- **Calls:** get, values, sum
### `mmm_guardian.py::_check_side_balance`
- **Calls:** get, upper
### `mmm_guardian.py::get_beat_deadline`
- **Calls:** get
### `mmm_guardian.py::is_deadline_exceeded`
- **Calls:** monotonic
### `mmm_guardian.py::post_beat_check`
- **Calls:** warning, values, sum, _check_side_balance, append, get
### `mmm_guardian.py::handle_violations`
- **Calls:** warning, critical, len, log_activity, getattr, emit_safety, error, pause
### `mmm_harvester.py::get_effective_harvest_params`
- **Calls:** get, max
### `mmm_harvester.py::scan_harvestable_positions`
- **Calls:** get_effective_harvest_params, sort, now, info, get, max
### `mmm_analytics_storage.py::get_analytics_storage`
- **Calls:** MMMAnalyticsStorage
### `mmm_analytics_storage.py::__init__`
- **Calls:** makedirs, dirname, _init_db
### `mmm_analytics_storage.py::_get_conn`
- **Calls:** execute, connect
### `mmm_analytics_storage.py::_init_db`
- **Calls:** close, _get_conn, execute, error, info, commit
### `mmm_analytics_storage.py::save_session_analytics`
- **Calls:** get, isoformat, _get_conn
### `mmm_analytics_storage.py::get_session_analytics`
- **Calls:** close, _get_conn, execute, fetchone, error, loads
### `mmm_analytics_storage.py::get_all_analytics`
- **Calls:** close, _get_conn, execute, error, append, loads, fetchall
### `mmm_analytics_storage.py::delete_analytics`
- **Calls:** close, _get_conn, execute, error, info, commit
### `mmm_config.py::validate_params`
- **Calls:** _interdependency_checks, bool, int, isinstance, type, append, lower, float, str, items
### `mmm_config.py::_interdependency_checks`
- **Calls:** get, range
### `mmm_config.py::get_hot_reload_params`
- **Calls:** get, items
### `mmm_config.py::get_param_info`
- **Calls:** get, items
### `mmm_regime.py::_update_vol_regime`
- **Calls:** int, isinstance, isoformat, list, float, get
- **State Mutations:** session['_vol_regime_score'] =, session['_vol_regime_since'] =, session['_vol_spot_history'] =, session['_vol_rv_annualized'] =, session['_vol_wind_down_triggered'] =, session['_vol_iv_change_pct'] =, session['_vol_last_valid_spot'] =, session['_vol_iv_history'] =, session['_vol_regime_beats_below'] =, session['_vol_regime'] =
### `mmm_regime.py::_update_gamma_cap`
- **Calls:** isoformat, list, append, round, get
- **State Mutations:** session['_gamma_emergency_limit_effective'] =, session['_gamma_history'] =, session['_gamma_regime_since'] =, session['_gamma_hard_limit_effective'] =, session['_gamma_regime'] =, session['_portfolio_dollar_gamma'] =, session['_gamma_soft_limit_effective'] =, session['_gamma_data_incomplete'] =, session['_portfolio_gamma'] =
### `mmm_regime.py::compute_projected_gamma`
- **Calls:** get, abs
### `mmm_regime.py::_check_acceleration`
- **Calls:** timestamp, len, fromisoformat, now, round, abs, get
### `mmm_regime.py::_compute_trend_tier`
- **Calls:** get
### `mmm_regime.py::_update_trend_guard`
- **Calls:** _check_acceleration, isoformat, round, abs, get
- **State Mutations:** session['_trend_move_pct'] =, session['_trend_low'] =, session['_trend_regime'] =, session['_trend_tier'] =, session['_trend_since'] =, session['_trend_acceleration_move_pct'] =, session['_trend_ema'] =, session['_trend_direction'] =, session['_trend_calm_beats'] =, session['_trend_anchor_spot'] =, session['_trend_ema_prev'] =, session['_trend_plateau_beats'] =, session['_trend_ema_slope'] =, session['_trend_high'] =, session['_trend_wind_down_triggered'] =
### `mmm_regime.py::_compute_regime_action`
- **Calls:** get
- **State Mutations:** session['_trend_wind_down_triggered'] =, session['_vol_wind_down_triggered'] =
### `mmm_regime.py::update_vol_regime`
- **Calls:** error, get, _update_vol_regime
### `mmm_regime.py::update_gamma_cap`
- **Calls:** error, get, _update_gamma_cap
### `mmm_regime.py::update_trend_guard`
- **Calls:** error, get, _update_trend_guard
### `mmm_regime.py::compute_regime_action`
- **Calls:** _compute_regime_action
- **State Mutations:** session['_regime_action'] =
### `mmm_regime.py::get_regime_status`
- **Calls:** get
### `mmm_regime.py::should_block_sell`
- **Calls:** get, append, lower, join
### `mmm_regime.py::check_projected_gamma`
- **Calls:** warning, get, compute_projected_gamma
- **State Mutations:** session['_gamma_blocked_count'] =
### `mmm_executor.py::_log_activity`
- **Calls:** debug, log_activity
### `mmm_executor.py::_parse_fill_price`
- **Calls:** ValueError, isinf, float, str, isnan, strip
### `mmm_executor.py::get_executor`
- **Calls:** MMMExecutor
### `mmm_executor.py::client`
- **Calls:** UnifiedAPIClient, info, get_api_credentials, error
### `mmm_executor.py::_create_rest_client`
- **Calls:** debug, get, AsyncDeltaClient, get_api_credentials
### `mmm_executor.py::smart_execute`
- **Calls:** _failure, time, range, error, _fetch_quotes, get, _create_rest_client, info, str, _log_activity
### `mmm_executor.py::emergency_execute`
- **Calls:** critical, _failure, time, range, round, lower, get, _create_rest_client, info, str, _log_activity
### `mmm_executor.py::execute_entry`
- **Calls:** isinstance, _failure, gather, get, info, smart_execute, _log_activity
### `mmm_executor.py::execute_adjustment`
- **Calls:** error, round, info, smart_execute, get
### `mmm_executor.py::_fetch_quotes`
- **Calls:** warning, get_orderbook, float, _create_rest_client, info, get
### `mmm_executor.py::_calculate_mid_price`
- **Calls:** get, round
### `mmm_executor.py::get_mid_price`
- **Calls:** _fetch_quotes, _calculate_mid_price
### `mmm_executor.py::_place_limit_order`
- **Calls:** warning, int, range, error, lower, _create_rest_client, info, str, get, place_order_by_symbol
### `mmm_executor.py::_amend_order`
- **Calls:** warning, int, info, _create_rest_client, str, edit_order
### `mmm_executor.py::_cancel_order`
- **Calls:** warning, int, cancel_order, _create_rest_client, info, str
### `mmm_executor.py::_get_order_status`
- **Calls:** warning, get_order, str, _create_rest_client
### `mmm_executor.py::_is_filled`
- **Calls:** lower, get
### `mmm_executor.py::_wait_for_fill`
- **Calls:** debug, time, _get_order_status, lower, get, sleep
### `mmm_atm_shield.py::_compute_time_mult`
- **Calls:** min, max
### `mmm_atm_shield.py::_compute_effective_proximity`
- **Calls:** get
### `mmm_atm_shield.py::_compute_effective_target_otm`
- **Calls:** get
### `mmm_atm_shield.py::check_atm_proximity`
- **Calls:** get, _compute_effective_proximity
### `mmm_atm_shield.py::_check_shield_gates`
- **Calls:** fromisoformat, get, total_seconds, now
### `mmm_atm_shield.py::execute_atm_shield`
- **Calls:** warning, getattr, _check_shield_gates, check_atm_proximity, get, _compute_time_mult
- **State Mutations:** session['_atm_shield_fired'] =, session['_atm_wind_down_triggered'] =, params['wind_down_enabled'] =, session['_atm_prev_wind_down_enabled'] =
### `mmm_pending_orders.py::register_pending`
- **Calls:** isoformat, now, upper, info, str, setdefault
### `mmm_pending_orders.py::clear_pending`
- **Calls:** get, upper, info
### `mmm_pending_orders.py::get_pending`
- **Calls:** get
### `mmm_pending_orders.py::clear_all`
- **Calls:** pop, info
### `mmm_pending_orders.py::check_and_resolve_pending`
- **Calls:** warning, total_seconds, fromisoformat, get_order, get_pending, clear_pending, lower, upper, info, replace, get
### `mmm_trigger.py::evaluate_triggers`
- **Calls:** strike_key, get, max
### `mmm_trigger.py::check_frozen_pnl_trigger`
- **Calls:** get, round, _compute_frozen_loss, info
### `mmm_trigger.py::update_trigger_snapshots`
- **Calls:** fetch_premium_fn, info, strike_key, get, debug
- **State Mutations:** session['pe'] =, session['ce'] =
### `mmm_trigger.py::apply_theta_acceleration`
- **Calls:** get, max, min
### `mmm_trigger.py::compute_adaptive_interval`
- **Calls:** max, int
### `mmm_trigger.py::compute_adaptive_interval_v2`
- **Calls:** max, int
### `mmm_trigger.py::apply_theta_acceleration_v2`
- **Calls:** get, max, min
### `mmm_trigger.py::_compute_frozen_loss`
- **Calls:** strike_key, get, max, fetch_premium_fn
### `mmm_websocket.py::init_websocket`
- **Calls:** info
### `mmm_websocket.py::get_ws_health`
- **Calls:** isoformat
### `mmm_websocket.py::_emit`
- **Calls:** critical, emit, now, error, isoformat
### `mmm_websocket.py::emit_heartbeat`
- **Calls:** _emit
### `mmm_websocket.py::emit_price_tick`
- **Calls:** _emit
### `mmm_websocket.py::emit_adjustment`
- **Calls:** _emit
### `mmm_websocket.py::emit_reversal`
- **Calls:** _emit
### `mmm_websocket.py::emit_strike_shift`
- **Calls:** _emit
### `mmm_websocket.py::emit_close_at_5`
- **Calls:** _emit
### `mmm_websocket.py::emit_both_sides_alert`
- **Calls:** _emit
### `mmm_websocket.py::emit_safety`
- **Calls:** _emit
### `mmm_websocket.py::emit_pnl_update`
- **Calls:** _emit
### `mmm_websocket.py::emit_params_changed`
- **Calls:** _emit
### `mmm_websocket.py::emit_status_change`
- **Calls:** _emit
### `mmm_websocket.py::emit_session_created`
- **Calls:** _emit
### `mmm_websocket.py::emit_session_deleted`
- **Calls:** _emit
### `mmm_websocket.py::emit_activity`
- **Calls:** _emit
### `mmm_websocket.py::emit_heartbeat_summary`
- **Calls:** _emit
### `mmm_websocket.py::emit_regime`
- **Calls:** _emit
### `mmm_websocket.py::emit_activities_updated`
- **Calls:** _emit
### `mmm_websocket.py::emit_perp_hedge_execution`
- **Calls:** _emit
### `mmm_websocket.py::emit_perp_hedge_update`
- **Calls:** _emit
### `mmm_websocket.py::emit_harvest`
- **Calls:** _emit
### `mmm_websocket.py::emit_recycle`
- **Calls:** _emit
### `mmm_websocket.py::emit_scale_up`
- **Calls:** _emit
### `mmm_websocket.py::emit_atm_shield`
- **Calls:** _emit
### `mmm_websocket.py::emit_perp_hedge_flip`
- **Calls:** _emit
### `mmm_websocket.py::emit_to_session`
- **Calls:** _emit
### `mmm_websocket.py::emit_manual_injection`
- **Calls:** _emit
### `mmm_websocket.py::emit_breakeven`
- **Calls:** _emit
### `mmm_websocket.py::emit_gamma`
- **Calls:** _emit
