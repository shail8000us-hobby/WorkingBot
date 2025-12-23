"""
Real-Time File Monitor

Single Responsibility: Monitor bot files for changes and predict impact.

This module:
1. Watches key bot files for modifications
2. Detects configuration changes
3. Predicts impact of changes on bot behavior
4. Provides real-time alerts for critical changes

Key Features:
- Non-intrusive file watching
- Change impact analysis
- Configuration drift detection
- Real-time notifications
"""

import logging
import json
import time
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, asdict
from datetime import datetime

log = logging.getLogger(__name__)


@dataclass
class FileChange:
    """Represents a detected file change"""
    file_path: str
    change_type: str  # 'modified', 'created', 'deleted'
    timestamp: float
    old_hash: Optional[str] = None
    new_hash: Optional[str] = None
    impact_level: str = 'low'  # 'low', 'medium', 'high', 'critical'
    predicted_impact: str = ''
    requires_restart: bool = False


@dataclass
class MonitoringState:
    """Current monitoring state"""
    files_watched: int
    last_scan: float
    changes_detected: int
    critical_changes: int
    monitoring_active: bool = True


class RealTimeFileMonitor:
    """
    Monitors bot files for changes and predicts impact on trading behavior.
    
    This is a READ-ONLY monitor that doesn't modify any files.
    """
    
    def __init__(self, bot_root: Path):
        """Initialize file monitor"""
        self.bot_root = Path(bot_root)
        self.file_hashes = {}
        self.last_scan = 0
        self.changes_history = []
        self.max_history = 100
        
        # Define critical files to monitor
        self.critical_files = {
            'config.yaml': 'critical',
            '.env': 'critical',
            'bot/strategy/gridbot.py': 'high',
            'bot/safety/gatekeeper.py': 'high',
            'bot/safety/volatility_monitor.py': 'high',
            'bot/state/positions.json': 'medium',
            '.volatility_status.json': 'medium',
            '.volatility_halt.json': 'medium'
        }
        
        log.info(f"RealTimeFileMonitor initialized: {self.bot_root}")
        self._initial_scan()
    
    def _initial_scan(self):
        """Perform initial scan to establish baseline"""
        try:
            for rel_path, importance in self.critical_files.items():
                file_path = self.bot_root / rel_path
                if file_path.exists():
                    file_hash = self._calculate_file_hash(file_path)
                    self.file_hashes[str(file_path)] = {
                        'hash': file_hash,
                        'last_modified': file_path.stat().st_mtime,
                        'importance': importance,
                        'size': file_path.stat().st_size
                    }
            
            self.last_scan = time.time()
            log.info(f"Initial scan complete: {len(self.file_hashes)} files monitored")
            
        except Exception as e:
            log.error(f"Error during initial scan: {e}")
    
    def scan_for_changes(self) -> List[FileChange]:
        """Scan for file changes since last check"""
        changes = []
        current_time = time.time()
        
        try:
            for rel_path, importance in self.critical_files.items():
                file_path = self.bot_root / rel_path
                file_path_str = str(file_path)
                
                if file_path.exists():
                    # Calculate current hash
                    current_hash = self._calculate_file_hash(file_path)
                    current_mtime = file_path.stat().st_mtime
                    current_size = file_path.stat().st_size
                    
                    if file_path_str in self.file_hashes:
                        # Check for modifications
                        stored_info = self.file_hashes[file_path_str]
                        if (current_hash != stored_info['hash'] or 
                            current_mtime > stored_info['last_modified']):
                            
                            change = FileChange(
                                file_path=rel_path,
                                change_type='modified',
                                timestamp=current_time,
                                old_hash=stored_info['hash'],
                                new_hash=current_hash,
                                impact_level=importance
                            )
                            
                            # Predict impact based on file type
                            change.predicted_impact = self._predict_change_impact(rel_path, stored_info, current_size)
                            change.requires_restart = self._requires_restart(rel_path)
                            
                            changes.append(change)
                            
                            # Update stored hash
                            self.file_hashes[file_path_str] = {
                                'hash': current_hash,
                                'last_modified': current_mtime,
                                'importance': importance,
                                'size': current_size
                            }
                    else:
                        # New file created
                        change = FileChange(
                            file_path=rel_path,
                            change_type='created',
                            timestamp=current_time,
                            new_hash=current_hash,
                            impact_level=importance,
                            predicted_impact=f"New {rel_path} file created",
                            requires_restart=self._requires_restart(rel_path)
                        )
                        changes.append(change)
                        
                        self.file_hashes[file_path_str] = {
                            'hash': current_hash,
                            'last_modified': current_mtime,
                            'importance': importance,
                            'size': current_size
                        }
                
                elif file_path_str in self.file_hashes:
                    # File was deleted
                    change = FileChange(
                        file_path=rel_path,
                        change_type='deleted',
                        timestamp=current_time,
                        old_hash=self.file_hashes[file_path_str]['hash'],
                        impact_level='critical',
                        predicted_impact=f"Critical file {rel_path} was deleted - bot may malfunction",
                        requires_restart=True
                    )
                    changes.append(change)
                    del self.file_hashes[file_path_str]
            
            # Store changes in history
            for change in changes:
                self.changes_history.append(change)
                if len(self.changes_history) > self.max_history:
                    self.changes_history.pop(0)
            
            self.last_scan = current_time
            
            if changes:
                log.info(f"Detected {len(changes)} file changes")
                for change in changes:
                    log.info(f"  {change.change_type.upper()}: {change.file_path} ({change.impact_level})")
            
            return changes
            
        except Exception as e:
            log.error(f"Error scanning for changes: {e}")
            return []
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file content"""
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                return hashlib.sha256(content).hexdigest()[:16]  # First 16 chars
        except Exception as e:
            log.error(f"Error calculating hash for {file_path}: {e}")
            return "error"
    
    def _predict_change_impact(self, rel_path: str, old_info: Dict, new_size: int) -> str:
        """Predict the impact of a file change"""
        try:
            if rel_path == 'config.yaml':
                return "Grid parameters changed - bot will reload configuration automatically"
            
            elif rel_path == '.env':
                return "Environment variables changed - requires bot restart"
            
            elif 'strategy' in rel_path:
                return "Trading strategy modified - requires bot restart for changes to take effect"
            
            elif 'safety' in rel_path:
                return "Safety system modified - critical for risk management, restart recommended"
            
            elif 'positions.json' in rel_path:
                return "Position data updated - reflects current trading state"
            
            elif 'volatility' in rel_path:
                return "Volatility monitoring data changed - affects trading decisions"
            
            else:
                size_change = new_size - old_info.get('size', 0)
                if size_change > 1000:
                    return f"Significant content change (+{size_change} bytes)"
                else:
                    return "Minor file modification detected"
                    
        except Exception as e:
            log.error(f"Error predicting impact for {rel_path}: {e}")
            return "Unknown impact"
    
    def _requires_restart(self, rel_path: str) -> bool:
        """Determine if file change requires bot restart"""
        restart_files = {
            '.env',
            'bot/strategy/gridbot.py',
            'bot/safety/gatekeeper.py',
            'bot/safety/volatility_monitor.py'
        }
        return rel_path in restart_files
    
    def get_monitoring_summary(self) -> Dict[str, Any]:
        """Get summary of monitoring status"""
        try:
            recent_changes = [c for c in self.changes_history if c.timestamp > time.time() - 3600]  # Last hour
            critical_changes = [c for c in recent_changes if c.impact_level in ['critical', 'high']]
            
            return {
                'monitoring_state': MonitoringState(
                    files_watched=len(self.file_hashes),
                    last_scan=self.last_scan,
                    changes_detected=len(recent_changes),
                    critical_changes=len(critical_changes),
                    monitoring_active=True
                ),
                'recent_changes': [asdict(c) for c in recent_changes[-10:]],  # Last 10 changes
                'file_status': {
                    path: {
                        'status': 'monitored',
                        'last_modified': info['last_modified'],
                        'importance': info['importance'],
                        'size_kb': round(info['size'] / 1024, 1)
                    }
                    for path, info in self.file_hashes.items()
                },
                'alerts': self._generate_alerts(recent_changes)
            }
            
        except Exception as e:
            log.error(f"Error generating monitoring summary: {e}")
            return {'error': str(e)}
    
    def _generate_alerts(self, recent_changes: List[FileChange]) -> List[Dict[str, Any]]:
        """Generate alerts based on recent changes"""
        alerts = []
        
        try:
            for change in recent_changes:
                if change.impact_level == 'critical':
                    alerts.append({
                        'type': 'critical',
                        'message': f"Critical file change: {change.file_path}",
                        'action_required': 'Immediate attention required',
                        'timestamp': change.timestamp
                    })
                
                elif change.requires_restart:
                    alerts.append({
                        'type': 'restart_required',
                        'message': f"Bot restart recommended due to {change.file_path} changes",
                        'action_required': 'Restart bot to apply changes',
                        'timestamp': change.timestamp
                    })
            
            # Check for configuration drift
            config_changes = [c for c in recent_changes if 'config' in c.file_path.lower()]
            if len(config_changes) > 3:
                alerts.append({
                    'type': 'config_drift',
                    'message': f"High configuration change frequency: {len(config_changes)} changes detected",
                    'action_required': 'Review configuration stability',
                    'timestamp': time.time()
                })
            
            return alerts
            
        except Exception as e:
            log.error(f"Error generating alerts: {e}")
            return []
    
    def get_change_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get change history for specified time period"""
        try:
            cutoff_time = time.time() - (hours * 3600)
            recent_changes = [c for c in self.changes_history if c.timestamp > cutoff_time]
            return [asdict(c) for c in recent_changes]
        except Exception as e:
            log.error(f"Error getting change history: {e}")
            return []