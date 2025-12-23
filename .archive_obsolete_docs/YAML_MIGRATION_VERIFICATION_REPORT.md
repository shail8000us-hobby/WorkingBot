
====================================================================================================
🎯 YAML MIGRATION VERIFICATION - FINAL REPORT
====================================================================================================

📊 MIGRATION SUMMARY
--------------------------------------------------
Files Analyzed:        257
Files Migrated:        202
Files Partial:         55
Migration %:           78.6%

os.getenv() calls:     7
dotenv imports:        38
Total Issues:          45

====================================================================================================
⚠️  MIGRATION STATUS: INCOMPLETE
====================================================================================================

45 migration issues found across 55 files.

See detailed reports below for specific files and line numbers.

====================================================================================================
YAML MIGRATION AUDIT - FILE-BY-FILE VERIFICATION
====================================================================================================

File                                                         Status       Issues     Notes               
----------------------------------------------------------------------------------------------------
bot/ai/advisor.py                                            ⚠️ PARTIAL   0          0 getenv            
bot/ai/predictive/optimizer.py                               ⚠️ PARTIAL   0          0 getenv            
bot/api/ccxt_handle.py                                       ⚠️ PARTIAL   0          0 getenv            
bot/api/client.py                                            ⚠️ PARTIAL   1          1 getenv            
bot/guardian/guardian_bot.py                                 ⚠️ PARTIAL   0          0 getenv            
bot/heartbeat/monitor.py                                     ⚠️ PARTIAL   0          0 getenv            
bot/legacy_config/config_manager_core.py                     ⚠️ PARTIAL   0          0 getenv            
bot/liquidation/delta_realtime_websocket.py                  ⚠️ PARTIAL   0          0 getenv            
bot/liquidation/integrated_monitor.py                        ⚠️ PARTIAL   2          2 getenv            
bot/news/aggregator.py                                       ⚠️ PARTIAL   0          0 getenv            
bot/observability/errors/catalog.py                          ⚠️ PARTIAL   0          0 getenv            
bot/observability/errors/remediator.py                       ⚠️ PARTIAL   0          0 getenv            
bot/orders/executor.py                                       ⚠️ PARTIAL   0          0 getenv            
bot/reconciliation/data_sources.py                           ⚠️ PARTIAL   0          0 getenv            
bot/refactor/compat.py                                       ⚠️ PARTIAL   3          3 getenv            
bot/reports/pnl_delta.py                                     ⚠️ PARTIAL   0          0 getenv            
bot/reports/pnl_html.py                                      ⚠️ PARTIAL   0          0 getenv            
bot/safety/blocker_tracker.py                                ⚠️ PARTIAL   0          0 getenv            
bot/safety/config_guard.py                                   ⚠️ PARTIAL   0          0 getenv            
bot/safety/gatekeeper.py                                     ⚠️ PARTIAL   0          0 getenv            
bot/safety/order_confirmation_guard.py                       ⚠️ PARTIAL   0          0 getenv            
bot/strategy/async_gridbot.py                                ⚠️ PARTIAL   0          0 getenv            
bot/utils/env_loader.py                                      ⚠️ PARTIAL   0          0 getenv            
bot/volatility/iv_rv_tracker.py                              ⚠️ PARTIAL   0          0 getenv            
config/__init__.py                                           ⚠️ PARTIAL   0          0 getenv            
config/env_converter.py                                      ⚠️ PARTIAL   0          0 getenv            
config/loader.py                                             ⚠️ PARTIAL   0          0 getenv            
config/models.py                                             ⚠️ PARTIAL   0          0 getenv            
config/strategy_manager.py                                   ⚠️ PARTIAL   0          0 getenv            
services/quick_error_scan.py                                 ⚠️ PARTIAL   0          0 getenv            
webui/backend/app.py                                         ⚠️ PARTIAL   0          0 getenv            
webui/backend/brain_analyzer/file_monitor.py                 ⚠️ PARTIAL   0          0 getenv            
webui/backend/brain_analyzer/interactive_simulator.py        ⚠️ PARTIAL   0          0 getenv            
webui/backend/brain_analyzer/master_brain_reader.py          ⚠️ PARTIAL   0          0 getenv            
webui/backend/brain_analyzer/realtime_predictor.py           ⚠️ PARTIAL   0          0 getenv            
webui/backend/brain_analyzer/robust_simulator.py             ⚠️ PARTIAL   0          0 getenv            
webui/backend/brain_analyzer/state_reader.py                 ⚠️ PARTIAL   0          0 getenv            
webui/backend/dev_server.py                                  ⚠️ PARTIAL   0          0 getenv            
webui/backend/error_resolution.py                            ⚠️ PARTIAL   0          0 getenv            
webui/backend/errors/manager.py                              ⚠️ PARTIAL   0          0 getenv            
webui/backend/log_parser.py                                  ⚠️ PARTIAL   0          0 getenv            
webui/backend/routes/bot_control.py                          ⚠️ PARTIAL   0          0 getenv            
webui/backend/routes/capital.py                              ⚠️ PARTIAL   0          0 getenv            
webui/backend/routes/config.py                               ⚠️ PARTIAL   0          0 getenv            
webui/backend/routes/dynamic_brain.py                        ⚠️ PARTIAL   0          0 getenv            
webui/backend/routes/grid_mode.py                            ⚠️ PARTIAL   0          0 getenv            
webui/backend/routes/health.py                               ⚠️ PARTIAL   0          0 getenv            
webui/backend/routes/robustness.py                           ⚠️ PARTIAL   0          0 getenv            
webui/backend/routes/strategy.py                             ⚠️ PARTIAL   0          0 getenv            
webui/backend/routes/system.py                               ⚠️ PARTIAL   0          0 getenv            
webui/backend/routes/tmux.py                                 ⚠️ PARTIAL   0          0 getenv            
webui/backend/routes/yaml_config_api.py                      ⚠️ PARTIAL   0          0 getenv            
webui/backend/utils/auth.py                                  ⚠️ PARTIAL   1          1 getenv            
webui/backend/utils/pm2_adapter.py                           ⚠️ PARTIAL   0          0 getenv            
webui/backend/utils/yaml_config.py                           ⚠️ PARTIAL   0          0 getenv            
----------------------------------------------------------------------------------------------------

