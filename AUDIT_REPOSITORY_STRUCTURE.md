# Repository Structure Audit — MMM/MMMX

**Date:** 2026-04-17
**Scope:** MMM/MMMX files discovered by path/name scan across workspace (file-by-file)

## 1. Executive Summary

- Total MMM-scoped files audited: **717**
- Action classification: **keep=264**, **review=30**, **archive=416**, **redesign=7**
- Tracking split: **tracked=287**, **untracked=430**
- Primary structural risk: duplicated trees + runtime data mixed with code + oversized orchestrators.

## 2. Files Audited

### Coverage summary

- Inventory source: `/tmp/mmm_audit_inventory.txt`
- Files included in this report: **717** (every discovered MMM/MMMX-scoped path)

### File-by-file action matrix

| File | Action | Tracking | Note |
|---|---|---|---|
| `.ai/AI_MMM_CONTEXT.md` | **REVIEW** | untracked | Documentation sprawl candidate; consolidate/archive by recency |
| `.claude/worktrees/bold-meninsky/.gemini/artifacts/mmm_manage_existing_positions_plan.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/AI_MMM_CONTEXT.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/AUDIT_MMM_DEEP_FEB17_2026.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/AUDIT_MMM_F48816_FEB17_2026.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/MMM_10_OF_10_PRODUCTION_PLAN.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/MMM_ANALYTICS_REDESIGN_FEB18_2026.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/MMM_DEEP_ANALYSIS_VERIFIED_FINDINGS.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/MMM_DEVELOPMENT_PLAN.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/MMM_INSTITUTIONAL_ANALYTICS_FEB18_2026.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/MMM_LOT_RECYCLING_IMPLEMENTATION_PLAN.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/MMM_MARGIN_GUARDIAN_SAFETY.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/MMM_REGIME_RISK_CONTROLS_DESIGN.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/MMM_RELIABILITY_ROADMAP.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/MMM_SCALE_UP_PLAN.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/MMM_SESSION_mmm04mar26_1_ANALYSIS.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/MMM_SETTINGS_DIALOG_IMPLEMENTATION.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/MMM_SHIFT_THRESHOLD_EXPLANATION.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/MMM_SPLIT_LEDGER_INSTRUCTIONS.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/MMM_SPLIT_LEDGER_PLAN.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/MMM_SUGGESTION_SYSTEM_DESIGN.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/MMM_USERGUIDE.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/MMM_robustv2.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/backtesting/strategies/mmm/__init__.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/backtesting/strategies/mmm/mmm_adapter.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/backtesting/strategies/mmm/mmm_heartbeat_bridge.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/backtesting/strategies/mmm/mmm_mock_client.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/backtesting/strategies/mmm/mmm_state_factory.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/data/mmm_analytics_history.json` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/data/mmm_analytics_history.lock` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/mmm_critical.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/mmm_observer.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/multiple_expiry_mmm.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/tasks/MMM_IMPLEMENTATION_PLAN.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/tasks/MMM_IMPROVEMENT_PLAN.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/tests/_test_mmm_perf.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/tests/mmm/__init__.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/tests/mmm/test_integration.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/tests/mmm/test_reliability.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/tests/mmm/test_stress.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/data/mmm_activity_log.json` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/data/mmm_sessions.json.migrated` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/MMM_REMAINING_WORK.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/__init__.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_activity.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_adopter.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_analytics_aggregator.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_analytics_aggregator.py.bak_feb18` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_analytics_storage.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_api.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_atm_shield.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_circuit_breaker.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_close_at_5.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_config.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_constants.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_dte_presets.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_engine.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_executor.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_guardian.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_harvester.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_heartbeat_health.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_initializer.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_margin_guardian.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_monitor.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_observer.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_pending_orders.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_perp_hedge.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_recycler.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_regime.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_reversal.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_safety.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_scaler.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_state.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_storage.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_storage.py.json_backup` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_strike_shift.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_telegram.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_trigger.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_walkthrough.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_watchdog.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_websocket.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/mmm_wind_down.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/tests/__init__.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/tests/pytest.ini` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/tests/test_hedge_integrity_guard.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/tests/test_mmm_close_at_5.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/tests/test_mmm_dte_presets.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/tests/test_mmm_engine.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/tests/test_mmm_harvester.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/tests/test_mmm_integration.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/tests/test_mmm_lot_lifecycle_integration.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/tests/test_mmm_observer.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/tests/test_mmm_recycler.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/tests/test_mmm_reversal.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/tests/test_mmm_safety.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/tests/test_mmm_state.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/tests/test_mmm_strike_shift.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/tests/test_mmm_trigger.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/tests/test_mmm_wind_down.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/tests/test_sealed_calculate_lots_to_sell.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/tests/test_sealed_check_side_fully_closed.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/tests/test_sealed_margin_guardian.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/backend/routes/mmm/tests/test_sealed_recompute_side_lots.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/MMMInstitutionalAnalytics.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/MMMInstitutionalAnalytics.js.bak_feb18` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/mmm/MMMActivityFeed.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/mmm/MMMAdjustmentLog.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/mmm/MMMAdoptPanel.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/mmm/MMMAlgoCalculations.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/mmm/MMMAnalyticsPanel.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/mmm/MMMAnalyticsSummary.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/mmm/MMMAnalyticsTable.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/mmm/MMMBothSidesAlert.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/mmm/MMMConfigPanel.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/mmm/MMMConsolidatedPositions.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/mmm/MMMContext.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/mmm/MMMDashboard.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/mmm/MMMEducation.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/mmm/MMMErrorBoundary.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/mmm/MMMGreeksPanel.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/mmm/MMMMarginGuardianPanel.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/mmm/MMMPerpHedgePanel.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/mmm/MMMPnLChart.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/mmm/MMMPositionsTable.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/mmm/MMMRegimePanel.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/mmm/MMMSafetyPanel.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/mmm/MMMSessionCard.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/mmm/MMMSettingsDialog.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/mmm/MMMStatusBanner.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/mmm/MMMStrikeMap.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/mmm/MMMStrikeSelector.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/mmm/MMMTriggerGauge.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/mmm/__tests__/test_sealed_mmm_margin_panel.test.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/mmm/__tests__/test_sealed_mmm_session_card.test.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/mmm/hooks/useMMMParams.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/mmm/hooks/useMMMWebSocket.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/mmm/index.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/mmm/mmmService.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/mmm/utils/mmmCalculations.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/components/mmm/utils/mmmFormatters.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/bold-meninsky/webui/frontend/src/pages/MMMPage.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/AI_MMMX_CONTEXT.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/AI_MMM_CONTEXT.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/MMMX_COMPLETE.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/MMMX_IMPLEMENTATION_PLAN.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/MMMX_WEBUI_DESIGN.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/MMM_AUDIT_FIXES_MAR24_2026.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/MMM_REVERSE_MODE_DESIGN.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/MMM_REVERSE_MODE_USERGUIDE.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/MMM_SAFETY_AUDIT_MAR31_2026.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/backtesting/strategies/mmm/__init__.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/backtesting/strategies/mmm/mmm_adapter.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/backtesting/strategies/mmm/mmm_heartbeat_bridge.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/backtesting/strategies/mmm/mmm_mock_client.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/backtesting/strategies/mmm/mmm_state_factory.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/data/mmm_analytics_history.json` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/data/mmm_analytics_history.lock` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/mmm_Pnl.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/mmm_Pnl_AUDIT.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/mmm_audit_plan.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/mmm_workdone_march.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/mmmx_brain.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/mmmx_plan.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/mmmx_webUI.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/mmmx_webUI_implementation_plan.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/mmmx_webUI_plan.md` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/tests/_test_mmm_perf.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/tests/mmm/__init__.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/tests/mmm/test_integration.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/tests/mmm/test_reliability.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/tests/mmm/test_stress.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/data/mmm_activity_log.json` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/data/mmm_sessions.json.migrated` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/__init__.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_activity.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_adaptive.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_adopter.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_analytics_aggregator.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_analytics_aggregator.py.bak_feb18` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_analytics_storage.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_api.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_atm_shield.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_audit_log.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_audit_reconciler.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_audit_remark.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_breakeven_engine.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_circuit_breaker.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_close_at_5.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_config.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_constants.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_dte_presets.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_engine.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_executor.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_exit_all.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_fill_sync.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_gamma.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_gamma_detector.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_guardian.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_harvester.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_heartbeat_health.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_initializer.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_margin_guardian.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_monitor.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_observer.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_pending_orders.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_performance.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_perp_hedge.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_pnl_core.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_recycler.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_regime.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_replenish.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_reversal.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_reverse.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_safety.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_scaler.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_state.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_storage.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_storage.py.json_backup` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_straddle_roll.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_straddle_roll.py.base_plan_backup` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_strike_shift.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_telegram.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_trigger.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_walkthrough.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_watchdog.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_websocket.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/mmm_wind_down.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/__init__.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/conftest.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/pytest.ini` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/simulate_mmm_trades.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_active_hours_shutdown.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_hedge_integrity_guard.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_mmm_adaptive.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_mmm_close_at_5.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_mmm_dte_presets.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_mmm_engine.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_mmm_harvester.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_mmm_integration.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_mmm_lot_lifecycle_integration.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_mmm_observer.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_mmm_recycler.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_mmm_reversal.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_mmm_safety.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_mmm_state.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_mmm_strike_shift.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_mmm_trigger.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_mmm_wind_down.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_sealed_calculate_loss.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_sealed_calculate_lots_to_sell.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_sealed_check_max_loss.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_sealed_check_max_loss_sizing.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_sealed_check_side_fully_closed.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_sealed_compute_adaptive_interval.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_sealed_margin_guardian.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_sealed_mmm_adopter.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_sealed_mmm_atm_shield.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_sealed_mmm_breakeven_engine.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_sealed_mmm_circuit_breaker.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_sealed_mmm_close_at_5.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_sealed_mmm_config.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_sealed_mmm_data_confidence.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_sealed_mmm_dte_presets.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_sealed_mmm_execution_events.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_sealed_mmm_gamma.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_sealed_mmm_gamma_detector.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_sealed_mmm_gamma_proportional.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_sealed_mmm_harvester.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_sealed_mmm_margin_guardian_async.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_sealed_mmm_pending_orders.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_sealed_mmm_perp_hedge.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_sealed_mmm_pnl_core.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_sealed_mmm_recycler.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_sealed_mmm_regime.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_sealed_mmm_replenish.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_sealed_mmm_reversal.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_sealed_mmm_safety.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_sealed_mmm_state.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_sealed_mmm_storage.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_sealed_mmm_strike_shift.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_sealed_mmm_trigger.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_sealed_mmm_wind_down.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmm/tests/test_sealed_recompute_side_lots.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/__init__.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/init_mmmx.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/mmmx_activity.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/mmmx_api.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/mmmx_atm_shield.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/mmmx_audit_log.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/mmmx_circuit_breaker.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/mmmx_close_all.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/mmmx_config.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/mmmx_constants.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/mmmx_engine.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/mmmx_executor.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/mmmx_hedger.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/mmmx_initializer.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/mmmx_integrity.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/mmmx_iv_adapter.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/mmmx_margin_guardian.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/mmmx_monitor.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/mmmx_param_audit.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/mmmx_premium_listener.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/mmmx_profit_booking.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/mmmx_reconciler.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/mmmx_safety.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/mmmx_state.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/mmmx_storage.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/mmmx_telegram.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/mmmx_trigger.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/mmmx_watchdog.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/mmmx_websocket.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/mmmx_whipsaw.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/tests/__init__.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/tests/test_phase1.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/tests/test_phase10.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/tests/test_phase11.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/tests/test_phase2.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/tests/test_phase3.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/tests/test_phase4.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/tests/test_phase5.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/tests/test_phase6.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/tests/test_phase7.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/tests/test_phase8.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/backend/routes/mmmx/tests/test_phase9.py` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/MMMInstitutionalAnalytics.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/MMMInstitutionalAnalytics.js.bak_feb18` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMActivityFeed.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMAdjustmentLog.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMAdoptPanel.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMAlgoCalculations.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMAnalyticsPanel.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMAnalyticsSummary.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMAnalyticsTable.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMBothSidesAlert.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMBreakevenPanel.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMCombinedZoneWidget.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMConfigPanel.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMConsolidatedPositions.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMContext.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMDashboard.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMDistanceHistoryChart.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMEducation.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMErrorBoundary.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMExecutionLogPanel.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMGammaPanel.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMGreeksPanel.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMHealthRadar.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMMarginGuardianPanel.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMPerformancePanel.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMPerpHedgePanel.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMPnLChart.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMPositionsTable.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMRegimePanel.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMReverseModePanel.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMRiskProfileChart.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMSafetyPanel.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMSessionCard.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMSettingsDialog.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMStatusBanner.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMStrikeMap.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMStrikeSelector.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMTradeAuditPanel.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/MMMTriggerGauge.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/__tests__/test_sealed_mmm_margin_panel.test.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/__tests__/test_sealed_mmm_session_card.test.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/hooks/useMMMParams.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/hooks/useMMMWebSocket.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/index.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/mmmService.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/utils/mmmCalculations.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmm/utils/mmmFormatters.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmmx/MMMXContext.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmmx/MMMXCreateSessionDialog.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmmx/MMMXCriticalModePanel.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmmx/MMMXDashboard.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmmx/MMMXErrorBoundary.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmmx/MMMXIncidentQueuePanel.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmmx/MMMXSessionCard.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmmx/MMMXTopCommandStrip.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmmx/mmmxControlSafety.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmmx/mmmxEventContracts.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmmx/mmmxService.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmmx/panels/MMMXDeltaExposurePanel.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmmx/panels/MMMXFeesCapitalPanel.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmmx/panels/MMMXHealthRadar.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmmx/panels/MMMXPerformancePanel.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmmx/panels/MMMXPnLChart.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmmx/panels/MMMXRegimePanel.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmmx/panels/MMMXRiskRail.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmmx/panels/MMMXSafetyPanel.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmmx/panels/MMMXTradeAuditPanel.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmmx/tabs/MMMXAdjustmentsTab.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmmx/tabs/MMMXExecutionTab.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmmx/tabs/MMMXHedgesTab.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmmx/tabs/MMMXParametersTab.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmmx/tabs/MMMXProfitBookingTab.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmmx/tabs/MMMXReconcileTab.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmmx/tabs/MMMXRiskTab.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmmx/tabs/MMMXStatusTab.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmmx/tabs/MMMXTranchesTab.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmmx/tabs/MMMXTriggerEngineTab.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmmx/useMMMXWebSocket.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmmx/utils/mmmxConstants.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmmx/utils/mmmxDerivations.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/components/mmmx/utils/mmmxFormatters.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/pages/MMMPage.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `.claude/worktrees/naughty-hoover/webui/frontend/src/pages/MMMXPage.js` | **ARCHIVE** | untracked | Workspace worktree duplicate; not part of primary runtime tree |
| `AI_MMMX_CONTEXT.md` | **REVIEW** | tracked | Documentation sprawl candidate; consolidate/archive by recency |
| `ML_FOR_MMM_DETAILED_GUIDE.md` | **KEEP** | tracked | Active code/documentation path |
| `MMMX_COMPLETE.md` | **KEEP** | tracked | Active code/documentation path |
| `MMMX_IMPLEMENTATION_PLAN.md` | **REVIEW** | tracked | Documentation sprawl candidate; consolidate/archive by recency |
| `MMMX_WEBUI_DESIGN.md` | **KEEP** | tracked | Active code/documentation path |
| `MMM_AI_Context_PureStraddle_Roll.md` | **REVIEW** | tracked | Documentation sprawl candidate; consolidate/archive by recency |
| `MMM_AUDIT_FIXES_MAR24_2026.md` | **REVIEW** | tracked | Documentation sprawl candidate; consolidate/archive by recency |
| `MMM_LAST_3_SESSIONS.md` | **KEEP** | untracked | Active code/documentation path |
| `MMM_PHASE2_OBSERVABILITY_HYGIENE_AUDIT_2026-04-13.md` | **REVIEW** | tracked | Documentation sprawl candidate; consolidate/archive by recency |
| `MMM_REVERSE_MODE_DESIGN.md` | **KEEP** | tracked | Active code/documentation path |
| `MMM_REVERSE_MODE_USERGUIDE.md` | **KEEP** | tracked | Active code/documentation path |
| `MMM_SAFETY_AUDIT_MAR31_2026.md` | **REVIEW** | tracked | Documentation sprawl candidate; consolidate/archive by recency |
| `MMM_SESSION_FORENSIC_AUDIT_mmm16apr26-2.md` | **REVIEW** | tracked | Documentation sprawl candidate; consolidate/archive by recency |
| `MMM_SESSION_FORENSIC_AUDIT_mmm17apr26-4.md` | **REVIEW** | untracked | Documentation sprawl candidate; consolidate/archive by recency |
| `MMM_SESSION_FORENSIC_AUDIT_mmm17apr26-5.md` | **REVIEW** | untracked | Documentation sprawl candidate; consolidate/archive by recency |
| `MMM_SESSION_FORENSIC_AUDIT_mmm17apr26-6.md` | **REVIEW** | untracked | Documentation sprawl candidate; consolidate/archive by recency |
| `MMM_SESSION_FORENSIC_COMPARATIVE_REVIEW_mmm17apr26-4_5_6.md` | **REVIEW** | untracked | Documentation sprawl candidate; consolidate/archive by recency |
| `MMM_SLIM_CONTEXT.md` | **REVIEW** | untracked | Documentation sprawl candidate; consolidate/archive by recency |
| `MMM_STRATEGY_ISOLATION_FORENSIC_REPORT_2026-04-13.md` | **REVIEW** | tracked | Documentation sprawl candidate; consolidate/archive by recency |
| `NEURAL_ENGINE_FOR_MMM.md` | **KEEP** | tracked | Active code/documentation path |
| `backtesting/strategies/mmm/__init__.py` | **KEEP** | tracked | Active code/documentation path |
| `backtesting/strategies/mmm/mmm_adapter.py` | **KEEP** | tracked | Active code/documentation path |
| `backtesting/strategies/mmm/mmm_heartbeat_bridge.py` | **KEEP** | tracked | Active code/documentation path |
| `backtesting/strategies/mmm/mmm_mock_client.py` | **KEEP** | tracked | Active code/documentation path |
| `backtesting/strategies/mmm/mmm_state_factory.py` | **KEEP** | tracked | Active code/documentation path |
| `context_archive/AI_MMM_CONTEXT.md` | **REVIEW** | untracked | Documentation sprawl candidate; consolidate/archive by recency |
| `data/mmm_analytics_history.json` | **KEEP** | tracked | Active code/documentation path |
| `data/mmm_analytics_history.lock` | **ARCHIVE** | tracked | Lock/runtime artifact should not be versioned |
| `data/mmm_sessions.db` | **REVIEW** | untracked | Runtime DB file in workspace; verify single source of truth |
| `data/mmm_sessions.db-shm` | **REVIEW** | untracked | SQLite transient runtime artifact |
| `data/mmm_sessions.db-wal` | **REVIEW** | untracked | SQLite transient runtime artifact |
| `mmm_Pnl.md` | **KEEP** | tracked | Active code/documentation path |
| `mmm_Pnl_AUDIT.md` | **REVIEW** | tracked | Documentation sprawl candidate; consolidate/archive by recency |
| `mmm_audit_plan.md` | **REVIEW** | tracked | Documentation sprawl candidate; consolidate/archive by recency |
| `mmm_workdone_march.md` | **REVIEW** | tracked | Documentation sprawl candidate; consolidate/archive by recency |
| `mmmx_brain.md` | **KEEP** | tracked | Active code/documentation path |
| `mmmx_plan.md` | **REVIEW** | tracked | Documentation sprawl candidate; consolidate/archive by recency |
| `mmmx_webUI.md` | **KEEP** | tracked | Active code/documentation path |
| `mmmx_webUI_implementation_plan.md` | **REVIEW** | tracked | Documentation sprawl candidate; consolidate/archive by recency |
| `mmmx_webUI_plan.md` | **REVIEW** | tracked | Documentation sprawl candidate; consolidate/archive by recency |
| `tasks/AIMMM_SHORT_STRADDLE.md` | **KEEP** | tracked | Active code/documentation path |
| `tasks/MMM_SEAL_ROADMAP_APR2026.md` | **KEEP** | untracked | Active code/documentation path |
| `tasks/MMM_STRATEGY_SEPARATION_PLAN.md` | **REVIEW** | tracked | Documentation sprawl candidate; consolidate/archive by recency |
| `tests/_test_mmm_perf.py` | **KEEP** | tracked | Active code/documentation path |
| `tests/mmm/__init__.py` | **KEEP** | tracked | Active code/documentation path |
| `tests/mmm/test_integration.py` | **KEEP** | tracked | Active code/documentation path |
| `tests/mmm/test_reliability.py` | **KEEP** | tracked | Active code/documentation path |
| `tests/mmm/test_stress.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/data/mmm_activity_log.json` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/data/mmm_activity_log.json.bak` | **ARCHIVE** | untracked | Legacy backup/migration artifact |
| `webui/backend/data/mmm_sessions.db` | **REVIEW** | untracked | Runtime DB file in workspace; verify single source of truth |
| `webui/backend/data/mmm_sessions.db-shm` | **REVIEW** | untracked | SQLite transient runtime artifact |
| `webui/backend/data/mmm_sessions.db-wal` | **REVIEW** | untracked | SQLite transient runtime artifact |
| `webui/backend/data/mmm_sessions.json.migrated` | **ARCHIVE** | tracked | Legacy backup/migration artifact |
| `webui/backend/data/mmmx_sessions.db` | **REVIEW** | untracked | Runtime DB file in workspace; verify single source of truth |
| `webui/backend/mmm_sessions.db` | **ARCHIVE** | untracked | DB file located in code path; unsafe placement |
| `webui/backend/routes/mmm/__init__.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_activity.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_adaptive.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_adopter.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_analytics_aggregator.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_analytics_aggregator.py.bak_feb18` | **ARCHIVE** | tracked | Legacy backup/migration artifact |
| `webui/backend/routes/mmm/mmm_analytics_storage.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_api.py` | **REDESIGN** | tracked | High coupling / large orchestrator module |
| `webui/backend/routes/mmm/mmm_atm_shield.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_audit_log.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_audit_reconciler.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_audit_remark.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_breakeven_engine.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_circuit_breaker.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_close_at_5.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_config.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_constants.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_dte_presets.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_engine.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_executor.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_exit_all.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_fill_sync.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_gamma.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_gamma_detector.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_god_layer.py` | **REDESIGN** | tracked | High coupling / large orchestrator module |
| `webui/backend/routes/mmm/mmm_guardian.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_harvester.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_heartbeat_health.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_initializer.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_margin_guardian.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_monitor.py` | **REDESIGN** | tracked | High coupling / large orchestrator module |
| `webui/backend/routes/mmm/mmm_observer.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_pending_orders.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_performance.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_perp_hedge.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_pnl_core.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_recycler.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_regime.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_replenish.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_reversal.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_reverse.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_safety.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_scaler.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_sessions.db` | **ARCHIVE** | untracked | DB file located in code path; unsafe placement |
| `webui/backend/routes/mmm/mmm_state.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_storage.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_storage.py.json_backup` | **ARCHIVE** | tracked | Legacy backup/migration artifact |
| `webui/backend/routes/mmm/mmm_straddle_adjustment.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_straddle_roll.py.base_plan_backup` | **ARCHIVE** | tracked | Legacy backup/migration artifact |
| `webui/backend/routes/mmm/mmm_straddle_roll_pure.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_strategy_dispatch.py` | **REDESIGN** | tracked | High coupling / large orchestrator module |
| `webui/backend/routes/mmm/mmm_strike_shift.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_telegram.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_trigger.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_walkthrough.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_watchdog.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_websocket.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/mmm_wind_down.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/__init__.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/conftest.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/pytest.ini` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/simulate_mmm_trades.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_active_hours_shutdown.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_hedge_integrity_guard.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_mmm_activity.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_mmm_adaptive.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_mmm_close_at_5.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_mmm_dte_presets.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_mmm_engine.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_mmm_harvester.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_mmm_integration.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_mmm_lot_lifecycle_integration.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_mmm_monitor_strategy_validation.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_mmm_observer.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_mmm_recycler.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_mmm_reversal.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_mmm_safety.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_mmm_state.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_mmm_strategy_dispatch.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_mmm_strategy_type_identity.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_mmm_strike_shift.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_mmm_summary_preset_source.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_mmm_trigger.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_mmm_wind_down.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_calculate_loss.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_calculate_lots_to_sell.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_check_max_loss.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_check_max_loss_sizing.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_check_side_fully_closed.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_compute_adaptive_interval.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_execution_risk_remediation.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_margin_guardian.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_mmm_adopter.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_mmm_adversarial_isolation.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_mmm_atm_shield.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_mmm_breakeven_engine.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_mmm_circuit_breaker.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_mmm_close_at_5.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_mmm_config.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_mmm_data_confidence.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_mmm_dte_presets.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_mmm_execution_events.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_mmm_fill_sync.py` | **KEEP** | untracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_mmm_gamma.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_mmm_gamma_detector.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_mmm_gamma_proportional.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_mmm_harvester.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_mmm_margin_guardian_async.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_mmm_pending_orders.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_mmm_perp_hedge.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_mmm_pnl_core.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_mmm_recycler.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_mmm_reduce_strike.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_mmm_regime.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_mmm_replenish.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_mmm_reversal.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_mmm_safety.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_mmm_state.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_mmm_storage.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_mmm_strike_shift.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_mmm_trigger.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_mmm_wind_down.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_process_adjustment_reversal.py` | **KEEP** | untracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_recompute_side_lots.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_smart_execute.py` | **KEEP** | untracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_straddle_adjustment.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmm/tests/test_sealed_straddle_roll_pure.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/__init__.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/init_mmmx.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/mmmx_activity.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/mmmx_api.py` | **REDESIGN** | tracked | High coupling / large orchestrator module |
| `webui/backend/routes/mmmx/mmmx_atm_shield.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/mmmx_audit_log.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/mmmx_circuit_breaker.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/mmmx_close_all.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/mmmx_config.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/mmmx_constants.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/mmmx_engine.py` | **REDESIGN** | tracked | High coupling / large orchestrator module |
| `webui/backend/routes/mmmx/mmmx_executor.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/mmmx_hedger.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/mmmx_initializer.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/mmmx_integrity.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/mmmx_iv_adapter.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/mmmx_margin_guardian.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/mmmx_monitor.py` | **REDESIGN** | tracked | High coupling / large orchestrator module |
| `webui/backend/routes/mmmx/mmmx_param_audit.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/mmmx_premium_listener.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/mmmx_profit_booking.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/mmmx_reconciler.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/mmmx_safety.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/mmmx_state.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/mmmx_storage.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/mmmx_telegram.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/mmmx_trigger.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/mmmx_watchdog.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/mmmx_websocket.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/mmmx_whipsaw.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/tests/__init__.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/tests/test_phase1.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/tests/test_phase10.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/tests/test_phase11.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/tests/test_phase2.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/tests/test_phase3.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/tests/test_phase4.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/tests/test_phase5.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/tests/test_phase6.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/tests/test_phase7.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/tests/test_phase8.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/backend/routes/mmmx/tests/test_phase9.py` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/MMMInstitutionalAnalytics.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/MMMInstitutionalAnalytics.js.bak_feb18` | **ARCHIVE** | tracked | Legacy backup/migration artifact |
| `webui/frontend/src/components/mmm/MMMActivityFeed.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/MMMAdjustmentLog.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/MMMAdoptPanel.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/MMMAlgoCalculations.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/MMMAnalyticsPanel.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/MMMAnalyticsSummary.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/MMMAnalyticsTable.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/MMMBothSidesAlert.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/MMMBreakevenPanel.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/MMMCombinedZoneWidget.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/MMMConfigPanel.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/MMMConsolidatedPositions.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/MMMContext.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/MMMDashboard.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/MMMDistanceHistoryChart.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/MMMEducation.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/MMMErrorBoundary.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/MMMExecutionLogPanel.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/MMMGammaPanel.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/MMMGreeksPanel.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/MMMHealthRadar.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/MMMMarginGuardianPanel.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/MMMPerformancePanel.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/MMMPerpHedgePanel.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/MMMPnLChart.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/MMMPositionsTable.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/MMMRegimePanel.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/MMMReverseModePanel.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/MMMRiskProfileChart.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/MMMSafetyPanel.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/MMMSessionCard.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/MMMSettingsDialog.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/MMMStatusBanner.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/MMMStrikeMap.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/MMMStrikeSelector.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/MMMTradeAuditPanel.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/MMMTriggerGauge.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/__tests__/test_sealed_mmm_margin_panel.test.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/__tests__/test_sealed_mmm_session_card.test.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/hooks/useMMMParams.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/hooks/useMMMWebSocket.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/index.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/mmmService.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/utils/mmmCalculations.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmm/utils/mmmFormatters.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmmx/MMMXContext.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmmx/MMMXCreateSessionDialog.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmmx/MMMXCriticalModePanel.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmmx/MMMXDashboard.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmmx/MMMXErrorBoundary.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmmx/MMMXIncidentQueuePanel.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmmx/MMMXSessionCard.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmmx/MMMXTopCommandStrip.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmmx/mmmxControlSafety.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmmx/mmmxEventContracts.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmmx/mmmxService.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmmx/panels/MMMXDeltaExposurePanel.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmmx/panels/MMMXFeesCapitalPanel.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmmx/panels/MMMXHealthRadar.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmmx/panels/MMMXPerformancePanel.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmmx/panels/MMMXPnLChart.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmmx/panels/MMMXRegimePanel.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmmx/panels/MMMXRiskRail.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmmx/panels/MMMXSafetyPanel.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmmx/panels/MMMXTradeAuditPanel.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmmx/tabs/MMMXAdjustmentsTab.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmmx/tabs/MMMXExecutionTab.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmmx/tabs/MMMXHedgesTab.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmmx/tabs/MMMXParametersTab.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmmx/tabs/MMMXProfitBookingTab.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmmx/tabs/MMMXReconcileTab.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmmx/tabs/MMMXRiskTab.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmmx/tabs/MMMXStatusTab.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmmx/tabs/MMMXTranchesTab.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmmx/tabs/MMMXTriggerEngineTab.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmmx/useMMMXWebSocket.js` | **REVIEW** | tracked | Likely orphan hook (no inbound references in src/) |
| `webui/frontend/src/components/mmmx/utils/mmmxConstants.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmmx/utils/mmmxDerivations.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/components/mmmx/utils/mmmxFormatters.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/mobile/MobileMMMView.js` | **KEEP** | untracked | Active code/documentation path |
| `webui/frontend/src/pages/MMMPage.js` | **KEEP** | tracked | Active code/documentation path |
| `webui/frontend/src/pages/MMMXPage.js` | **KEEP** | tracked | Active code/documentation path |

