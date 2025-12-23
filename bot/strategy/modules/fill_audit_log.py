"""
Fill Audit Log - Persistent memory of all fill processing events

CRITICAL: This solves the bot's amnesia problem!

The bot needs permanent memory of:
- Which fills it has processed
- What actions it took (TP placement, next grid order)
- Success/failure of each action
- Timestamps for debugging

Without this, the bot forgets everything on restart and can:
- Process the same fill twice
- Miss fills completely
- Not know if TP orders were placed
- Lose track of what happened
"""

import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, asdict

log = logging.getLogger("runner")


@dataclass
class FillProcessingRecord:
    """
    Complete record of a single fill processing event
    """
    # Fill identification
    order_id: str
    fill_price: float
    fill_size: float
    side: str  # 'buy' or 'sell'
    role: str  # 'maker' or 'taker'
    
    # Processing details
    detected_at: float  # Unix timestamp when fill was detected
    processed_at: float  # Unix timestamp when processing completed
    detection_method: str  # 'websocket', 'polling', 'reconciliation'
    
    # Actions taken
    tp_order_placed: bool
    tp_order_id: Optional[str]
    tp_price: Optional[float]
    
    next_grid_placed: bool
    next_grid_order_id: Optional[str]
    next_grid_price: Optional[float]
    
    # Status
    success: bool
    error_message: Optional[str] = None
    retry_count: int = 0
    
    # Metadata
    session_tag: str = ""
    bot_pid: int = 0


class FillAuditLog:
    """
    Persistent audit log for fill processing
    
    Provides bot with permanent memory so it never forgets:
    - What fills it has processed
    - What actions it took
    - Success/failure status
    
    Critical for:
    - Crash recovery (know what was done)
    - Duplicate detection (prevent reprocessing)
    - Debugging (full history of events)
    - Reconciliation (detect missing actions)
    """
    
    def __init__(self, log_file: str = 'bot/audit/fill_processing_log.jsonl'):
        """
        Initialize fill audit log
        
        Args:
            log_file: Path to JSONL log file (one JSON object per line)
        """
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # In-memory cache of recent fills (last 1000)
        self.recent_fills: Dict[str, FillProcessingRecord] = {}
        self.max_cache_size = 1000
        
        # Load recent history from file
        self._load_recent_history()
        
        log.info(f"✅ Fill Audit Log initialized: {self.log_file}")
        log.info(f"   📝 {len(self.recent_fills)} recent fills in memory")
    
    def _load_recent_history(self):
        """
        Load recent fill history from log file into memory
        """
        if not self.log_file.exists():
            return
        
        try:
            with open(self.log_file, 'r') as f:
                # Read last N lines (recent history)
                lines = f.readlines()[-self.max_cache_size:]
                
                for line in lines:
                    try:
                        data = json.loads(line.strip())
                        record = FillProcessingRecord(**data)
                        self.recent_fills[record.order_id] = record
                    except Exception as e:
                        log.warning(f"⚠️ Failed to parse log line: {e}")
            
            log.info(f"📖 Loaded {len(self.recent_fills)} fills from audit log")
        
        except Exception as e:
            log.error(f"❌ Failed to load fill history: {e}")
    
    def record_fill_processing(self, record: FillProcessingRecord) -> None:
        """
        Append fill processing record to persistent log
        
        Args:
            record: Complete fill processing record
        """
        try:
            # Add to in-memory cache
            self.recent_fills[record.order_id] = record
            
            # Trim cache if too large
            if len(self.recent_fills) > self.max_cache_size:
                # Remove oldest entries
                sorted_fills = sorted(
                    self.recent_fills.items(),
                    key=lambda x: x[1].processed_at
                )
                self.recent_fills = dict(sorted_fills[-self.max_cache_size:])
            
            # Append to log file (JSONL format - one JSON per line)
            with open(self.log_file, 'a') as f:
                json.dump(asdict(record), f)
                f.write('\n')
            
            # Log summary
            status = "✅" if record.success else "❌"
            tp_info = f"TP: {record.tp_order_id}" if record.tp_order_placed else "NO TP"
            grid_info = f"Grid: {record.next_grid_order_id}" if record.next_grid_placed else "NO GRID"
            
            log.info(f"{status} Fill processed: {record.side.upper()} @ ${record.fill_price:,.2f} "
                    f"| {tp_info} | {grid_info} | Method: {record.detection_method}")
        
        except Exception as e:
            log.error(f"❌ Failed to write fill audit log: {e}")
    
    def update_fill_record(self, order_id: str, **updates) -> None:
        """
        Update existing fill record with additional info
        
        This is called AFTER initial processing to add results like:
        - TP order ID after placement
        - Next grid order ID after placement
        
        Args:
            order_id: Order ID to update
            **updates: Fields to update (tp_order_placed, tp_order_id, etc.)
        """
        try:
            record = self.recent_fills.get(str(order_id))
            if not record:
                log.warning(f"⚠️ Cannot update fill record - not found: {order_id}")
                return
            
            # Update fields
            for key, value in updates.items():
                if hasattr(record, key):
                    setattr(record, key, value)
                else:
                    log.warning(f"⚠️ Unknown field in fill record update: {key}")
            
            # Mark as updated
            record.processed_at = time.time()  # Update timestamp
            
            # Re-append to log file (creates updated entry)
            with open(self.log_file, 'a') as f:
                json.dump(asdict(record), f)
                f.write('\n')
            
            log.debug(f"📝 Fill record updated: {order_id} - {updates}")
        
        except Exception as e:
            log.error(f"❌ Failed to update fill record: {e}")
    
    def was_fill_processed(self, order_id: str) -> bool:
        """
        Check if a fill has already been processed
        
        Args:
            order_id: Order ID to check
            
        Returns:
            True if fill was already processed successfully
        """
        record = self.recent_fills.get(str(order_id))
        if not record:
            return False
        
        return record.success
    
    def get_fill_record(self, order_id: str) -> Optional[FillProcessingRecord]:
        """
        Get complete fill processing record
        
        Args:
            order_id: Order ID to look up
            
        Returns:
            Fill processing record or None
        """
        return self.recent_fills.get(str(order_id))
    
    def get_unfinished_fills(self) -> List[FillProcessingRecord]:
        """
        Get fills that were not successfully processed
        
        Returns:
            List of failed/incomplete fill records
        """
        return [
            record for record in self.recent_fills.values()
            if not record.success
        ]
    
    def get_recent_fills(self, limit: int = 20) -> List[FillProcessingRecord]:
        """
        Get most recent fill records
        
        Args:
            limit: Maximum number of records to return
            
        Returns:
            List of recent fill records
        """
        sorted_fills = sorted(
            self.recent_fills.values(),
            key=lambda x: x.processed_at,
            reverse=True
        )
        return sorted_fills[:limit]
    
    def get_stats(self) -> Dict:
        """
        Get audit log statistics
        
        Returns:
            Dict with success/failure counts, methods, etc.
        """
        records = list(self.recent_fills.values())
        
        if not records:
            return {
                'total': 0,
                'success': 0,
                'failed': 0,
                'detection_methods': {}
            }
        
        success_count = sum(1 for r in records if r.success)
        failed_count = len(records) - success_count
        
        # Count by detection method
        methods = {}
        for record in records:
            method = record.detection_method
            methods[method] = methods.get(method, 0) + 1
        
        return {
            'total': len(records),
            'success': success_count,
            'failed': failed_count,
            'success_rate': f"{(success_count / len(records) * 100):.1f}%",
            'detection_methods': methods,
            'cached_records': len(self.recent_fills)
        }
