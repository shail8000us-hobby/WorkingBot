import asyncio
from enum import Enum
from typing import Optional
import json
from pathlib import Path
from datetime import datetime
import logging

class BotState(Enum):
    WAITING_FOR_GUARDIAN = "waiting_for_guardian"
    RECOVERY_CHECK = "recovery_check"
    RECOVERY_IN_PROGRESS = "recovery_in_progress"
    ASYNC_TRADING = "async_trading"
    HALTED = "halted"

class BotStateMachine:
    
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.current_state = BotState.WAITING_FOR_GUARDIAN
        self.state_file = Path("data/bot_state.json")
        self.logger = logging.getLogger(__name__)
        self._recovery_in_progress = False
        self._load_state()
    
    def _load_state(self):
        if self.state_file.exists():
            try:
                with open(self.state_file) as f:
                    data = json.load(f)
                    state_value = data.get("current_state", "waiting_for_guardian")
                    self.current_state = BotState(state_value)
                    self.logger.info(f"Loaded state: {self.current_state.value}")
            except Exception as e:
                self.logger.error(f"Failed to load state: {e}, starting fresh")
                self.current_state = BotState.WAITING_FOR_GUARDIAN
    
    def _save_state(self, reason: str = ""):
        try:
            guardian_status = self.bot._get_guardian_status()
        except:
            guardian_status = "UNKNOWN"
        
        data = {
            "current_state": self.current_state.value,
            "last_transition": datetime.utcnow().isoformat(),
            "transition_reason": reason,
            "guardian_status": guardian_status,
            "mode": self.bot.mode
        }
        
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def is_recovery_in_progress(self) -> bool:
        return self._recovery_in_progress
    
    async def run(self):
        self.logger.info(f"State machine starting in state: {self.current_state.value}")
        
        while True:
            try:
                next_state = None
                
                if self.current_state == BotState.WAITING_FOR_GUARDIAN:
                    next_state = await self._handle_waiting()
                
                elif self.current_state == BotState.RECOVERY_CHECK:
                    next_state = await self._handle_recovery_check()
                
                elif self.current_state == BotState.RECOVERY_IN_PROGRESS:
                    next_state = await self._handle_recovery()
                
                elif self.current_state == BotState.ASYNC_TRADING:
                    next_state = await self._handle_trading()
                
                elif self.current_state == BotState.HALTED:
                    next_state = await self._handle_halted()
                
                if next_state and next_state != self.current_state:
                    reason = self._get_transition_reason(self.current_state, next_state)
                    await self._transition(next_state, reason)
                
            except Exception as e:
                self.logger.error(f"State machine error in {self.current_state.value}: {e}", exc_info=True)
                await asyncio.sleep(5)
    
    def _get_transition_reason(self, from_state: BotState, to_state: BotState) -> str:
        transitions = {
            (BotState.WAITING_FOR_GUARDIAN, BotState.RECOVERY_CHECK): "guardian_go_signal",
            (BotState.RECOVERY_CHECK, BotState.RECOVERY_IN_PROGRESS): "missed_grids_found",
            (BotState.RECOVERY_CHECK, BotState.ASYNC_TRADING): "no_missed_grids",
            (BotState.RECOVERY_IN_PROGRESS, BotState.ASYNC_TRADING): "recovery_complete",
            (BotState.ASYNC_TRADING, BotState.HALTED): "guardian_halt_signal",
            (BotState.HALTED, BotState.RECOVERY_CHECK): "guardian_go_signal",
        }
        return transitions.get((from_state, to_state), "unknown")
    
    async def _transition(self, next_state: BotState, reason: str = ""):
        self.logger.info(f"State transition: {self.current_state.value} → {next_state.value} (reason: {reason})")
        
        await self._exit_state(self.current_state)
        
        self.current_state = next_state
        self._save_state(reason)
        
        await self._enter_state(next_state)
    
    async def _exit_state(self, state: BotState):
        if state == BotState.ASYNC_TRADING:
            self.logger.info("Exiting ASYNC_TRADING state")
        elif state == BotState.RECOVERY_IN_PROGRESS:
            self._recovery_in_progress = False
            self.logger.info("Exiting RECOVERY_IN_PROGRESS state")
    
    async def _enter_state(self, state: BotState):
        if state == BotState.ASYNC_TRADING:
            self.logger.info("Entering ASYNC_TRADING state")
        elif state == BotState.RECOVERY_IN_PROGRESS:
            self._recovery_in_progress = True
            self.logger.info("Entering RECOVERY_IN_PROGRESS state")
        elif state == BotState.HALTED:
            self.logger.warning("Entering HALTED state - trading stopped")
    
    async def _handle_waiting(self) -> Optional[BotState]:
        self.logger.info("Waiting for Guardian GO signal...")
        guardian_status = self.bot._get_guardian_status()
        
        if guardian_status == "GO":
            self.logger.info("Guardian GO signal received")
            return BotState.RECOVERY_CHECK
        
        await asyncio.sleep(5)
        return None
    
    async def _handle_recovery_check(self) -> BotState:
        self.logger.info("Checking for missed grids...")
        
        try:
            missed_grids = await self.bot._check_missed_grids()
            
            if missed_grids and len(missed_grids) > 0:
                self.logger.info(f"Found {len(missed_grids)} missed grids: {missed_grids}")
                return BotState.RECOVERY_IN_PROGRESS
            else:
                self.logger.info("No missed grids found")
                return BotState.ASYNC_TRADING
                
        except Exception as e:
            self.logger.error(f"Error checking missed grids: {e}", exc_info=True)
            return BotState.ASYNC_TRADING
    
    async def _handle_recovery(self) -> BotState:
        self.logger.info("Executing recovery...")
        
        try:
            await self.bot._execute_recovery()
            self.logger.info("Recovery complete")
            return BotState.ASYNC_TRADING
            
        except Exception as e:
            self.logger.error(f"Recovery failed: {e}", exc_info=True)
            return BotState.ASYNC_TRADING
    
    async def _handle_trading(self) -> Optional[BotState]:
        guardian_status = self.bot._get_guardian_status()
        if guardian_status == "HALT":
            self.logger.warning("Guardian HALT signal detected")
            return BotState.HALTED
        
        await asyncio.sleep(1)
        return None
    
    async def _handle_halted(self) -> Optional[BotState]:
        self.logger.debug("Bot halted, waiting for Guardian GO signal...")
        guardian_status = self.bot._get_guardian_status()
        
        if guardian_status == "GO":
            self.logger.info("Guardian GO signal received, checking for recovery")
            return BotState.RECOVERY_CHECK
        
        await asyncio.sleep(5)
        return None
