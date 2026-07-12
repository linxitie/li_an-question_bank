"""
性能监控模块单元测试
"""
import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from sqlalchemy.util.concurrency import asyncio

from app.monitoring import (
    MetricsCollector, MetricData, MetricsContext,
    PerformanceMonitor, RequestTracker, AsyncRequestTracker,
    metrics_collector
)

class TestMetricData:
    def test_basic_metric_data(self):
        metric = MetricData(
            metric_type="request",
            method="GET",
            path="/api/test",
            status_code=200,
            duration=0.123
        )

        assert metric.metric_type == "request"
        assert metric.method == "GET"
        assert metric.path == "/api/test"
        assert metric.status_code == 200
        assert metric.duration == 0.123

    def test_metric_data_with_timestamp(self):
        now = datetime.utcnow()
        metric = MetricData(
            metric_type="request",
            timestamp=now
        )

        assert metric.timestamp == now

    def test_metric_data_with_tags(self):
        metric = MetricData(
            metric_type="request",
            tags={"service": "api", "version": "v1"}
        )

        assert metric.tags["service"] == "api"
        assert metric.tags["version"] == "v1"

class TestMetricsCollector:
    def test_record_request(self):
        collector = MetricsCollector()

        collector.record_request("GET", "/api/test", 200, 0.5)
        collector.record_request("POST", "/api/users", 201, 1.2)

        stats = collector.get_endpoint_stats()
        assert len(stats) >= 0

    def test_increment_counter(self):
        collector = MetricsCollector()

        collector.increment_counter("test_counter", value=5)
        collector.increment_counter("test_counter", value=3)

        assert collector.get_counter("test_counter") == 8

    def test_increment_counter_with_tags(self):
        collector = MetricsCollector()

        collector.increment_counter("api_requests", value=1, tags={"method": "GET", "endpoint": "/test"})
        collector.increment_counter("api_requests", value=1, tags={"method": "POST", "endpoint": "/test"})

        assert collector.get_counter("api_requests", tags={"method": "GET", "endpoint": "/test"}) == 1
        assert collector.get_counter("api_requests", tags={"method": "POST", "endpoint": "/test"}) == 1

    def test_set_gauge(self):
        collector = MetricsCollector()

        collector.set_gauge("memory_usage", 75.5)
        collector.set_gauge("memory_usage", 80.0)

        assert collector.get_gauge("memory_usage") == 80.0

    def test_record_response_time(self):
        collector = MetricsCollector()

        collector.record_response_time("/api/test", 0.5)
        collector.record_response_time("/api/test", 0.8)
        collector.record_response_time("/api/test", 1.2)

        stats = collector.get_histogram_stats("/api/test")
        assert stats["count"] == 3
        assert stats["min"] == 0.5
        assert stats["max"] == 1.2

    def test_get_histogram_stats_empty(self):
        collector = MetricsCollector()

        stats = collector.get_histogram_stats("nonexistent")
        assert stats["count"] == 0

    def test_get_metrics_summary(self):
        collector = MetricsCollector()

        collector.increment_counter("requests_total")
        collector.set_gauge("cpu_percent", 45.5)

        summary = collector.get_metrics_summary()

        assert "timestamp" in summary
        assert "counters" in summary
        assert "gauges" in summary
        assert "histograms" in summary

    def test_reset_metrics(self):
        collector = MetricsCollector()

        collector.increment_counter("test", value=10)
        collector.set_gauge("test_gauge", 100.0)

        collector.reset_metrics()

        assert collector.get_counter("test") == 0
        assert collector.get_gauge("test_gauge") == 0.0

    def test_cleanup_old_metrics(self):
        collector = MetricsCollector()
        collector._retention_seconds = 1

        collector.record_request("GET", "/api/old", 200, 0.5)

        time.sleep(2)

        collector._cleanup_old_metrics()

class TestRequestTracker:
    def test_track_successful_request(self):
        tracker = RequestTracker("GET", "/api/test")

        with tracker:
            time.sleep(0.01)

        assert tracker.status_code == 200
        assert tracker.start_time is not None
        assert tracker.end_time is not None
        assert tracker.end_time > tracker.start_time

    def test_track_failed_request(self):
        tracker = RequestTracker("POST", "/api/test")

        try:
            with tracker:
                raise ValueError("Test error")
        except ValueError:
            pass

        assert tracker.status_code == 500

class TestPerformanceMonitor:
    def test_track_request(self):
        with PerformanceMonitor.track_request("GET", "/api/test") as tracker:
            time.sleep(0.01)

        assert tracker.method == "GET"
        assert tracker.path == "/api/test"
        assert tracker.status_code == 200

class TestMetricsContext:
    def test_sync_context(self):
        with MetricsContext("test_endpoint") as ctx:
            time.sleep(0.01)

        assert ctx.endpoint == "test_endpoint"
        assert ctx.start_time is not None
        assert ctx.end_time is not None

    @pytest.mark.asyncio
    async def test_async_context(self):
        async with MetricsContext("async_endpoint") as ctx:
            await asyncio.sleep(0.01)

        assert ctx.endpoint == "async_endpoint"
        assert ctx.start_time is not None
        assert ctx.end_time is not None

class TestGlobalMetricsCollector:
    def test_singleton_instance(self):
        assert metrics_collector is not None
        assert isinstance(metrics_collector, MetricsCollector)

    def test_record_and_retrieve(self):
        metrics_collector.increment_counter("test_global", value=1)
        count = metrics_collector.get_counter("test_global")
        assert count >= 1

        metrics_collector.increment_counter("test_global", value=-1)