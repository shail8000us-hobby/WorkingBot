import requests
import json

response = requests.get('http://localhost:5555/api/mmm/session/mmm_d8b725')
data = response.json()['session']

print('Strategy Status:', data.get('strategy_status'))
print('\nCE Side:')
ce = data.get('ce', {})
print('  Active Strike:', ce.get('active_strike'))
print('  Original Premium:', ce.get('original_premium'))
print('  Entry Fill Price:', ce.get('entry_fill_price'))
print('  Total Lots:', ce.get('total_lots'))
print('  Adjustment Fills:', len(ce.get('adjustment_fills', [])))
if ce.get('adjustment_fills'):
    for i, fill in enumerate(ce['adjustment_fills'], 1):
        print(f'    Adj #{i}: {fill.get("lots")} lots @ ${fill.get("premium")} (strike {fill.get("strike")}) at {fill.get("timestamp")}')

print('\nPE Side:')
pe = data.get('pe', {})
print('  Active Strike:', pe.get('active_strike'))
print('  Original Premium:', pe.get('original_premium'))
print('  Entry Fill Price:', pe.get('entry_fill_price'))
print('  Total Lots:', pe.get('total_lots'))
print('  Adjustment Fills:', len(pe.get('adjustment_fills', [])))
if pe.get('adjustment_fills'):
    for i, fill in enumerate(pe['adjustment_fills'], 1):
        print(f'    Adj #{i}: {fill.get("lots")} lots @ ${fill.get("premium")} (strike {fill.get("strike")}) at {fill.get("timestamp")}')

print('\n' + '='*60)
print('Full CE adjustment_fills:')
print(json.dumps(ce.get('adjustment_fills', []), indent=2))
