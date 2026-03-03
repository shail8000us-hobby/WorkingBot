#!/usr/bin/env python3
"""Calculate and display grid levels"""

lower = 98000
upper = 110000
step = 500
ref = 101000

print('=' * 70)
print('🎯 GRID CONFIGURATION')
print('=' * 70)
print(f'Lower Bound:  ${lower:,}')
print(f'Upper Bound:  ${upper:,}')
print(f'Step Size:    ${step:,}')
print(f'Reference:    ${ref:,}')
print(f'First BUY:    ${ref - step:,}')
print()
print('=' * 70)
print('📊 GRID LEVELS (BUY Orders)')
print('=' * 70)
levels = []
current = lower
while current <= upper:
    levels.append(current)
    current += step

for i, level in enumerate(levels, 1):
    marker = ' ← REF' if level == ref else ''
    marker = marker or (' ← First BUY' if level == ref - step else '')
    print(f'{i:2d}. ${level:,}{marker}')

print()
print(f'Total Grid Levels: {len(levels)}')
print(f'Grid Range: ${upper - lower:,}')
print('=' * 70)
