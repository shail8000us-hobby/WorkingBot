"""
Mode-Atomic State Manager

Ensures clean state separation when switching between LONG and SHORT modes:
- Each mode gets its own fresh state
- Mode switch = forget previous mode's positions
- All open positions treated as manual (bot never touches them)
- TP orders are sacred (never cancel/modify)
"""

import os
import sys
import json
import logging
import hashlib
from pathlib import Path
from typing import Optional, Tuple

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import get_config

log = logging.getLogger("runner")


class ModeStateManager:
    """
    Manages mode-specific state files and handles mode transitions.
    
    Design Philosophy:
    1. Mode switch = Manual intervention = Fresh start
    2. All existing positions = Manual positions (bot ignores them)
    3. TP orders are sacred (never cancel, never modify)
    4. Clean atomic state per mode
    """
    
    def __init__(self, state_dir: str = '.'):
        """
        Initialize mode state manager.
        
        Args:
            state_dir: Directory to store state files
        """
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(exist_ok=True)
        
        # State file naming: runtime_state_{mode}.json
        self.long_state_file = self.state_dir / 'runtime_state_LONG.json'
        self.short_state_file = self.state_dir / 'runtime_state_SHORT.json'
        self.mode_marker_file = self.state_dir / '.current_mode'
        self.STATE_VERSION = "1.0"
    
    def _compute_state_checksum(self, state_data: dict) -> str:
        state_copy = state_data.copy()
        state_copy.pop('checksum', None)
        state_copy.pop('version', None)
        
        state_json = json.dumps(state_copy, sort_keys=True)
        return hashlib.sha256(state_json.encode()).hexdigest()
    
    def _validate_state_file(self, state_file: Path) -> Tuple[bool, str, Optional[dict]]:
        if not state_file.exists():
            return False, "File does not exist", None
        
        try:
            with open(state_file, 'r') as f:
                state_data = json.load(f)
            
            if not isinstance(state_data, dict):
                return False, "Invalid state format - not a dictionary", None
            
            file_version = state_data.get('version')
            if file_version != self.STATE_VERSION:
                return False, f"Version mismatch: file={file_version}, expected={self.STATE_VERSION}", None
            
            file_checksum = state_data.get('checksum')
            if not file_checksum:
                return False, "Missing checksum", None
            
            computed_checksum = self._compute_state_checksum(state_data)
            if file_checksum != computed_checksum:
                return False, "Checksum mismatch - file may be corrupted", None
            
            return True, "Valid", state_data
            
        except json.JSONDecodeError as e:
            return False, f"JSON parse error: {e}", None
        except Exception as e:
            return False, f"Validation error: {e}", None
    
    def save_state_with_validation(self, state_file: Path, state_data: dict) -> bool:
        try:
            state_data['version'] = self.STATE_VERSION
            state_data['checksum'] = self._compute_state_checksum(state_data)
            
            with open(state_file, 'w') as f:
                json.dump(state_data, f, indent=2)
            
            return True
        except Exception as e:
            log.error(f"Failed to save state: {e}")
            return False
        
    def get_current_mode(self) -> str:
        """
        Get current mode from config.
        
        Returns:
            'LONG' or 'SHORT'
        """
        cfg = get_config()
        return cfg.bot.mode.upper()
    
    def get_previous_mode(self) -> Optional[str]:
        """
        Get mode from last bot run.
        
        Returns:
            'LONG', 'SHORT', or None if first run
        """
        try:
            if self.mode_marker_file.exists():
                with open(self.mode_marker_file, 'r') as f:
                    return f.read().strip().upper()
        except Exception as e:
            log.warning(f"Failed to read mode marker: {e}")
        return None
    
    def save_current_mode(self, mode: str) -> None:
        """
        Save current mode marker.
        
        Args:
            mode: 'LONG' or 'SHORT'
        """
        try:
            with open(self.mode_marker_file, 'w') as f:
                f.write(mode.upper())
        except Exception as e:
            log.error(f"Failed to save mode marker: {e}")
    
    def detect_mode_switch(self) -> bool:
        """
        Detect if mode has changed since last run.
        
        Returns:
            True if mode switch detected, False otherwise
        """
        current_mode = self.get_current_mode()
        previous_mode = self.get_previous_mode()
        
        if previous_mode is None:
            # First run
            log.info(f"🆕 First run detected - starting in {current_mode} mode")
            return False
        
        if current_mode != previous_mode:
            log.info("=" * 80)
            log.info("🔄 MODE SWITCH DETECTED")
            log.info("=" * 80)
            log.info(f"   Previous Mode: {previous_mode}")
            log.info(f"   Current Mode:  {current_mode}")
            log.info("=" * 80)
            log.info("📋 Mode Switch Policy:")
            log.info("   ✅ Starting with clean state for new mode")
            log.info("   ✅ All open positions treated as MANUAL")
            log.info("   ✅ Bot will NOT touch existing positions")
            log.info("   ✅ Bot will NOT cancel/modify existing TPs")
            log.info("   ✅ Fresh start with mode-specific grid logic")
            log.info("=" * 80)
            return True
        
        return False
    
    def get_mode_state_file(self, mode: Optional[str] = None) -> Path:
        """
        Get state file for specific mode.
        
        Args:
            mode: 'LONG' or 'SHORT', or None to use current mode
            
        Returns:
            Path to mode-specific state file
        """
        if mode is None:
            mode = self.get_current_mode()
        
        mode = mode.upper()
        if mode == 'LONG':
            return self.long_state_file
        elif mode == 'SHORT':
            return self.short_state_file
        else:
            raise ValueError(f"Invalid mode: {mode}")
    
    def should_load_state(self) -> tuple:
        current_mode = self.get_current_mode()
        mode_switched = self.detect_mode_switch()
        
        if mode_switched:
            return False, self.get_mode_state_file(current_mode), "Mode switch detected - starting fresh"
        
        state_file = self.get_mode_state_file(current_mode)
        if state_file.exists():
            is_valid, reason, _ = self._validate_state_file(state_file)
            if is_valid:
                return True, state_file, f"Loading {current_mode} mode state"
            else:
                log.warning(f"State file validation failed: {reason}")
                log.warning(f"Starting fresh to avoid corrupted state")
                
                backup_file = state_file.with_suffix('.json.corrupted')
                try:
                    import shutil
                    shutil.move(str(state_file), str(backup_file))
                    log.info(f"Moved corrupted state to: {backup_file}")
                except Exception as e:
                    log.error(f"Failed to backup corrupted state: {e}")
                
                return False, state_file, f"State validation failed: {reason}"
        else:
            return False, state_file, f"No existing {current_mode} mode state - starting fresh"
    
    def archive_old_mode_state(self, old_mode: str) -> None:
        """
        Archive state from previous mode (for debugging/analysis).
        
        Args:
            old_mode: Mode to archive ('LONG' or 'SHORT')
        """
        try:
            old_state_file = self.get_mode_state_file(old_mode)
            if old_state_file.exists():
                # Create archive with timestamp
                import time
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                archive_dir = self.state_dir / 'mode_archives'
                archive_dir.mkdir(exist_ok=True)
                
                archive_file = archive_dir / f'runtime_state_{old_mode}_{timestamp}.json'
                
                import shutil
                shutil.copy2(old_state_file, archive_file)
                
                log.info(f"📦 Archived {old_mode} mode state: {archive_file.name}")
        except Exception as e:
            log.warning(f"⚠️  Failed to archive old mode state: {e}")
    
    def handle_mode_transition(self) -> tuple:
        """
        Handle mode transition logic.
        
        Returns:
            Tuple of (should_load_state: bool, state_file: Path, message: str)
        """
        current_mode = self.get_current_mode()
        previous_mode = self.get_previous_mode()
        
        # Check for mode switch
        if previous_mode and previous_mode != current_mode:
            log.info("=" * 80)
            log.info("🔄 HANDLING MODE TRANSITION")
            log.info("=" * 80)
            log.info(f"   {previous_mode} → {current_mode}")
            log.info("")
            log.info("📋 Transition Actions:")
            log.info("   1️⃣  Archive old mode state (for reference)")
            log.info("   2️⃣  Start fresh state for new mode")
            log.info("   3️⃣  Treat all open positions as MANUAL")
            log.info("   4️⃣  Bot will place orders for NEW mode only")
            log.info("=" * 80)
            
            # Archive old mode state
            self.archive_old_mode_state(previous_mode)
            
            # Save new mode marker
            self.save_current_mode(current_mode)
            
            # Return: Don't load state, use new mode's state file, with message
            state_file = self.get_mode_state_file(current_mode)
            return False, state_file, f"Mode switch: {previous_mode} → {current_mode}"
        
        # No mode switch - normal operation
        self.save_current_mode(current_mode)
        should_load, state_file, reason = self.should_load_state()
        return should_load, state_file, reason
    
    def log_manual_position_policy(self) -> None:
        """
        Log the manual position policy for user awareness.
        """
        log.info("=" * 80)
        log.info("📋 MANUAL POSITION POLICY")
        log.info("=" * 80)
        log.info("When mode switching, the bot will:")
        log.info("")
        log.info("✅ WILL DO:")
        log.info("   • Treat ALL existing positions as MANUAL")
        log.info("   • Start fresh grid for NEW mode")
        log.info("   • Place new orders based on NEW mode logic")
        log.info("   • Ignore manual positions completely")
        log.info("")
        log.info("❌ WILL NOT DO:")
        log.info("   • Cancel existing TP orders (they are SACRED)")
        log.info("   • Modify existing positions")
        log.info("   • Interfere with manual trades")
        log.info("   • Try to 'take over' manual positions")
        log.info("")
        log.info("🎯 Result:")
        log.info("   • Manual positions remain protected")
        log.info("   • Their TPs continue to work")
        log.info("   • Bot operates independently with NEW mode grid")
        log.info("=" * 80)


def get_mode_state_manager(state_dir: str = '.') -> ModeStateManager:
    """
    Get or create mode state manager instance.
    
    Args:
        state_dir: Directory for state files
        
    Returns:
        ModeStateManager instance
    """
    return ModeStateManager(state_dir)
