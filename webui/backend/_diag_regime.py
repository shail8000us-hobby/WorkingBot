#!/usr/bin/env python3
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
# Load session directly from JSON storage
data_dir = os.path.join(os.path.dirname(__file__), 'data', 'mmm_sessions')
sid = 'mmm20feb26-5'
fpath = os.path.join(data_dir, f'{sid}.json')
if not os.path.exists(fpath):
    # Try finding it
    for f in os.listdir(data_dir):
        if sid in f:
            fpath = os.path.join(data_dir, f)
            break
with open(fpath) as f:
    session = json.load(f)
if not session:
    print('Session not found')
    sys.exit(1)
print('Paused:', session.get('paused'))
print('Status:', session.get('status'))
print('Vol regime:', session.get('_vol_regime'))
print('IV hist len:', len(session.get('_vol_iv_history', []) or []))
print('Gamma regime:', session.get('_gamma_regime'))
print('Gamma hist len:', len(session.get('_gamma_history', []) or []))
print('Trend regime:', session.get('_trend_regime'))
print('Trend anchor:', session.get('_trend_anchor_spot'))
print('Regime action:', session.get('_regime_action'))
print('Vol score:', session.get('_vol_regime_score'))
print('IV change:', session.get('_vol_iv_change_pct'))
print('RV:', session.get('_vol_rv_annualized'))
print('Dollar gamma:', session.get('_portfolio_dollar_gamma'))
print('Portfolio gamma:', session.get('_portfolio_gamma'))
print('Trend move:', session.get('_trend_move_pct'))
print('EMA slope:', session.get('_trend_ema_slope'))
