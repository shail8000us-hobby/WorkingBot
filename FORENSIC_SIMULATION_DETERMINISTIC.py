"""
DETERMINISTIC SIMULATION OF ASYNC GRIDBOT ORDER FLOW
Pure logic simulation based on actual code paths

Grid Config: Lower=95000, Upper=110000, Step=500, Ref=100000
"""

class SimulatedState:
    """Simulates PositionManagerActor state"""
    def __init__(self):
        self.open_tranches = []
        self.pending_buy = None
        self.pending_sell = None
        self.total_profit = 0
        
    def add_position(self, entry_price, tp_price):
        pos = {"entry": entry_price, "tp": tp_price}
        self.open_tranches.append(pos)
        return pos
    
    def remove_position_by_tp(self, tp_price):
        for pos in self.open_tranches:
            if pos["tp"] == tp_price:
                self.open_tranches.remove(pos)
                profit = tp_price - pos["entry"]
                self.total_profit += profit
                return pos, profit
        return None, 0

class SimulatedGridCalc:
    """Simulates GridCalculator logic"""
    def __init__(self, lower, upper, step, ref):
        self.lower = lower
        self.upper = upper
        self.step = step
        self.ref = ref
    
    def compute_next_buy_level(self, positions):
        """From grid_calculator.py line 78-141"""
        if positions:
            lowest_entry = min(p["entry"] for p in positions)
        else:
            lowest_entry = self.ref
        
        target = lowest_entry - self.step
        
        if target < self.lower or target > self.upper:
            return None
        return target
    
    def compute_tp_price(self, entry_price):
        """From grid_calculator.py line 208-218"""
        return entry_price + self.step

def simulate_long_mode():
    """
    Simulate LONG mode with price sequence:
    100000 → 99500 → 99000 → 98500 → 98000 → 98500 → 99000 → 99500 → 100000
    """
    print("=" * 80)
    print("ASYNC GRIDBOT DETERMINISTIC SIMULATION - LONG MODE")
    print("=" * 80)
    print()
    
    # Initialize
    state = SimulatedState()
    grid = SimulatedGridCalc(lower=95000, upper=110000, step=500, ref=100000)
    
    prices = [100000, 99500, 99000, 98500, 98000, 98500, 99000, 99500, 100000]
    
    print(f"Grid Config: {grid.lower:,} - {grid.upper:,}, Step: {grid.step:,}, Ref: {grid.ref:,}")
    print()
    print(f"{'Tick':<6} {'Price':<10} {'Event':<25} {'Pending':<15} {'Positions':<12} {'Profit':<10}")
    print("-" * 90)
    
    tick = 0
    
    # TICK 0: Initial state at price 100,000
    price = prices[0]
    next_buy = grid.compute_next_buy_level(state.open_tranches)
    state.pending_buy = next_buy
    print(f"{tick:<6} ${price:<9,} {'BOT START':<25} BUY @{next_buy:<9,} {len(state.open_tranches):<12} ${state.total_profit:<9,}")
    tick += 1
    
    # Process price sequence
    for price in prices[1:]:
        events = []
        
        # Check if pending buy fills
        if state.pending_buy and price <= state.pending_buy:
            # BUY FILLS - Execute buy_fill_saga
            entry_price = state.pending_buy
            tp_price = grid.compute_tp_price(entry_price)
            
            # Saga Step 1: Add position
            state.add_position(entry_price, tp_price)
            events.append(f"BUY @{entry_price:,} FILLS")
            
            # Saga Step 2: Place TP (tracked implicitly)
            
            # Saga Step 3: Place next grid order
            next_buy = grid.compute_next_buy_level(state.open_tranches)
            state.pending_buy = next_buy if next_buy else None
            
            pending_str = f"{state.pending_buy:,}" if state.pending_buy else "None"
            print(f"{tick:<6} ${price:<9,} {events[0]:<25} BUY @{pending_str:<9} {len(state.open_tranches):<12} ${state.total_profit:<9,}")
            events = []
        
        # Check if any TP hits
        tp_hit = False
        for pos in list(state.open_tranches):  # Copy list to avoid modification during iteration
            if price >= pos["tp"]:
                # TP FILLS - Execute sell_fill_saga
                tp_price = pos["tp"]
                
                # Saga Step 1: Remove position
                removed_pos, profit = state.remove_position_by_tp(tp_price)
                
                # Saga Step 2: Clear pending_sell (N/A for TP)
                
                # Saga Step 3: Place next grid order
                next_buy = grid.compute_next_buy_level(state.open_tranches)
                state.pending_buy = next_buy if next_buy else None
                
                events.append(f"TP @{tp_price:,} HITS")
                pending_str = f"{state.pending_buy:,}" if state.pending_buy else "None"
                print(f"{tick:<6} ${price:<9,} {events[0]:<25} BUY @{pending_str:<9} {len(state.open_tranches):<12} +${profit:<9,}")
                tp_hit = True
                break  # Process one TP per tick
        
        if not events:
            # No event
            pending_str = f"{state.pending_buy:,}" if state.pending_buy else "None"
            print(f"{tick:<6} ${price:<9,} {'Price update':<25} BUY @{pending_str:<9} {len(state.open_tranches):<12} ${state.total_profit:<9,}")
        
        tick += 1
    
    print()
    print("=" * 80)
    print(f"SIMULATION COMPLETE")
    print(f"Total Profit: ${state.total_profit:,}")
    print(f"Final Positions: {len(state.open_tranches)}")
    pending_str = f"{state.pending_buy:,}" if state.pending_buy else "None"
    print(f"Final Pending: BUY @{pending_str}")
    print("=" * 80)

