import asyncio
from enum import Enum
from typing import Optional
import json
from pathlib import Path
from datetime import datetime
from loguru import logger as log

class SystemState(Enum):
    WAITING_FOR_GUARDIAN = "waiting_for_guardian"
    RECOVERY_NEEDED = "recovery_needed"
    NORMAL_TRADING = "normal_trading"
    HALTED = "halted"

class SimpleStateCoordinator:
    
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.current_state = SystemState.WAITING_FOR_GUARDIAN
        self.state_file = Path("data/system_state.json")
        self.recovery_in_progress = False
        self._load_state()
    
    def _load_state(self):
        if self.state_file.exists():
            try:
                with open(self.state_file) as f:
                    data = json.load(f)
                    state_value = data.get("current_state", "waiting_for_guardian")
                    self.current_state = SystemState(state_value)
                    log.info(f"[StateCoordinator] Loaded state: {self.current_state.value}")
            except Exception as e:
                log.error(f"[StateCoordinator] Failed to load state: {e}, starting fresh")
                self.current_state = SystemState.WAITING_FOR_GUARDIAN
    
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
            "mode": self.bot.mode,
            "recovery_in_progress": self.recovery_in_progress
        }
        
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def is_recovery_in_progress(self) -> bool:
        return self.recovery_in_progress
    
    def should_allow_trading(self) -> bool:
        return self.current_state == SystemState.NORMAL_TRADING
    
    async def run_startup_sequence(self):
        log.info("=" * 80)
        log.info("🚀 SYSTEM COORDINATOR - Startup Sequence")
        log.info("=" * 80)
        
        await self._wait_for_guardian()
        
        await self._check_and_run_recovery()
        
        self._transition_to(SystemState.NORMAL_TRADING, "startup_complete")
        
        log.info("✅ Startup sequence complete - normal trading enabled")
        log.info("=" * 80)
    
    async def monitor_guardian(self):
        """
        Monitor Guardian state and trigger recovery when Guardian resumes.
        
        JAN 29 2026: Enhanced to use GuardianRecoveryEngine for proper recovery.
        """
        while self.bot._running:
            try:
                guardian_status = await self._get_guardian_status()
                
                if guardian_status == "HALT" and self.current_state == SystemState.NORMAL_TRADING:
                    log.warning("Guardian HALT detected - transitioning to HALTED state")
                    self._transition_to(SystemState.HALTED, "guardian_halt")
                
                elif guardian_status == "GO" and self.current_state == SystemState.HALTED:
                    log.info("Guardian GO detected - checking for recovery")
                    await self._run_guardian_recovery()
                    self._transition_to(SystemState.NORMAL_TRADING, "guardian_resume")
                
                await asyncio.sleep(1)
                
            except Exception as e:
                log.error(f"Guardian monitor error: {e}", exc_info=True)
                await asyncio.sleep(5)
    
    async def _run_guardian_recovery(self):
        """
        Run recovery when Guardian resumes from HALT to GO.
        
        JAN 29 2026: Uses GuardianRecoveryEngine for proper recovery.
        """
        log.info("Running Guardian resume recovery...")
        
        try:
            if not hasattr(self.bot, 'guardian_recovery'):
                log.warning("⚠️  Guardian recovery engine not initialized - skipping")
                return
            
            # Mark recovery in progress
            self.recovery_in_progress = True
            self._save_state("guardian_recovery_started")
            
            try:
                result = await self.bot.guardian_recovery.execute_recovery()
                
                if result.get('success'):
                    recovered = result.get('recovered', 0)
                    if recovered > 0:
                        log.info(f"✅ Guardian recovery complete: {recovered} grids recovered")
                    else:
                        log.info("✅ No missed grids during halt")
                else:
                    log.info(f"✅ Guardian recovery: {result.get('reason', 'no action needed')}")
            
            finally:
                self.recovery_in_progress = False
                self._save_state("guardian_recovery_complete")
                
        except Exception as e:
            log.error(f"Guardian recovery failed: {e}", exc_info=True)
            self.recovery_in_progress = False
    
    async def _wait_for_guardian(self):
        log.info("Waiting for Guardian GO signal...")
        
        while True:
            guardian_status = await self._get_guardian_status()
            
            if guardian_status == "GO":
                log.info("✅ Guardian GO signal received")
                break
            
            log.info("⏳ Guardian HALT - waiting 5s...")
            await asyncio.sleep(5)
    
    async def _get_guardian_status(self) -> str:
        try:
            signal, reason = await self.bot._read_guardian_signal()
            return signal
        except Exception as e:
            log.error(f"Error reading Guardian status: {e}")
            return "GO"
    
    async def _check_and_run_recovery(self):
        """
        Check for missed grids and execute recovery if needed.
        
        JAN 29 2026: Fixed to actually execute recovery instead of just logging.
        Uses the StartupRecoveryEngine for proper recovery with safety mechanisms.
        """
        log.info("Checking for missed grids...")
        
        try:
            # Check if recovery engine is available
            if not hasattr(self.bot, 'startup_recovery'):
                log.warning("⚠️  Startup recovery engine not initialized - skipping recovery")
                return
            
            # Use the recovery engine's should_trigger check
            should_trigger, reason = await self.bot.startup_recovery.should_trigger()
            
            if not should_trigger:
                log.info(f"✅ No recovery needed: {reason}")
                return
            
            log.warning(f"⚠️  Recovery triggered: {reason}")
            
            # Mark recovery in progress
            self.recovery_in_progress = True
            self._save_state("recovery_started")
            
            try:
                # Execute recovery through the engine
                result = await self.bot.startup_recovery.execute_recovery()
                
                if result.get('success'):
                    recovered = result.get('recovered', 0)
                    failed = result.get('failed', 0)
                    duration = result.get('duration', 0)
                    
                    if recovered > 0:
                        log.info(f"✅ Recovery complete: {recovered} grids recovered, {failed} failed")
                        log.info(f"   Duration: {duration:.2f}s, Session: {result.get('session_id', 'N/A')}")
                    else:
                        log.info("✅ No missed grids to recover")
                else:
                    reason = result.get('reason', 'unknown')
                    log.warning(f"⚠️  Recovery did not execute: {reason}")
            
            finally:
                self.recovery_in_progress = False
                self._save_state("recovery_complete")
                
        except Exception as e:
            log.error(f"Recovery check failed: {e}", exc_info=True)
            self.recovery_in_progress = False
            self._save_state("recovery_error")
    
    def _transition_to(self, new_state: SystemState, reason: str):
        log.info(f"State transition: {self.current_state.value} → {new_state.value} (reason: {reason})")
        self.current_state = new_state
        self._save_state(reason)
    
    async def run_reconciliation_loop(self):
        while self.bot._running:
            try:
                await asyncio.sleep(300)
                
                if self.recovery_in_progress:
                    log.info("Skipping reconciliation - recovery in progress")
                    continue
                
                log.debug("Running reconciliation check...")
                
            except Exception as e:
                log.error(f"Reconciliation loop error: {e}", exc_info=True)
                await asyncio.sleep(60)
