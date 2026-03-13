"""
Prometheus-compatible metrics for the copy trading engine.

Tracks:
  - Trade propagation time (detect → execute)
  - Distribution fan-out latency
  - Execution success/failure rates
  - Per-symbol, per-strategy latency histograms
  - Active connections, queue depths

Exposes metrics via:
  1. Redis keys (for dashboard / Grafana)
  2. HTTP endpoint (for Prometheus scraping)
"""

from __future__ import annotations
import time
import json
import logging
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import redis

from engine.config import get_engine_settings

settings = get_engine_settings()
logger = logging.getLogger("engine.metrics")


@dataclass
class LatencyBucket:
    """Histogram bucket for latency tracking."""
    count: int = 0
    total_ms: float = 0.0
    min_ms: float = float("inf")
    max_ms: float = 0.0
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    _samples: List[float] = field(default_factory=list)

    def record(self, latency_ms: float):
        self.count += 1
        self.total_ms += latency_ms
        self.min_ms = min(self.min_ms, latency_ms)
        self.max_ms = max(self.max_ms, latency_ms)
        self._samples.append(latency_ms)
        # Keep last 1000 samples for percentile calculation
        if len(self._samples) > 1000:
            self._samples = self._samples[-1000:]

    def compute_percentiles(self):
        if not self._samples:
            return
        s = sorted(self._samples)
        n = len(s)
        self.p50_ms = s[int(n * 0.50)]
        self.p95_ms = s[int(n * 0.95)]
        self.p99_ms = s[min(int(n * 0.99), n - 1)]

    @property
    def avg_ms(self) -> float:
        return self.total_ms / self.count if self.count > 0 else 0.0

    def to_dict(self) -> dict:
        self.compute_percentiles()
        return {
            "count": self.count,
            "avg_ms": round(self.avg_ms, 2),
            "min_ms": round(self.min_ms, 2) if self.min_ms != float("inf") else 0,
            "max_ms": round(self.max_ms, 2),
            "p50_ms": round(self.p50_ms, 2),
            "p95_ms": round(self.p95_ms, 2),
            "p99_ms": round(self.p99_ms, 2),
        }


