"""
Unit tests for the Burly MCP resource limits module.
"""

import pytest
from unittest.mock import Mock, patch
import time
import threading


class TestResourceLimiter:
    """Test the resource limiting functionality."""

    def test_resource_limiter_initialization(self):
        """Test resource limiter initialization."""
        from burly_mcp.resource_limits import ResourceLimiter

        limiter = ResourceLimiter()
        assert hasattr(limiter, "max_memory_mb")
        assert hasattr(limiter, "max_cpu_percent")
        assert hasattr(limiter, "max_execution_time_sec")

    def test_resource_limiter_with_custom_limits(self):
        """Test resource limiter with custom limits."""
        from burly_mcp.resource_limits import ResourceLimiter

        limiter = ResourceLimiter(
            max_memory_mb=512, max_cpu_percent=75, max_execution_time_sec=300
        )

        assert limiter.max_memory_mb == 512
        assert limiter.max_cpu_percent == 75
        assert limiter.max_execution_time_sec == 300

    @patch("psutil.Process")
    def test_check_memory_usage_within_limit(self, mock_process_class):
        """Test memory usage check within limits."""
        from burly_mcp.resource_limits import ResourceLimiter

        mock_process = Mock()
        mock_memory_info = Mock()
        mock_memory_info.rss = 100 * 1024 * 1024  # 100 MB in bytes
        mock_process.memory_info.return_value = mock_memory_info
        mock_process_class.return_value = mock_process

        limiter = ResourceLimiter(max_memory_mb=200)

        result = limiter.check_memory_usage(pid=1234)
        assert result is True

    @patch("psutil.Process")
    def test_check_memory_usage_exceeds_limit(self, mock_process_class):
        """Test memory usage check exceeding limits."""
        from burly_mcp.resource_limits import ResourceLimiter

        mock_process = Mock()
        mock_memory_info = Mock()
        mock_memory_info.rss = 300 * 1024 * 1024  # 300 MB in bytes
        mock_process.memory_info.return_value = mock_memory_info
        mock_process_class.return_value = mock_process

        limiter = ResourceLimiter(max_memory_mb=200)

        result = limiter.check_memory_usage(pid=1234)
        assert result is False

    @patch("psutil.Process")
    def test_check_cpu_usage_within_limit(self, mock_process_class):
        """Test CPU usage check within limits."""
        from burly_mcp.resource_limits import ResourceLimiter

        mock_process = Mock()
        mock_process.cpu_percent.return_value = 50.0
        mock_process_class.return_value = mock_process

        limiter = ResourceLimiter(max_cpu_percent=75)

        result = limiter.check_cpu_usage(pid=1234)
        assert result is True

    @patch("psutil.Process")
    def test_check_cpu_usage_exceeds_limit(self, mock_process_class):
        """Test CPU usage check exceeding limits."""
        from burly_mcp.resource_limits import ResourceLimiter

        mock_process = Mock()
        mock_process.cpu_percent.return_value = 90.0
        mock_process_class.return_value = mock_process

        limiter = ResourceLimiter(max_cpu_percent=75)

        result = limiter.check_cpu_usage(pid=1234)
        assert result is False

    def test_check_execution_time_within_limit(self):
        """Test execution time check within limits."""
        from burly_mcp.resource_limits import ResourceLimiter

        limiter = ResourceLimiter(max_execution_time_sec=10)

        start_time = time.time() - 5  # 5 seconds ago
        result = limiter.check_execution_time(start_time)
        assert result is True

    def test_check_execution_time_exceeds_limit(self):
        """Test execution time check exceeding limits."""
        from burly_mcp.resource_limits import ResourceLimiter

        limiter = ResourceLimiter(max_execution_time_sec=10)

        start_time = time.time() - 15  # 15 seconds ago
        result = limiter.check_execution_time(start_time)
        assert result is False

    @patch("psutil.Process")
    def test_monitor_process_within_limits(self, mock_process_class):
        """Test process monitoring within all limits."""
        from burly_mcp.resource_limits import ResourceLimiter

        mock_process = Mock()
        mock_memory_info = Mock()
        mock_memory_info.rss = 100 * 1024 * 1024  # 100 MB
        mock_process.memory_info.return_value = mock_memory_info
        mock_process.cpu_percent.return_value = 50.0
        mock_process_class.return_value = mock_process

        limiter = ResourceLimiter(
            max_memory_mb=200, max_cpu_percent=75, max_execution_time_sec=60
        )

        start_time = time.time()
        result = limiter.monitor_process(pid=1234, start_time=start_time)

        assert result["within_limits"] is True
        assert result["memory_ok"] is True
        assert result["cpu_ok"] is True
        assert result["time_ok"] is True

    @patch("psutil.Process")
    def test_monitor_process_exceeds_memory_limit(self, mock_process_class):
        """Test process monitoring exceeding memory limit."""
        from burly_mcp.resource_limits import ResourceLimiter

        mock_process = Mock()
        mock_memory_info = Mock()
        mock_memory_info.rss = 300 * 1024 * 1024  # 300 MB
        mock_process.memory_info.return_value = mock_memory_info
        mock_process.cpu_percent.return_value = 50.0
        mock_process_class.return_value = mock_process

        limiter = ResourceLimiter(max_memory_mb=200)

        start_time = time.time()
        result = limiter.monitor_process(pid=1234, start_time=start_time)

        assert result["within_limits"] is False
        assert result["memory_ok"] is False

    @patch("psutil.Process")
    def test_terminate_process_exceeding_limits(self, mock_process_class):
        """Test terminating process that exceeds limits."""
        from burly_mcp.resource_limits import ResourceLimiter

        mock_process = Mock()
        mock_process.terminate.return_value = None
        mock_process.wait.return_value = None
        mock_process_class.return_value = mock_process

        limiter = ResourceLimiter()

        result = limiter.terminate_process(pid=1234, reason="Memory limit exceeded")

        assert result is True
        mock_process.terminate.assert_called_once()

    @patch("psutil.Process")
    def test_terminate_process_force_kill(self, mock_process_class):
        """Test force killing process that doesn't terminate gracefully."""
        from burly_mcp.resource_limits import ResourceLimiter

        mock_process = Mock()
        mock_process.terminate.return_value = None
        mock_process.wait.side_effect = TimeoutError("Process didn't terminate")
        mock_process.kill.return_value = None
        mock_process_class.return_value = mock_process

        limiter = ResourceLimiter()

        result = limiter.terminate_process(
            pid=1234, reason="Timeout", force_kill_timeout=1
        )

        assert result is True
        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()

    @patch("psutil.Process")
    def test_get_process_stats(self, mock_process_class):
        """Test getting process statistics."""
        from burly_mcp.resource_limits import ResourceLimiter

        mock_process = Mock()
        mock_memory_info = Mock()
        mock_memory_info.rss = 150 * 1024 * 1024  # 150 MB
        mock_memory_info.vms = 200 * 1024 * 1024  # 200 MB virtual
        mock_process.memory_info.return_value = mock_memory_info
        mock_process.cpu_percent.return_value = 65.5
        mock_process.num_threads.return_value = 4
        mock_process_class.return_value = mock_process

        limiter = ResourceLimiter()

        stats = limiter.get_process_stats(pid=1234)

        assert stats["memory_mb"] == 150
        assert stats["memory_virtual_mb"] == 200
        assert stats["cpu_percent"] == 65.5
        assert stats["num_threads"] == 4

    def test_create_resource_monitor_context(self):
        """Test creating resource monitor context manager."""
        from burly_mcp.resource_limits import ResourceLimiter

        limiter = ResourceLimiter()

        with patch("os.getpid", return_value=1234):
            context = limiter.create_resource_monitor()

            assert hasattr(context, "__enter__")
            assert hasattr(context, "__exit__")

    @patch("psutil.Process")
    def test_resource_monitor_context_manager(self, mock_process_class):
        """Test resource monitor as context manager."""
        from burly_mcp.resource_limits import ResourceLimiter

        mock_process = Mock()
        mock_memory_info = Mock()
        mock_memory_info.rss = 100 * 1024 * 1024
        mock_process.memory_info.return_value = mock_memory_info
        mock_process.cpu_percent.return_value = 50.0
        mock_process_class.return_value = mock_process

        limiter = ResourceLimiter(max_memory_mb=200)

        with patch("os.getpid", return_value=1234):
            with limiter.create_resource_monitor() as monitor:
                # Simulate some work
                time.sleep(0.1)

                # Check that monitoring is active
                assert monitor.is_monitoring is True

    def test_resource_limits_configuration_from_env(self):
        """Test resource limits configuration from environment variables."""
        from burly_mcp.resource_limits import ResourceLimiter

        with patch.dict(
            "os.environ",
            {
                "MAX_MEMORY_MB": "1024",
                "MAX_CPU_PERCENT": "80",
                "MAX_EXECUTION_TIME_SEC": "600",
            },
        ):
            limiter = ResourceLimiter.from_environment()

            assert limiter.max_memory_mb == 1024
            assert limiter.max_cpu_percent == 80
            assert limiter.max_execution_time_sec == 600

    def test_resource_limits_validation(self):
        """Test resource limits validation."""
        from burly_mcp.resource_limits import ResourceLimiter

        # Test valid limits
        limiter = ResourceLimiter(
            max_memory_mb=512, max_cpu_percent=75, max_execution_time_sec=300
        )

        errors = limiter.validate_limits()
        assert len(errors) == 0

    def test_resource_limits_validation_invalid(self):
        """Test resource limits validation with invalid values."""
        from burly_mcp.resource_limits import ResourceLimiter

        # Test invalid limits
        limiter = ResourceLimiter(
            max_memory_mb=-100,  # Negative memory
            max_cpu_percent=150,  # CPU > 100%
            max_execution_time_sec=0,  # Zero execution time
        )

        errors = limiter.validate_limits()
        assert len(errors) > 0
        assert any("memory" in error.lower() for error in errors)
        assert any("cpu" in error.lower() for error in errors)
        assert any("execution time" in error.lower() for error in errors)

    @patch("threading.Thread")
    def test_background_monitoring_thread(self, mock_thread_class):
        """Test background monitoring thread."""
        from burly_mcp.resource_limits import ResourceLimiter

        mock_thread = Mock()
        mock_thread_class.return_value = mock_thread

        limiter = ResourceLimiter()

        limiter.start_background_monitoring(pid=1234, callback=Mock())

        mock_thread_class.assert_called_once()
        mock_thread.start.assert_called_once()

    def test_resource_usage_history(self):
        """Test resource usage history tracking."""
        from burly_mcp.resource_limits import ResourceLimiter

        limiter = ResourceLimiter()

        # Add some usage data points
        limiter.add_usage_data_point(memory_mb=100, cpu_percent=50.0)
        limiter.add_usage_data_point(memory_mb=120, cpu_percent=60.0)
        limiter.add_usage_data_point(memory_mb=110, cpu_percent=55.0)

        history = limiter.get_usage_history()

        assert len(history) == 3
        assert history[0]["memory_mb"] == 100
        assert history[1]["cpu_percent"] == 60.0

    def test_resource_usage_statistics(self):
        """Test resource usage statistics calculation."""
        from burly_mcp.resource_limits import ResourceLimiter

        limiter = ResourceLimiter()

        # Add usage data
        usage_data = [
            {"memory_mb": 100, "cpu_percent": 50.0},
            {"memory_mb": 120, "cpu_percent": 60.0},
            {"memory_mb": 110, "cpu_percent": 55.0},
            {"memory_mb": 130, "cpu_percent": 65.0},
        ]

        for data in usage_data:
            limiter.add_usage_data_point(**data)

        stats = limiter.get_usage_statistics()

        assert stats["memory_avg"] == 115.0  # (100+120+110+130)/4
        assert stats["memory_max"] == 130
        assert stats["memory_min"] == 100
        assert stats["cpu_avg"] == 57.5  # (50+60+55+65)/4
