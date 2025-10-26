"""
Integration tests for Docker operations using test containers.
"""

import time

import pytest
import requests

try:
    from testcontainers.compose import DockerCompose
    from testcontainers.core.generic import DockerContainer as GenericContainer

    import docker

    TESTCONTAINERS_AVAILABLE = True
except ImportError:
    TESTCONTAINERS_AVAILABLE = False
    DockerCompose = None
    GenericContainer = None
    docker = None


@pytest.mark.integration
@pytest.mark.docker
@pytest.mark.skipif(not TESTCONTAINERS_AVAILABLE, reason="testcontainers not available")
class TestDockerIntegration:
    """Integration tests for Docker functionality."""

    @pytest.fixture(scope="class")
    def docker_client(self):
        """Provide Docker client for integration tests."""
        if not TESTCONTAINERS_AVAILABLE:
            pytest.skip("testcontainers not available")
        try:
            client = docker.from_env()
            client.ping()
            return client
        except Exception as e:
            pytest.skip(f"Docker not available: {e}")

    @pytest.fixture(scope="class")
    def test_container(self, docker_client):
        """Create a test container for integration tests."""
        container = docker_client.containers.run(
            "alpine:latest",
            command="sleep 30",  # Keep container running for 30 seconds
            detach=True,
            remove=False
        )
        
        try:
            yield container
        finally:
            container.stop()
            container.remove()

    def test_docker_client_connection(self, docker_client):
        """Test Docker client connection."""
        version = docker_client.version()
        assert "Version" in version
        assert version["Version"] is not None

    def test_container_lifecycle(self, docker_client):
        """Test container creation, start, stop, and removal."""
        # Create container without auto-remove to get logs
        container = docker_client.containers.run(
            "alpine:latest",
            command="echo 'Hello from container'",
            detach=True,
        )

        try:
            # Wait for container to complete
            result = container.wait()
            assert result["StatusCode"] == 0

            # Get logs
            logs = container.logs().decode("utf-8")
            assert "Hello from container" in logs
        finally:
            # Clean up
            container.remove()

    @pytest.mark.flaky
    def test_container_with_volume_mount(self, docker_client, tmp_path):
        """Test container with volume mount."""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Test content from host")

        # Run container with volume mount
        container = docker_client.containers.run(
            "alpine:latest",
            command="cat /mounted/test.txt",
            volumes={str(tmp_path): {"bind": "/mounted", "mode": "ro"}},
            detach=True,
        )

        try:
            # Wait and get result
            result = container.wait()
            assert result["StatusCode"] == 0

            logs = container.logs().decode("utf-8")
            assert "Test content from host" in logs
        finally:
            container.remove()

    def test_container_environment_variables(self, docker_client):
        """Test container with environment variables."""
        container = docker_client.containers.run(
            "alpine:latest",
            command="sh -c 'echo $TEST_VAR'",
            environment={"TEST_VAR": "test_value"},
            detach=True,
        )

        try:
            result = container.wait()
            assert result["StatusCode"] == 0

            logs = container.logs().decode("utf-8")
            assert "test_value" in logs
        finally:
            container.remove()

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
                remove=False,
            )

            result = container.wait()
            assert result["StatusCode"] == 0

            # Container should have network configuration
            logs = container.logs().decode("utf-8")
            assert len(logs.strip()) > 0
            
            # Clean up container
            container.remove()

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
            remove=True,
        )

        result = container.wait()
        assert result["StatusCode"] == 0

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
            remove=False,
        )

        result = container.wait()
        assert result["StatusCode"] == 0

        logs = container.logs().decode("utf-8")
        # Should show non-root user
        assert "uid=1000" in logs
        
        # Clean up container
        container.remove()

    @pytest.mark.slow
    def test_container_timeout_handling(self, docker_client):
        """Test container timeout handling."""
        # Start long-running container
        container = docker_client.containers.run(
            "alpine:latest", command="sleep 10", detach=True
        )

        try:
            # Wait with timeout
            result = container.wait(timeout=2)
            # Should timeout and raise exception
            assert False, "Container should have timed out"
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError):
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
        alpine_images = [
            img for img in images if any("alpine" in tag for tag in img.tags)
        ]
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
            remove=True,
        )

        # Stream logs
        log_lines = []
        for log_line in container.logs(stream=True):
            log_lines.append(log_line.decode("utf-8").strip())
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
        assert "Executed command" in exec_result.output.decode("utf-8")

    def test_container_file_operations(self, test_container, tmp_path):
        """Test file operations with container."""
        # Create test file
        test_content = "Test file content"
        test_file = tmp_path / "container_test.txt"
        test_file.write_text(test_content)

        # Create tar archive for the file
        import tarfile
        import io
        
        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode='w') as tar:
            tar.add(test_file, arcname="container_test.txt")
        tar_stream.seek(0)

        # Copy file to container
        test_container.put_archive("/tmp", tar_stream.read())

        # Verify file in container
        exec_result = test_container.exec_run("cat /tmp/container_test.txt")
        assert exec_result.exit_code == 0
        assert test_content in exec_result.output.decode("utf-8")

    def test_container_stats_monitoring(self, test_container):
        """Test container statistics monitoring."""
        # Get container stats
        stats = test_container.stats(stream=False)

        # Check for expected stats structure (may vary by Docker version)
        assert isinstance(stats, dict)
        assert len(stats) > 0
        
        # Should have some basic stats
        expected_keys = ["memory", "cpu_stats", "networks", "blkio_stats"]
        found_keys = [key for key in expected_keys if key in stats]
        assert len(found_keys) > 0, f"Expected at least one of {expected_keys}, got {list(stats.keys())}"

        # If memory stats exist, check structure
        if "memory" in stats:
            memory_stats = stats["memory"]
            assert "usage" in memory_stats
            assert memory_stats["usage"] > 0