class EngineMetrics:
    """
    Centralized metrics collector for the copy trading engine.
    Thread-safe — all methods can be called from any thread/process.
    """

    def __init__(self):
        self._lock = threading.Lock()

        # Counters
        self.events_detected: int = 0
        self.events_distributed: int = 0
        self.orders_created: int = 0
        self.orders_executed: int = 0
        self.orders_failed: int = 0
        self.orders_skipped: int = 0
        self.orders_slippage_rejected: int = 0
        self.retries_total: int = 0

        # Latency histograms
        self.latency_detect_to_distribute = LatencyBucket()
        self.latency_distribute_to_execute = LatencyBucket()
        self.latency_total = LatencyBucket()  # detect → execute (the SLA metric)
        self.latency_execution = LatencyBucket()  # mt5 order_send time

        # Per-symbol metrics
        self.per_symbol: Dict[str, LatencyBucket] = defaultdict(LatencyBucket)
        # Per-strategy metrics
        self.per_strategy: Dict[str, LatencyBucket] = defaultdict(LatencyBucket)

        # Gauges
        self.active_listeners: int = 0
        self.active_workers: int = 0
        self.queue_depth: int = 0

        # Slippage tracking
        self.slippage_total_points: float = 0.0
        self.slippage_count: int = 0

        self._start_time = time.time()

    def record_event_detected(self):
        with self._lock:
            self.events_detected += 1

    def record_event_distributed(self, detect_to_dist_ms: float):
        with self._lock:
            self.events_distributed += 1
            self.latency_detect_to_distribute.record(detect_to_dist_ms)

    def record_order_created(self):
        with self._lock:
            self.orders_created += 1

    def record_execution(
        self,
        success: bool,
        total_latency_ms: float,
        execution_latency_ms: float,
        dist_to_exec_ms: float,
        symbol: str = "",
        strategy: str = "",
        slippage_points: float = 0.0,
        slippage_rejected: bool = False,
    ):
        with self._lock:
            if slippage_rejected:
                self.orders_slippage_rejected += 1
            elif success:
                self.orders_executed += 1
                self.latency_total.record(total_latency_ms)
                self.latency_execution.record(execution_latency_ms)
                self.latency_distribute_to_execute.record(dist_to_exec_ms)

                if symbol:
                    self.per_symbol[symbol].record(total_latency_ms)
                if strategy:
                    self.per_strategy[strategy].record(total_latency_ms)

                self.slippage_total_points += abs(slippage_points)
                self.slippage_count += 1
            else:
                self.orders_failed += 1

    def record_retry(self):
        with self._lock:
            self.retries_total += 1

    def record_skip(self):
        with self._lock:
            self.orders_skipped += 1

    def set_gauges(self, listeners: int = None, workers: int = None, queue_depth: int = None):
        with self._lock:
            if listeners is not None:
                self.active_listeners = listeners
            if workers is not None:
                self.active_workers = workers
            if queue_depth is not None:
                self.queue_depth = queue_depth

    def get_success_rate(self) -> float:
        total = self.orders_executed + self.orders_failed
        return (self.orders_executed / total * 100) if total > 0 else 100.0

    def get_avg_slippage(self) -> float:
        return self.slippage_total_points / self.slippage_count if self.slippage_count > 0 else 0.0

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "uptime_s": int(time.time() - self._start_time),
                "counters": {
                    "events_detected": self.events_detected,
                    "events_distributed": self.events_distributed,
                    "orders_created": self.orders_created,
                    "orders_executed": self.orders_executed,
                    "orders_failed": self.orders_failed,
                    "orders_skipped": self.orders_skipped,
                    "orders_slippage_rejected": self.orders_slippage_rejected,
                    "retries_total": self.retries_total,
                    "success_rate_pct": round(self.get_success_rate(), 2),
                },
                "latency": {
                    "total_e2e": self.latency_total.to_dict(),
                    "detect_to_distribute": self.latency_detect_to_distribute.to_dict(),
                    "distribute_to_execute": self.latency_distribute_to_execute.to_dict(),
                    "mt5_execution": self.latency_execution.to_dict(),
                },
                "slippage": {
                    "avg_points": round(self.get_avg_slippage(), 2),
                    "total_count": self.slippage_count,
                },
                "gauges": {
                    "active_listeners": self.active_listeners,
                    "active_workers": self.active_workers,
                    "queue_depth": self.queue_depth,
                },
                "per_symbol": {k: v.to_dict() for k, v in self.per_symbol.items()},
                "per_strategy": {k: v.to_dict() for k, v in self.per_strategy.items()},
            }

    def to_prometheus(self) -> str:
        """Generate Prometheus exposition format."""
        lines = []
        d = self.to_dict()

        # Counters
        for k, v in d["counters"].items():
            lines.append(f"# TYPE copytrade_{k} gauge")
            lines.append(f"copytrade_{k} {v}")

        # Latency gauges
        for bucket_name, bucket in d["latency"].items():
            prefix = f"copytrade_latency_{bucket_name}"
            for metric in ("avg_ms", "p50_ms", "p95_ms", "p99_ms", "min_ms", "max_ms"):
                lines.append(f"# TYPE {prefix}_{metric} gauge")
                lines.append(f"{prefix}_{metric} {bucket.get(metric, 0)}")

        # Slippage
        lines.append(f"# TYPE copytrade_slippage_avg_points gauge")
        lines.append(f"copytrade_slippage_avg_points {d['slippage']['avg_points']}")

        # Gauges
        for k, v in d["gauges"].items():
            lines.append(f"# TYPE copytrade_{k} gauge")
            lines.append(f"copytrade_{k} {v}")

        # Per-symbol latency
        for symbol, bucket in d["per_symbol"].items():
            lines.append(f'copytrade_symbol_latency_avg_ms{{symbol="{symbol}"}} {bucket["avg_ms"]}')
            lines.append(f'copytrade_symbol_latency_p99_ms{{symbol="{symbol}"}} {bucket["p99_ms"]}')

        return "\n".join(lines) + "\n"


class MetricsPublisher(threading.Thread):
    """Periodically publishes metrics to Redis and serves Prometheus endpoint."""

    def __init__(self, metrics: EngineMetrics):
        super().__init__(daemon=True, name="MetricsPublisher")
        self.metrics = metrics
        self.running = False
        self.redis_client = redis.from_url(settings.REDIS_URL)

    def run(self):
        self.running = True
        logger.info(f"Metrics publisher started (interval: {settings.METRICS_PUBLISH_INTERVAL_S}s)")

        # Start Prometheus HTTP server if enabled
        if settings.METRICS_ENABLED:
            self._start_prometheus_server()

        while self.running:
            try:
                snapshot = self.metrics.to_dict()
                self.redis_client.set(
                    "copytrade:metrics:engine",
                    json.dumps(snapshot),
                    ex=settings.METRICS_PUBLISH_INTERVAL_S * 10,
                )
            except Exception as e:
                logger.error(f"Metrics publish error: {e}")

            time.sleep(settings.METRICS_PUBLISH_INTERVAL_S)

    def _start_prometheus_server(self):
        """Start a minimal HTTP server for Prometheus scraping."""
        from http.server import HTTPServer, BaseHTTPRequestHandler
        import threading

        metrics = self.metrics

        class MetricsHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/metrics":
                    body = metrics.to_prometheus().encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain; version=0.0.4")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, *args):
                pass  # Suppress HTTP logs

        try:
            server = HTTPServer(("0.0.0.0", settings.METRICS_PORT), MetricsHandler)
            t = threading.Thread(target=server.serve_forever, daemon=True, name="PrometheusHTTP")
            t.start()
            logger.info(f"Prometheus metrics server on :{settings.METRICS_PORT}/metrics")
        except Exception as e:
            logger.warning(f"Could not start metrics server: {e}")

    def stop(self):
        self.running = False


# Global singleton
_metrics: Optional[EngineMetrics] = None


def get_metrics() -> EngineMetrics:
    global _metrics
    if _metrics is None:
        _metrics = EngineMetrics()
    return _metrics
