import requests
import json

response = requests.get('http://localhost:5555/api/mmm/session/mmm_d8b725')
data = response.json()['session']

print('Strategy Status:', data.get('strategy_status'))
print('Adjustment Count:', data.get('adjustment_count', 0))
print('Last Aggressor:', data.get('last_aggressor'))
print('\nAdjustment History:')
history = data.get('adjustment_history', [])
if history:
    for i, adj in enumerate(history, 1):
        aggressor = adj.get('aggressor', '?')
        timestamp = adj.get('timestamp', '')
        adj_type = adj.get('type', 'standard')
        print(f"  Adj #{i}: {aggressor} ({adj_type}) at {timestamp}")
else:
    print('  No adjustment history')

print(f'\nTotal adjustments in history: {len(history)}')
print(f'Recent sequence (last 3):')
if len(history) >= 3:
    recent_3 = history[-3:]
    sequence = [h.get('aggressor', '?') for h in recent_3]
    print(f'  {" → ".join(sequence)}')
    
    # Check if alternating
    alternating = True
    for i in range(1, len(sequence)):
        if sequence[i] == sequence[i - 1]:
            alternating = False
            break
    
    if alternating:
        print('  ⚠️ ALTERNATING PATTERN DETECTED - This triggers whipsaw auto-pause!')
    else:
        print('  ✓ Not alternating')
