"""
Resolved System State API Blueprint

This module provides a SINGLE authoritative source of truth for system state.
All UI components should consume ResolvedSystemState instead of querying
multiple endpoints or deriving state independently.

CRITICAL: This is the ONLY place where state resolution logic lives.
All other endpoints should reference this resolver.

Routes:
- GET /api/resolved_state - Get complete resolved system state

State Model:
{
    "trading_allowed": bool,
    "guardian_active": bool,
    "safety_level": "SAFE" | "CAUTION" | "BLOCKED",
    "execution_mode": "LIVE" | "SIM" | "TESTNET",
    "net_exposure": {
        "delta": float,
        "delta_pct": float,
        "label": "Bullish" | "Neutral" | "Bearish",
        "gamma": float,
        "vega": float
    },
    "warning_list": [
        {
            "severity": "critical" | "warning" | "info",
            "source": str,
            "message": str,
            "timestamp": str
        }
    ],
    "guardian": {
        "state": "ACTIVE" | "STOPPED",
        "reason": str,
        "last_decision_time": str
    },
    "timestamp": str
}
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
from flask import Blueprint, jsonify, request

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.loader import get_config
from utils.process_helpers import is_guardian_running, is_bot_running

log = logging.getLogger(__name__)

# Create blueprint
resolved_state_bp = Blueprint('resolved_state', __name__)

# File paths
BASE_DIR = Path(__file__).parent.parent.parent.parent


class ResolvedSystemState:
    """
    Single authoritative resolver for all system state.
    
    This class consolidates state from:
    - Guardian service
    - Safety Gatekeeper
    - Blocker Tracker
    - Configuration
    - Position data
    - Process health
    """
    
    def __init__(self):
        self.config = get_config()
        self.workspace_root = BASE_DIR
        
    def resolve(self) -> Dict[str, Any]:
        """
        Resolve complete system state from all sources.
        
        Returns:
            Complete ResolvedSystemState dict
        """
        # Step 1: Resolve Guardian state
        guardian_state = self._resolve_guardian_state()
        
        # Step 2: Resolve execution mode
        execution_mode = self._resolve_execution_mode()
        
        # Step 3: Resolve trading_allowed (depends on guardian_active)
        trading_allowed = self._resolve_trading_allowed(guardian_state)
        
        # Step 4: Resolve safety_level
        safety_level = self._resolve_safety_level(guardian_state, trading_allowed)
        
        # Step 5: Resolve net exposure (delta-based)
        net_exposure = self._resolve_net_exposure()
        
        # Step 6: Collect all warnings
        warning_list = self._collect_warnings(guardian_state, trading_allowed)
        
        return {
            'trading_allowed': trading_allowed,
            'guardian_active': guardian_state['active'],
            'safety_level': safety_level,
            'execution_mode': execution_mode,
            'net_exposure': net_exposure,
            'warning_list': warning_list,
            'guardian': {
                'state': guardian_state['state'],
                'reason': guardian_state['reason'],
                'last_decision_time': guardian_state['last_decision_time']
            },
            'timestamp': datetime.now().isoformat()
        }
    
    def _resolve_guardian_state(self) -> Dict[str, Any]:
        """
        Resolve Guardian state according to rules:
        - If guardian_enabled=false OR guardian_service!=running → guardian_active=false
        - Returns state, reason, and last_decision_time
        """
        guardian_enabled = self.config.guardian.enabled if hasattr(self.config, 'guardian') else False
        guardian_running = is_guardian_running()
        
        # Check if Guardian service is actually running
        guardian_active = guardian_enabled and guardian_running
        
        # Determine state
        if not guardian_enabled:
            state = 'STOPPED'
            reason = 'Guardian disabled in configuration'
        elif not guardian_running:
            state = 'STOPPED'
            reason = 'Guardian service not running'
        else:
            state = 'ACTIVE'
            reason = 'Guardian monitoring active'
        
        # Get last decision time from Guardian health file
        last_decision_time = None
        try:
            health_file = self.workspace_root / '.guardian_health.json'
            if health_file.exists():
                import json
                with open(health_file, 'r') as f:
                    health = json.load(f)
                    timestamp = health.get('timestamp') or health.get('last_check')
                    if timestamp:
                        last_decision_time = datetime.fromtimestamp(timestamp).isoformat()
        except Exception as e:
            log.warning(f"Could not read Guardian health: {e}")
        
        return {
            'active': guardian_active,
            'state': state,
            'reason': reason,
            'last_decision_time': last_decision_time or datetime.now().isoformat()
        }
    
    def _resolve_execution_mode(self) -> str:
        """Resolve execution mode from config"""
        trading_mode = self.config.trading_mode if hasattr(self.config, 'trading_mode') else 'demo'
        
        # Map config values to execution_mode
        mode_map = {
            'live': 'LIVE',
            'demo': 'SIM',
            'testnet': 'TESTNET'
        }
        
        return mode_map.get(trading_mode.lower(), 'SIM')
    
    def _resolve_trading_allowed(self, guardian_state: Dict[str, Any]) -> bool:
        """
        Resolve trading_allowed with hard rule:
        - If guardian_active=false → trading_allowed=false (hard rule)
        - Otherwise, check blocker tracker
        """
        # Hard rule: Guardian must be active for trading
        if not guardian_state['active']:
            return False
        
        # Check blocker tracker for other blockers
        try:
            from bot.safety.blocker_tracker import get_blocker_tracker
            tracker = get_blocker_tracker()
            blocker_data = tracker.check_all_blockers()
            return blocker_data.get('trading_allowed', False)
        except Exception as e:
            log.warning(f"Could not check blockers: {e}")
            # If we can't check blockers, default to False for safety
            return False
    
    def _resolve_safety_level(self, guardian_state: Dict[str, Any], trading_allowed: bool) -> str:
        """
        Resolve safety_level:
        - BLOCKED: trading_allowed=false
        - CAUTION: trading_allowed=true but warnings exist
        - SAFE: trading_allowed=true and no warnings
        """
        if not trading_allowed:
            return 'BLOCKED'
        
        # Check for warnings (will be populated later, but we can check blockers here)
        try:
            from bot.safety.blocker_tracker import get_blocker_tracker
            tracker = get_blocker_tracker()
            blocker_data = tracker.check_all_blockers()
            active_blockers = [b for b in blocker_data.get('blockers', []) if b.get('active', False)]
            
            # If there are any critical blockers, it's BLOCKED (shouldn't happen if trading_allowed=true)
            critical_blockers = [b for b in active_blockers if b.get('severity') == 'critical']
            if critical_blockers:
                return 'BLOCKED'
            
            # If there are warnings, it's CAUTION
            if active_blockers:
                return 'CAUTION'
        except Exception:
            pass
        
        return 'SAFE'
    
    def _resolve_net_exposure(self) -> Dict[str, Any]:
        """
        Resolve net exposure using DELTA-based calculation, not LONG/SHORT.
        
        Returns:
            {
                "delta": float,  # Net delta (positive = bullish, negative = bearish)
                "delta_pct": float,  # Delta as percentage
                "label": "Bullish" | "Neutral" | "Bearish",
                "gamma": float,
                "vega": float
            }
        """
        try:
            cfg = get_config()
            mode = cfg.trading_mode if hasattr(cfg, 'trading_mode') else 'demo'
            positions_file = BASE_DIR / 'bot' / 'data' / mode / 'positions.json'
            
            if not positions_file.exists():
                return {
                    'delta': 0.0,
                    'delta_pct': 0.0,
                    'label': 'Neutral',
                    'gamma': 0.0,
                    'vega': 0.0
                }
            
            from bot.state.store import load_positions_file
            positions_data = load_positions_file(positions_file)
            positions = positions_data.get('positions', [])
            
            # Calculate net delta from positions
            total_delta = 0.0
            total_gamma = 0.0
            total_vega = 0.0
            
            for pos in positions:
                # For spot/futures: delta = size (positive for long, negative for short)
                size = pos.get('size', 0)
                if pos.get('side') == 'SHORT' or size < 0:
                    total_delta -= abs(size)
                else:
                    total_delta += abs(size)
                
                # For options, we'd need greeks - placeholder for now
                total_gamma += pos.get('gamma', 0.0)
                total_vega += pos.get('vega', 0.0)
            
            # Calculate delta percentage (normalize by some reference)
            # For now, use absolute delta as percentage
            delta_pct = abs(total_delta) * 100 if total_delta != 0 else 0.0
            
            # Determine label
            if total_delta > 0.01:
                label = 'Bullish'
            elif total_delta < -0.01:
                label = 'Bearish'
            else:
                label = 'Neutral'
            
            return {
                'delta': round(total_delta, 4),
                'delta_pct': round(delta_pct, 2),
                'label': label,
                'gamma': round(total_gamma, 4),
                'vega': round(total_vega, 4)
            }
        except Exception as e:
            log.warning(f"Could not calculate net exposure: {e}")
            return {
                'delta': 0.0,
                'delta_pct': 0.0,
                'label': 'Neutral',
                'gamma': 0.0,
                'vega': 0.0
            }
    
    def _collect_warnings(self, guardian_state: Dict[str, Any], trading_allowed: bool) -> List[Dict[str, Any]]:
        """
        Collect all warnings from various sources with severity and source.
        """
        warnings = []
        
        # Warning 1: Guardian not active
        if not guardian_state['active']:
            warnings.append({
                'severity': 'critical',
                'source': 'GUARDIAN',
                'message': guardian_state['reason'],
                'timestamp': datetime.now().isoformat()
            })
        
        # Warning 2: Trading blocked
        if not trading_allowed:
            try:
                from bot.safety.blocker_tracker import get_blocker_tracker
                tracker = get_blocker_tracker()
                blocker_data = tracker.check_all_blockers()
                active_blockers = [b for b in blocker_data.get('blockers', []) if b.get('active', False)]
                
                for blocker in active_blockers:
                    warnings.append({
                        'severity': blocker.get('severity', 'warning'),
                        'source': blocker.get('category', 'UNKNOWN'),
                        'message': blocker.get('message', 'Unknown blocker'),
                        'timestamp': datetime.now().isoformat()
                    })
            except Exception:
                warnings.append({
                    'severity': 'critical',
                    'source': 'SYSTEM',
                    'message': 'Trading is blocked - unable to determine reason',
                    'timestamp': datetime.now().isoformat()
                })
        
        # Warning 3: Mixed LIVE + TESTNET configuration
        execution_mode = self._resolve_execution_mode()
        if execution_mode == 'LIVE':
            # Check if any testnet config exists
            # This is a placeholder - would need to check actual config
            pass
        
        return warnings


# Singleton instance
_resolver_instance = None

def get_resolver() -> ResolvedSystemState:
    """Get singleton instance of ResolvedSystemState"""
    global _resolver_instance
    if _resolver_instance is None:
        _resolver_instance = ResolvedSystemState()
    return _resolver_instance


# ============================================================================
# Route Handlers
# ============================================================================

@resolved_state_bp.route('/api/resolved_state', methods=['GET'])
def get_resolved_state():
    """
    Get complete resolved system state - SINGLE SOURCE OF TRUTH.
    
    This endpoint consolidates all state information into a single
    authoritative model. All UI components should consume this instead
    of querying multiple endpoints.
    
    Returns:
        JSON response with complete ResolvedSystemState
        
    Example:
        GET /api/resolved_state
        Response: {
            "trading_allowed": false,
            "guardian_active": false,
            "safety_level": "BLOCKED",
            "execution_mode": "LIVE",
            "net_exposure": {
                "delta": 0.5,
                "delta_pct": 50.0,
                "label": "Bullish",
                "gamma": 0.0,
                "vega": 0.0
            },
            "warning_list": [
                {
                    "severity": "critical",
                    "source": "GUARDIAN",
                    "message": "Guardian service not running",
                    "timestamp": "2025-01-01T12:00:00"
                }
            ],
            "guardian": {
                "state": "STOPPED",
                "reason": "Guardian service not running",
                "last_decision_time": "2025-01-01T12:00:00"
            },
            "timestamp": "2025-01-01T12:00:00"
        }
    """
    try:
        resolver = get_resolver()
        state = resolver.resolve()
        return jsonify(state), 200
    except Exception as e:
        log.error(f"Error resolving system state: {e}", exc_info=True)
        return jsonify({
            'error': str(e),
            'trading_allowed': False,
            'guardian_active': False,
            'safety_level': 'BLOCKED',
            'execution_mode': 'SIM',
            'net_exposure': {
                'delta': 0.0,
                'delta_pct': 0.0,
                'label': 'Neutral',
                'gamma': 0.0,
                'vega': 0.0
            },
            'warning_list': [{
                'severity': 'critical',
                'source': 'SYSTEM',
                'message': f'State resolution failed: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }],
            'guardian': {
                'state': 'STOPPED',
                'reason': 'State resolution error',
                'last_decision_time': datetime.now().isoformat()
            },
            'timestamp': datetime.now().isoformat()
        }), 500



