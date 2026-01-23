"""
Enhanced Options Analysis API Routes

Endpoints for:
- Greeks calculation
- Probability analysis (PoP, Monte Carlo)
- Risk metrics
- Payoff analysis

Created: January 23, 2026
Part of: PAYOFF_GRAPH_ENHANCEMENT_PLAN.md
"""

from flask import Blueprint, request, jsonify
from ..options_strategy.pricing_engine import OptionPricingEngine
from ..options_strategy.probability_analyzer import ProbabilityAnalyzer
from ..options_strategy.greeks_calculator import GreeksCalculator

bp = Blueprint('enhanced_options', __name__, url_prefix='/api/enhanced-options')


@bp.route('/greeks/calculate', methods=['POST'])
def calculate_greeks():
    """
    Calculate complete Greeks for a position
    
    Request: {
        "spot": float,
        "strike": float,
        "time_to_expiry": float,  // years
        "risk_free_rate": float,
        "volatility": float,
        "dividend_yield": float,
        "option_type": "call" | "put"
    }
    """
    data = request.json
    
    try:
        greeks = GreeksCalculator.calculate_all_greeks(
            spot=float(data['spot']),
            strike=float(data['strike']),
            time_to_expiry=float(data.get('time_to_expiry', 0)),
            risk_free_rate=float(data.get('risk_free_rate', 0.0)),
            volatility=float(data['volatility']),
            dividend_yield=float(data.get('dividend_yield', 0.0)),
            option_type=data['option_type']
        )
        
        return jsonify({
            'success': True,
            'greeks': greeks
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@bp.route('/greeks/portfolio', methods=['POST'])
def calculate_portfolio_greeks():
    """
    Calculate aggregated portfolio Greeks
    
    Request: {
        "positions": [
            {
                "greeks": {...},
                "quantity": int,
                "multiplier": float,
                "spot_price": float
            }
        ]
    }
    """
    data = request.json
    
    try:
        portfolio_greeks = GreeksCalculator.calculate_portfolio_greeks(
            positions=data['positions']
        )
        
        return jsonify({
            'success': True,
            'portfolio_greeks': portfolio_greeks
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@bp.route('/probability/pop', methods=['POST'])
def calculate_pop():
    """
    Calculate Probability of Profit
    
    Request: {
        "positions": [...],
        "spot_price": float,
        "volatility": float,
        "time_to_expiry": float,
        "risk_free_rate": float
    }
    """
    data = request.json
    
    try:
        result = ProbabilityAnalyzer.probability_of_profit(
            positions=data['positions'],
            spot_price=float(data['spot_price']),
            volatility=float(data['volatility']),
            time_to_expiry=float(data['time_to_expiry']),
            risk_free_rate=float(data.get('risk_free_rate', 0.0))
        )
        
        return jsonify({
            'success': True,
            **result
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@bp.route('/probability/monte-carlo', methods=['POST'])
def run_monte_carlo():
    """
    Run Monte Carlo simulation
    
    Request: {
        "positions": [...],
        "spot_price": float,
        "volatility": float,
        "time_to_expiry": float,
        "risk_free_rate": float,
        "num_simulations": int  // default 10000
    }
    """
    data = request.json
    
    try:
        result = ProbabilityAnalyzer.monte_carlo_simulation(
            positions=data['positions'],
            spot_price=float(data['spot_price']),
            volatility=float(data['volatility']),
            time_to_expiry=float(data['time_to_expiry']),
            risk_free_rate=float(data.get('risk_free_rate', 0.0)),
            num_simulations=int(data.get('num_simulations', 10000))
        )
        
        return jsonify({
            'success': True,
            **result
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@bp.route('/pricing/black-scholes', methods=['POST'])
def price_black_scholes():
    """
    Price option using Black-Scholes-Merton
    
    Request: {
        "spot": float,
        "strike": float,
        "time_to_expiry": float,
        "risk_free_rate": float,
        "volatility": float,
        "dividend_yield": float,
        "option_type": "call" | "put"
    }
    """
    data = request.json
    
    try:
        result = OptionPricingEngine.black_scholes_merton(
            spot=float(data['spot']),
            strike=float(data['strike']),
            time_to_expiry=float(data['time_to_expiry']),
            risk_free_rate=float(data.get('risk_free_rate', 0.0)),
            volatility=float(data['volatility']),
            dividend_yield=float(data.get('dividend_yield', 0.0)),
            option_type=data['option_type']
        )
        
        return jsonify({
            'success': True,
            **result
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@bp.route('/pricing/binomial', methods=['POST'])
def price_binomial():
    """
    Price option using Binomial Tree (for American options)
    
    Request: {
        "spot": float,
        "strike": float,
        "time_to_expiry": float,
        "risk_free_rate": float,
        "volatility": float,
        "dividend_yield": float,
        "option_type": "call" | "put",
        "steps": int,  // default 100
        "american": bool  // default true
    }
    """
    data = request.json
    
    try:
        result = OptionPricingEngine.binomial_tree(
            spot=float(data['spot']),
            strike=float(data['strike']),
            time_to_expiry=float(data['time_to_expiry']),
            risk_free_rate=float(data.get('risk_free_rate', 0.0)),
            volatility=float(data['volatility']),
            dividend_yield=float(data.get('dividend_yield', 0.0)),
            option_type=data['option_type'],
            steps=int(data.get('steps', 100)),
            american=bool(data.get('american', True))
        )
        
        return jsonify({
            'success': True,
            **result
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@bp.route('/pricing/monte-carlo', methods=['POST'])
def price_monte_carlo():
    """
    Price option using Monte Carlo simulation
    
    Request: {
        "spot": float,
        "strike": float,
        "time_to_expiry": float,
        "risk_free_rate": float,
        "volatility": float,
        "dividend_yield": float,
        "option_type": "call" | "put",
        "num_simulations": int  // default 10000
    }
    """
    data = request.json
    
    try:
        result = OptionPricingEngine.monte_carlo(
            spot=float(data['spot']),
            strike=float(data['strike']),
            time_to_expiry=float(data['time_to_expiry']),
            risk_free_rate=float(data.get('risk_free_rate', 0.0)),
            volatility=float(data['volatility']),
            dividend_yield=float(data.get('dividend_yield', 0.0)),
            option_type=data['option_type'],
            num_simulations=int(data.get('num_simulations', 10000))
        )
        
        return jsonify({
            'success': True,
            **result
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
