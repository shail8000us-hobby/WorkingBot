"""
AI Advisor API Blueprint

This module handles all API routes related to AI/ML features including:
- AI Advisor (conversational Q&A with Ollama + fallback)
- Institutional Analytics (performance, risk, execution)
- Advanced ML (Monte Carlo, predictions, win probability)
- Market Regime Detection and Optimization

Routes:
- POST /api/ai/ask - Ask the AI Advisor a question
- GET  /api/ai/health - Check AI Advisor health status
- GET  /api/institutional/comprehensive_analysis - Get comprehensive analysis
- POST /api/institutional/ask - Ask intelligent advisor
- GET  /api/institutional/performance - Get performance analytics
- GET  /api/institutional/risk - Get risk analytics
- GET  /api/institutional/execution - Get execution quality analytics
- GET  /api/institutional/market_regime - Get market regime analysis
- GET  /api/institutional/optimization - Get grid optimization recommendations
- GET  /api/institutional/log_analysis - Get log analysis
- GET  /api/institutional/monte_carlo - Run Monte Carlo simulation
- GET  /api/institutional/ml_prediction - Get ML-based price predictions
- POST /api/institutional/win_probability - Calculate win probability for a trade

Dependencies:
- bot.ai.conversational.intelligent_advisor (Ollama-based AI)
- bot.ai.advisor (rule-based fallback)
- bot.ai.institutional_advisor (institutional analytics)
- bot.ai.analytics (performance/risk/execution analytics)
- bot.ai.predictive (market regime/optimization)
- bot.ai.advanced (Monte Carlo/ML predictions)
"""

import logging
from datetime import datetime
from pathlib import Path
from flask import Blueprint, jsonify, request

try:
    from webui.backend.utils.response_helpers import convert_numpy_types
    NUMPY_CONVERSION_AVAILABLE = True
except ImportError:
    NUMPY_CONVERSION_AVAILABLE = False
    def convert_numpy_types(obj):
        return obj

log = logging.getLogger(__name__)

# Create blueprint
ai_bp = Blueprint('ai', __name__)

# File paths
BASE_DIR = Path(__file__).parent.parent.parent.parent

# ============================================================================
# AI Advisor Routes (Conversational Q&A)
# ============================================================================

@ai_bp.route('/api/ai/ask', methods=['POST'])
def ai_ask():
    """Ask the AI Advisor a question (Ollama + Fallback)"""
    try:
        data = request.json
        question = data.get('question', '')
        
        if not question:
            return jsonify({
                'success': False,
                'error': 'No question provided'
            }), 400
        
        # Try intelligent advisor with Ollama first
        try:
            from bot.ai.conversational.intelligent_advisor import get_intelligent_advisor
            
            advisor = get_intelligent_advisor()
            response = advisor.ask(question)
            
            # Add source indicator
            if 'answer' in response:
                response['source'] = 'ollama'
                response['success'] = True
                return jsonify(response), 200
        except Exception as ollama_error:
            # Log Ollama failure
            log.warning(f"Ollama advisor failed: {ollama_error}")
            
            # Fallback to rule-based advisor
            try:
                from bot.ai.advisor import get_ai_advisor
                
                advisor = get_ai_advisor()
                response = advisor.ask(question)
                response['source'] = 'rule_based'
                response['fallback'] = True
                response['ollama_error'] = str(ollama_error)
                
                return jsonify(response), 200
            except Exception as fallback_error:
                return jsonify({
                    'success': False,
                    'error': f'Both AI systems failed. Ollama: {ollama_error}, Fallback: {fallback_error}',
                    'answer': 'AI Advisor is temporarily unavailable. Please try again later.',
                    'suggestions': [],
                    'related_links': []
                }), 500
                
    except Exception as e:
        log.error(f"Error in AI ask: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'answer': 'An unexpected error occurred. Please try again.',
            'suggestions': [],
            'related_links': []
        }), 500


