"""
Standalone Recovery Engine Runner

Runs independently of async_gridbot.py.
Coordinates via shared state file.

Created: November 20, 2025
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import List, Dict, Optional
from loguru import logger as log

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import get_config, get_api_credentials
from bot.api.unified_api_client import UnifiedAPIClient


class RecoveryRunner:
    """
    Standalone recovery engine runner.
    Completely separate from async_gridbot.py.
    """
    
    def __init__(self):
        # Load config
        self.config = get_config()
        
        # Get API credentials
        credentials = get_api_credentials(self.config.trading_mode)
        self.api_key = credentials['api_key']
        self.api_secret = credentials['api_secret']
        
        # State file for coordination
        self.state_file = Path("data/recovery/recovery_state.json")
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Recovery parameters
        self.mode = self.config.bot.mode
        self.reference = float(self.config.grid.geometry.reference)
        self.step = float(self.config.grid.geometry.step)
        self.lower = float(self.config.grid.geometry.lower)
        self.upper = float(self.config.grid.geometry.upper)
        self.lot_size = float(self.config.grid.limits.lot_size)
        self.product_id = 27  # BTC-USD
        
        # CRITICAL FIX (Nov 20, 2025): Max grids now CONFIGURABLE from config.yaml
        if hasattr(self.config, 'recovery') and hasattr(self.config.recovery, 'max_grids'):
            self.MAX_GRIDS = self.config.recovery.max_grids
            self.cooldown_minutes = self.config.recovery.cooldown_minutes
            self.execution_delay = self.config.recovery.execution_delay_seconds
        else:
            self.MAX_GRIDS = 3
            self.cooldown_minutes = 60
            self.execution_delay = 2
        
        # API client
        self.api_client = None
        
        log.info("✅ Recovery runner initialized")
        log.info(f"   Mode: {self.mode}")
        log.info(f"   Reference: ${self.reference:,.0f}")
        log.info(f"   Step: ${self.step:,.0f}")
        log.info(f"   Max grids: {self.MAX_GRIDS}")
    
    async def initialize(self):
        """Initialize async components"""
        self.api_client = UnifiedAPIClient(
            api_key=self.api_key,
            api_secret=self.api_secret,
            testnet=(self.config.trading_mode == 'demo'),
            enable_websocket=False,  # Recovery runner doesn't need WebSocket
            symbol=self.config.bot.symbol,
            product_id=27
        )
        log.info("✅ API client initialized")
    
    async def run_startup_recovery(self):
        """
        Run startup recovery independently.
        This is the main entry point.
        """
        log.info("=" * 70)
        log.info("🔄 STARTUP RECOVERY - STANDALONE MODE")
        log.info("=" * 70)
        
        try:
            # Initialize
            await self.initialize()
            
            # Set recovery active flag
            self._set_recovery_active(True)
            log.info("🔒 Recovery active - normal grid trading paused")
            
            # Get current price
            current_price = await self._get_current_price()
            log.info(f"📊 Current market price: ${current_price:,.0f}")
            
            # Calculate missed grids
            missed_grids = self._calculate_missed_grids(current_price)
            
            if not missed_grids:
                log.info("✅ No missed grids - recovery not needed")
                return
            
            log.info(f"📋 Found {len(missed_grids)} missed grids: {[f'${g:,.0f}' for g in missed_grids]}")
            
            # Check for existing positions
            existing_positions = await self._get_existing_positions()
            log.info(f"📊 Existing positions: {len(existing_positions)}")
            
            # Filter out grids that already have positions
            grids_to_recover = []
            for grid in missed_grids:
                if self._has_position_at_grid(grid, existing_positions):
                    log.info(f"⏭️  Grid ${grid:,.0f} already has position - skipping")
                else:
                    grids_to_recover.append(grid)
            
            if not grids_to_recover:
                log.info("✅ All missed grids already have positions - recovery not needed")
                return
            
            log.info(f"🎯 Grids to recover: {len(grids_to_recover)}")
            
            # Recover each grid
            recovered_grids = []
            for i, grid in enumerate(grids_to_recover, 1):
                log.info(f"📍 Recovering grid {i}/{len(grids_to_recover)}: ${grid:,.0f}")
                
                success = await self._recover_single_grid(grid, current_price)
                
                if success:
                    recovered_grids.append(grid)
                    log.info(f"✅ Grid ${grid:,.0f} recovered successfully")
                else:
                    log.error(f"❌ Grid ${grid:,.0f} recovery failed")
                
                # Rate limiting: Wait configured delay between orders
                if i < len(grids_to_recover):
                    await asyncio.sleep(self.execution_delay)
            
            # Save recovered grids
            self._save_recovered_grids(recovered_grids)
            
            log.info("=" * 70)
            log.info(f"✅ RECOVERY COMPLETE: {len(recovered_grids)}/{len(grids_to_recover)} grids recovered")
            log.info("=" * 70)
            
        except Exception as e:
            log.error(f"❌ Recovery failed: {e}", exc_info=True)
        
        finally:
            # Clear recovery active flag
            self._set_recovery_active(False)
            log.info("🔓 Recovery inactive - normal grid trading can resume")
            
            # Cleanup
            if self.api_client and hasattr(self.api_client, 'close'):
                await self.api_client.close()
    
    def _calculate_missed_grids(self, current_price: float) -> List[float]:
        """
        Calculate missed grids with STRICT max limit.
        """
        missed = []
        
        if self.mode == "LONG":
            # Start from first grid below reference
            grid = self.reference - self.step
            
            while grid > current_price and grid >= self.lower:
                missed.append(grid)
                grid -= self.step
                
                # CRITICAL: Enforce max grids limit
                if len(missed) >= self.MAX_GRIDS:
                    log.warning(f"⚠️  Max grids limit reached ({self.MAX_GRIDS}) - stopping")
                    break
        else:
            # SHORT mode
            grid = self.reference + self.step
            
            while grid < current_price and grid <= self.upper:
                missed.append(grid)
                grid += self.step
                
                # CRITICAL: Enforce max grids limit
                if len(missed) >= self.MAX_GRIDS:
                    log.warning(f"⚠️  Max grids limit reached ({self.MAX_GRIDS}) - stopping")
                    break
        
        # Double-check limit (fail-safe)
        return missed[:self.MAX_GRIDS]
    
    async def _get_current_price(self) -> float:
        """Get current market price"""
        try:
            ticker = await self.api_client.get_ticker(self.product_id)
            return float(ticker.get('mark_price', 0))
        except Exception as e:
            log.error(f"Error getting current price: {e}")
            raise
    
    async def _get_existing_positions(self) -> List[Dict]:
        """Get existing positions from exchange"""
        try:
            response = await self.api_client.get_positions(self.product_id)
            positions = response.get('result', [])
            return [p for p in positions if p.get('size', 0) != 0]
        except Exception as e:
            log.error(f"Error getting positions: {e}")
            return []
    
    def _has_position_at_grid(self, grid_price: float, positions: List[Dict]) -> bool:
        """Check if position exists at grid level"""
        tolerance = 1.0
        
        for pos in positions:
            entry_price = float(pos.get('entry_price', 0))
            if abs(entry_price - grid_price) < tolerance:
                return True
        
        return False
    
    async def _recover_single_grid(self, grid_price: float, current_price: float) -> bool:
        """
        Recover a single grid with market order + TP order.
        CRITICAL FIX (Nov 20, 2025): Now places TP orders for grid alignment.
        Returns True if successful, False otherwise.
        """
        try:
            # Determine side
            side = "buy" if self.mode == "LONG" else "sell"
            
            # Generate unique tag
            tag = f"RECOVERY_{int(time.time())}_{int(grid_price)}"
            
            log.info(f"   Placing {side.upper()} market order @ current price ${current_price:,.0f}")
            log.info(f"   Grid level: ${grid_price:,.0f}")
            log.info(f"   Size: {self.lot_size}")
            log.info(f"   Tag: {tag}")
            
            # STEP 1: Place market order (entry)
            order_id = await self.api_client.place_order(
                product_id=self.product_id,
                size=self.lot_size,
                side=side,
                order_type="market_order",
                client_order_id=tag
            )
            
            if not order_id:
                log.error(f"   No order ID returned")
                return False
            
            log.info(f"   ✅ Entry order placed: {order_id}")
            
            # Wait for fill confirmation
            await asyncio.sleep(1)
            
            # STEP 2: Calculate and place TP order (grid-aligned)
            if self.mode == "LONG":
                tp_price = grid_price + self.step
                tp_side = "sell"
            else:
                tp_price = grid_price - self.step
                tp_side = "buy"
            
            log.info(f"   Placing TP {tp_side.upper()} order @ ${tp_price:,.0f}")
            
            tp_tag = f"RECOVERY_TP_{int(time.time())}_{int(grid_price)}"
            
            tp_order_id = await self.api_client.place_order(
                product_id=self.product_id,
                size=self.lot_size,
                side=tp_side,
                price=tp_price,
                order_type="limit_order",
                reduce_only=True,
                client_order_id=tp_tag
            )
            
            if tp_order_id:
                log.info(f"   ✅ TP order placed: {tp_order_id} @ ${tp_price:,.0f}")
                return True
            else:
                log.warning(f"   ⚠️  TP order failed but entry succeeded - bot will handle")
                return True
                
        except Exception as e:
            log.error(f"   Recovery order failed: {e}")
            return False
    
    def _set_recovery_active(self, active: bool):
        """Set recovery active flag in state file"""
        try:
            state = self._load_state()
            state['recovery_active'] = active
            state['timestamp'] = time.time()
            
            # Atomic write
            temp_file = self.state_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(state, f, indent=2)
            temp_file.replace(self.state_file)
            
        except Exception as e:
            log.error(f"Error setting recovery active: {e}")
    
    def _save_recovered_grids(self, grids: List[float]):
        """Save recovered grids to state file"""
        try:
            state = self._load_state()
            state['recovered_grids'] = grids
            state['last_recovery'] = time.time()
            
            # Atomic write
            temp_file = self.state_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(state, f, indent=2)
            temp_file.replace(self.state_file)
            
            log.info(f"💾 Saved {len(grids)} recovered grids to state file")
            
        except Exception as e:
            log.error(f"Error saving recovered grids: {e}")
    
    def _load_state(self) -> Dict:
        """Load state from file"""
        try:
            if self.state_file.exists():
                with open(self.state_file) as f:
                    return json.load(f)
        except:
            pass
        
        return {
            'recovery_active': False,
            'recovered_grids': [],
            'timestamp': None,
            'last_recovery': None
        }


async def main():
    """Main entry point"""
    runner = RecoveryRunner()
    await runner.run_startup_recovery()


if __name__ == "__main__":
    asyncio.run(main())
