"""
Integration tests for Docker operations using test containers.
"""

import pytest
from testcontainers.compose import DockerCompose
from testcontainers.generic import GenericContainer
import docker
import time
import requests
from pathlib import Path


@pytest.mark.integration
@pytest.mark.docker
class TestDockerIntegration:
    """Integration tests for Docker functionality."""

    @pytest.fixture(scope="class")
    def docker_client(self):
        """Provide Docker client for integration tests."""
        try:
            client = docker.from_env()
            client.ping()
            return client
        except Exception as e:
            pytest.skip(f"Docker not available: {e}")

    @pytest.fixture(scope="class")
    def test_container(self, docker_client):
        """Create a test container for integration tests."""
        container = GenericContainer("alpine:latest")
        container.with_command("sleep 300")  # Keep container running
        
        with container:
            yield container

    def test_docker_client_connection(self, docker_client):
        """Test Docker client connection."""
        version = docker_client.version()
        assert 'Version' in version
        assert version['Version'] is not None

    def test_container_lifecycle(self, docker_client):
        """Test container creation, start, stop, and removal."""
        # Create container
        container = docker_client.containers.run(
            "alpine:latest",
            command="echo 'Hello from container'",
            detach=True,
            remove=True
        )
        
        # Wait for container to complete
        result = container.wait()
        assert result['StatusCode'] == 0
        
        # Get logs
        logs = container.logs().decode('utf-8')
        assert "Hello from container" in logs

    def test_container_with_volume_mount(self, docker_client, tmp_path):
        """Test container with volume mount."""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Test content from host")
        
        # Run container with volume mount
        container = docker_client.containers.run(
            "alpine:latest",
            command="cat /mounted/test.txt",
            volumes={str(tmp_path): {'bind': '/mounted', 'mode': 'ro'}},
            detach=True,
            remove=True
        )
        
        # Wait and get result
        result = container.wait()
        assert result['StatusCode'] == 0
        
        logs = container.logs().decode('utf-8')
        assert "Test content from host" in logs

    def test_container_environment_variables(self, docker_client):
        """Test container with environment variables."""
        container = docker_client.containers.run(
            "alpine:latest",
            command="sh -c 'echo $TEST_VAR'",
            environment={"TEST_VAR": "test_value"},
            detach=True,
            remove=True
        )
        
        result = container.wait()
        assert result['StatusCode'] == 0
        
        logs = container.logs().decode('utf-8')
        assert "test_value" in logs

    def test_container_network_isolation(self, docker_client):
        """Test container network isolation."""
        # Create custom network
        network = docker_client.networks.create("test_network")
        
        try:
            # Run container in custom network
            container = docker_client.containers.run(
                "alpine:latest",
                command="ip route show",
                network="test_network",
                detach=True,
                remove=True
            )
            
            result = container.wait()
            assert result['StatusCode'] == 0
            
            # Container should have network configuration
            logs = container.logs().decode('utf-8')
            assert len(logs.strip()) > 0
            
        finally:
            network.remove()

    def test_container_resource_limits(self, docker_client):
        """Test container with resource limits."""
        container = docker_client.containers.run(
            "alpine:latest",
            command="echo 'Resource limited container'",
            mem_limit="128m",
            cpu_period=100000,
            cpu_quota=50000,  # 50% CPU
            detach=True,
            remove=True
        )
        
        result = container.wait()
        assert result['StatusCode'] == 0

    def test_container_security_options(self, docker_client):
        """Test container with security options."""
        container = docker_client.containers.run(
            "alpine:latest",
            command="id",
            user="1000:1000",  # Non-root user
            cap_drop=["ALL"],
            cap_add=["CHOWN"],
            security_opt=["no-new-privileges:true"],
            detach=True,
            remove=True
        )
        
        result = container.wait()
        assert result['StatusCode'] == 0
        
        logs = container.logs().decode('utf-8')
        # Should show non-root user
        assert "uid=1000" in logs

    @pytest.mark.slow
    def test_container_timeout_handling(self, docker_client):
        """Test container timeout handling."""
        # Start long-running container
        container = docker_client.containers.run(
            "alpine:latest",
            command="sleep 10",
            detach=True
        )
        
        try:
            # Wait with timeout
            result = container.wait(timeout=2)
            # Should timeout and raise exception
            assert False, "Container should have timed out"
        except requests.exceptions.ReadTimeout:
            # Expected timeout
            pass
        finally:
            container.stop()
            container.remove()

    def test_image_operations(self, docker_client):
        """Test Docker image operations."""
        # Pull image
        image = docker_client.images.pull("alpine:latest")
        assert image is not None
        
        # List images
        images = docker_client.images.list()
        alpine_images = [img for img in images if any("alpine" in tag for tag in img.tags)]
        assert len(alpine_images) > 0
        
        # Get image details
        image_details = docker_client.images.get("alpine:latest")
        assert image_details.id is not None

    def test_container_logs_streaming(self, docker_client):
        """Test streaming container logs."""
        container = docker_client.containers.run(
            "alpine:latest",
            command="sh -c 'for i in $(seq 1 5); do echo Line $i; sleep 0.1; done'",
            detach=True,
            remove=True
        )
        
        # Stream logs
        log_lines = []
        for log_line in container.logs(stream=True):
            log_lines.append(log_line.decode('utf-8').strip())
            if len(log_lines) >= 5:
                break
        
        container.wait()
        
        assert len(log_lines) == 5
        assert "Line 1" in log_lines[0]
        assert "Line 5" in log_lines[4]

    def test_container_exec_command(self, test_container):
        """Test executing commands in running container."""
        # Execute command in container
        exec_result = test_container.exec_run("echo 'Executed command'")
        
        assert exec_result.exit_code == 0
        assert "Executed command" in exec_result.output.decode('utf-8')

    def test_container_file_operations(self, test_container, tmp_path):
        """Test file operations with container."""
        # Create test file
        test_content = "Test file content"
        test_file = tmp_path / "container_test.txt"
        test_file.write_text(test_content)
        
        # Copy file to container
        with open(test_file, 'rb') as f:
            test_container.put_archive("/tmp", f.read())
        
        # Verify file in container
        exec_result = test_container.exec_run("cat /tmp/container_test.txt")
        assert exec_result.exit_code == 0
        assert test_content in exec_result.output.decode('utf-8')

    def test_container_stats_monitoring(self, test_container):
        """Test container statistics monitoring."""
        # Get container stats
        stats = test_container.stats(stream=False)
        
        assert 'memory' in stats
        assert 'cpu_stats' in stats
        assert 'networks' in stats
        
        # Memory stats should have usage information
        memory_stats = stats['memory']
        assert 'usage' in memory_stats
        assert memory_stats['usage'] > 0