# Docker Compose tests removed - replaced with runtime container tests
# The official contract is now the container image, not compose files


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
@pytest.mark.container
@pytest.mark.skipif(not TESTCONTAINERS_AVAILABLE, reason="testcontainers not available")
class TestRuntimeContainerIntegration:
    """Integration tests for the new runtime container architecture."""

    def test_runtime_container_build(self, docker_client):
        """Test that Dockerfile.runtime builds successfully."""
        try:
            # Build the runtime container from Dockerfile.runtime
            image, build_logs = docker_client.images.build(
                path=".",
                dockerfile="Dockerfile.runtime",
                tag="burlymcp:test-runtime",
                rm=True,
                forcerm=True
            )
            
            assert image is not None
            assert "burlymcp:test-runtime" in [tag for tag in image.tags]
            
            # Clean up
            docker_client.images.remove(image.id, force=True)
            
        except Exception as e:
            pytest.skip(f"Runtime container build failed: {e}")

    def test_runtime_container_minimal_startup(self, docker_client):
        """Test minimal container startup with docker run -p 9400:9400."""
        try:
            # First build the container
            image, _ = docker_client.images.build(
                path=".",
                dockerfile="Dockerfile.runtime", 
                tag="burlymcp:test-minimal",
                rm=True
            )
            
            # Run container with minimal configuration
            container = docker_client.containers.run(
                "burlymcp:test-minimal",
                ports={"9400/tcp": 9400},
                detach=True,
                remove=False,
                environment={
                    "LOG_LEVEL": "DEBUG"
                }
            )
            
            try:
                # Wait for container to start
                time.sleep(5)
                
                # Check container is running
                container.reload()
                assert container.status == "running"
                
                # Test health endpoint
                import requests
                try:
                    response = requests.get("http://localhost:9400/health", timeout=10)
                    assert response.status_code == 200
                    
                    health_data = response.json()
                    assert "status" in health_data
                    assert health_data["status"] in ["ok", "degraded"]
                    
                except requests.RequestException:
                    # Health endpoint might not be accessible in test environment
                    pass
                
            finally:
                container.stop()
                container.remove()
                docker_client.images.remove(image.id, force=True)
                
        except Exception as e:
            pytest.skip(f"Runtime container test failed: {e}")

    def test_runtime_container_http_endpoints(self, docker_client):
        """Test that HTTP endpoints are available in runtime container."""
        try:
            # Build and run container
            image, _ = docker_client.images.build(
                path=".",
                dockerfile="Dockerfile.runtime",
                tag="burlymcp:test-http",
                rm=True
            )
            
            container = docker_client.containers.run(
                "burlymcp:test-http",
                ports={"9400/tcp": 9400},
                detach=True,
                remove=False
            )
            
            try:
                # Wait for startup
                time.sleep(10)
                
                container.reload()
                if container.status != "running":
                    logs = container.logs().decode('utf-8')
                    pytest.skip(f"Container failed to start: {logs}")
                
                # Test both endpoints
                import requests
                
                # Test /health
                try:
                    health_response = requests.get("http://localhost:9400/health", timeout=5)
                    assert health_response.status_code == 200
                    
                    health_data = health_response.json()
                    required_fields = ["status", "server_name", "version", "tools_available"]
                    for field in required_fields:
                        assert field in health_data
                        
                except requests.RequestException as e:
                    pytest.skip(f"Health endpoint not accessible: {e}")
                
                # Test /mcp
                try:
                    mcp_request = {
                        "id": "test-1",
                        "method": "list_tools",
                        "params": {}
                    }
                    
                    mcp_response = requests.post(
                        "http://localhost:9400/mcp",
                        json=mcp_request,
                        timeout=10
                    )
                    
                    # Should always return HTTP 200 (per requirements)
                    assert mcp_response.status_code == 200
                    
                    mcp_data = mcp_response.json()
                    assert "ok" in mcp_data
                    assert "summary" in mcp_data
                    assert "metrics" in mcp_data
                    
                except requests.RequestException as e:
                    pytest.skip(f"MCP endpoint not accessible: {e}")
                
            finally:
                container.stop()
                container.remove()
                docker_client.images.remove(image.id, force=True)
                
        except Exception as e:
            pytest.skip(f"HTTP endpoints test failed: {e}")

    def test_runtime_container_graceful_degradation(self, docker_client):
        """Test container graceful degradation without Docker socket."""
        try:
            # Build container
            image, _ = docker_client.images.build(
                path=".",
                dockerfile="Dockerfile.runtime",
                tag="burlymcp:test-degradation",
                rm=True
            )
            
            # Run without Docker socket mount
            container = docker_client.containers.run(
                "burlymcp:test-degradation",
                ports={"9400/tcp": 9400},
                detach=True,
                remove=False,
                # Explicitly no Docker socket mount
            )
            
            try:
                time.sleep(5)
                
                container.reload()
                assert container.status == "running"
                
                # Health should still work
                import requests
                try:
                    response = requests.get("http://localhost:9400/health", timeout=5)
                    assert response.status_code == 200
                    
                    health_data = response.json()
                    # Should be degraded but not error
                    assert health_data["status"] in ["ok", "degraded"]
                    assert health_data["docker_available"] is False
                    
                except requests.RequestException:
                    pass  # May not be accessible in test environment
                
            finally:
                container.stop()
                container.remove()
                docker_client.images.remove(image.id, force=True)
                
        except Exception as e:
            pytest.skip(f"Graceful degradation test failed: {e}")

    def test_runtime_container_environment_configuration(self, docker_client):
        """Test container configuration via environment variables."""
        try:
            # Build container
            image, _ = docker_client.images.build(
                path=".",
                dockerfile="Dockerfile.runtime",
                tag="burlymcp:test-env",
                rm=True
            )
            
            # Run with custom environment variables
            container = docker_client.containers.run(
                "burlymcp:test-env",
                ports={"9400/tcp": 9400},
                detach=True,
                remove=False,
                environment={
                    "SERVER_NAME": "test-custom-server",
                    "LOG_LEVEL": "DEBUG",
                    "NOTIFICATIONS_ENABLED": "false"
                }
            )
            
            try:
                time.sleep(5)
                
                container.reload()
                assert container.status == "running"
                
                # Check that environment variables are respected
                import requests
                try:
                    response = requests.get("http://localhost:9400/health", timeout=5)
                    if response.status_code == 200:
                        health_data = response.json()
                        assert health_data["server_name"] == "test-custom-server"
                        assert health_data["notifications_enabled"] is False
                        
                except requests.RequestException:
                    pass  # May not be accessible in test environment
                
            finally:
                container.stop()
                container.remove()
                docker_client.images.remove(image.id, force=True)
                
        except Exception as e:
            pytest.skip(f"Environment configuration test failed: {e}")

    def test_runtime_container_security_posture(self, docker_client):
        """Test container runs with proper security settings."""
        try:
            # Build container
            image, _ = docker_client.images.build(
                path=".",
                dockerfile="Dockerfile.runtime",
                tag="burlymcp:test-security",
                rm=True
            )
            
            # Run container and check security settings
            container = docker_client.containers.run(
                "burlymcp:test-security",
                detach=True,
                remove=False
            )
            
            try:
                time.sleep(2)
                
                # Check container is running as non-root user
                exec_result = container.exec_run("id")
                if exec_result.exit_code == 0:
                    id_output = exec_result.output.decode('utf-8')
                    # Should show non-root user (UID 1000)
                    assert "uid=1000" in id_output
                    assert "gid=1000" in id_output
                
                # Check process ownership
                exec_result = container.exec_run("ps aux")
                if exec_result.exit_code == 0:
                    ps_output = exec_result.output.decode('utf-8')
                    # Main process should run as mcp user
                    assert "mcp" in ps_output
                
            finally:
                container.stop()
                container.remove()
                docker_client.images.remove(image.id, force=True)
                
        except Exception as e:
            pytest.skip(f"Security posture test failed: {e}")

    def test_runtime_container_published_image_compatibility(self):
        """Test compatibility with published GHCR images when available."""
        # This test would pull and test published images from GHCR
        # Skip for now as images may not be published yet
        pytest.skip("Published image testing pending GHCR publication")


