"""
Predictive Intelligence API Routes

Exposes volatility spike prediction functionality via REST API.
"""

import sys
from pathlib import Path
from flask import Blueprint, jsonify, request
import logging

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from bot.volatility.predictive_engine import get_predictor
except ImportError:
    get_predictor = None

log = logging.getLogger("prediction_api")

prediction_bp = Blueprint('prediction', __name__, url_prefix='/api/prediction')

@prediction_bp.route('/spike-forecast', methods=['GET'])
def get_spike_forecast():
    """Get volatility spike prediction for next 5-10 minutes"""
    try:
        if not get_predictor:
            return jsonify({
                "error": "Prediction engine not available",
                "available": False
            }), 503
        
        predictor = get_predictor()
        prediction = predictor.predict_spike()
        
        if not prediction:
            return jsonify({
                "available": True,
                "prediction": None,
                "message": "Insufficient data for prediction"
            })
        
        return jsonify({
            "available": True,
            "prediction": {
                "will_spike": prediction.will_spike,
                "confidence": round(prediction.confidence, 3),
                "minutes_ahead": prediction.minutes_ahead,
                "current_iv": round(prediction.current_iv, 2),
                "predicted_iv": round(prediction.predicted_iv, 2),
                "spike_threshold": prediction.spike_threshold,
                "pattern_match": prediction.pattern_match,
                "alert_level": "HIGH" if prediction.confidence > 0.8 else "MEDIUM" if prediction.confidence > 0.6 else "LOW"
            }
        })
        
    except Exception as e:
        log.error(f"Spike forecast error: {e}")
        return jsonify({"error": str(e)}), 500

@prediction_bp.route('/early-warning', methods=['GET'])
def get_early_warning():
    """Get early warning if high-confidence spike predicted"""
    try:
        if not get_predictor:
            return jsonify({
                "warning": None,
                "available": False
            })
        
        predictor = get_predictor()
        warning = predictor.get_early_warning()
        
        return jsonify({
            "available": True,
            "warning": warning
        })
        
    except Exception as e:
        log.error(f"Early warning error: {e}")
        return jsonify({"error": str(e)}), 500

@prediction_bp.route('/status', methods=['GET'])
def get_prediction_status():
    """Get prediction engine status and capabilities"""
    return jsonify({
        "engine_available": get_predictor is not None,
        "features": {
            "spike_prediction": True,
            "early_warning": True,
            "pattern_recognition": True,
            "confidence_scoring": True
        },
        "parameters": {
            "spike_threshold": "5.0% IV increase",
            "prediction_horizon": "7 minutes ahead",
            "min_confidence": "60%",
            "lookback_window": "30 minutes"
        }
    })