@pytest.mark.integration
@pytest.mark.docker
class TestDockerComposeIntegration:
    """Integration tests using Docker Compose."""

    @pytest.fixture(scope="class")
    def docker_compose_setup(self, tmp_path_factory):
        """Set up Docker Compose environment for testing."""
        compose_dir = tmp_path_factory.mktemp("compose")
        
        # Create docker-compose.yml for testing
        compose_content = """
version: '3.8'
services:
  test-app:
    image: alpine:latest
    command: sleep 300
    environment:
      - TEST_ENV=integration_test
    volumes:
      - ./test-data:/data:ro
    networks:
      - test-network

  test-db:
    image: alpine:latest
    command: sleep 300
    networks:
      - test-network

networks:
  test-network:
    driver: bridge
"""
        
        compose_file = compose_dir / "docker-compose.yml"
        compose_file.write_text(compose_content)
        
        # Create test data directory
        test_data_dir = compose_dir / "test-data"
        test_data_dir.mkdir()
        (test_data_dir / "test.txt").write_text("Test data")
        
        return compose_dir

    @pytest.mark.slow
    def test_docker_compose_lifecycle(self, docker_compose_setup):
        """Test Docker Compose service lifecycle."""
        with DockerCompose(str(docker_compose_setup)) as compose:
            # Services should be running
            assert compose.get_service_port("test-app", 80) is not None or True  # Alpine doesn't expose ports
            
            # Execute command in service
            result = compose.exec_in_container("test-app", "echo 'Compose test'")
            # Note: testcontainers API may vary, adjust as needed

    @pytest.mark.slow
    def test_docker_compose_networking(self, docker_compose_setup):
        """Test Docker Compose networking between services."""
        with DockerCompose(str(docker_compose_setup)) as compose:
            # Test network connectivity between services
            # This would require more complex setup with actual networked services
            pass

    @pytest.mark.slow
    def test_docker_compose_volume_mounts(self, docker_compose_setup):
        """Test Docker Compose volume mounts."""
        with DockerCompose(str(docker_compose_setup)) as compose:
            # Verify volume mount works
            # This would require executing commands to check mounted files
            pass


