"""
ML Trading API Endpoints

Provides REST API for:
- Viewing trade history
- Training ML model
- Getting predictions
- Generating automation rules

Created: January 14, 2026
"""

import sys
from pathlib import Path
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
import pandas as pd

# Add backend directory to path for direct file imports
_backend_dir = str(Path(__file__).parent.parent)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

# Add project root for config imports
_project_root = str(Path(__file__).parent.parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Import ML components directly (bypass options_strategy/__init__.py)
# This avoids the circular import chain
import importlib.util

def _import_direct(name, path):
    """Import a module directly from file path without triggering __init__.py"""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

# Import trade_logger directly and register in sys.modules for continuous_learning
_trade_logger_module = _import_direct(
    'trade_logger',  # Use actual name for sys.modules
    Path(__file__).parent.parent / 'options_strategy' / 'trade_logger.py'
)
trade_logger = _trade_logger_module.trade_logger

# Import ml_model directly
_ml_model_module = _import_direct(
    'ml_model_direct', 
    Path(__file__).parent.parent / 'options_strategy' / 'ml_model.py'
)
options_ml_model = _ml_model_module.options_ml_model

# Import style_profiler directly and register in sys.modules for decision_engine
_style_profiler_module = _import_direct(
    'style_profiler',  # Use actual name for sys.modules
    Path(__file__).parent.parent / 'options_strategy' / 'style_profiler.py'
)
style_profiler = _style_profiler_module.style_profiler

# Import opportunity_scanner directly and register in sys.modules for decision_engine
_scanner_module = _import_direct(
    'opportunity_scanner',  # Use actual name for sys.modules
    Path(__file__).parent.parent / 'options_strategy' / 'opportunity_scanner.py'
)
opportunity_scanner = _scanner_module.opportunity_scanner

# Import regime_detector directly and register in sys.modules for decision_engine
_regime_module = _import_direct(
    'regime_detector',  # Use actual name for sys.modules
    Path(__file__).parent.parent / 'options_strategy' / 'regime_detector.py'
)
regime_detector = _regime_module.regime_detector

ml_trading_bp = Blueprint('ml_trading', __name__)


# ============================================================
# TRADE HISTORY ENDPOINTS
# ============================================================

@ml_trading_bp.route('/api/ml/trades', methods=['GET'])
def get_trades():
    """Get all trades with optional filtering."""
    try:
        days = request.args.get('days', type=int)
        symbol = request.args.get('symbol')
        
        if symbol:
            df = trade_logger.get_trades_by_symbol(symbol)
        elif days:
            df = trade_logger.get_recent_trades(days)
        else:
            df = trade_logger.get_all_trades()
        
        # Convert to list of dicts
        trades = df.to_dict('records') if len(df) > 0 else []
        
        return jsonify({
            'success': True,
            'trades': trades,
            'count': len(trades),
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/trades/stats', methods=['GET'])
def get_trade_stats():
    """Get trade statistics."""
    try:
        stats = trade_logger.get_trade_statistics()
        
        return jsonify({
            'success': True,
            'statistics': stats,
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/trades/log', methods=['POST'])
def log_trade():
    """Manually log a trade (for testing or manual entry)."""
    try:
        data = request.json
        
        required = ['symbol', 'action', 'quantity', 'price']
        for field in required:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}',
                }), 400
        
        trade_id = trade_logger.log_trade(
            symbol=data['symbol'],
            action=data['action'],
            quantity=data['quantity'],
            price=data['price'],
            side=data.get('side', 'OPEN'),
            position_before=data.get('position_before'),
            market_data=data.get('market_data'),
            greeks=data.get('greeks'),
            strategy_tag=data.get('strategy_tag', ''),
            automation_rule=data.get('automation_rule', ''),
            user_notes=data.get('user_notes', ''),
        )
        
        return jsonify({
            'success': True,
            'trade_id': trade_id,
            'message': f'Trade logged successfully',
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/trades/<trade_id>/outcome', methods=['PUT'])
def update_trade_outcome(trade_id):
    """Update trade outcome when position is closed."""
    try:
        data = request.json
        
        trade_logger.update_trade_outcome(
            trade_id=trade_id,
            pnl=data.get('pnl', 0),
            pnl_pct=data.get('pnl_pct', 0),
            duration_hours=data.get('duration_hours', 0),
            max_profit=data.get('max_profit', 0),
            max_loss=data.get('max_loss', 0),
            status=data.get('status', 'closed'),
        )
        
        return jsonify({
            'success': True,
            'message': f'Trade {trade_id} outcome updated',
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/trades/export', methods=['GET'])
def export_trades():
    """Export trades for ML training."""
    try:
        output_file = trade_logger.export_for_ml()
        
        return jsonify({
            'success': True,
            'file': output_file,
            'message': 'Trades exported successfully',
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


# ============================================================
# ML MODEL ENDPOINTS
# ============================================================

@ml_trading_bp.route('/api/ml/model/status', methods=['GET'])
def get_model_status():
    """Get ML model status and metrics."""
    try:
        status = options_ml_model.get_model_status()
        
        return jsonify({
            'success': True,
            **status,
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/model/train', methods=['POST'])
def train_model():
    """Train or retrain the ML model."""
    try:
        force = request.json.get('force', False) if request.json else False
        
        result = options_ml_model.train(force=force)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/model/predict', methods=['POST'])
def predict_trade():
    """Get prediction for a potential trade."""
    try:
        trade_params = request.json
        
        if not trade_params:
            return jsonify({
                'success': False,
                'error': 'Trade parameters required',
            }), 400
        
        result = options_ml_model.predict(trade_params)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


# ============================================================
# PATTERN ANALYSIS ENDPOINTS
# ============================================================

@ml_trading_bp.route('/api/ml/patterns', methods=['GET'])
def analyze_patterns():
    """Analyze trading patterns from historical data."""
    try:
        result = options_ml_model.analyze_patterns()
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/automation-rules', methods=['GET'])
def get_automation_rules():
    """Generate automation rule suggestions."""
    try:
        result = options_ml_model.generate_automation_rules()
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/suggestion', methods=['POST'])
def get_trade_suggestion():
    """Get trade suggestion based on current market conditions."""
    try:
        market_conditions = request.json or {}
        
        result = options_ml_model.get_trade_suggestion(market_conditions)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


# ============================================================
# DASHBOARD SUMMARY
# ============================================================

@ml_trading_bp.route('/api/ml/dashboard', methods=['GET'])
def get_ml_dashboard():
    """Get comprehensive ML dashboard data."""
    try:
        # Model status
        model_status = options_ml_model.get_model_status()
        
        # Trade statistics
        trade_stats = trade_logger.get_trade_statistics()
        
        # Recent trades
        recent_trades = trade_logger.get_recent_trades(days=7)
        recent_count = len(recent_trades)
        
        # Pattern analysis (if enough data)
        patterns = None
        if trade_stats.get('closed_trades', 0) >= 10:
            patterns_result = options_ml_model.analyze_patterns()
            if patterns_result.get('success'):
                patterns = patterns_result.get('patterns')
        
        # Automation rules (if model trained)
        automation_rules = None
        if model_status.get('is_trained'):
            rules_result = options_ml_model.generate_automation_rules()
            if rules_result.get('success'):
                automation_rules = rules_result.get('rules')
        
        return jsonify({
            'success': True,
            'model': model_status,
            'statistics': trade_stats,
            'recent_trades_count': recent_count,
            'patterns': patterns,
            'automation_rules': automation_rules,
            'readiness': {
                'can_train': model_status.get('can_train', False),
                'is_trained': model_status.get('is_trained', False),
                'trades_needed': max(0, 30 - trade_stats.get('total_trades', 0)),
                'closed_trades_needed': max(0, 20 - trade_stats.get('closed_trades', 0)),
            },
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


# ============================================================
# STYLE PROFILER ENDPOINTS (Phase 2)
# ============================================================

@ml_trading_bp.route('/api/ml/style/profile', methods=['GET'])
def get_style_profile():
    """
    Get complete trading style profile.
    
    Returns:
        TradingStyleDNA with all style attributes
    """
    try:
        force_refresh = request.args.get('refresh', 'false').lower() == 'true'
        
        if force_refresh:
            # Re-analyze from trade data
            profile = style_profiler.analyze_trading_style()
        else:
            # Get cached or analyze
            profile = style_profiler.get_cached_profile()
            if not profile:
                profile = style_profiler.analyze_trading_style()
        
        return jsonify({
            'success': True,
            'profile': profile.to_dict() if profile else None,
            'has_profile': profile is not None
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/style/summary', methods=['GET'])
def get_style_summary():
    """
    Get human-readable style summary with strengths and areas to improve.
    """
    try:
        summary = style_profiler.get_style_summary()
        
        return jsonify({
            'success': True,
            **summary
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/style/analyze', methods=['POST'])
def analyze_style():
    """
    Force re-analysis of trading style from all available data.
    
    Body:
        min_trades: int (optional) - Minimum trades required for analysis
    """
    try:
        data = request.json or {}
        min_trades = data.get('min_trades', 10)
        
        profile = style_profiler.analyze_trading_style(min_trades=min_trades)
        
        return jsonify({
            'success': True,
            'profile': profile.to_dict(),
            'message': f'Analyzed {profile.total_trades_analyzed} trades',
            'confidence': profile.confidence
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/style/validate', methods=['POST'])
def validate_trade_style():
    """
    Validate if a proposed trade matches the trader's style.
    
    Body:
        trade: dict - Proposed trade parameters
            - option_type: "Call" or "Put"
            - action: "BUY" or "SELL"
            - quantity: int
            - (optional) hour: int - Hour of proposed entry
    
    Returns:
        match_score: 0-1 how well trade matches style
        warnings: list of style deviations
        recommendations: list of adjustments
    """
    try:
        trade = request.json
        
        if not trade:
            return jsonify({
                'success': False,
                'error': 'Trade parameters required',
            }), 400
        
        profile = style_profiler.get_cached_profile()
        
        if not profile or profile.confidence < 0.2:
            return jsonify({
                'success': True,
                'match_score': 1.0,
                'warnings': [],
                'recommendations': [],
                'message': 'Insufficient data for style validation'
            })
        
        warnings = []
        recommendations = []
        scores = []
        
        # Check option type preference
        option_type = trade.get('option_type', '').upper()
        if option_type == 'CALL':
            type_match = profile.call_preference
        elif option_type == 'PUT':
            type_match = 1 - profile.call_preference
        else:
            type_match = 0.5
        scores.append(type_match)
        
        if type_match < 0.3:
            warnings.append(f"You typically trade {'Calls' if profile.call_preference > 0.5 else 'Puts'} more often")
        
        # Check action preference
        action = trade.get('action', '').upper()
        if action == 'BUY':
            action_match = profile.buy_preference
        elif action == 'SELL':
            action_match = 1 - profile.buy_preference
        else:
            action_match = 0.5
        scores.append(action_match)
        
        if action_match < 0.3:
            warnings.append(f"You typically {'buy' if profile.buy_preference > 0.5 else 'sell'} more often")
        
        # Check timing
        hour = trade.get('hour')
        if hour is not None and profile.preferred_entry_hours:
            if hour in profile.preferred_entry_hours:
                scores.append(1.0)
            else:
                scores.append(0.5)
                warnings.append(f"Outside your preferred trading hours ({profile.preferred_entry_hours})")
                recommendations.append(f"Consider trading during hours {profile.preferred_entry_hours}")
        
        # Check position size
        quantity = trade.get('quantity', 0)
        if quantity > 0 and profile.avg_position_size > 0:
            size_ratio = quantity / profile.avg_position_size
            if size_ratio > 2:
                warnings.append(f"Position size {quantity} is much larger than your average ({profile.avg_position_size:.0f})")
                recommendations.append(f"Consider reducing to {profile.avg_position_size:.0f}")
                scores.append(0.3)
            elif size_ratio < 0.5:
                scores.append(0.7)
            else:
                scores.append(1.0)
        
        match_score = sum(scores) / len(scores) if scores else 1.0
        
        return jsonify({
            'success': True,
            'match_score': round(match_score, 2),
            'warnings': warnings,
            'recommendations': recommendations,
            'style_confidence': profile.confidence
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


# ============================================================
# PHASE 3: OPPORTUNITY SCANNER ENDPOINTS
# ============================================================

@ml_trading_bp.route('/api/ml/scanner/scan', methods=['POST'])
def scan_opportunities():
    """Scan options chain for opportunities matching trader's style."""
    try:
        import asyncio
        
        data = request.json or {}
        symbol = data.get('symbol', 'BTC')
        
        # Run async scan
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            opportunities = loop.run_until_complete(
                opportunity_scanner.scan_options_chain(symbol)
            )
        finally:
            loop.close()
        
        return jsonify({
            'success': True,
            'opportunities': [o.to_dict() for o in opportunities[:20]],
            'count': len(opportunities),
            'scanned_at': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/scanner/opportunities', methods=['GET'])
def get_opportunities():
    """Get cached opportunities from last scan."""
    try:
        opportunities = opportunity_scanner.get_cached_opportunities()
        
        return jsonify({
            'success': True,
            'opportunities': [o.to_dict() for o in opportunities],
            'count': len(opportunities)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/scanner/signals', methods=['GET'])
def get_signals():
    """Get active trading signals."""
    try:
        signals = opportunity_scanner.get_active_signals()
        
        return jsonify({
            'success': True,
            'signals': [s.to_dict() for s in signals],
            'count': len(signals)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/scanner/generate-signals', methods=['POST'])
def generate_signals():
    """Generate trading signals from opportunities."""
    try:
        data = request.json or {}
        min_score = data.get('min_score', 0.6)
        max_signals = data.get('max_signals', 5)
        
        opportunities = opportunity_scanner.get_cached_opportunities()
        signals = opportunity_scanner.generate_signals(
            opportunities,
            max_signals=max_signals,
            min_score=min_score
        )
        
        return jsonify({
            'success': True,
            'signals': [s.to_dict() for s in signals],
            'count': len(signals)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/scanner/status', methods=['GET'])
def get_scanner_status():
    """Get scanner status and statistics."""
    try:
        status = opportunity_scanner.get_scanner_status()
        
        return jsonify({
            'success': True,
            **status
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


# ============================================================
# PHASE 3: MARKET REGIME ENDPOINTS
# ============================================================

@ml_trading_bp.route('/api/ml/regime/detect', methods=['POST'])
def detect_regime():
    """Detect current market regime."""
    try:
        data = request.json or {}
        symbol = data.get('symbol', 'BTC')
        current_price = data.get('current_price', 0)
        iv = data.get('iv', 0)
        
        regime = regime_detector.detect_regime(
            symbol=symbol,
            current_price=current_price,
            iv=iv
        )
        
        return jsonify({
            'success': True,
            'regime': regime.to_dict(),
            'summary': regime.get_summary()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/regime/current', methods=['GET'])
def get_current_regime():
    """Get cached market regime."""
    try:
        symbol = request.args.get('symbol', 'BTC')
        regime = regime_detector.get_cached_regime(symbol)
        
        if regime:
            return jsonify({
                'success': True,
                'regime': regime.to_dict(),
                'summary': regime.get_summary()
            })
        else:
            return jsonify({
                'success': True,
                'regime': None,
                'message': 'No regime data available. Call /api/ml/regime/detect first.'
            })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/regime/should-trade', methods=['GET'])
def should_trade():
    """Check if conditions are favorable for trading."""
    try:
        style_pref = request.args.get('style', 'neutral')
        
        should, reason = regime_detector.should_trade_now(style_pref)
        score = regime_detector.get_trading_conditions_score(style_pref)
        
        return jsonify({
            'success': True,
            'should_trade': should,
            'reason': reason,
            'conditions_score': round(score, 2)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


# ============================================================
# PHASE 4: DECISION ENGINE ENDPOINTS
# ============================================================

# Import decision engine
try:
    _decision_engine_module = _import_direct(
        'decision_engine_direct',
        Path(__file__).parent.parent / 'options_strategy' / 'decision_engine.py'
    )
    decision_engine = _decision_engine_module.decision_engine
except Exception as e:
    print(f"Warning: Could not import decision_engine: {e}")
    decision_engine = None


@ml_trading_bp.route('/api/ml/decision/evaluate', methods=['POST'])
def evaluate_signal():
    """Evaluate a trading signal and return decision."""
    if not decision_engine:
        return jsonify({'success': False, 'error': 'Decision engine not available'}), 500
    
    try:
        from options_strategy.opportunity_scanner import TradingSignal
        
        data = request.json or {}
        
        # Create signal from request
        signal = TradingSignal(
            signal_id=data.get('signal_id', f"SIG-{datetime.now().strftime('%Y%m%d%H%M%S')}"),
            symbol=data.get('symbol', ''),
            action=data.get('action', 'BUY'),
            option_type=data.get('option_type', 'call'),
            strike=data.get('strike', 0),
            expiry=data.get('expiry', ''),
            quantity=data.get('quantity', 1),
            entry_price=data.get('entry_price', 0),
            stop_loss=data.get('stop_loss', 0),
            take_profit=data.get('take_profit', 0),
            max_loss=data.get('max_loss', 0),
            confidence=data.get('confidence', 0.5),
            risk_reward=data.get('risk_reward', 1.0)
        )
        
        decision = decision_engine.evaluate_signal(signal)
        
        return jsonify({
            'success': True,
            'decision': decision.to_dict()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/decision/pending', methods=['GET'])
def get_pending_decisions():
    """Get pending decisions awaiting approval."""
    if not decision_engine:
        return jsonify({'success': False, 'error': 'Decision engine not available'}), 500
    
    try:
        decisions = decision_engine.get_pending_decisions()
        
        return jsonify({
            'success': True,
            'decisions': [d.to_dict() for d in decisions],
            'count': len(decisions)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/decision/<decision_id>/approve', methods=['POST'])
def approve_decision(decision_id):
    """Approve a pending decision."""
    if not decision_engine:
        return jsonify({'success': False, 'error': 'Decision engine not available'}), 500
    
    try:
        result = decision_engine.approve_decision(decision_id)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/decision/<decision_id>/reject', methods=['POST'])
def reject_decision(decision_id):
    """Reject a pending decision."""
    if not decision_engine:
        return jsonify({'success': False, 'error': 'Decision engine not available'}), 500
    
    try:
        data = request.json or {}
        reason = data.get('reason', '')
        
        result = decision_engine.reject_decision(decision_id, reason)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/decision/status', methods=['GET'])
def get_engine_status():
    """Get decision engine status."""
    if not decision_engine:
        return jsonify({'success': False, 'error': 'Decision engine not available'}), 500
    
    try:
        status = decision_engine.get_engine_status()
        
        return jsonify({
            'success': True,
            **status
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/decision/autonomy', methods=['POST'])
def set_autonomy():
    """Set autonomy level."""
    if not decision_engine:
        return jsonify({'success': False, 'error': 'Decision engine not available'}), 500
    
    try:
        data = request.json or {}
        level = data.get('level', 'advisory')
        
        result = decision_engine.set_autonomy_level(level)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/decision/risk-limits', methods=['POST'])
def set_risk_limits():
    """Update risk limits."""
    if not decision_engine:
        return jsonify({'success': False, 'error': 'Decision engine not available'}), 500
    
    try:
        limits = request.json or {}
        
        result = decision_engine.set_risk_limits(limits)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/circuit-breaker/status', methods=['GET'])
def get_circuit_breaker():
    """Get circuit breaker status."""
    if not decision_engine:
        return jsonify({'success': False, 'error': 'Decision engine not available'}), 500
    
    try:
        status = decision_engine.get_circuit_breaker_status()
        
        return jsonify({
            'success': True,
            'circuit_breaker': status.to_dict()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/circuit-breaker/reset', methods=['POST'])
def reset_circuit_breaker():
    """Reset circuit breaker."""
    if not decision_engine:
        return jsonify({'success': False, 'error': 'Decision engine not available'}), 500
    
    try:
        result = decision_engine.reset_circuit_breaker(manual=True)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/decision/record-outcome', methods=['POST'])
def record_outcome():
    """Record trade outcome for circuit breaker updates."""
    if not decision_engine:
        return jsonify({'success': False, 'error': 'Decision engine not available'}), 500
    
    try:
        trade_result = request.json or {}
        
        decision_engine.record_trade_outcome(trade_result)
        
        return jsonify({
            'success': True,
            'message': 'Outcome recorded',
            'circuit_breaker': decision_engine.get_circuit_breaker_status().to_dict()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


# ============================================================
# PHASE 5: CONTINUOUS LEARNING ENDPOINTS
# ============================================================

# Import continuous learning module
try:
    _continuous_learning_module = _import_direct(
        'continuous_learning_direct',
        Path(__file__).parent.parent / 'options_strategy' / 'continuous_learning.py'
    )
    reinforcement_learner = _continuous_learning_module.reinforcement_learner
    model_monitor = _continuous_learning_module.model_monitor
except Exception as e:
    print(f"Warning: Could not import continuous_learning: {e}")
    reinforcement_learner = None
    model_monitor = None


@ml_trading_bp.route('/api/ml/learning/from-trade', methods=['POST'])
def learn_from_trade():
    """Learn from a completed trade outcome."""
    if not reinforcement_learner:
        return jsonify({'success': False, 'error': 'Reinforcement learner not available'}), 500
    
    try:
        data = request.json or {}
        trade = data.get('trade', {})
        outcome = data.get('outcome', {})
        context = data.get('context')
        
        result = reinforcement_learner.learn_from_trade(trade, outcome, context)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/learning/recommendation', methods=['POST'])
def get_learning_recommendation():
    """Get action recommendation based on learned Q-values."""
    if not reinforcement_learner:
        return jsonify({'success': False, 'error': 'Reinforcement learner not available'}), 500
    
    try:
        state = request.json or {}
        
        recommendation = reinforcement_learner.get_action_recommendation(state)
        
        return jsonify({
            'success': True,
            'recommendation': recommendation,
            'learning_stats': reinforcement_learner.get_learning_stats()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/learning/stats', methods=['GET'])
def get_learning_stats():
    """Get reinforcement learning statistics."""
    if not reinforcement_learner:
        return jsonify({'success': False, 'error': 'Reinforcement learner not available'}), 500
    
    try:
        stats = reinforcement_learner.get_learning_stats()
        
        return jsonify({
            'success': True,
            **stats
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/monitor/metrics', methods=['GET'])
def get_performance_metrics():
    """Get model performance metrics."""
    if not model_monitor:
        return jsonify({'success': False, 'error': 'Model monitor not available'}), 500
    
    try:
        days = request.args.get('days', 30, type=int)
        
        metrics = model_monitor.calculate_metrics(days)
        
        return jsonify({
            'success': True,
            'metrics': metrics.to_dict()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/monitor/drift', methods=['GET'])
def detect_drift():
    """Detect model drift from trading style."""
    if not model_monitor:
        return jsonify({'success': False, 'error': 'Model monitor not available'}), 500
    
    try:
        drift = model_monitor.detect_model_drift()
        
        return jsonify({
            'success': True,
            **drift
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/monitor/should-retrain', methods=['GET'])
def should_retrain():
    """Check if model should be retrained."""
    if not model_monitor:
        return jsonify({'success': False, 'error': 'Model monitor not available'}), 500
    
    try:
        should, reason = model_monitor.should_retrain()
        
        return jsonify({
            'success': True,
            'should_retrain': should,
            'reason': reason
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/monitor/alerts', methods=['GET'])
def get_monitor_alerts():
    """Get performance monitoring alerts."""
    if not model_monitor:
        return jsonify({'success': False, 'error': 'Model monitor not available'}), 500
    
    try:
        severity = request.args.get('severity')
        
        alerts = model_monitor.get_alerts(severity)
        
        return jsonify({
            'success': True,
            'alerts': alerts
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/monitor/summary', methods=['GET'])
def get_monitoring_summary():
    """Get comprehensive monitoring summary."""
    if not model_monitor:
        return jsonify({'success': False, 'error': 'Model monitor not available'}), 500
    
    try:
        summary = model_monitor.get_monitoring_summary()
        
        return jsonify({
            'success': True,
            **summary
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ml_trading_bp.route('/api/ml/monitor/track', methods=['POST'])
def track_trade_for_monitoring():
    """Track a trade for performance monitoring."""
    if not model_monitor:
        return jsonify({'success': False, 'error': 'Model monitor not available'}), 500
    
    try:
        data = request.json or {}
        trade = data.get('trade', {})
        is_ai = data.get('is_ai_trade', True)
        
        model_monitor.track_trade(trade, is_ai)
        
        return jsonify({
            'success': True,
            'message': 'Trade tracked'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


# ============================================================
# DELTA EXCHANGE TRADE SYNC ENDPOINTS
# ============================================================

# Import delta fetcher
try:
    _delta_fetcher_module = _import_direct(
        'delta_fetcher',
        Path(__file__).parent.parent / 'options_strategy' / 'delta_fetcher.py'
    )
    delta_fetcher = _delta_fetcher_module.delta_fetcher
except Exception as e:
    print(f"Warning: Could not import delta_fetcher: {e}")
    delta_fetcher = None


@ml_trading_bp.route('/api/ml/delta/status', methods=['GET'])
def get_delta_sync_status():
    """Get Delta Exchange sync status."""
    if not delta_fetcher:
        return jsonify({'success': False, 'error': 'Delta fetcher not available'}), 500
    
    try:
        status = delta_fetcher.get_sync_status()
        return jsonify({
            'success': True,
            **status
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@ml_trading_bp.route('/api/ml/delta/sync', methods=['POST'])
def sync_delta_trades():
    """Sync trades from Delta Exchange."""
    if not delta_fetcher:
        return jsonify({'success': False, 'error': 'Delta fetcher not available'}), 500
    
    try:
        data = request.json or {}
        days_back = data.get('days', 30)
        
        result = delta_fetcher.sync_trades(days_back=days_back)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@ml_trading_bp.route('/api/ml/delta/daily', methods=['GET'])
def get_delta_daily_summary():
    """Get daily trading summary from Delta Exchange data."""
    if not delta_fetcher:
        return jsonify({'success': False, 'error': 'Delta fetcher not available'}), 500
    
    try:
        date = request.args.get('date')  # YYYY-MM-DD format
        summary = delta_fetcher.get_daily_summary(date)
        
        return jsonify({
            'success': True,
            **summary
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@ml_trading_bp.route('/api/ml/delta/trades', methods=['GET'])
def get_delta_trades():
    """Get synced trades from Delta Exchange."""
    if not delta_fetcher:
        return jsonify({'success': False, 'error': 'Delta fetcher not available'}), 500
    
    try:
        days = request.args.get('days', 30, type=int)
        df = delta_fetcher.get_trades_for_ml()
        
        if len(df) == 0:
            return jsonify({
                'success': True,
                'trades': [],
                'total': 0
            })
        
        # Filter by days using timezone-aware cutoff
        if days:
            from datetime import timezone
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            df['created_at_dt'] = pd.to_datetime(df['created_at'], utc=True)
            df = df[df['created_at_dt'] > cutoff]
            # Drop the helper column
            df = df.drop(columns=['created_at_dt'])
        
        trades = df.to_dict('records')
        
        return jsonify({
            'success': True,
            'trades': trades,
            'total': len(trades)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@ml_trading_bp.route('/api/ml/delta/train-model', methods=['POST'])
def train_model_from_delta():
    """Train ML model using Delta Exchange trade history with calculated PnL."""
    if not delta_fetcher:
        return jsonify({'success': False, 'error': 'Delta fetcher not available'}), 500
    
    try:
        # Get paired trades with calculated PnL
        df = delta_fetcher.get_paired_trades_for_ml()
        
        if len(df) < 5:
            return jsonify({
                'success': False,
                'error': f'Not enough paired trades for training. Have {len(df)}, need at least 5 symbol groups.'
            }), 400
        
        # Calculate training stats
        total_symbols = len(df)
        closed_positions = len(df[df['is_closed'] == True])
        winners = len(df[df['is_win'] == 1])
        losers = len(df[df['is_win'] == 0])
        total_pnl = df['net_pnl'].sum()
        
        # Train a simple model on the Delta data directly
        from sklearn.ensemble import GradientBoostingClassifier
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import StandardScaler
        
        # Prepare features
        feature_cols = ['hour', 'day_of_week', 'is_call', 'is_net_buyer', 'strike',
                       'total_sell_qty', 'avg_sell_price', 'avg_buy_price', 'num_trades']
        
        # Ensure all columns exist
        for col in feature_cols:
            if col not in df.columns:
                df[col] = 0
        
        X = df[feature_cols].fillna(0).values
        y = df['is_win'].values
        
        # Check we have both classes
        if len(set(y)) < 2:
            # All trades same outcome - report stats but can't train
            return jsonify({
                'success': True,
                'message': 'All trades have same outcome - cannot train classifier',
                'total_symbols': total_symbols,
                'closed_positions': closed_positions,
                'winners': winners,
                'losers': losers,
                'total_pnl': round(total_pnl, 2),
                'win_rate': round(winners / total_symbols * 100, 1) if total_symbols > 0 else 0,
                'model_trained': False,
                'model_accuracy': 0
            })
        
        # Split and train
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        model = GradientBoostingClassifier(n_estimators=50, max_depth=3, random_state=42)
        model.fit(X_train_scaled, y_train)
        
        accuracy = model.score(X_test_scaled, y_test)
        
        # Save model to ML model store
        options_ml_model.model = model
        options_ml_model.scaler = scaler
        options_ml_model.feature_columns = feature_cols
        options_ml_model.model_metadata = {
            'accuracy': accuracy,
            'trained_on': total_symbols,
            'source': 'delta_exchange',
            'feature_columns': feature_cols
        }
        options_ml_model._save_model()
        
        return jsonify({
            'success': True,
            'total_symbols': total_symbols,
            'closed_positions': closed_positions,
            'winners': winners,
            'losers': losers,
            'total_pnl': round(total_pnl, 2),
            'win_rate': round(winners / total_symbols * 100, 1) if total_symbols > 0 else 0,
            'model_trained': True,
            'model_accuracy': round(accuracy * 100, 1)
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500