"""
Recovery Monitor

Health monitoring and metrics aggregation for recovery engines.

Created: November 20, 2025
"""

from typing import Dict
from datetime import datetime


class RecoveryMonitor:
    """Health monitoring for recovery engines"""
    
    def __init__(self, startup_engine, guardian_engine):
        self.startup = startup_engine
        self.guardian = guardian_engine
    
    def get_overall_health(self) -> Dict:
        """Get health status of all engines"""
        return {
            "startup": self.startup.get_health_status(),
            "guardian": self.guardian.get_health_status(),
            "timestamp": datetime.now().isoformat()
        }
    
    def get_metrics_summary(self) -> Dict:
        """Get aggregated metrics"""
        startup_metrics = self.startup.health_metrics
        guardian_metrics = self.guardian.health_metrics
        
        total_sessions = startup_metrics['total_sessions'] + guardian_metrics['total_sessions']
        total_recovered = startup_metrics['total_recovered'] + guardian_metrics['total_recovered']
        total_failed = startup_metrics['total_failed'] + guardian_metrics['total_failed']
        
        overall_success_rate = 0
        if total_recovered + total_failed > 0:
            overall_success_rate = (total_recovered / (total_recovered + total_failed)) * 100
        
        return {
            "total_sessions": total_sessions,
            "total_recovered": total_recovered,
            "total_failed": total_failed,
            "overall_success_rate": f"{overall_success_rate:.1f}%"
        }
    
    def get_recent_sessions(self, limit: int = 10) -> Dict:
        """Get recent recovery sessions from both engines"""
        startup_sessions = list(self.startup.session_history)[-limit:]
        guardian_sessions = list(self.guardian.session_history)[-limit:]
        
        # Combine and sort by timestamp
        all_sessions = startup_sessions + guardian_sessions
        all_sessions.sort(key=lambda s: s.start_time, reverse=True)
        
        return {
            "sessions": [
                {
                    "session_id": s.session_id,
                    "engine": s.engine_name,
                    "start_time": datetime.fromtimestamp(s.start_time).isoformat(),
                    "duration": f"{s.end_time - s.start_time:.2f}s" if s.end_time else "running",
                    "recovered": s.total_recovered,
                    "failed": s.total_failed,
                    "status": s.status.value if hasattr(s.status, 'value') else str(s.status)
                }
                for s in all_sessions[:limit]
            ]
        }