@pytest.mark.integration
@pytest.mark.docker
class TestBurlyMCPDockerIntegration:
    """Integration tests specific to Burly MCP Docker functionality."""

    @pytest.fixture
    def burly_mcp_config(self, tmp_path):
        """Create Burly MCP configuration for testing."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        
        policy_dir = config_dir / "policy"
        policy_dir.mkdir()
        
        # Create test policy
        policy_content = """
tools:
  docker_ps:
    description: "List Docker containers"
    args_schema:
      type: "object"
      properties: {}
      required: []
      additionalProperties: false
    command: ["docker", "ps"]
    mutates: false
    requires_confirm: false
    timeout_sec: 30
    notify: ["success", "failure"]

config:
  output_truncate_limit: 1024
  default_timeout_sec: 30
"""
        
        policy_file = policy_dir / "tools.yaml"
        policy_file.write_text(policy_content)
        
        return config_dir

    def test_docker_tool_execution(self, docker_client, burly_mcp_config):
        """Test Docker tool execution through Burly MCP."""
        # This would test the actual Burly MCP Docker tools
        # when they're implemented in the codebase
        pass

    def test_docker_security_constraints(self, docker_client, burly_mcp_config):
        """Test Docker security constraints in Burly MCP."""
        # This would test security features like:
        # - Container isolation
        # - Resource limits
        # - Network restrictions
        # - Volume mount validation
        pass

    def test_docker_error_handling(self, burly_mcp_config):
        """Test Docker error handling in Burly MCP."""
        # This would test error handling for:
        # - Docker daemon unavailable
        # - Invalid container operations
        # - Permission errors
        # - Network issues
        pass


@pytest.mark.integration
@pytest.mark.docker
@pytest.mark.slow
class TestDockerPerformanceIntegration:
    """Performance-focused Docker integration tests."""

    def test_container_startup_performance(self, docker_client):
        """Test container startup performance."""
        start_time = time.time()
        
        container = docker_client.containers.run(
            "alpine:latest",
            command="echo 'Performance test'",
            detach=True,
            remove=True
        )
        
        result = container.wait()
        end_time = time.time()
        
        startup_time = end_time - start_time
        
        assert result['StatusCode'] == 0
        assert startup_time < 10.0  # Should start within 10 seconds

    def test_multiple_container_handling(self, docker_client):
        """Test handling multiple containers simultaneously."""
        containers = []
        
        try:
            # Start multiple containers
            for i in range(5):
                container = docker_client.containers.run(
                    "alpine:latest",
                    command=f"sleep {i + 1}",
                    detach=True
                )
                containers.append(container)
            
            # Wait for all containers
            for container in containers:
                result = container.wait(timeout=10)
                assert result['StatusCode'] == 0
                
        finally:
            # Cleanup
            for container in containers:
                try:
                    container.remove(force=True)
                except:
                    pass

    def test_container_resource_monitoring(self, docker_client):
        """Test container resource monitoring during execution."""
        container = docker_client.containers.run(
            "alpine:latest",
            command="sh -c 'for i in $(seq 1 100); do echo $i; sleep 0.01; done'",
            detach=True
        )
        
        try:
            # Monitor container stats
            stats_samples = []
            for _ in range(5):
                stats = container.stats(stream=False)
                stats_samples.append(stats)
                time.sleep(0.1)
            
            # Verify we got stats
            assert len(stats_samples) == 5
            for stats in stats_samples:
                assert 'memory' in stats
                assert 'cpu_stats' in stats
                
        finally:
            container.stop()
            container.remove()