TOTAL FILES ANALYZED: 257
FILES WITH ISSUES: 55
MIGRATION COMPLETE: 202

====================================================================================================
OS.GETENV() USAGE REPORT
====================================================================================================


GRIDBOT_REF (1 occurrences)
--------------------------------------------------------------------------------
  📄 bot/api/client.py:18
     ref_str = os.getenv("GRIDBOT_REF")

LIVE_DELTA_API_KEY (1 occurrences)
--------------------------------------------------------------------------------
  📄 bot/liquidation/integrated_monitor.py:142
     self.api_key = os.getenv('DELTA_API_KEY') or os.getenv('LIVE_DELTA_API_KEY')

LIVE_DELTA_API_SECRET (1 occurrences)
--------------------------------------------------------------------------------
  📄 bot/liquidation/integrated_monitor.py:143
     self.api_secret = os.getenv('DELTA_API_SECRET') or os.getenv('LIVE_DELTA_API_SECRET')

REFACTOR_COMPAT (1 occurrences)
--------------------------------------------------------------------------------
  📄 bot/refactor/compat.py:42
     return os.getenv("REFACTOR_COMPAT", "1").strip()

REFACTOR_COMPAT_FAIL (1 occurrences)
--------------------------------------------------------------------------------
  📄 bot/refactor/compat.py:27
     ERROR_THRESHOLD = _compat_cfg.fail_threshold if _compat_cfg else int(os.getenv("REFACTOR_COMPAT_FAIL", "2"))

REFACTOR_COMPAT_WARN (1 occurrences)
--------------------------------------------------------------------------------
  📄 bot/refactor/compat.py:26
     WARNING_THRESHOLD = _compat_cfg.warn_threshold if _compat_cfg else int(os.getenv("REFACTOR_COMPAT_WARN", "1"))

