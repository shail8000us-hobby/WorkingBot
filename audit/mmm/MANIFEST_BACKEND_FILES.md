# MANIFEST — Backend MMM Files

- MMM module files (`mmm_*.py`): **57**
- Support files (non-`mmm_*`): **1**
- Total python files in MMM route package: **58**

## MMM modules

| # | File | Lines | Approx Chunks (@450) |
|---:|---|---:|---:|
| 1 | `webui/backend/routes/mmm/mmm_activity.py` | 958 | 3 |
| 2 | `webui/backend/routes/mmm/mmm_adaptive.py` | 449 | 1 |
| 3 | `webui/backend/routes/mmm/mmm_adopter.py` | 704 | 2 |
| 4 | `webui/backend/routes/mmm/mmm_analytics_aggregator.py` | 767 | 2 |
| 5 | `webui/backend/routes/mmm/mmm_analytics_storage.py` | 240 | 1 |
| 6 | `webui/backend/routes/mmm/mmm_api.py` | 8750 | 20 |
| 7 | `webui/backend/routes/mmm/mmm_atm_shield.py` | 646 | 2 |
| 8 | `webui/backend/routes/mmm/mmm_audit_log.py` | 841 | 2 |
| 9 | `webui/backend/routes/mmm/mmm_audit_reconciler.py` | 133 | 1 |
| 10 | `webui/backend/routes/mmm/mmm_audit_remark.py` | 324 | 1 |
| 11 | `webui/backend/routes/mmm/mmm_breakeven_engine.py` | 745 | 2 |
| 12 | `webui/backend/routes/mmm/mmm_circuit_breaker.py` | 396 | 1 |
| 13 | `webui/backend/routes/mmm/mmm_close_at_5.py` | 961 | 3 |
| 14 | `webui/backend/routes/mmm/mmm_config.py` | 1003 | 3 |
| 15 | `webui/backend/routes/mmm/mmm_constants.py` | 40 | 1 |
| 16 | `webui/backend/routes/mmm/mmm_dte_presets.py` | 702 | 2 |
| 17 | `webui/backend/routes/mmm/mmm_engine.py` | 1102 | 3 |
| 18 | `webui/backend/routes/mmm/mmm_executor.py` | 1988 | 5 |
| 19 | `webui/backend/routes/mmm/mmm_exit_all.py` | 672 | 2 |
| 20 | `webui/backend/routes/mmm/mmm_fill_sync.py` | 504 | 2 |
| 21 | `webui/backend/routes/mmm/mmm_gamma.py` | 328 | 1 |
| 22 | `webui/backend/routes/mmm/mmm_gamma_detector.py` | 293 | 1 |
| 23 | `webui/backend/routes/mmm/mmm_god_layer.py` | 328 | 1 |
| 24 | `webui/backend/routes/mmm/mmm_guardian.py` | 397 | 1 |
| 25 | `webui/backend/routes/mmm/mmm_harvester.py` | 264 | 1 |
| 26 | `webui/backend/routes/mmm/mmm_heartbeat_health.py` | 366 | 1 |
| 27 | `webui/backend/routes/mmm/mmm_initializer.py` | 870 | 2 |
| 28 | `webui/backend/routes/mmm/mmm_margin_guardian.py` | 531 | 2 |
| 29 | `webui/backend/routes/mmm/mmm_monitor.py` | 11755 | 27 |
| 30 | `webui/backend/routes/mmm/mmm_observer.py` | 331 | 1 |
| 31 | `webui/backend/routes/mmm/mmm_pending_orders.py` | 250 | 1 |
| 32 | `webui/backend/routes/mmm/mmm_performance.py` | 619 | 2 |
| 33 | `webui/backend/routes/mmm/mmm_perp_hedge.py` | 940 | 3 |
| 34 | `webui/backend/routes/mmm/mmm_pnl_core.py` | 934 | 3 |
| 35 | `webui/backend/routes/mmm/mmm_recycler.py` | 590 | 2 |
| 36 | `webui/backend/routes/mmm/mmm_regime.py` | 1052 | 3 |
| 37 | `webui/backend/routes/mmm/mmm_replenish.py` | 170 | 1 |
| 38 | `webui/backend/routes/mmm/mmm_reversal.py` | 305 | 1 |
| 39 | `webui/backend/routes/mmm/mmm_reverse.py` | 822 | 2 |
| 40 | `webui/backend/routes/mmm/mmm_safety.py` | 1198 | 3 |
| 41 | `webui/backend/routes/mmm/mmm_scaler.py` | 288 | 1 |
| 42 | `webui/backend/routes/mmm/mmm_state.py` | 1436 | 4 |
| 43 | `webui/backend/routes/mmm/mmm_storage.py` | 1256 | 3 |
| 44 | `webui/backend/routes/mmm/mmm_straddle_adjustment.py` | 773 | 2 |
| 45 | `webui/backend/routes/mmm/mmm_straddle_roll_pure.py` | 977 | 3 |
| 46 | `webui/backend/routes/mmm/mmm_strategy_dispatch.py` | 269 | 1 |
| 47 | `webui/backend/routes/mmm/mmm_strike_shift.py` | 614 | 2 |
| 48 | `webui/backend/routes/mmm/mmm_telegram.py` | 546 | 2 |
| 49 | `webui/backend/routes/mmm/mmm_trigger.py` | 763 | 2 |
| 50 | `webui/backend/routes/mmm/mmm_walkthrough.py` | 660 | 2 |
| 51 | `webui/backend/routes/mmm/mmm_watchdog.py` | 544 | 2 |
| 52 | `webui/backend/routes/mmm/mmm_websocket.py` | 554 | 2 |
| 53 | `webui/backend/routes/mmm/mmm_whipsaw.py` | 317 | 1 |
| 54 | `webui/backend/routes/mmm/mmm_whipsaw_replay.py` | 209 | 1 |
| 55 | `webui/backend/routes/mmm/mmm_whipsaw_smart.py` | 798 | 2 |
| 56 | `webui/backend/routes/mmm/mmm_whipsaw_spot_log.py` | 61 | 1 |
| 57 | `webui/backend/routes/mmm/mmm_wind_down.py` | 428 | 1 |

## Support files

| # | File | Lines | Approx Chunks (@450) |
|---:|---|---:|---:|
| 1 | `webui/backend/routes/mmm/__init__.py` | 112 | 1 |
