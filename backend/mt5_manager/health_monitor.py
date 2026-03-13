"""
MT5 Manager Health Monitor — monitors terminal processes, system resources,
and session health. Publishes metrics to Redis for Prometheus/Grafana.

Monitors:
  - Per-terminal: CPU, memory, heartbeat freshness, account count
  - Per-session: connection age, reconnect count, last activity
  - System-wide: total capacity, utilization, error rates
  - Process liveness: detects crashed subprocesses

Redis keys:
  mt5health:system       → aggregated system metrics
  mt5health:terminal:*   → per-terminal metrics
  mt5health:alerts       → active alerts channel
"""

from __future__ import annotations
import logging
import json
import time
import threading
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional
import redis

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from mt5_manager.config import get_manager_settings

settings = get_manager_settings()
logger = logging.getLogger("mt5_manager.health")


class AlertLevel(str):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class HealthMonitor(threading.Thread):
    """
    Periodically collects health metrics from all managed terminals and sessions.
    Publishes alerts when thresholds are exceeded.
    """

    def __init__(self, pool, session_manager, allocator):
        """
        Args:
            pool: TerminalPool instance
            session_manager: SessionManager instance
            allocator: TerminalAllocator instance
        """
        super().__init__(daemon=True, name="HealthMonitor")
        self.pool = pool
        self.session_manager = session_manager
        self.allocator = allocator
        self.running = False
        self.redis_client = redis.from_url(settings.REDIS_URL)
        self._alert_history: List[dict] = []

        # Thresholds
        self.memory_warn_mb = settings.MAX_MEMORY_PER_TERMINAL_MB * 0.8
        self.memory_crit_mb = settings.MAX_MEMORY_PER_TERMINAL_MB
        self.cpu_warn_pct = 80.0
        self.stale_heartbeat_s = settings.HEARTBEAT_STALE_S

    def _collect_process_metrics(self) -> List[dict]:
        """Collect CPU/memory metrics for all terminal subprocesses."""
        metrics = []
        if not HAS_PSUTIL:
            return metrics

        for account_id, terminal in self.pool.terminals.items():
            if not terminal.pid:
                continue

            try:
                proc = psutil.Process(terminal.pid)
                mem_info = proc.memory_info()
                cpu_pct = proc.cpu_percent(interval=0.1)

                metric = {
                    "account_id": account_id,
                    "login": terminal.login,
                    "pid": terminal.pid,
                    "memory_mb": mem_info.rss / (1024 * 1024),
                    "cpu_percent": cpu_pct,
                    "threads": proc.num_threads(),
                    "status": proc.status(),
                    "uptime_s": time.time() - (terminal.started_at or time.time()),
                }
                metrics.append(metric)

                # Check thresholds
                if metric["memory_mb"] > self.memory_crit_mb:
                    self._emit_alert(
                        AlertLevel.CRITICAL,
                        f"Terminal {terminal.login} memory critical: {metric['memory_mb']:.0f}MB",
                        account_id,
                    )
                elif metric["memory_mb"] > self.memory_warn_mb:
                    self._emit_alert(
                        AlertLevel.WARNING,
                        f"Terminal {terminal.login} memory high: {metric['memory_mb']:.0f}MB",
                        account_id,
                    )

                if cpu_pct > self.cpu_warn_pct:
                    self._emit_alert(
                        AlertLevel.WARNING,
                        f"Terminal {terminal.login} CPU high: {cpu_pct:.1f}%",
                        account_id,
                    )

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                metrics.append({
                    "account_id": account_id,
                    "login": terminal.login,
                    "pid": terminal.pid,
                    "status": "dead",
                    "memory_mb": 0,
                    "cpu_percent": 0,
                })

        return metrics

    def _collect_system_metrics(self) -> dict:
        """Collect overall system resource usage."""
        system = {"timestamp": datetime.now(timezone.utc).isoformat()}

        if HAS_PSUTIL:
            system["system_cpu_percent"] = psutil.cpu_percent(interval=0.5)
            mem = psutil.virtual_memory()
            system["system_memory_total_mb"] = mem.total / (1024 * 1024)
            system["system_memory_used_mb"] = mem.used / (1024 * 1024)
            system["system_memory_percent"] = mem.percent
            disk = psutil.disk_usage("/")
            system["disk_usage_percent"] = disk.percent

        pool_status = self.pool.get_pool_status()
        system["terminals_active"] = pool_status["active"]
        system["terminals_total"] = pool_status["total"]
        system["terminals_max"] = pool_status["max"]

        session_summary = self.session_manager.get_session_summary()
        system["sessions_total"] = session_summary["total"]
        system["sessions_active"] = session_summary["active"]
        system["sessions_by_state"] = session_summary["by_state"]
        system["sessions_by_strategy"] = session_summary["by_strategy"]

        alloc_summary = self.allocator.get_allocation_summary()
        system["allocation_utilization"] = alloc_summary["utilization"]

        return system

    def _check_stale_sessions(self):
        """Detect sessions with stale heartbeats."""
        now = datetime.now(timezone.utc)

        for session in self.session_manager.get_active_sessions():
            if not session.last_heartbeat:
                continue

            try:
                last_beat = datetime.fromisoformat(session.last_heartbeat)
                age_s = (now - last_beat).total_seconds()

                if age_s > self.stale_heartbeat_s * 2:
                    self._emit_alert(
                        AlertLevel.CRITICAL,
                        f"Session {session.login} heartbeat stale: {age_s:.0f}s",
                        session.account_id,
                    )
                elif age_s > self.stale_heartbeat_s:
                    self._emit_alert(
                        AlertLevel.WARNING,
                        f"Session {session.login} heartbeat aging: {age_s:.0f}s",
                        session.account_id,
                    )
            except (ValueError, TypeError):
                pass

    def _emit_alert(self, level: str, message: str, account_id: str = ""):
        """Publish an alert to Redis."""
        alert = {
            "level": level,
            "message": message,
            "account_id": account_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._alert_history.append(alert)
        # Keep last 100 alerts
        self._alert_history = self._alert_history[-100:]

        try:
            self.redis_client.publish("mt5health:alerts", json.dumps(alert))
            self.redis_client.lpush("mt5health:alert_log", json.dumps(alert))
            self.redis_client.ltrim("mt5health:alert_log", 0, 499)  # Keep 500
        except Exception:
            pass

        if level == AlertLevel.CRITICAL:
            logger.critical(f"ALERT: {message}")
        elif level == AlertLevel.WARNING:
            logger.warning(f"ALERT: {message}")

    def run(self):
        self.running = True
        logger.info(f"Health Monitor started — interval: {settings.HEALTH_REPORT_INTERVAL_S}s")

        while self.running:
            try:
                # Collect metrics
                process_metrics = self._collect_process_metrics()
                system_metrics = self._collect_system_metrics()

                # Check for stale sessions
                self._check_stale_sessions()

                # Publish to Redis
                self.redis_client.set(
                    "mt5health:system",
                    json.dumps(system_metrics),
                    ex=settings.HEALTH_REPORT_INTERVAL_S * 5,
                )

                for pm in process_metrics:
                    self.redis_client.set(
                        f"mt5health:terminal:{pm['account_id']}",
                        json.dumps(pm),
                        ex=settings.HEALTH_REPORT_INTERVAL_S * 5,
                    )

                # Log summary
                logger.info(
                    f"Health: {system_metrics.get('terminals_active', 0)} terminals, "
                    f"{system_metrics.get('sessions_active', 0)} sessions, "
                    f"CPU: {system_metrics.get('system_cpu_percent', 'N/A')}%, "
                    f"MEM: {system_metrics.get('system_memory_percent', 'N/A')}%"
                )

            except Exception as e:
                logger.error(f"Health monitor error: {e}", exc_info=True)

            time.sleep(settings.HEALTH_REPORT_INTERVAL_S)

    def stop(self):
        self.running = False

    def get_health_report(self) -> dict:
        """Return full health report on demand."""
        return {
            "system": self._collect_system_metrics(),
            "processes": self._collect_process_metrics(),
            "recent_alerts": self._alert_history[-20:],
        }
