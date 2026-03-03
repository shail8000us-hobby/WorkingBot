#!/usr/bin/env python3
"""Quick diagnostic: what does the exchange actually return for positions & wallet."""
import asyncio, json, sys
sys.path.insert(0, '.')

from bot.api.async_delta_client import AsyncDeltaClient
from config.loader import get_api_credentials

async def main():
    creds = get_api_credentials()
    rest = AsyncDeltaClient(
        api_key=creds.get('api_key', ''),
        api_secret=creds.get('api_secret', ''),
        testnet=creds.get('testnet', False) or False,
    )

    # 1. /v2/positions/margined (all positions across all products)
    print('=== /v2/positions/margined ===')
    try:
        resp = await rest._request_with_retry('GET', '/v2/positions/margined')
        margined = resp.get('result', [])
        print(f'Count: {len(margined)}')
        non_zero = [p for p in margined if float(p.get('size', 0) or 0) != 0]
        print(f'Non-zero size: {len(non_zero)}')
        if margined:
            print(f'Keys: {list(margined[0].keys())}')
        for p in non_zero[:5]:
            sym = p.get('product_symbol', p.get('symbol', '?'))
            print(f'  {sym} size={p.get("size")} margin={p.get("margin")} entry={p.get("entry_price")} uPnL={p.get("unrealized_pnl")}')
    except Exception as e:
        print(f'Error: {e}')

    # 2. /v2/positions with BTC underlying
    print('\n=== /v2/positions?underlying=BTC ===')
    try:
        pos = await rest.get_positions_for_underlying('BTC')
        non_zero = [p for p in pos if float(p.get('size', 0) or 0) != 0]
        print(f'Count: {len(pos)}, Non-zero: {len(non_zero)}')
        for p in non_zero[:3]:
            sym = p.get('product_symbol', '?')
            print(f'  {sym} size={p.get("size")} margin={p.get("margin")} entry={p.get("entry_price")}')
    except Exception as e:
        print(f'Error: {e}')

    # 3. Full wallet response
    print('\n=== Wallet (full response) ===')
    wallet_full = await rest.get_wallet_balances_full()
    meta = wallet_full.get('meta', {})
    print(f'meta: {json.dumps(meta, indent=2)}')
    wallets = wallet_full.get('result', [])
    print(f'\nTotal wallets: {len(wallets)}')
    for i, w in enumerate(wallets):
        sym = w.get('asset_symbol', '?')
        bal = w.get('balance', 0)
        avail = w.get('available_balance', 0)
        pos_m = w.get('position_margin', 0)
        order_m = w.get('order_margin', 0)
        blocked = w.get('blocked_margin', 0)
        portfolio = w.get('portfolio_margin', 0)
        cross_pm = w.get('cross_position_margin', 0)
        cross_om = w.get('cross_order_margin', 0)
        print(f'\n  [{i}] {sym}: balance={bal} available={avail}')
        print(f'       pos_margin={pos_m} order_margin={order_m} blocked={blocked}')
        print(f'       portfolio_margin={portfolio} cross_pos={cross_pm} cross_order={cross_om}')

asyncio.run(main())
