"""
性能监控模块 - Metrics采集、响应时间追踪、错误率统计
"""
import time
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio
from contextlib import asynccontextmanager

class MetricsCollector:
    def __init__(self):
        self._metrics: Dict[str, List[MetricData]] = defaultdict(list)
        self._counters: Dict[str, int] = defaultdict(int)
        self._gauges: Dict[str, float] = defaultdict(float)
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()

        self._cleanup_interval = 3600
        self._retention_seconds = 86400
        self._start_cleanup_task()

    def _start_cleanup_task(self):
        def cleanup():
            while True:
                time.sleep(self._cleanup_interval)
                self._cleanup_old_metrics()

        cleanup_thread = threading.Thread(target=cleanup, daemon=True)
        cleanup_thread.start()

    def _cleanup_old_metrics(self):
        cutoff = datetime.utcnow() - timedelta(seconds=self._retention_seconds)

        with self._lock:
            for key in list(self._metrics.keys()):
                self._metrics[key] = [
                    m for m in self._metrics[key]
                    if m.timestamp > cutoff
                ]
                if not self._metrics[key]:
                    del self._metrics[key]

    def record_request(self, method: str, path: str, status_code: int, duration: float):
        metric = MetricData(
            metric_type="request",
            method=method,
            path=path,
            status_code=status_code,
            duration=duration,
            timestamp=datetime.utcnow()
        )

        with self._lock:
            self._metrics[f"request:{method}:{path}"].append(metric)
            self._histograms[f"request_duration:{method}:{path}"].append(duration)

            counter_key = f"requests:{method}:{path}:{status_code}"
            self._counters[counter_key] += 1

            if status_code >= 500:
                self._counters["errors:5xx"] += 1
            elif status_code >= 400:
                self._counters["errors:4xx"] += 1

    def record_response_time(self, endpoint: str, duration: float):
        with self._lock:
            self._histograms[f"response_time:{endpoint}"].append(duration)

    def increment_counter(self, name: str, value: int = 1, tags: Optional[Dict[str, str]] = None):
        with self._lock:
            key = self._format_metric_key(name, tags)
            self._counters[key] += value

    def set_gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        with self._lock:
            key = self._format_metric_key(name, tags)
            self._gauges[key] = value

    def _format_metric_key(self, name: str, tags: Optional[Dict[str, str]] = None) -> str:
        if not tags:
            return name
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}[{tag_str}]"

    def get_counter(self, name: str, tags: Optional[Dict[str, str]] = None) -> int:
        key = self._format_metric_key(name, tags)
        return self._counters.get(key, 0)

    def get_gauge(self, name: str, tags: Optional[Dict[str, str]] = None) -> float:
        key = self._format_metric_key(name, tags)
        return self._gauges.get(key, 0.0)

    def get_histogram_stats(self, name: str, tags: Optional[Dict[str, str]] = None) -> Dict[str, float]:
        key = self._format_metric_key(name, tags)
        values = self._histograms.get(key, [])

        if not values:
            return {"count": 0, "min": 0, "max": 0, "avg": 0, "p50": 0, "p90": 0, "p99": 0}

        sorted_values = sorted(values)
        count = len(sorted_values)

        return {
            "count": count,
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "avg": sum(sorted_values) / count,
            "p50": sorted_values[int(count * 0.5)],
            "p90": sorted_values[int(count * 0.9)],
            "p99": sorted_values[int(count * 0.99)] if count >= 100 else sorted_values[-1],
        }

    def get_metrics_summary(self) -> Dict[str, Any]:
        with self._lock:
            summary = {
                "timestamp": datetime.utcnow().isoformat(),
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {}
            }

            for key in self._histograms.keys():
                summary["histograms"][key] = self.get_histogram_stats(key.replace("response_time:", ""))

            return summary

    def get_endpoint_stats(self, method: Optional[str] = None, path: Optional[str] = None) -> List[Dict[str, Any]]:
        stats = []

        with self._lock:
            for key, metrics in self._metrics.items():
                if not key.startswith("request:"):
                    continue

                parts = key.split(":")
                if len(parts) < 3:
                    continue

                m_method, m_path = parts[1], parts[2]

                if method and m_method != method:
                    continue
                if path and not m_path.startswith(path):
                    continue

                durations = [m.duration for m in metrics]
                status_codes = [m.status_code for m in metrics]

                success_count = sum(1 for s in status_codes if 200 <= s < 400)
                error_count = len(status_codes) - success_count

                stats.append({
                    "method": m_method,
                    "path": m_path,
                    "total_requests": len(metrics),
                    "success_count": success_count,
                    "error_count": error_count,
                    "error_rate": error_count / len(metrics) if metrics else 0,
                    "avg_duration": sum(durations) / len(durations) if durations else 0,
                    "min_duration": min(durations) if durations else 0,
                    "max_duration": max(durations) if durations else 0,
                })

        return stats

    def reset_metrics(self):
        with self._lock:
            self._metrics.clear()
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()

metrics_collector = MetricsCollector()

@dataclass
class MetricData:
    metric_type: str
    method: Optional[str] = None
    path: Optional[str] = None
    status_code: Optional[int] = None
    duration: Optional[float] = None
    timestamp: Optional[datetime] = None
    tags: Dict[str, str] = field(default_factory=dict)

class MetricsContext:
    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        duration = self.end_time - self.start_time
        metrics_collector.record_response_time(self.endpoint, duration)

    async def __aenter__(self):
        self.start_time = time.time()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        duration = self.end_time - self.start_time
        metrics_collector.record_response_time(self.endpoint, duration)

@asynccontextmanager
async def metrics_context(endpoint: str):
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        metrics_collector.record_response_time(endpoint, duration)

class PerformanceMonitor:
    @staticmethod
    def track_request(method: str, path: str):
        return RequestTracker(method, path)

    @staticmethod
    async def track_async_request(method: str, path: str):
        return AsyncRequestTracker(method, path)

class RequestTracker:
    def __init__(self, method: str, path: str):
        self.method = method
        self.path = path
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.status_code: Optional[int] = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        duration = self.end_time - self.start_time

        self.status_code = 500 if exc_type else 200

        metrics_collector.record_request(self.method, self.path, self.status_code, duration)

class AsyncRequestTracker:
    def __init__(self, method: str, path: str):
        self.method = method
        self.path = path
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.status_code: Optional[int] = None

    async def __aenter__(self):
        self.start_time = time.time()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        duration = self.end_time - self.start_time

        self.status_code = 500 if exc_type else 200

        metrics_collector.record_request(self.method, self.path, self.status_code, duration)

def get_system_metrics() -> Dict[str, Any]:
    import psutil
    import os

    process = psutil.Process(os.getpid())
    cpu_percent = process.cpu_percent(interval=0.1)
    memory_info = process.memory_info()

    return {
        "system": {
            "cpu_percent": cpu_percent,
            "memory_rss": memory_info.rss,
            "memory_vms": memory_info.vms,
            "memory_percent": process.memory_percent(),
            "num_threads": process.num_threads(),
        },
        "application": metrics_collector.get_metrics_summary()
    }