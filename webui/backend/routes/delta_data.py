"""
Delta Data API Routes
=====================

API endpoints for Delta Exchange data collection infrastructure.
This module provides access to:
- Historical OHLCV data fetching
- Live streaming status
- Data manager status
- Database statistics

These features are INDEPENDENT and do not impact existing bot functionality.

Author: WorkingBot
Date: January 2026
"""

from flask import Blueprint, jsonify, request
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import logging
import pandas as pd

# Add parent paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

logger = logging.getLogger(__name__)

delta_data_bp = Blueprint('delta_data', __name__, url_prefix='/api/delta-data')


def get_data_manager():
    """Get or create DeltaDataManager instance."""
    try:
        from bot.delta_data import DeltaDataManager, DataConfig
        
        # Use user_data directory relative to project root
        base_dir = Path(__file__).parent.parent.parent.parent
        data_dir = base_dir / 'user_data' / 'ohlcv'
        db_path = base_dir / 'user_data' / 'market_data.db'
        
        config = DataConfig(
            db_path=str(db_path),
            data_dir=str(data_dir),
            testnet=True  # Use testnet by default for safety
        )
        
        return DeltaDataManager(config)
    except ImportError as e:
        logger.error(f"Could not import DeltaDataManager: {e}")
        return None
    except Exception as e:
        logger.error(f"Error creating DeltaDataManager: {e}")
        return None


def get_data_provider():
    """Get or create WorkingBotDataProvider instance."""
    try:
        from bot.delta_data import create_workingbot_provider
        return create_workingbot_provider(testnet=True)
    except ImportError as e:
        logger.error(f"Could not import WorkingBotDataProvider: {e}")
        return None
    except Exception as e:
        logger.error(f"Error creating WorkingBotDataProvider: {e}")
        return None


# ============================================================================
# STATUS & HEALTH ENDPOINTS
# ============================================================================

