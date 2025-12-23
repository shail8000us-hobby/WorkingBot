"""
Backtest CLI Entry Point

Command-line interface for running backtests.

Usage:
    python -m backtest.run \\
        --symbol "BTC/USD:USD" \\
        --start "2025-08-01 00:00:00" \\
        --end "2025-09-01 00:00:00" \\
        --timeframe 1m \\
        --assume-maker true \\
        --config grid_config.env
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime
from dotenv import dotenv_values

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.runner.grid_backtester import GridBacktester


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="GridBot Pro Backtesting System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Basic backtest (1 week)
    python -m backtest.run --start "2025-10-01" --end "2025-10-08"
    
    # Full month with custom config
    python -m backtest.run \\
        --symbol "BTC/USD:USD" \\
        --start "2025-08-01" \\
        --end "2025-09-01" \\
        --config grid_config.env \\
        --assume-maker true
    
    # Testnet data
    python -m backtest.run \\
        --start "2025-10-01" \\
        --end "2025-10-08" \\
        --testnet
        """
    )
    
    # Required arguments
    parser.add_argument(
        '--start',
        type=str,
        required=True,
        help='Start date/time (YYYY-MM-DD or "YYYY-MM-DD HH:MM:SS")'
    )
    
    parser.add_argument(
        '--end',
        type=str,
        required=True,
        help='End date/time (YYYY-MM-DD or "YYYY-MM-DD HH:MM:SS")'
    )
    
    # Optional arguments
    parser.add_argument(
        '--symbol',
        type=str,
        default='BTC/USD:USD',
        help='Trading symbol (default: BTC/USD:USD)'
    )
    
    parser.add_argument(
        '--timeframe',
        type=str,
        default='1m',
        help='Candle timeframe (default: 1m)'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        default='config.yaml',
        help='Path to grid config file (default: grid_config.env)'
    )
    
    parser.add_argument(
        '--assume-maker',
        type=str,
        default='true',
        choices=['true', 'false'],
        help='Assume all fills are maker (default: true)'
    )
    
    parser.add_argument(
        '--funding',
        type=str,
        default='off',
        choices=['off', 'simple', 'historical'],
        help='Funding mode (default: off)'
    )
    
    parser.add_argument(
        '--testnet',
        action='store_true',
        help='Use testnet data instead of live'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default=None,
        help='Output directory for reports (default: reports/backtests/)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable debug logging'
    )
    
    return parser.parse_args()


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def parse_datetime(date_str: str) -> datetime:
    """Parse datetime string in various formats."""
    formats = [
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d',
        '%Y/%m/%d %H:%M:%S',
        '%Y/%m/%d'
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    raise ValueError(f"Could not parse date: {date_str}. Use YYYY-MM-DD or 'YYYY-MM-DD HH:MM:SS'")


def load_config(config_path: str) -> dict:
    """Load configuration from .env file."""
    if not os.path.exists(config_path):
        logging.warning(f"Config file not found: {config_path}")
        return {}
    
    # Load from .env file
    config = dotenv_values(config_path)
    
    # Extract relevant grid parameters
    grid_config = {
        'symbol': config.get('GRIDBOT_SYMBOL', 'BTC/USD:USD'),
        'ref': float(config.get('GRIDBOT_REF', 112000)),
        'step': float(config.get('GRIDBOT_STEP', 100)),
        'lot': float(config.get('GRIDBOT_LOT', 1)),
        'max_open': int(config.get('GRIDBOT_MAX_OPEN', 10)),
        'lower': float(config.get('GRIDBOT_LOWER', 110000)),
        'upper': float(config.get('GRIDBOT_UPPER', 115000)),
        'tick_size': float(config.get('GRIDBOT_TICK_SIZE', 0.5))
    }
    
    logging.info(f"Loaded config from {config_path}")
    logging.info(f"Grid params: REF={grid_config['ref']} STEP={grid_config['step']} LOT={grid_config['lot']} MAX_OPEN={grid_config['max_open']}")
    
    return grid_config


def save_results(results: dict, output_dir: str, symbol: str, start: datetime, end: datetime):
    """Save backtest results to files."""
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Generate filename prefix
    symbol_safe = symbol.replace('/', '_').replace(':', '_')
    start_str = start.strftime('%Y%m%d')
    end_str = end.strftime('%Y%m%d')
    prefix = f"{symbol_safe}_{start_str}_{end_str}"
    
    # Save trades CSV
    trades_file = output_path / f"{prefix}_trades.csv"
    if not results['trades_df'].empty:
        results['trades_df'].to_csv(trades_file, index=False)
        logging.info(f"Saved trades: {trades_file}")
    
    # Save equity CSV
    equity_file = output_path / f"{prefix}_equity.csv"
    if not results['equity_df'].empty:
        results['equity_df'].to_csv(equity_file, index=False)
        logging.info(f"Saved equity: {equity_file}")
    
    # Save summary JSON
    import json
    summary_file = output_path / f"{prefix}_summary.json"
    
    # Prepare JSON-serializable summary
    json_summary = {
        'symbol': results['symbol'],
        'timeframe': results['timeframe'],
        'start': results['start'].isoformat() if results['start'] else None,
        'end': results['end'].isoformat() if results['end'] else None,
        'metrics': _serialize_metrics(results['metrics']),
        'sim_summary': results['sim_summary'],
        'config': results['config']
    }
    
    with open(summary_file, 'w') as f:
        json.dump(json_summary, f, indent=2)
    
    logging.info(f"Saved summary: {summary_file}")
    
    return str(output_path)


def _serialize_metrics(metrics: dict) -> dict:
    """Convert metrics to JSON-serializable format."""
    serialized = {}
    for key, value in metrics.items():
        if isinstance(value, datetime):
            serialized[key] = value.isoformat()
        elif isinstance(value, (int, float, str, bool, type(None))):
            serialized[key] = value
        else:
            serialized[key] = str(value)
    return serialized


def main():
    """Main CLI entry point."""
    args = parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    logging.info("╔" + "=" * 68 + "╗")
    logging.info("║" + " " * 20 + "GRIDBOT PRO BACKTEST" + " " * 28 + "║")
    logging.info("╚" + "=" * 68 + "╝")
    
    # Parse dates
    try:
        start = parse_datetime(args.start)
        end = parse_datetime(args.end)
    except ValueError as e:
        logging.error(f"Date parse error: {e}")
        sys.exit(1)
    
    # Load configuration
    config = load_config(args.config)
    
    # Override symbol if specified
    if args.symbol != 'BTC/USD:USD':
        config['symbol'] = args.symbol
    
    # Add backtest-specific config
    config['assume_maker'] = args.assume_maker.lower() == 'true'
    config['funding_mode'] = args.funding
    config['same_bar_priority'] = os.getenv('BACKTEST_SAME_BAR_PRIORITY', 'tp_first')
    
    # Create backtester
    backtester = GridBacktester(
        symbol=config['symbol'],
        timeframe=args.timeframe,
        start=start,
        end=end,
        config=config,
        is_testnet=args.testnet
    )
    
    # Run backtest
    try:
        results = backtester.run()
    except Exception as e:
        logging.error(f"Backtest failed: {e}", exc_info=True)
        sys.exit(1)
    
    # Print summary
    print("\n" + results['summary'])
    
    # Save results
    if args.output_dir:
        output_dir = args.output_dir
    else:
        output_dir = f"reports/backtests/{config['symbol'].replace('/', '_').replace(':', '_')}/{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}"
    
    saved_path = save_results(results, output_dir, config['symbol'], start, end)
    
    print(f"\n📁 Results saved to: {saved_path}\n")
    
    # Exit code based on profitability (optional)
    if results['metrics'].get('net_pnl', 0) > 0:
        sys.exit(0)  # Success + profitable
    else:
        sys.exit(0)  # Success but not profitable (still success for testing)


if __name__ == '__main__':
    main()

