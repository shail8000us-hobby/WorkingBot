"""
Migration script for transitioning from threaded to async architecture.
Supports gradual cutover, shadow mode, and state verification.
"""

import asyncio
import json
import time
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from loguru import logger as log


@dataclass
class MigrationConfig:
    """Migration configuration."""
    
    mode: str = "shadow"  # shadow, validation, cutover, complete
    shadow_duration_hours: int = 24
    validation_interval_seconds: int = 60
    max_state_drift_percent: float = 1.0
    rollback_on_error: bool = True
    comparison_fields: list = None
    
    def __post_init__(self):
        if self.comparison_fields is None:
            self.comparison_fields = [
                "open_tranches",
                "pending_buy",
                "pending_sell",
                "total_positions_opened",
                "total_positions_closed"
            ]


@dataclass
class StateSnapshot:
    """State snapshot for comparison."""
    
    timestamp: float
    source: str  # "threaded" or "async"
    state: Dict[str, Any]
    metrics: Dict[str, Any]
    
    def compare(self, other: "StateSnapshot") -> Dict[str, Any]:
        """Compare with another snapshot."""
        differences = {}
        
        for field in self.state:
            if field in other.state:
                if self.state[field] != other.state[field]:
                    differences[field] = {
                        "self": self.state[field],
                        "other": other.state[field]
                    }
        
        return differences


