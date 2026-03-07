import sys
sys.path.insert(0, '.')
from webui.backend.options_chain.chain_service import OptionsChainService
from concurrent.futures import ThreadPoolExecutor

# Test both legs directly
svc = OptionsChainService()
symbols = ['C-BTC-74000-200326', 'C-BTC-74000-290526']
for sym in symbols:
    r = svc.get_option_ticker(sym)
    if r:
        print(f'{sym} -> bid={r.get("bid")} ask={r.get("ask")} mark={r.get("mark_price")}')
    else:
        print(f'{sym} -> NOT FOUND in exchange tickers')

# Replicate _fetch_quote_via_chain exactly
def _fetch(symbol):
    try:
        svc2 = OptionsChainService()
        data = svc2.get_option_ticker(symbol)
        if data and (data.get('bid') or data.get('ask') or data.get('mark_price')):
            bid = data['bid'] or None
            ask = data['ask'] or None
            mark = data.get('mark_price') or None
            mid = round((bid + ask) / 2, 4) if bid and ask else mark
            return {'bid': bid, 'ask': ask, 'mid': mid, 'mark_price': mark, 'source': 'chain'}
        print(f'  CHAIN MISS for {symbol}: data={data}')
    except Exception as e:
        print(f'  CHAIN EXCEPTION for {symbol}: {e}')
    return {'bid': None, 'ask': None, 'mid': None, 'mark_price': None, 'source': 'none'}

print('\n--- ThreadPoolExecutor test ---')
with ThreadPoolExecutor(max_workers=2) as pool:
    f1 = pool.submit(_fetch, 'C-BTC-74000-200326')
    f2 = pool.submit(_fetch, 'C-BTC-74000-290526')
    print('close leg:', f1.result(timeout=20))
    print('new leg  :', f2.result(timeout=20))