@ai_bp.route('/api/ai/health', methods=['GET'])
def ai_health():
    """Check AI Advisor health status"""
    
    health_status = {
        'success': True,
        'timestamp': datetime.now().isoformat(),
        'ollama_status': 'disconnected',
        'ollama_model': None,
        'fallback_status': 'available',
        'recommended_source': 'rule_based'
    }
    
    # Check Ollama connection
    try:
        import requests
        response = requests.get('http://localhost:11434/api/tags', timeout=2)
        if response.status_code == 200:
            data = response.json()
            models = data.get('models', [])
            if models:
                health_status['ollama_status'] = 'connected'
                health_status['ollama_model'] = models[0].get('name', 'unknown')
                health_status['recommended_source'] = 'ollama'
    except Exception as e:
        health_status['ollama_error'] = str(e)
    
    # Check rule-based advisor
    try:
        from bot.ai.advisor import get_ai_advisor
        advisor = get_ai_advisor()
        health_status['fallback_status'] = 'available'
    except Exception as e:
        health_status['fallback_status'] = 'error'
        health_status['fallback_error'] = str(e)
    
    return jsonify(health_status), 200


# ============================================================================
# Institutional AI Routes
# ============================================================================

@ai_bp.route('/api/institutional/comprehensive_analysis', methods=['GET'])
def get_institutional_analysis():
    """Get comprehensive institutional-grade analysis"""
    try:
        from bot.ai.institutional_advisor import get_institutional_advisor
        
        lookback_days = request.args.get('lookback_days', 30, type=int)
        force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
        
        advisor = get_institutional_advisor()
        analysis = advisor.get_comprehensive_analysis(lookback_days, force_refresh)
        
        # Convert numpy types to native Python types
        analysis = convert_numpy_types(analysis)
        
        return jsonify({
            'success': True,
            'analysis': analysis
        }), 200
    except Exception as e:
        log.error(f"Error getting institutional analysis: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ai_bp.route('/api/institutional/ask', methods=['POST'])
def institutional_ask():
    """Ask the intelligent AI advisor a question"""
    try:
        from bot.ai.conversational import get_intelligent_advisor
        
        data = request.json
        question = data.get('question', '')
        
        if not question:
            return jsonify({
                'success': False,
                'error': 'No question provided'
            }), 400
        
        advisor = get_intelligent_advisor()
        response = advisor.ask(question)
        
        # Convert numpy types to native Python types
        response = convert_numpy_types(response)
        
        # Ensure success field is present
        if 'success' not in response:
            response['success'] = True
        
        return jsonify(response), 200
    except Exception as e:
        log.error(f"Error in institutional ask: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'answer': f"❌ Sorry, I encountered an error: {str(e)}\n\nPlease try again or rephrase your question."
        }), 500


