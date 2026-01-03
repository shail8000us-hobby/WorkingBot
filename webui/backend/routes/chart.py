"""
Chart data API routes - price data and indicators
"""
from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
import random

chart_bp = Blueprint('chart', __name__)

@chart_bp.route('/api/chart/prices', methods=['GET'])
def get_price_data():
    """Get price data for charting (mock data for now)"""
    try:
        symbol = request.args.get('symbol', 'BTCUSD')
        timeframe = request.args.get('timeframe', '1h')
        limit = request.args.get('limit', 100, type=int)
        
        # Generate mock OHLCV data
        # In production, this would fetch from exchange or database
        now = datetime.now()
        
        # Timeframe to minutes mapping
        tf_minutes = {
            '1m': 1,
            '5m': 5,
            '15m': 15,
            '1h': 60,
            '4h': 240,
            '1d': 1440
        }
        minutes = tf_minutes.get(timeframe, 60)
        
        # Generate mock price data
        base_price = 88000 if symbol == 'BTCUSD' else 3000
        candles = []
        
        for i in range(limit):
            timestamp = now - timedelta(minutes=minutes * (limit - i))
            
            # Simple random walk
            open_price = base_price + random.uniform(-500, 500)
            high = open_price + random.uniform(0, 200)
            low = open_price - random.uniform(0, 200)
            close = random.uniform(low, high)
            volume = random.uniform(100, 1000)
            
            candles.append({
                'timestamp': timestamp.isoformat(),
                'open': round(open_price, 2),
                'high': round(high, 2),
                'low': round(low, 2),
                'close': round(close, 2),
                'volume': round(volume, 2)
            })
        
        return jsonify({
            'symbol': symbol,
            'timeframe': timeframe,
            'candles': candles
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@chart_bp.route('/api/chart/indicators', methods=['GET'])
def get_indicators():
    """Get technical indicators"""
    try:
        symbol = request.args.get('symbol', 'BTCUSD')
        
        # Mock indicator data
        indicators = {
            'symbol': symbol,
            'rsi': round(random.uniform(30, 70), 2),
            'macd': {
                'macd': round(random.uniform(-100, 100), 2),
                'signal': round(random.uniform(-100, 100), 2),
                'histogram': round(random.uniform(-50, 50), 2)
            },
            'moving_averages': {
                'ma20': round(88000 + random.uniform(-500, 500), 2),
                'ma50': round(88000 + random.uniform(-1000, 1000), 2),
                'ma200': round(88000 + random.uniform(-2000, 2000), 2)
            },
            'bollinger_bands': {
                'upper': round(89000 + random.uniform(0, 500), 2),
                'middle': round(88000, 2),
                'lower': round(87000 - random.uniform(0, 500), 2)
            }
        }
        
        return jsonify(indicators)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
