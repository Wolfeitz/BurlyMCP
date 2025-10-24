"""
Integration test configuration and fixtures.
"""

import subprocess
import time

import pytest

import docker


def pytest_configure(config):
    """Configure integration test markers."""
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "docker: mark test as requiring Docker")
    config.addinivalue_line("markers", "mcp: mark test as MCP protocol test")
    config.addinivalue_line("markers", "slow: mark test as slow running")


def pytest_collection_modifyitems(config, items):
    """Automatically mark integration tests."""
    for item in items:
        # Mark all tests in integration directory
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)

        # Mark Docker tests
        if "docker" in str(item.fspath) or "docker" in item.name.lower():
            item.add_marker(pytest.mark.docker)

        # Mark MCP tests
        if "mcp" in str(item.fspath) or "mcp" in item.name.lower():
            item.add_marker(pytest.mark.mcp)


@pytest.fixture(scope="session")
def docker_available():
    """Check if Docker is available for testing."""
    try:
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def docker_client(docker_available):
    """Provide Docker client for integration tests."""
    if not docker_available:
        pytest.skip("Docker not available")

    return docker.from_env()


@pytest.fixture(scope="session")
def burly_mcp_available():
    """Check if Burly MCP server is available for testing."""
    try:
        result = subprocess.run(
            ["python", "-c", "import burly_mcp.server.main"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


@pytest.fixture
def integration_test_config(tmp_path):
    """Create integration test configuration."""
    config_dir = tmp_path / "integration_config"
    config_dir.mkdir()

    policy_dir = config_dir / "policy"
    policy_dir.mkdir()

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()

    # Create basic policy for integration tests
    policy_content = """
tools:
  integration_echo:
    description: "Echo command for integration testing"
    args_schema:
      type: "object"
      properties:
        message:
          type: "string"
          description: "Message to echo"
      required: ["message"]
      additionalProperties: false
    command: ["echo"]
    mutates: false
    requires_confirm: false
    timeout_sec: 10
    notify: ["success"]

  integration_sleep:
    description: "Sleep command for integration testing"
    args_schema:
      type: "object"
      properties:
        seconds:
          type: "integer"
          minimum: 1
          maximum: 5
      required: ["seconds"]
      additionalProperties: false
    command: ["sleep"]
    mutates: false
    requires_confirm: false
    timeout_sec: 10
    notify: ["success", "failure"]

config:
  output_truncate_limit: 1024
  default_timeout_sec: 30
  security:
    enable_path_validation: true
    allowed_paths: ["/tmp", "/var/tmp"]
"""

    policy_file = policy_dir / "tools.yaml"
    policy_file.write_text(policy_content)

    return {"config_dir": config_dir, "policy_file": policy_file, "logs_dir": logs_dir}


@pytest.fixture
def integration_environment(integration_test_config):
    """Set up integration test environment variables."""
    return {
        "BURLY_CONFIG_DIR": str(integration_test_config["config_dir"]),
        "BURLY_LOG_DIR": str(integration_test_config["logs_dir"]),
        "NOTIFICATIONS_ENABLED": "false",
        "AUDIT_ENABLED": "true",
        "PYTHONPATH": "src",
    }


@pytest.fixture
def clean_docker_environment(docker_client):
    """Ensure clean Docker environment for testing."""
    if not docker_client:
        yield
        return

    # Store initial state
    initial_containers = docker_client.containers.list(all=True)
    initial_images = docker_client.images.list()

    yield

    # Cleanup after test
    try:
        # Remove test containers
        current_containers = docker_client.containers.list(all=True)
        for container in current_containers:
            if container not in initial_containers:
                try:
                    container.stop()
                    container.remove()
                except:
                    pass

        # Remove test images (be careful not to remove system images)
        current_images = docker_client.images.list()
        for image in current_images:
            if image not in initial_images and any("test" in tag for tag in image.tags):
                try:
                    docker_client.images.remove(image.id, force=True)
                except:
                    pass
    except:
        pass  # Best effort cleanup


@pytest.fixture
def test_container_config():
    """Configuration for test containers."""
    return {
        "image": "alpine:latest",
        "command": "sleep 300",
        "environment": {"TEST_ENV": "integration_test"},
        "labels": {"test.type": "integration", "test.framework": "pytest"},
    }


@pytest.fixture
def mock_external_services():
    """Mock external services for integration testing."""
    # This could set up mock HTTP servers, databases, etc.
    # For now, return empty dict
    return {}


@pytest.fixture(autouse=True)
def integration_test_isolation(tmp_path, monkeypatch):
    """Ensure integration tests are isolated."""
    # Set temporary directory for any file operations
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    monkeypatch.setenv("TEMP", str(tmp_path))

    # Ensure tests don't interfere with real configuration
    monkeypatch.setenv("BURLY_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("BURLY_LOG_DIR", str(tmp_path / "logs"))


def pytest_runtest_setup(item):
    """Setup for individual integration tests."""
    # Skip Docker tests if Docker is not available
    if item.get_closest_marker("docker"):
        try:
            docker.from_env().ping()
        except Exception:
            pytest.skip("Docker not available")

    # Skip MCP tests if Burly MCP is not available
    if item.get_closest_marker("mcp"):
        try:
            subprocess.run(
                ["python", "-c", "import burly_mcp.server.main"],
                capture_output=True,
                timeout=5,
                check=True,
            )
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            FileNotFoundError,
        ):
            pytest.skip("Burly MCP server not available")


def pytest_runtest_teardown(item):
    """Teardown for individual integration tests."""
    # Cleanup any remaining processes
    try:
        # Kill any remaining test processes
        subprocess.run(["pkill", "-f", "burly_mcp"], capture_output=True)
    except:
        pass  # Best effort cleanup


@pytest.fixture
def performance_monitor():
    """Monitor performance during integration tests."""
    import psutil

    start_time = time.time()
    start_memory = psutil.virtual_memory().used
    start_cpu = psutil.cpu_percent()

    yield

    end_time = time.time()
    end_memory = psutil.virtual_memory().used
    end_cpu = psutil.cpu_percent()

    # Log performance metrics
    duration = end_time - start_time
    memory_delta = end_memory - start_memory
    cpu_delta = end_cpu - start_cpu

    print("\nPerformance metrics:")
    print(f"  Duration: {duration:.2f}s")
    print(f"  Memory delta: {memory_delta / 1024 / 1024:.2f}MB")
    print(f"  CPU delta: {cpu_delta:.2f}%")


@pytest.fixture
def test_timeout():
    """Provide timeout configuration for integration tests."""
    return {
        "short": 10,  # 10 seconds for quick operations
        "medium": 30,  # 30 seconds for normal operations
        "long": 120,  # 2 minutes for slow operations
        "very_long": 300,  # 5 minutes for very slow operations
    }