@ai_bp.route('/api/institutional/performance', methods=['GET'])
def get_performance_metrics():
    """Get performance analytics"""
    try:
        from bot.ai.analytics import get_performance_analytics
        
        lookback_days = request.args.get('lookback_days', 30, type=int)
        
        perf = get_performance_analytics()
        metrics = perf.calculate_all_metrics(lookback_days)
        grades = perf.get_performance_grade(metrics)
        
        return jsonify({
            'success': True,
            'metrics': metrics,
            'grades': grades
        }), 200
    except Exception as e:
        log.error(f"Error getting performance metrics: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ai_bp.route('/api/institutional/risk', methods=['GET'])
def get_risk_metrics():
    """Get risk analytics"""
    try:
        from bot.ai.analytics import get_risk_analytics
        
        lookback_days = request.args.get('lookback_days', 30, type=int)
        
        risk = get_risk_analytics()
        metrics = risk.calculate_all_metrics(lookback_days)
        grades = risk.get_risk_grade(metrics)
        
        return jsonify({
            'success': True,
            'metrics': metrics,
            'grades': grades
        }), 200
    except Exception as e:
        log.error(f"Error getting risk metrics: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ai_bp.route('/api/institutional/execution', methods=['GET'])
def get_execution_metrics():
    """Get execution quality analytics"""
    try:
        from bot.ai.analytics import get_execution_analytics
        
        lookback_days = request.args.get('lookback_days', 30, type=int)
        
        execution = get_execution_analytics()
        metrics = execution.calculate_all_metrics(lookback_days)
        grades = execution.get_execution_grade(metrics)
        
        return jsonify({
            'success': True,
            'metrics': metrics,
            'grades': grades
        }), 200
    except Exception as e:
        log.error(f"Error getting execution metrics: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ai_bp.route('/api/institutional/market_regime', methods=['GET'])
def get_market_regime():
    """Get market regime analysis"""
    try:
        from bot.ai.predictive import get_market_regime_detector
        
        regime_detector = get_market_regime_detector()
        analysis = regime_detector.analyze_market()
        
        return jsonify({
            'success': True,
            'analysis': analysis
        }), 200
    except Exception as e:
        log.error(f"Error getting market regime: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ai_bp.route('/api/institutional/optimization', methods=['GET'])
def get_optimization_recommendations():
    """Get grid optimization recommendations"""
    try:
        from bot.ai.predictive import get_grid_optimizer
        
        optimizer = get_grid_optimizer()
        recommendations = optimizer.get_optimization_recommendations()
        
        return jsonify({
            'success': True,
            'recommendations': recommendations
        }), 200
    except Exception as e:
        log.error(f"Error getting optimization recommendations: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ai_bp.route('/api/institutional/log_analysis', methods=['GET'])
def get_log_analysis():
    """Get log analysis"""
    try:
        from bot.ai.analytics import get_log_analyzer
        
        lookback_hours = request.args.get('lookback_hours', 24, type=int)
        
        log_analyzer = get_log_analyzer()
        analysis = log_analyzer.analyze_logs(lookback_hours)
        health = log_analyzer.get_health_status(analysis)
        
        return jsonify({
            'success': True,
            'analysis': analysis,
            'health': health
        }), 200
    except Exception as e:
        log.error(f"Error getting log analysis: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# Advanced AI Routes (Monte Carlo, ML Predictions)
# ============================================================================

@ai_bp.route('/api/institutional/monte_carlo', methods=['GET'])
def get_monte_carlo_analysis():
    """Run Monte Carlo simulation"""
    try:
        from bot.ai.advanced import get_monte_carlo_simulator
        from bot.state.manager import get_state_manager
        
        # Get parameters
        num_simulations = int(request.args.get('num_simulations', 10000))
        time_horizon = int(request.args.get('time_horizon_days', 30))
        
        # Get current portfolio value and metrics
        state = get_state_manager()
        current_value = state.get_total_capital()
        
        # Estimate return and volatility from recent performance
        mean_return = 0.15  # 15% annualized (placeholder)
        volatility = 0.25   # 25% annualized (placeholder)
        
        # Run Monte Carlo simulation
        simulator = get_monte_carlo_simulator(num_simulations)
        results = simulator.run_full_analysis(
            current_value,
            mean_return,
            volatility,
            time_horizon
        )
        
        return jsonify({
            'success': True,
            'results': results
        }), 200
    except Exception as e:
        log.error(f"Error getting Monte Carlo analysis: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ai_bp.route('/api/institutional/ml_prediction', methods=['GET'])
def get_ml_prediction():
    """Get ML-based price predictions"""
    try:
        from bot.ai.advanced import get_ml_predictor
        
        # Get predictor
        predictor = get_ml_predictor()
        
        # Get current price (from state or exchange)
        current_price = 111500.0  # Placeholder
        
        # Get predictions
        price_prediction = predictor.predict_price_movement(horizon=5)
        entry_exit = predictor.suggest_entry_exit(current_price)
        patterns = predictor.detect_patterns()
        
        return jsonify({
            'success': True,
            'prediction': price_prediction,
            'suggestion': entry_exit,
            'patterns': patterns
        }), 200
    except Exception as e:
        log.error(f"Error getting ML prediction: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ai_bp.route('/api/institutional/win_probability', methods=['POST'])
def calculate_win_probability():
    """Calculate win probability for a trade"""
    try:
        from bot.ai.advanced import get_ml_predictor
        
        data = request.get_json()
        entry_price = float(data.get('entry_price'))
        target_price = float(data.get('target_price'))
        stop_loss = float(data.get('stop_loss'))
        
        predictor = get_ml_predictor()
        probability = predictor.estimate_win_probability(
            entry_price,
            target_price,
            stop_loss
        )
        
        return jsonify({
            'success': True,
            'probability': probability
        }), 200
    except Exception as e:
        log.error(f"Error calculating win probability: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