def simulate_short_mode():
    """
    Simulate SHORT mode with price sequence:
    100000 → 100500 → 101000 → 101500 → 102000 → 101500 → 101000 → 100500 → 100000
    
    NOTE: This shows EXPECTED behavior, but actual code is BROKEN for SHORT mode!
    """
    print()
    print("=" * 80)
    print("ASYNC GRIDBOT DETERMINISTIC SIMULATION - SHORT MODE")
    print("⚠️  WARNING: Actual implementation is BROKEN - this shows EXPECTED behavior")
    print("=" * 80)
    print()
    
    # Initialize
    state = SimulatedState()
    
    class ShortGridCalc(SimulatedGridCalc):
        def compute_next_sell_level(self, positions):
            """From grid_calculator.py line 143-206"""
            if positions:
                highest_entry = max(p["entry"] for p in positions)
            else:
                highest_entry = self.ref
            
            target = highest_entry + self.step
            
            if target < self.lower or target > self.upper:
                return None
            return target
        
        def compute_tp_price(self, entry_price):
            """SHORT mode: TP is BELOW entry"""
            return entry_price - self.step
    
    grid = ShortGridCalc(lower=95000, upper=110000, step=500, ref=100000)
    
    prices = [100000, 100500, 101000, 101500, 102000, 101500, 101000, 100500, 100000]
    
    print(f"Grid Config: {grid.lower:,} - {grid.upper:,}, Step: {grid.step:,}, Ref: {grid.ref:,}")
    print()
    print(f"{'Tick':<6} {'Price':<10} {'Event':<25} {'Pending':<15} {'Positions':<12} {'Profit':<10}")
    print("-" * 90)
    
    tick = 0
    
    # TICK 0: Initial state
    price = prices[0]
    next_sell = grid.compute_next_sell_level(state.open_tranches)
    state.pending_sell = next_sell
    print(f"{tick:<6} ${price:<9,} {'BOT START':<25} SELL @{next_sell:<8,} {len(state.open_tranches):<12} ${state.total_profit:<9,}")
    tick += 1
    
    # Process price sequence
    for price in prices[1:]:
        events = []
        
        # Check if pending sell fills
        if state.pending_sell and price >= state.pending_sell:
            # SELL FILLS (ENTRY for SHORT)
            entry_price = state.pending_sell
            tp_price = grid.compute_tp_price(entry_price)
            
            state.add_position(entry_price, tp_price)
            events.append(f"SELL @{entry_price:,} FILLS")
            
            next_sell = grid.compute_next_sell_level(state.open_tranches)
            state.pending_sell = next_sell if next_sell else None
            
            pending_str = f"{state.pending_sell:,}" if state.pending_sell else "None"
            print(f"{tick:<6} ${price:<9,} {events[0]:<25} SELL @{pending_str:<8} {len(state.open_tranches):<12} ${state.total_profit:<9,}")
            events = []
        
        # Check if any TP hits (BUY back at lower price)
        for pos in list(state.open_tranches):
            if price <= pos["tp"]:
                # TP FILLS (BUY back)
                tp_price = pos["tp"]
                removed_pos, profit = state.remove_position_by_tp(tp_price)
                
                next_sell = grid.compute_next_sell_level(state.open_tranches)
                state.pending_sell = next_sell if next_sell else None
                
                events.append(f"TP @{tp_price:,} HITS")
                pending_str = f"{state.pending_sell:,}" if state.pending_sell else "None"
                print(f"{tick:<6} ${price:<9,} {events[0]:<25} SELL @{pending_str:<8} {len(state.open_tranches):<12} +${profit:<9,}")
                break
        
        if not events:
            pending_str = f"{state.pending_sell:,}" if state.pending_sell else "None"
            print(f"{tick:<6} ${price:<9,} {'Price update':<25} SELL @{pending_str:<8} {len(state.open_tranches):<12} ${state.total_profit:<9,}")
        
        tick += 1
    
    print()
    print("=" * 80)
    print(f"SIMULATION COMPLETE")
    print(f"Total Profit: ${state.total_profit:,}")
    print(f"Final Positions: {len(state.open_tranches)}")
    pending_str = f"{state.pending_sell:,}" if state.pending_sell else "None"
    print(f"Final Pending: SELL @{pending_str}")
    print("=" * 80)

if __name__ == "__main__":
    simulate_long_mode()
    print()
    simulate_short_mode()