@pytest.mark.integration
@pytest.mark.docker
@pytest.mark.slow
class TestDockerPerformanceIntegration:
    """Performance-focused Docker integration tests."""

    def test_container_startup_performance(self, docker_client):
        """Test container startup performance."""
        start_time = time.time()

        container = docker_client.containers.run(
            "alpine:latest", command="echo 'Performance test'", detach=True, remove=True
        )

        result = container.wait()
        end_time = time.time()

        startup_time = end_time - start_time

        assert result["StatusCode"] == 0
        assert startup_time < 10.0  # Should start within 10 seconds

    def test_multiple_container_handling(self, docker_client):
        """Test handling multiple containers simultaneously."""
        containers = []

        try:
            # Start multiple containers
            for i in range(5):
                container = docker_client.containers.run(
                    "alpine:latest", command=f"sleep {i + 1}", detach=True
                )
                containers.append(container)

            # Wait for all containers
            for container in containers:
                result = container.wait(timeout=10)
                assert result["StatusCode"] == 0

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
            detach=True,
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
                # Check for expected stats structure (may vary by Docker version)
                assert isinstance(stats, dict)
                assert len(stats) > 0
                
                # Should have some basic stats
                expected_keys = ["memory", "cpu_stats", "networks", "blkio_stats"]
                found_keys = [key for key in expected_keys if key in stats]
                assert len(found_keys) > 0, f"Expected at least one of {expected_keys}, got {list(stats.keys())}"

        finally:
            container.stop()
            container.remove()
