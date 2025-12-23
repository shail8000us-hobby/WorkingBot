"""
Change Detector Module

Single Responsibility: Detect changes in bot brain files and predict logic impact.

Tracks file modification times and AST structure to identify:
- Which files changed
- What logic was modified
- Predicted impact on decision flow

Auto-refresh compatible: Compares current state with previous snapshot.
"""

import logging
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional
from .ast_parser import DecisionParser

log = logging.getLogger(__name__)


class ChangeDetector:
    """
    Detects changes in bot brain files and predicts impact.
    
    Features:
    - Tracks file modification timestamps
    - Compares AST structure (decision points, conditions)
    - Predicts impact on decision flow
    - No caching - always compares current vs previous scan
    """
    
    def __init__(self, bot_root: Path):
        """
        Initialize change detector.
        
        Args:
            bot_root: Path to bot root directory
        """
        self.bot_root = Path(bot_root)
        self.strategy_dir = self.bot_root / 'bot' / 'strategy'
        self.modules_dir = self.strategy_dir / 'modules'
        self.parser = DecisionParser()
        
        # In-memory snapshot (cleared on restart - no persistence to avoid conflicts)
        self._previous_snapshots: Dict[str, Dict[str, Any]] = {}
        
        log.debug(f"ChangeDetector initialized: {self.strategy_dir}")
    
    def calculate_file_hash(self, file_path: Path) -> str:
        """
        Calculate SHA256 hash of file content.
        
        Args:
            file_path: Path to file
            
        Returns:
            Hexadecimal hash string
        """
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                return hashlib.sha256(content).hexdigest()
        except Exception as e:
            log.error(f"Error calculating hash for {file_path}: {e}")
            return ""
    
    def get_ast_signature(self, source_code: str) -> Dict[str, Any]:
        """
        Get AST signature (decision points, conditions, actions).
        
        Args:
            source_code: Python source code
            
        Returns:
            Dict with AST signature (decision count, action count, etc.)
        """
        try:
            parsed = self.parser.parse_source_code(source_code, "temp.py")
            
            # Extract signature
            decisions = parsed.get('decisions', [])
            actions = parsed.get('actions', [])
            conditions = parsed.get('conditions', [])
            
            return {
                'decision_count': len(decisions),
                'action_count': len(actions),
                'condition_count': len(conditions),
                'decision_labels': [d.get('label', '') for d in decisions],
                'action_labels': [a.get('label', '') for a in actions]
            }
        except Exception as e:
            log.error(f"Error getting AST signature: {e}")
            return {}
    
    def detect_changes(self, brain_code: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect changes in brain files since last scan.
        
        Args:
            brain_code: Current brain code dict from BotCodeReader
            
        Returns:
            Dict with change detection results
        """
        changes = {
            'files_changed': [],
            'files_unchanged': [],
            'logic_impact': [],
            'new_files': [],
            'deleted_files': [],
            'scan_timestamp': time.time()
        }
        
        try:
            current_files = set(brain_code.get('files', {}).keys())
            previous_files = set(self._previous_snapshots.keys())
            
            # Detect new files
            new_files = current_files - previous_files
            for file_path in new_files:
                changes['new_files'].append({
                    'file': file_path,
                    'impact': 'NEW_LOGIC_ADDED'
                })
            
            # Detect deleted files
            deleted_files = previous_files - current_files
            for file_path in deleted_files:
                changes['deleted_files'].append({
                    'file': file_path,
                    'impact': 'LOGIC_REMOVED'
                })
            
            # Detect modified files
            for file_path, file_data in brain_code.get('files', {}).items():
                source = file_data.get('source', '')
                metadata = file_data.get('metadata', {})
                
                if not source:
                    continue
                
                current_hash = self.calculate_file_hash(Path(file_path))
                current_mtime = metadata.get('modified_timestamp', 0)
                current_ast = self.get_ast_signature(source)
                
                # Compare with previous snapshot
                if file_path in self._previous_snapshots:
                    prev_snapshot = self._previous_snapshots[file_path]
                    prev_hash = prev_snapshot.get('hash', '')
                    prev_mtime = prev_snapshot.get('mtime', 0)
                    prev_ast = prev_snapshot.get('ast_signature', {})
                    
                    # Check if file changed
                    if current_hash != prev_hash or current_mtime > prev_mtime:
                        # File content changed
                        changes['files_changed'].append({
                            'file': file_path,
                            'modified_time': current_mtime,
                            'previous_hash': prev_hash,
                            'current_hash': current_hash,
                            'ast_changes': self._compare_ast_signatures(prev_ast, current_ast)
                        })
                        
                        # Predict impact
                        impact = self._predict_impact(prev_ast, current_ast, Path(file_path).name)
                        changes['logic_impact'].append({
                            'file': file_path,
                            'impact_level': impact['level'],
                            'impact_description': impact['description'],
                            'affected_decisions': impact['affected_decisions']
                        })
                    else:
                        changes['files_unchanged'].append(file_path)
                else:
                    # New file (already in new_files, but also track for snapshot)
                    changes['files_unchanged'].append(file_path)
                
                # Update snapshot
                self._previous_snapshots[file_path] = {
                    'hash': current_hash,
                    'mtime': current_mtime,
                    'ast_signature': current_ast,
                    'scan_time': time.time()
                }
            
            log.info(f"✅ Change detection: {len(changes['files_changed'])} changed, "
                    f"{len(changes['new_files'])} new, {len(changes['logic_impact'])} impacts")
            
        except Exception as e:
            log.error(f"Error detecting changes: {e}")
            import traceback
            log.error(traceback.format_exc())
        
        return changes
    
    def _compare_ast_signatures(self, prev_ast: Dict, current_ast: Dict) -> Dict[str, Any]:
        """Compare two AST signatures and return differences."""
        differences = {
            'decision_count_delta': current_ast.get('decision_count', 0) - prev_ast.get('decision_count', 0),
            'action_count_delta': current_ast.get('action_count', 0) - prev_ast.get('action_count', 0),
            'decisions_added': [],
            'decisions_removed': [],
            'actions_added': [],
            'actions_removed': []
        }
        
        prev_decisions = set(prev_ast.get('decision_labels', []))
        current_decisions = set(current_ast.get('decision_labels', []))
        differences['decisions_added'] = list(current_decisions - prev_decisions)
        differences['decisions_removed'] = list(prev_decisions - current_decisions)
        
        prev_actions = set(prev_ast.get('action_labels', []))
        current_actions = set(current_ast.get('action_labels', []))
        differences['actions_added'] = list(current_actions - prev_actions)
        differences['actions_removed'] = list(prev_actions - current_actions)
        
        return differences
    
    def _predict_impact(self, prev_ast: Dict, current_ast: Dict, filename: str) -> Dict[str, Any]:
        """
        Predict impact of AST changes on bot logic.
        
        Returns:
            Dict with impact_level (LOW/MEDIUM/HIGH/CRITICAL) and description
        """
        impact_level = 'LOW'
        description = f"Minor changes detected in {filename}"
        affected_decisions = []
        
        # Check decision count changes
        decision_delta = current_ast.get('decision_count', 0) - prev_ast.get('decision_count', 0)
        if decision_delta > 0:
            impact_level = 'MEDIUM'
            description = f"{filename}: New decision points added (+{decision_delta})"
        elif decision_delta < 0:
            impact_level = 'HIGH'
            description = f"{filename}: Decision points removed ({decision_delta})"
        
        # Check action count changes
        action_delta = current_ast.get('action_count', 0) - prev_ast.get('action_count', 0)
        if action_delta != 0:
            if impact_level == 'LOW':
                impact_level = 'MEDIUM'
            description += f", Actions changed ({action_delta:+d})"
        
        # Check critical files
        critical_files = ['grid_calculator.py', 'volatility_handler.py', 'order_manager.py', 'gridbot.py']
        if filename in critical_files:
            if impact_level == 'MEDIUM':
                impact_level = 'HIGH'
            elif impact_level == 'LOW':
                impact_level = 'MEDIUM'
            description = f"⚠️ CRITICAL FILE CHANGED: {description}"
        
        # Find affected decisions
        prev_decisions = set(prev_ast.get('decision_labels', []))
        current_decisions = set(current_ast.get('decision_labels', []))
        affected_decisions = list(prev_decisions.symmetric_difference(current_decisions))
        
        if not affected_decisions:
            affected_decisions = list(current_decisions)
        
        return {
            'level': impact_level,
            'description': description,
            'affected_decisions': affected_decisions[:5]  # Limit to 5
        }