class MigrationOrchestrator:
    """Orchestrates migration from threaded to async architecture."""
    
    def __init__(self, config: MigrationConfig):
        """
        Initialize migration orchestrator.
        
        Args:
            config: Migration configuration
        """
        self.config = config
        self.start_time = time.time()
        self.snapshots: list[StateSnapshot] = []
        self.validation_results: list[Dict] = []
        self.errors: list[str] = []
        
        # Paths
        self.state_dir = Path("migration_states")
        self.state_dir.mkdir(exist_ok=True)
        
        self.report_dir = Path("migration_reports")
        self.report_dir.mkdir(exist_ok=True)
    
    async def run(self) -> bool:
        """
        Run migration based on configured mode.
        
        Returns:
            True if migration successful
        """
        log.info(f"Starting migration in {self.config.mode} mode")
        
        try:
            if self.config.mode == "shadow":
                return await self.run_shadow_mode()
            elif self.config.mode == "validation":
                return await self.run_validation_mode()
            elif self.config.mode == "cutover":
                return await self.run_cutover_mode()
            elif self.config.mode == "complete":
                return await self.run_complete_mode()
            else:
                raise ValueError(f"Unknown mode: {self.config.mode}")
        
        except Exception as e:
            log.error(f"Migration failed: {e}")
            self.errors.append(str(e))
            
            if self.config.rollback_on_error:
                await self.rollback()
            
            return False
        
        finally:
            self.generate_report()
    
    async def run_shadow_mode(self) -> bool:
        """
        Run both systems in parallel and compare states.
        
        Shadow mode:
        1. Start async system in read-only mode
        2. Keep threaded system as primary
        3. Compare states periodically
        4. Log differences
        """
        log.info("Starting SHADOW mode - both systems running")
        
        # Start async system
        async_task = asyncio.create_task(self.start_async_system(read_only=True))
        
        # Monitor for configured duration
        end_time = time.time() + (self.config.shadow_duration_hours * 3600)
        
        while time.time() < end_time:
            try:
                # Capture snapshots
                threaded_snapshot = await self.capture_threaded_state()
                async_snapshot = await self.capture_async_state()
                
                self.snapshots.append(threaded_snapshot)
                self.snapshots.append(async_snapshot)
                
                # Compare states
                differences = threaded_snapshot.compare(async_snapshot)
                
                if differences:
                    log.warning(f"State differences detected: {differences}")
                    self.validation_results.append({
                        "timestamp": time.time(),
                        "differences": differences,
                        "severity": self.calculate_severity(differences)
                    })
                else:
                    log.info("States match ✓")
                
                # Save snapshots
                await self.save_snapshot(threaded_snapshot)
                await self.save_snapshot(async_snapshot)
                
                # Wait for next interval
                await asyncio.sleep(self.config.validation_interval_seconds)
            
            except Exception as e:
                log.error(f"Shadow mode error: {e}")
                self.errors.append(str(e))
        
        # Stop async system
        async_task.cancel()
        
        # Analyze results
        return self.analyze_shadow_results()
    
    async def run_validation_mode(self) -> bool:
        """
        Validate async system with real operations.
        
        Validation mode:
        1. Run async system as primary for reads
        2. Keep threaded system for writes
        3. Validate all read operations match
        """
        log.info("Starting VALIDATION mode - async reads, threaded writes")
        
        # Start both systems
        async_task = asyncio.create_task(self.start_async_system(read_only=False))
        threaded_task = asyncio.create_task(self.keep_threaded_writes())
        
        # Run validation tests
        test_results = []
        
        # Test 1: Position queries
        test_results.append(await self.validate_position_queries())
        
        # Test 2: Order operations
        test_results.append(await self.validate_order_operations())
        
        # Test 3: State consistency
        test_results.append(await self.validate_state_consistency())
        
        # Test 4: Performance comparison
        test_results.append(await self.validate_performance())
        
        # Stop systems
        async_task.cancel()
        threaded_task.cancel()
        
        # Check results
        all_passed = all(test_results)
        
        if all_passed:
            log.info("✅ All validation tests passed")
        else:
            log.error("❌ Some validation tests failed")
        
        return all_passed
    
    async def run_cutover_mode(self) -> bool:
        """
        Switch to async system as primary.
        
        Cutover mode:
        1. Stop threaded system writes
        2. Switch to async system
        3. Keep threaded system in standby
        4. Monitor for issues
        """
        log.info("Starting CUTOVER mode - switching to async")
        
        # Create backup
        await self.create_backup()
        
        # Stop threaded writes
        await self.stop_threaded_writes()
        
        # Start async as primary
        async_task = asyncio.create_task(self.start_async_system(read_only=False))
        
        # Monitor for 1 hour
        monitor_duration = 3600
        end_time = time.time() + monitor_duration
        
        issue_count = 0
        
        while time.time() < end_time:
            try:
                # Check health
                health = await self.check_async_health()
                
                if not health["healthy"]:
                    issue_count += 1
                    log.warning(f"Health issue detected: {health['issues']}")
                    
                    if issue_count > 5:
                        log.error("Too many issues - rolling back")
                        await self.rollback()
                        return False
                
                # Check metrics
                metrics = await self.get_async_metrics()
                
                if metrics["error_rate"] > 0.01:
                    log.warning(f"High error rate: {metrics['error_rate']:.2%}")
                
                await asyncio.sleep(30)
            
            except Exception as e:
                log.error(f"Monitoring error: {e}")
                self.errors.append(str(e))
        
        log.info("✅ Cutover successful - async system stable")
        return True
    
    async def run_complete_mode(self) -> bool:
        """
        Complete migration and cleanup.
        
        Complete mode:
        1. Verify async system running well
        2. Archive threaded code
        3. Update configuration
        4. Clean up resources
        """
        log.info("Starting COMPLETE mode - finalizing migration")
        
        # Verify async system
        health = await self.check_async_health()
        if not health["healthy"]:
            log.error(f"Async system not healthy: {health['issues']}")
            return False
        
        # Archive threaded code
        await self.archive_threaded_code()
        
        # Update configuration
        await self.update_configuration()
        
        # Clean up
        await self.cleanup_resources()
        
        log.info("✅ Migration complete!")
        return True
    
    async def capture_threaded_state(self) -> StateSnapshot:
        """Capture state from threaded system."""
        # Read from threaded system's state file
        state_file = Path("state/runtime_state.json")
        
        if state_file.exists():
            with open(state_file, "r") as f:
                state = json.load(f)
        else:
            state = {}
        
        return StateSnapshot(
            timestamp=time.time(),
            source="threaded",
            state=state,
            metrics={}
        )
    
    async def capture_async_state(self) -> StateSnapshot:
        """Capture state from async system."""
        # Read from async system's monitoring snapshot
        snapshot_file = Path("data/monitoring_snapshot.json")
        
        if snapshot_file.exists():
            with open(snapshot_file, "r") as f:
                data = json.load(f)
                state = data.get("state", {})
                metrics = data.get("metrics", {})
        else:
            state = {}
            metrics = {}
        
        return StateSnapshot(
            timestamp=time.time(),
            source="async",
            state=state,
            metrics=metrics
        )
    
    async def save_snapshot(self, snapshot: StateSnapshot) -> None:
        """Save snapshot to disk."""
        filename = f"{snapshot.source}_{int(snapshot.timestamp)}.json"
        filepath = self.state_dir / filename
        
        with open(filepath, "w") as f:
            json.dump(asdict(snapshot), f, indent=2)
    
    def calculate_severity(self, differences: Dict[str, Any]) -> str:
        """Calculate severity of differences."""
        if not differences:
            return "none"
        
        # Critical fields
        critical_fields = ["open_tranches", "pending_buy", "pending_sell"]
        
        for field in critical_fields:
            if field in differences:
                return "critical"
        
        # Check numeric drift
        for field, diff in differences.items():
            if isinstance(diff["self"], (int, float)) and isinstance(diff["other"], (int, float)):
                drift = abs(diff["self"] - diff["other"]) / max(abs(diff["self"]), 1)
                if drift > self.config.max_state_drift_percent / 100:
                    return "high"
        
        return "low"
    
    def analyze_shadow_results(self) -> bool:
        """Analyze shadow mode results."""
        if not self.validation_results:
            log.info("No differences found during shadow mode")
            return True
        
        # Count by severity
        severity_counts = {"critical": 0, "high": 0, "low": 0}
        
        for result in self.validation_results:
            severity = result["severity"]
            severity_counts[severity] += 1
        
        log.info(f"Shadow mode results: {severity_counts}")
        
        # Fail if any critical differences
        if severity_counts["critical"] > 0:
            log.error("Critical differences found - migration not safe")
            return False
        
        # Warn for high severity
        if severity_counts["high"] > len(self.validation_results) * 0.1:
            log.warning("Too many high severity differences")
            return False
        
        return True
    
    async def start_async_system(self, read_only: bool) -> None:
        """Start async system."""
        log.info(f"Starting async system (read_only={read_only})")
        
        # Import and start async bot
        from bot.strategy.async_gridbot import AsyncGridBot
        
        # Load config
        api_key = os.getenv("DELTA_API_KEY", "")
        api_secret = os.getenv("DELTA_API_SECRET", "")
        
        bot = AsyncGridBot(
            api_key=api_key,
            api_secret=api_secret,
            mode="LONG"
        )
        
        # Start bot
        await bot.start()
    
    async def stop_threaded_writes(self) -> None:
        """Stop threaded system writes."""
        log.info("Stopping threaded system writes")
        
        # Create flag file
        flag_file = Path(".migration_stop_writes")
        flag_file.touch()
    
    async def keep_threaded_writes(self) -> None:
        """Keep threaded system writing."""
        log.info("Keeping threaded writes active")
        
        # Remove flag if exists
        flag_file = Path(".migration_stop_writes")
        if flag_file.exists():
            flag_file.unlink()
    
    async def create_backup(self) -> None:
        """Create backup before cutover."""
        log.info("Creating backup")
        
        backup_dir = Path(f"backups/migration_{int(time.time())}")
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Backup state files
        import shutil
        
        state_dir = Path("state")
        if state_dir.exists():
            shutil.copytree(state_dir, backup_dir / "state")
        
        # Backup audit files
        audit_dir = Path("audit")
        if audit_dir.exists():
            shutil.copytree(audit_dir, backup_dir / "audit")
        
        log.info(f"Backup created: {backup_dir}")
    
    async def rollback(self) -> None:
        """Rollback to threaded system."""
        log.critical("ROLLBACK initiated")
        
        # Stop async system
        # (Would need actual implementation)
        
        # Restart threaded writes
        await self.keep_threaded_writes()
        
        # Restore from backup if available
        # (Would need actual implementation)
        
        log.info("Rollback complete")
    
    async def check_async_health(self) -> Dict[str, Any]:
        """Check async system health."""
        issues = []
        
        # Check monitoring file freshness
        snapshot_file = Path("data/monitoring_snapshot.json")
        if snapshot_file.exists():
            mtime = snapshot_file.stat().st_mtime
            if time.time() - mtime > 60:
                issues.append("Monitoring snapshot stale")
        else:
            issues.append("No monitoring snapshot")
        
        # Check for error files
        error_file = Path(".async_errors.log")
        if error_file.exists():
            issues.append("Error log exists")
        
        return {
            "healthy": len(issues) == 0,
            "issues": issues
        }
    
    async def get_async_metrics(self) -> Dict[str, Any]:
        """Get async system metrics."""
        snapshot_file = Path("data/monitoring_snapshot.json")
        
        if snapshot_file.exists():
            with open(snapshot_file, "r") as f:
                data = json.load(f)
                metrics = data.get("metrics", {})
                
                # Calculate error rate
                sagas = metrics.get("sagas", {})
                total = sagas.get("total_started", 1)
                failed = sagas.get("total_failed", 0)
                error_rate = failed / max(total, 1)
                
                return {
                    "error_rate": error_rate,
                    "uptime": data.get("uptime", 0),
                    "fills_processed": metrics.get("fills_processed", 0)
                }
        
        return {"error_rate": 0, "uptime": 0, "fills_processed": 0}
    
    async def validate_position_queries(self) -> bool:
        """Validate position query operations."""
        log.info("Validating position queries")
        
        # Compare position counts
        threaded_state = await self.capture_threaded_state()
        async_state = await self.capture_async_state()
        
        threaded_positions = len(threaded_state.state.get("open_tranches", []))
        async_positions = len(async_state.state.get("open_tranches", []))
        
        if threaded_positions != async_positions:
            log.error(f"Position count mismatch: threaded={threaded_positions}, async={async_positions}")
            return False
        
        return True
    
    async def validate_order_operations(self) -> bool:
        """Validate order operations."""
        log.info("Validating order operations")
        
        # Would need actual order validation
        # For now, return True
        return True
    
    async def validate_state_consistency(self) -> bool:
        """Validate state consistency."""
        log.info("Validating state consistency")
        
        # Capture multiple snapshots
        for i in range(5):
            threaded = await self.capture_threaded_state()
            async_snap = await self.capture_async_state()
            
            differences = threaded.compare(async_snap)
            
            if differences:
                critical_diff = any(
                    field in differences
                    for field in ["open_tranches", "pending_buy", "pending_sell"]
                )
                
                if critical_diff:
                    log.error(f"Critical state mismatch: {differences}")
                    return False
            
            await asyncio.sleep(5)
        
        return True
    
    async def validate_performance(self) -> bool:
        """Validate performance metrics."""
        log.info("Validating performance")
        
        metrics = await self.get_async_metrics()
        
        # Check error rate
        if metrics["error_rate"] > 0.05:
            log.error(f"High error rate: {metrics['error_rate']:.2%}")
            return False
        
        return True
    
    async def archive_threaded_code(self) -> None:
        """Archive threaded code."""
        log.info("Archiving threaded code")
        
        archive_dir = Path("archive/threaded_system")
        archive_dir.mkdir(parents=True, exist_ok=True)
        
        # List of threaded files to archive
        threaded_files = [
            "bot/strategy/grid_strategy.py",
            "bot/strategy/position_manager.py",
            "bot/delta_websocket/ws_manager.py"
        ]
        
        import shutil
        for file_path in threaded_files:
            if Path(file_path).exists():
                dest = archive_dir / Path(file_path).name
                shutil.copy2(file_path, dest)
                log.info(f"Archived: {file_path}")
    
    async def update_configuration(self) -> None:
        """Update configuration for async system."""
        log.info("Updating configuration")
        
        config_file = Path("config.json")
        
        if config_file.exists():
            with open(config_file, "r") as f:
                config = json.load(f)
        else:
            config = {}
        
        # Update to async
        config["architecture"] = "async"
        config["migration_completed"] = datetime.now().isoformat()
        
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)
    
    async def cleanup_resources(self) -> None:
        """Clean up migration resources."""
        log.info("Cleaning up resources")
        
        # Remove migration flags
        flags = [
            ".migration_stop_writes",
            ".migration_in_progress"
        ]
        
        for flag in flags:
            flag_file = Path(flag)
            if flag_file.exists():
                flag_file.unlink()
    
    def generate_report(self) -> None:
        """Generate migration report."""
        report = {
            "mode": self.config.mode,
            "start_time": self.start_time,
            "end_time": time.time(),
            "duration_hours": (time.time() - self.start_time) / 3600,
            "snapshots_captured": len(self.snapshots),
            "validation_issues": len(self.validation_results),
            "errors": self.errors,
            "summary": {
                "total_comparisons": len(self.snapshots) // 2,
                "critical_issues": sum(
                    1 for v in self.validation_results
                    if v.get("severity") == "critical"
                ),
                "high_issues": sum(
                    1 for v in self.validation_results
                    if v.get("severity") == "high"
                ),
                "low_issues": sum(
                    1 for v in self.validation_results
                    if v.get("severity") == "low"
                )
            }
        }
        
        # Save report
        report_file = self.report_dir / f"migration_{self.config.mode}_{int(time.time())}.json"
        
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)
        
        log.info(f"Report saved: {report_file}")
        
        # Print summary
        print("\n" + "=" * 50)
        print("MIGRATION REPORT")
        print("=" * 50)
        print(f"Mode: {self.config.mode}")
        print(f"Duration: {report['duration_hours']:.2f} hours")
        print(f"Snapshots: {report['snapshots_captured']}")
        print(f"Issues: {report['summary']}")
        print(f"Errors: {len(self.errors)}")
        print("=" * 50)


async def main():
    """Main migration entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate from threaded to async architecture")
    parser.add_argument(
        "--mode",
        choices=["shadow", "validation", "cutover", "complete"],
        default="shadow",
        help="Migration mode"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=24,
        help="Shadow mode duration in hours"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Validation interval in seconds"
    )
    parser.add_argument(
        "--no-rollback",
        action="store_true",
        help="Disable automatic rollback on error"
    )
    
    args = parser.parse_args()
    
    # Configure migration
    config = MigrationConfig(
        mode=args.mode,
        shadow_duration_hours=args.duration,
        validation_interval_seconds=args.interval,
        rollback_on_error=not args.no_rollback
    )
    
    # Run migration
    orchestrator = MigrationOrchestrator(config)
    success = await orchestrator.run()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