## 3. Findings

- **F1 — Worktree duplication explosion in `.claude/worktrees`**: 407 / 717 MMM-scoped files are under `.claude` worktrees.
- **F2 — Runtime data artifacts mixed with code paths**: Multiple DB and transient SQLite files exist across `data/`, `webui/backend/data/`, and code-adjacent paths.
- **F3 — Legacy backup/migration clutter is still present**: Tracked legacy MMM artifacts include `.bak_feb18`, `.json_backup`, `.base_plan_backup`, `.migrated`, and `.lock` files.
- **F4 — Core orchestration files are very large and highly coupled**: `mmm_monitor.py` 11179 LOC with out-degree 47; `mmm_api.py` 8368 LOC.
- **F5 — Import cycles remain in critical control plane**: Detected 4 cyclic components including monitor/watchdog/dispatch cluster.
- **F6 — Potential dead/orphan frontend utility**: Likely orphan file(s): components/mmmx/useMMMXWebSocket.js.
- **F7 — Testing strategy split adds maintenance overhead**: MMM tests: 65 total (43 sealed, 22 regular) with 10 overlapping module targets.

## 4. Severity (P0/P1/P2/P3)

| Finding | Severity |
|---|---|
| F1 | **P1** |
| F2 | **P1** |
| F3 | **P2** |
| F4 | **P1** |
| F5 | **P2** |
| F6 | **P3** |
| F7 | **P2** |