WEBUI_AUTH_PASSWORD (1 occurrences)
--------------------------------------------------------------------------------
  📄 webui/backend/utils/auth.py:66
     valid_pass = os.getenv('WEBUI_AUTH_PASSWORD')


TOTAL os.getenv() CALLS: 7
UNIQUE ENVIRONMENT VARIABLES: 7

====================================================================================================
DOTENV IMPORT/USAGE REPORT
====================================================================================================


📄 bot/api/ccxt_handle.py
  Line 4: from dotenv import load_dotenv

📄 bot/guardian/guardian_bot.py
  Line 126: from dotenv import load_dotenv
  Line 392: from dotenv import dotenv_values
  Line 392: from dotenv import dotenv_values
  Line 134: load_dotenv(secrets_path)
  Line 139: load_dotenv(grid_config_path, override=True)

📄 bot/heartbeat/monitor.py
  Line 90: from dotenv import load_dotenv
  Line 359: from dotenv import load_dotenv
  Line 95: load_dotenv("secrets/api_keys.env")
  Line 96: load_dotenv("grid_config.env", override=True)
  Line 360: load_dotenv("grid_config.env")

📄 bot/liquidation/delta_realtime_websocket.py
  Line 601: from dotenv import load_dotenv
  Line 602: load_dotenv('secrets/api_keys.env')
  Line 603: load_dotenv('grid_config.env')

📄 bot/news/aggregator.py
  Line 15: from dotenv import load_dotenv
  Line 19: load_dotenv(CONFIG_FILE)

📄 bot/orders/executor.py
  Line 23: from dotenv import load_dotenv

📄 bot/safety/blocker_tracker.py
  Line 14: from dotenv import load_dotenv
  Line 26: load_dotenv(CONFIG_FILE)
  Line 82: load_dotenv(self.config_file, override=True)

📄 bot/safety/gatekeeper.py
  Line 41: from dotenv import load_dotenv
  Line 70: load_dotenv(config_file, override=True)

📄 bot/strategy/async_gridbot.py
  Line 3710: from dotenv import load_dotenv
  Line 3713: load_dotenv()

📄 bot/volatility/iv_rv_tracker.py
  Line 318: from dotenv import load_dotenv
  Line 319: load_dotenv(env_file)

📄 config/env_converter.py
  Line 9: from dotenv import load_dotenv
  Line 33: load_dotenv(env_file)
  Line 206: load_dotenv(self.env_file)

📄 config/loader.py
  Line 10: from dotenv import load_dotenv
  Line 92: load_dotenv(self.config_path)

📄 webui/backend/app.py
  Line 21: from dotenv import load_dotenv
  Line 26: load_dotenv(SECRETS_FILE, override=False)
  Line 29: load_dotenv(CONFIG_FILE, override=False)

📄 webui/backend/routes/robustness.py
  Line 33: from dotenv import load_dotenv
  Line 272: load_dotenv(CONFIG_FILE, override=True)

📄 webui/backend/utils/pm2_adapter.py
  Line 46: from dotenv import load_dotenv
  Line 49: load_dotenv(env_file)


TOTAL DOTENV REFERENCES: 38
FILES WITH DOTENV: 15

====================================================================================================
YAML CONFIGURATION COMPLETENESS CHECK
====================================================================================================

YAML Config Path: /Users/ssr/Projects/WorkingBot/config.yaml
Total YAML Keys: 301

Sample Keys:
  - active_strategies
  - api
  - api.credentials
  - api.credentials.use_env
  - api.demo
  - api.demo.base_url
  - api.demo.private_url
  - api.demo.product_id
  - api.demo.public_url
  - api.demo.testnet
  - api.demo.websocket_url
  - api.live
  - api.live.base_url
  - api.live.private_url
  - api.live.product_id
  - api.live.public_url
  - api.live.testnet
  - api.live.websocket_url
  - api.reference_level
  - bot
  ... and 281 more