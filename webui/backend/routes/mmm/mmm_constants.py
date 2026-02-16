"""
MMM Constants

Shared constants for the MMM algorithm.
"""

# Delta Exchange BTC Options: 1 BTC = 1000 lots, so 1 lot = 0.001 BTC
# Premiums are quoted in USD per BTC. To get USD value for N lots:
#   usd_value = premium_per_btc * N * LOT_SIZE_BTC
LOT_SIZE_BTC = 0.001
