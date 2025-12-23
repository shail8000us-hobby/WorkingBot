"""
Bot Code Reader Module

Single Responsibility: Read bot's source code files without interference.

This module ONLY reads - never writes, never modifies.
Scans bot/strategy directory and loads all Python files.

Auto-refresh compatible: Reads fresh on every call (no caching).
"""

import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

log = logging.getLogger(__name__)


class BotCodeReader:
    """
    Reads bot source code files in real-time.
    
    Features:
    - Auto-discovers all strategy modules
    - Reads source code without interference
    - No caching (always fresh data)
    - Thread-safe reading
    """
    
    def __init__(self, bot_root: Path):
        """
        Initialize code reader.
        
        Args:
            bot_root: Path to bot root directory
        """
        self.bot_root = Path(bot_root)
        self.strategy_dir = self.bot_root / 'bot' / 'strategy'
        self.modules_dir = self.strategy_dir / 'modules'
        
        log.debug(f"BotCodeReader initialized: {self.strategy_dir}")
    
    def discover_all_modules(self) -> List[Path]:
        """
        Discover all Python files in bot/strategy.
        
        Returns list of file paths to analyze.
        """
        discovered = []
        
        try:
            # Main strategy files (EXCLUDE old gbot_ws.py - it's deprecated)
            if self.strategy_dir.exists():
                for py_file in self.strategy_dir.glob('*.py'):
                    if not py_file.name.startswith('_') and py_file.name != 'gbot_ws.py':
                        discovered.append(py_file)
            
            # Module files
            if self.modules_dir.exists():
                for py_file in self.modules_dir.glob('*.py'):
                    if not py_file.name.startswith('_'):
                        discovered.append(py_file)
            
            log.debug(f"Discovered {len(discovered)} strategy files")
            
        except Exception as e:
            log.error(f"Error discovering modules: {e}")
        
        return discovered
    
    def read_source_code(self, file_path: Path) -> Optional[str]:
        """
        Read source code from file.
        
        Args:
            file_path: Path to Python file
            
        Returns:
            Source code string or None if error
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            
            log.debug(f"Read {len(source)} chars from {file_path.name}")
            return source
            
        except Exception as e:
            log.error(f"Error reading {file_path}: {e}")
            return None
    
    def get_file_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Get metadata about a source file.
        
        Args:
            file_path: Path to file
            
        Returns:
            Dict with metadata (size, modified time, etc.)
        """
        try:
            stat = file_path.stat()
            
            return {
                'path': str(file_path),
                'name': file_path.name,
                'size_bytes': stat.st_size,
                'modified_timestamp': stat.st_mtime,
                'relative_path': str(file_path.relative_to(self.bot_root))
            }
            
        except Exception as e:
            log.error(f"Error getting metadata for {file_path}: {e}")
            return {}
    
    def read_all_brain_code(self) -> Dict[str, Any]:
        """
        Read ALL bot brain source code.
        
        Returns dict mapping file paths to source code and metadata.
        Fresh read every time (no caching for real-time accuracy).
        """
        brain_code = {
            'files': {},
            'total_files': 0,
            'total_lines': 0,
            'scan_timestamp': None
        }
        
        try:
            import time
            brain_code['scan_timestamp'] = time.time()
            
            discovered_files = self.discover_all_modules()
            
            for file_path in discovered_files:
                source_code = self.read_source_code(file_path)
                metadata = self.get_file_metadata(file_path)
                
                if source_code:
                    brain_code['files'][str(file_path)] = {
                        'source': source_code,
                        'metadata': metadata,
                        'line_count': len(source_code.split('\n'))
                    }
                    brain_code['total_files'] += 1
                    brain_code['total_lines'] += len(source_code.split('\n'))
            
            log.info(f"✅ Read {brain_code['total_files']} brain files ({brain_code['total_lines']} lines)")
            
        except Exception as e:
            log.error(f"Error reading brain code: {e}")
        
        return brain_code