@delta_data_bp.route('/health', methods=['GET'])
def health_check():
    """
    Health check for delta data module.
    
    Returns:
        Module availability and component status
    """
    try:
        # Check if modules are importable
        modules_status = {}
        
        try:
            from bot.delta_data import DeltaHistoricalFetcher
            modules_status['historical_fetcher'] = True
        except:
            modules_status['historical_fetcher'] = False
            
        try:
            from bot.delta_data import DeltaLiveStreamer
            modules_status['live_streamer'] = True
        except:
            modules_status['live_streamer'] = False
            
        try:
            from bot.delta_data import DeltaDataManager
            modules_status['data_manager'] = True
        except:
            modules_status['data_manager'] = False
            
        try:
            from bot.delta_data import WorkingBotDataProvider
            modules_status['data_provider'] = True
        except:
            modules_status['data_provider'] = False
        
        all_healthy = all(modules_status.values())
        
        return jsonify({
            'status': 'healthy' if all_healthy else 'degraded',
            'modules': modules_status,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@delta_data_bp.route('/status', methods=['GET'])
def get_status():
    """
    Get comprehensive status of delta data infrastructure.
    
    Returns:
        Status of data collection, storage, and streaming components
    """
    try:
        status = {
            'timestamp': datetime.now().isoformat(),
            'components': {}
        }
        
        # Check data manager
        manager = get_data_manager()
        if manager:
            status['components']['data_manager'] = {
                'available': True,
                'db_path': manager.config.db_path,
                'data_dir': manager.config.data_dir,
                'testnet': manager.config.testnet
            }
            
            # Get database statistics
            try:
                stats = manager.get_database_stats()
                status['components']['database'] = {
                    'available': True,
                    'stats': stats
                }
            except Exception as e:
                status['components']['database'] = {
                    'available': False,
                    'error': str(e)
                }
        else:
            status['components']['data_manager'] = {'available': False}
            status['components']['database'] = {'available': False}
        
        # Check data provider
        provider = get_data_provider()
        if provider:
            status['components']['data_provider'] = {
                'available': True,
                'testnet': provider.config.testnet
            }
        else:
            status['components']['data_provider'] = {'available': False}
        
        return jsonify(status)
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


# ============================================================================
# DATA FETCHING ENDPOINTS
# ============================================================================

@delta_data_bp.route('/symbols', methods=['GET'])
def get_available_symbols():
    """
    Get list of available symbols for data collection.
    
    Returns:
        List of supported symbols
    """
    try:
        provider = get_data_provider()
        if not provider:
            return jsonify({
                'symbols': [],
                'error': 'Data provider not available'
            }), 503
        
        # Common Delta Exchange symbols
        symbols = [
            {'symbol': 'BTCUSD', 'type': 'perpetual', 'description': 'BTC/USD Perpetual'},
            {'symbol': 'ETHUSD', 'type': 'perpetual', 'description': 'ETH/USD Perpetual'},
            {'symbol': 'BTCUSDT', 'type': 'perpetual', 'description': 'BTC/USDT Perpetual'},
            {'symbol': 'ETHUSDT', 'type': 'perpetual', 'description': 'ETH/USDT Perpetual'},
        ]
        
        return jsonify({
            'symbols': symbols,
            'count': len(symbols),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'symbols': [],
            'error': str(e)
        }), 500


@delta_data_bp.route('/resolutions', methods=['GET'])
def get_available_resolutions():
    """
    Get available timeframe resolutions for OHLCV data.
    
    Returns:
        List of supported resolutions
    """
    resolutions = [
        {'value': '1m', 'label': '1 Minute', 'seconds': 60},
        {'value': '5m', 'label': '5 Minutes', 'seconds': 300},
        {'value': '15m', 'label': '15 Minutes', 'seconds': 900},
        {'value': '30m', 'label': '30 Minutes', 'seconds': 1800},
        {'value': '1h', 'label': '1 Hour', 'seconds': 3600},
        {'value': '4h', 'label': '4 Hours', 'seconds': 14400},
        {'value': '1d', 'label': '1 Day', 'seconds': 86400},
        {'value': '1w', 'label': '1 Week', 'seconds': 604800},
    ]
    
    return jsonify({
        'resolutions': resolutions,
        'default': '1h',
        'timestamp': datetime.now().isoformat()
    })


@delta_data_bp.route('/ohlcv', methods=['GET'])
def get_ohlcv_data():
    """
    Get OHLCV data for a symbol.
    
    Query params:
        symbol: Symbol name (default: BTCUSD)
        resolution: Timeframe (default: 1h)
        days: Number of days of data (default: 7)
        limit: Maximum candles to return (default: 500)
    
    Returns:
        OHLCV data as JSON array
    """
    try:
        symbol = request.args.get('symbol', 'BTCUSD')
        resolution = request.args.get('resolution', '1h')
        days = int(request.args.get('days', 7))
        limit = int(request.args.get('limit', 500))
        
        provider = get_data_provider()
        if not provider:
            return jsonify({
                'data': [],
                'error': 'Data provider not available'
            }), 503
        
        # Get OHLCV data
        try:
            df = provider.get_ohlcv(symbol, resolution, days=days)
            
            if df is None or df.empty:
                return jsonify({
                    'data': [],
                    'symbol': symbol,
                    'resolution': resolution,
                    'message': 'No data available'
                })
            
            # Convert to list of dicts for JSON
            df = df.tail(limit)  # Limit results
            data = df.reset_index().to_dict(orient='records')
            
            # Format datetime for JSON
            for row in data:
                if 'datetime' in row:
                    if hasattr(row['datetime'], 'isoformat'):
                        row['datetime'] = row['datetime'].isoformat()
            
            return jsonify({
                'data': data,
                'symbol': symbol,
                'resolution': resolution,
                'count': len(data),
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error fetching OHLCV: {e}")
            return jsonify({
                'data': [],
                'error': str(e)
            }), 500
        
    except Exception as e:
        return jsonify({
            'data': [],
            'error': str(e)
        }), 500


@delta_data_bp.route('/fetch-historical', methods=['POST'])
def fetch_historical_data():
    """
    Trigger historical data fetch for a symbol.
    
    Request body:
        symbol: Symbol to fetch (required)
        resolution: Timeframe (default: 1h)
        days: Number of days to fetch (default: 30)
    
    Returns:
        Fetch status and statistics
    """
    try:
        data = request.get_json() or {}
        symbol = data.get('symbol', 'BTCUSD')
        resolution = data.get('resolution', '1h')
        days = int(data.get('days', 30))
        
        manager = get_data_manager()
        if not manager:
            return jsonify({
                'success': False,
                'error': 'Data manager not available'
            }), 503
        
        # Trigger historical fetch
        try:
            result = manager.fetch_and_store_historical(
                symbol=symbol,
                resolution=resolution,
                days=days
            )
            
            return jsonify({
                'success': True,
                'symbol': symbol,
                'resolution': resolution,
                'days': days,
                'result': result if isinstance(result, dict) else str(result),
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error fetching historical data: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# DATABASE STATISTICS ENDPOINTS
# ============================================================================

@delta_data_bp.route('/database/stats', methods=['GET'])
def get_database_stats():
    """
    Get database statistics for stored data.
    
    Returns:
        Database size, record counts, and data coverage
    """
    try:
        manager = get_data_manager()
        if not manager:
            return jsonify({
                'stats': None,
                'error': 'Data manager not available'
            }), 503
        
        try:
            stats = manager.get_database_stats()
            return jsonify({
                'stats': stats,
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return jsonify({
                'stats': None,
                'error': str(e)
            }), 500
        
    except Exception as e:
        return jsonify({
            'stats': None,
            'error': str(e)
        }), 500


@delta_data_bp.route('/database/coverage', methods=['GET'])
def get_data_coverage():
    """
    Get data coverage report for all symbols.
    
    Returns:
        Coverage statistics for each symbol/resolution pair
    """
    try:
        manager = get_data_manager()
        if not manager:
            return jsonify({
                'coverage': [],
                'error': 'Data manager not available'
            }), 503
        
        try:
            coverage = manager.get_data_coverage()
            return jsonify({
                'coverage': coverage if isinstance(coverage, list) else [],
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Error getting data coverage: {e}")
            return jsonify({
                'coverage': [],
                'error': str(e)
            }), 500
        
    except Exception as e:
        return jsonify({
            'coverage': [],
            'error': str(e)
        }), 500


# ============================================================================
# LIVE STREAMING ENDPOINTS
# ============================================================================

@delta_data_bp.route('/stream/status', methods=['GET'])
def get_stream_status():
    """
    Get status of live data streaming.
    
    Returns:
        Streaming connection status and statistics
    """
    try:
        # Note: Live streaming requires websocket infrastructure
        # This endpoint returns the status if streaming is active
        
        return jsonify({
            'streaming': False,
            'message': 'Live streaming not yet implemented in WebUI',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'streaming': False,
            'error': str(e)
        }), 500


# ============================================================================
# TECHNICAL INDICATORS
# ============================================================================

@delta_data_bp.route('/indicators', methods=['GET'])
def get_available_indicators():
    """
    Get list of available technical indicators.
    
    Returns:
        List of indicators that can be calculated
    """
    indicators = [
        {'name': 'sma', 'label': 'Simple Moving Average', 'params': ['period']},
        {'name': 'ema', 'label': 'Exponential Moving Average', 'params': ['period']},
        {'name': 'rsi', 'label': 'Relative Strength Index', 'params': ['period']},
        {'name': 'macd', 'label': 'MACD', 'params': ['fast', 'slow', 'signal']},
        {'name': 'bollinger', 'label': 'Bollinger Bands', 'params': ['period', 'std']},
        {'name': 'atr', 'label': 'Average True Range', 'params': ['period']},
        {'name': 'volume_profile', 'label': 'Volume Profile', 'params': ['bins']},
    ]
    
    return jsonify({
        'indicators': indicators,
        'count': len(indicators),
        'timestamp': datetime.now().isoformat()
    })


@delta_data_bp.route('/indicators/calculate', methods=['GET'])
def calculate_indicators():
    """
    Calculate technical indicators from stored OHLCV data.
    
    Query params:
        symbol: Symbol name (default: BTCUSD)
        resolution: Timeframe (default: 1h)
        days: Number of days of data (default: 7)
    
    Returns:
        Calculated indicator values (latest values for each indicator)
    """
    try:
        symbol = request.args.get('symbol', 'BTCUSD')
        resolution = request.args.get('resolution', '1h')
        days = int(request.args.get('days', 7))
        
        provider = get_data_provider()
        if not provider:
            return jsonify({
                'success': False,
                'indicators': {},
                'error': 'Data provider not available'
            }), 503
        
        try:
            # Get OHLCV data
            df = provider.get_ohlcv(symbol, resolution, days=days)
            
            if df is None or df.empty:
                return jsonify({
                    'success': False,
                    'indicators': {},
                    'symbol': symbol,
                    'message': 'No data available - fetch historical data first'
                })
            
            # Add technical indicators
            df = provider.add_technical_indicators(df)
            
            # Get the latest row with all indicator values
            latest = df.iloc[-1]
            
            # Build indicator results
            indicator_values = {}
            
            # SMA
            if 'sma_20' in df.columns:
                indicator_values['sma'] = {
                    'label': 'Simple Moving Average (20)',
                    'value': round(float(latest['sma_20']), 2) if not pd.isna(latest['sma_20']) else None,
                    'period': 20
                }
            
            # EMA
            if 'ema_12' in df.columns:
                indicator_values['ema'] = {
                    'label': 'Exponential MA (12)',
                    'value': round(float(latest['ema_12']), 2) if not pd.isna(latest['ema_12']) else None,
                    'period': 12
                }
            
            # RSI
            if 'rsi_14' in df.columns:
                indicator_values['rsi'] = {
                    'label': 'RSI (14)',
                    'value': round(float(latest['rsi_14']), 2) if not pd.isna(latest['rsi_14']) else None,
                    'period': 14
                }
            
            # MACD
            if 'macd' in df.columns:
                indicator_values['macd'] = {
                    'label': 'MACD',
                    'value': round(float(latest['macd']), 4) if not pd.isna(latest['macd']) else None,
                    'signal': round(float(latest.get('macd_signal', 0)), 4) if 'macd_signal' in df.columns and not pd.isna(latest.get('macd_signal')) else None,
                    'histogram': round(float(latest.get('macd_hist', 0)), 4) if 'macd_hist' in df.columns and not pd.isna(latest.get('macd_hist')) else None
                }
            
            # Bollinger Bands
            if 'bb_upper' in df.columns:
                indicator_values['bollinger'] = {
                    'label': 'Bollinger Bands',
                    'upper': round(float(latest['bb_upper']), 2) if not pd.isna(latest['bb_upper']) else None,
                    'middle': round(float(latest.get('bb_middle', latest.get('sma_20', 0))), 2) if 'bb_middle' in df.columns or 'sma_20' in df.columns else None,
                    'lower': round(float(latest['bb_lower']), 2) if not pd.isna(latest['bb_lower']) else None,
                    'period': 20,
                    'std': 2
                }
            
            # ATR
            if 'atr_14' in df.columns:
                indicator_values['atr'] = {
                    'label': 'Average True Range',
                    'value': round(float(latest['atr_14']), 2) if not pd.isna(latest['atr_14']) else None,
                    'period': 14
                }
            
            # Volume Profile (calculate from volume column)
            if 'volume' in df.columns:
                avg_vol = df['volume'].mean()
                latest_vol = float(latest['volume']) if not pd.isna(latest['volume']) else 0
                indicator_values['volume_profile'] = {
                    'label': 'Volume Profile',
                    'current': round(latest_vol, 2),
                    'average': round(float(avg_vol), 2) if not pd.isna(avg_vol) else None,
                    'ratio': round(latest_vol / avg_vol, 2) if avg_vol > 0 else None
                }
            
            # Add price context
            current_price = float(latest['close']) if 'close' in df.columns else None
            
            return jsonify({
                'success': True,
                'symbol': symbol,
                'resolution': resolution,
                'current_price': round(current_price, 2) if current_price else None,
                'indicators': indicator_values,
                'data_points': len(df),
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'indicators': {},
                'error': str(e)
            }), 500
        
    except Exception as e:
        return jsonify({
            'success': False,
            'indicators': {},
            'error': str(e)
        }), 500


@delta_data_bp.route('/ohlcv/with-indicators', methods=['GET'])
def get_ohlcv_with_indicators():
    """
    Get OHLCV data with technical indicators calculated.
    
    Query params:
        symbol: Symbol name (default: BTCUSD)
        resolution: Timeframe (default: 1h)
        days: Number of days of data (default: 7)
        indicators: Comma-separated list of indicators (default: sma,rsi)
    
    Returns:
        OHLCV data with indicator columns
    """
    try:
        symbol = request.args.get('symbol', 'BTCUSD')
        resolution = request.args.get('resolution', '1h')
        days = int(request.args.get('days', 7))
        indicators_str = request.args.get('indicators', 'sma,rsi')
        indicators = [i.strip() for i in indicators_str.split(',')]
        
        provider = get_data_provider()
        if not provider:
            return jsonify({
                'data': [],
                'error': 'Data provider not available'
            }), 503
        
        try:
            # Get OHLCV data
            df = provider.get_ohlcv(symbol, resolution, days=days)
            
            if df is None or df.empty:
                return jsonify({
                    'data': [],
                    'symbol': symbol,
                    'message': 'No data available'
                })
            
            # Add indicators
            df = provider.add_technical_indicators(df)
            
            # Convert to list of dicts
            data = df.tail(500).reset_index().to_dict(orient='records')
            
            # Format datetime for JSON
            for row in data:
                if 'datetime' in row:
                    if hasattr(row['datetime'], 'isoformat'):
                        row['datetime'] = row['datetime'].isoformat()
            
            return jsonify({
                'data': data,
                'symbol': symbol,
                'resolution': resolution,
                'indicators': indicators,
                'count': len(data),
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error fetching OHLCV with indicators: {e}")
            return jsonify({
                'data': [],
                'error': str(e)
            }), 500
        
    except Exception as e:
        return jsonify({
            'data': [],
            'error': str(e)
        }), 500


# ============================================================================
# BACKTESTING ENDPOINTS
# ============================================================================

@delta_data_bp.route('/backtest/strategies', methods=['GET'])
def get_available_strategies():
    """
    Get list of available backtesting strategies.
    
    Returns:
        List of strategy names with descriptions and parameters
    """
    strategies = [
        {
            'name': 'sma_crossover',
            'label': 'SMA Crossover',
            'description': 'Buy when fast SMA crosses above slow SMA, sell when it crosses below.',
            'params': {
                'fast_period': {'type': 'int', 'default': 10, 'min': 2, 'max': 100},
                'slow_period': {'type': 'int', 'default': 50, 'min': 5, 'max': 200}
            }
        },
        {
            'name': 'rsi',
            'label': 'RSI Strategy',
            'description': 'Buy when RSI is oversold, sell when overbought.',
            'params': {
                'period': {'type': 'int', 'default': 14, 'min': 2, 'max': 50},
                'oversold_level': {'type': 'float', 'default': 30, 'min': 10, 'max': 50},
                'overbought_level': {'type': 'float', 'default': 70, 'min': 50, 'max': 90}
            }
        },
        {
            'name': 'macd',
            'label': 'MACD Strategy',
            'description': 'Buy on bullish MACD crossover, sell on bearish crossover.',
            'params': {
                'fast_period': {'type': 'int', 'default': 12, 'min': 5, 'max': 50},
                'slow_period': {'type': 'int', 'default': 26, 'min': 10, 'max': 100},
                'signal_period': {'type': 'int', 'default': 9, 'min': 3, 'max': 30}
            }
        }
    ]
    
    return jsonify({
        'strategies': strategies,
        'count': len(strategies),
        'timestamp': datetime.now().isoformat()
    })


@delta_data_bp.route('/backtest/run', methods=['POST'])
def run_backtest():
    """
    Run a backtest with specified strategy and parameters.
    
    Request body:
        strategy: Strategy name (sma_crossover, rsi, macd)
        params: Strategy parameters (optional)
        symbol: Symbol to backtest (default: BTCUSD)
        resolution: Timeframe (default: 1h)
        days: Days of historical data (default: 30)
        initial_capital: Starting capital (default: 10000)
        commission_rate: Commission rate (default: 0.001)
    
    Returns:
        Backtest results with metrics
    """
    try:
        data = request.get_json() or {}
        
        strategy_name = data.get('strategy', 'sma_crossover')
        params = data.get('params', {})
        symbol = data.get('symbol', 'BTCUSD')
        resolution = data.get('resolution', '1h')
        days = int(data.get('days', 30))
        initial_capital = float(data.get('initial_capital', 10000))
        commission_rate = float(data.get('commission_rate', 0.001))
        
        # Get data provider
        provider = get_data_provider()
        if not provider:
            return jsonify({
                'success': False,
                'error': 'Data provider not available'
            }), 503
        
        # Fetch data
        df = provider.get_ohlcv(symbol, resolution, days=days)
        
        if df is None or df.empty:
            return jsonify({
                'success': False,
                'error': 'No data available. Fetch historical data first.'
            }), 400
        
        # Import backtesting modules
        try:
            from bot.delta_data.backtesting import (
                BacktestEngine, BacktestConfig
            )
            from bot.delta_data.backtesting.strategy import (
                SMAcrossoverStrategy, RSIStrategy, MACDStrategy
            )
        except ImportError as e:
            logger.error(f"Could not import backtesting modules: {e}")
            return jsonify({
                'success': False,
                'error': f'Backtesting module not available: {str(e)}'
            }), 500
        
        # Create strategy
        if strategy_name == 'sma_crossover':
            strategy = SMAcrossoverStrategy(
                fast_period=int(params.get('fast_period', 10)),
                slow_period=int(params.get('slow_period', 50))
            )
        elif strategy_name == 'rsi':
            strategy = RSIStrategy(
                period=int(params.get('period', 14)),
                oversold_level=float(params.get('oversold_level', 30)),
                overbought_level=float(params.get('overbought_level', 70))
            )
        elif strategy_name == 'macd':
            strategy = MACDStrategy(
                fast_period=int(params.get('fast_period', 12)),
                slow_period=int(params.get('slow_period', 26)),
                signal_period=int(params.get('signal_period', 9))
            )
        else:
            return jsonify({
                'success': False,
                'error': f'Unknown strategy: {strategy_name}'
            }), 400
        
        # Create engine and run backtest
        config = BacktestConfig(
            initial_capital=initial_capital,
            commission_rate=commission_rate,
            slippage_rate=0.0005
        )
        engine = BacktestEngine(config)
        
        result = engine.run(strategy, df, verbose=False)
        
        # Format trades for response
        trades = []
        for trade in result.trades:
            trades.append({
                'entry_time': str(trade.entry_time),
                'exit_time': str(trade.exit_time),
                'entry_price': round(trade.entry_price, 2),
                'exit_price': round(trade.exit_price, 2),
                'pnl': round(trade.pnl, 2),
                'pnl_percent': round(trade.pnl_percent, 2),
                'side': trade.side.value,
                'exit_reason': trade.exit_reason,
                'duration_hours': round(trade.duration_hours, 1)
            })
        
        # Format equity curve
        equity_data = []
        if not result.equity_curve.empty:
            for ts, row in result.equity_curve.iterrows():
                equity_data.append({
                    'timestamp': str(ts),
                    'equity': round(row['equity'], 2)
                })
        
        return jsonify({
            'success': True,
            'strategy': strategy_name,
            'symbol': symbol,
            'resolution': resolution,
            'days': days,
            'metrics': result.metrics.to_dict(),
            'trades': trades,
            'equity_curve': equity_data[-100:],  # Last 100 points
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error running backtest: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@delta_data_bp.route('/backtest/quick', methods=['GET'])
def quick_backtest():
    """
    Run a quick backtest with default parameters.
    
    Query params:
        strategy: Strategy name (default: sma_crossover)
        symbol: Symbol (default: BTCUSD)
        days: Days of data (default: 30)
    
    Returns:
        Quick backtest summary
    """
    try:
        strategy_name = request.args.get('strategy', 'sma_crossover')
        symbol = request.args.get('symbol', 'BTCUSD')
        days = int(request.args.get('days', 30))
        
        # Get data
        provider = get_data_provider()
        if not provider:
            return jsonify({
                'success': False,
                'error': 'Data provider not available'
            }), 503
        
        df = provider.get_ohlcv(symbol, '1h', days=days)
        
        if df is None or df.empty:
            return jsonify({
                'success': False,
                'error': 'No data available'
            }), 400
        
        # Import and run
        try:
            from bot.delta_data.backtesting import BacktestEngine, BacktestConfig
            from bot.delta_data.backtesting.strategy import SMAcrossoverStrategy, RSIStrategy
        except ImportError:
            return jsonify({
                'success': False,
                'error': 'Backtesting module not available'
            }), 500
        
        if strategy_name == 'rsi':
            strategy = RSIStrategy()
        else:
            strategy = SMAcrossoverStrategy()
        
        config = BacktestConfig(initial_capital=10000)
        engine = BacktestEngine(config)
        result = engine.run(strategy, df)
        
        return jsonify({
            'success': True,
            'strategy': strategy_name,
            'symbol': symbol,
            'days': days,
            'data_points': len(df),
            'summary': {
                'total_return': round(result.total_return, 2),
                'total_return_percent': round(result.total_return_percent, 2),
                'sharpe_ratio': round(result.sharpe_ratio, 2),
                'max_drawdown_percent': round(result.max_drawdown_percent, 2),
                'win_rate': round(result.win_rate, 1),
                'total_trades': result.metrics.total_trades
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in quick backtest: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500