## 5. Why It Matters

- **F1**: Creates review noise, accidental stale edits risk, and unclear source-of-truth during incident response.
- **F2**: Increases chance of reading/writing wrong DB, breaks reproducibility, and complicates disaster recovery.
- **F3**: Confuses maintainers and increases odds of editing wrong files or shipping stale logic.
- **F4**: Large orchestrators degrade change safety and increase regression probability under emergency fixes.
- **F5**: Cycles make initialization order brittle and can hide side effects during runtime recovery.
- **F6**: Unused code drifts silently and misleads maintainers.
- **F7**: Dual suites can diverge unless ownership and purpose boundaries are explicit.

## 6. Suggested Fix

- **F1**: Move worktrees outside repo root or hard-ignore/de-track them from main development workspace scans.
- **F2**: Enforce a single data root and environment-driven DB path resolution; archive code-path DB copies.
- **F3**: Move all backups to dated `archive/` folders (or VCS history only) and enforce linting for forbidden suffixes.
- **F4**: Slice monitor/api into sealed services (state transitions, risk gates, execution adapter, persistence adapter).
- **F5**: Introduce explicit interfaces and one-way dependency rule (API → services → adapters → storage).
- **F6**: Remove or wire intentionally, and add unused-export detection to CI.
- **F7**: Document test taxonomy and periodically de-duplicate overlapping tests with explicit contract focus.

## 7. Safe Implementation Notes for Claude

- Do **not** touch trading logic first; start with repository hygiene and path isolation.
- Phase changes in this order:
  1. Add guardrails (`.gitignore` policy, artifact lints, CI checks).
  2. Move/archive duplicate and backup files with no runtime references.
  3. Consolidate DB pathing behind one config source and one runtime directory.
  4. Refactor orchestrators in thin slices with sealed tests preserving behavior.
- Before each move/delete:
  - verify runtime references (import/use search)
  - snapshot current DB files
  - run MMM and MMMX test suites
- Keep rollback simple: one PR per category (archive, data-path, monitor/api split).

## 8. Final Score /10

**6.1 / 10**

Scoring rationale: architecture depth and test volume are strong, but structural hygiene (duplication, data placement, oversized orchestrators, and cycle debt) materially reduces operational clarity and change safety.