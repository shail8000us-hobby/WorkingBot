import asyncio
import time
from abc import ABC, abstractmethod
from typing import Optional
from loguru import logger as log


class BaseMonitor(ABC):
    
    def __init__(self, name: str):
        self.name = name
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._start_time = 0
        self._loop_count = 0
        self._error_count = 0
        self._last_execution = 0
    
    async def start(self) -> None:
        if self._running:
            log.warning(f"[{self.name}] Already running")
            return
        
        log.info(f"[{self.name}] Starting monitor")
        self._running = True
        self._start_time = time.time()
        self._task = asyncio.create_task(self._run(), name=f"{self.name}_monitor")
    
    async def stop(self) -> None:
        if not self._running:
            log.warning(f"[{self.name}] Not running")
            return
        
        log.info(f"[{self.name}] Stopping monitor")
        self._running = False
        
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        uptime = time.time() - self._start_time
        log.info(f"[{self.name}] Stopped - Uptime: {uptime:.1f}s, Loops: {self._loop_count}, Errors: {self._error_count}")
    
    async def _run(self) -> None:
        log.info(f"[{self.name}] Monitor loop started")
        
        try:
            while self._running:
                try:
                    self._last_execution = time.time()
                    await self._execute()
                    self._loop_count += 1
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self._error_count += 1
                    log.error(f"[{self.name}] Error in monitor loop: {e}")
                    await asyncio.sleep(5)
        
        except asyncio.CancelledError:
            log.info(f"[{self.name}] Monitor loop cancelled")
        finally:
            log.info(f"[{self.name}] Monitor loop ended")
    
    @abstractmethod
    async def _execute(self) -> None:
        pass
    
    def get_health_status(self) -> dict:
        uptime = time.time() - self._start_time if self._start_time > 0 else 0
        time_since_last = time.time() - self._last_execution if self._last_execution > 0 else 0
        
        return {
            "name": self.name,
            "running": self._running,
            "uptime": uptime,
            "loop_count": self._loop_count,
            "error_count": self._error_count,
            "last_execution": self._last_execution,
            "time_since_last": time_since_last,
            "health": "healthy" if self._running and time_since_last < 120 else "unhealthy"
        }
