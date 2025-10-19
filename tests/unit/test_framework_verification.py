"""
Test to verify the testing framework is working correctly.
"""

import pytest
from unittest.mock import Mock, patch


class TestFrameworkVerification:
    """Test that the testing framework is set up correctly."""

    def test_basic_functionality(self):
        """Test basic test functionality."""
        assert True

    def test_mock_functionality(self):
        """Test that mocking works correctly."""
        mock_obj = Mock()
        mock_obj.test_method.return_value = "mocked_value"
        
        result = mock_obj.test_method()
        assert result == "mocked_value"
        mock_obj.test_method.assert_called_once()

    @patch('os.environ.get')
    def test_patching_functionality(self, mock_env_get):
        """Test that patching works correctly."""
        mock_env_get.return_value = "test_value"
        
        import os
        result = os.environ.get("TEST_VAR")
        
        assert result == "test_value"
        mock_env_get.assert_called_once_with("TEST_VAR")

    def test_fixture_usage(self, tmp_path):
        """Test that pytest fixtures work correctly."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        
        assert test_file.exists()
        assert test_file.read_text() == "test content"

    @pytest.mark.unit
    def test_marker_functionality(self):
        """Test that pytest markers work correctly."""
        # This test should be marked as a unit test
        assert True

    def test_parametrized_test(self, test_input, expected):
        """Test parametrized testing."""
        assert test_input == expected

    # Parametrize the test
    test_parametrized_test = pytest.mark.parametrize(
        "test_input,expected",
        [
            ("hello", "hello"),
            ("world", "world"),
            (123, 123),
        ]
    )(test_parametrized_test)

    def test_exception_handling(self):
        """Test exception handling in tests."""
        with pytest.raises(ValueError, match="test error"):
            raise ValueError("test error")

    def test_skip_functionality(self):
        """Test skipping functionality."""
        pytest.skip("This test is intentionally skipped")

    @pytest.mark.skipif(True, reason="Conditional skip test")
    def test_conditional_skip(self):
        """Test conditional skipping."""
        assert False  # This should not run

    def test_multiple_assertions(self):
        """Test multiple assertions in one test."""
        data = {"key1": "value1", "key2": "value2"}
        
        assert "key1" in data
        assert data["key1"] == "value1"
        assert len(data) == 2
        assert isinstance(data, dict)


class TestAdvancedFrameworkFeatures:
    """Test advanced testing framework features."""

    @pytest.fixture
    def sample_data(self):
        """Provide sample data for testing."""
        return {
            "numbers": [1, 2, 3, 4, 5],
            "strings": ["a", "b", "c"],
            "nested": {"inner": {"value": 42}}
        }

    def test_fixture_usage_advanced(self, sample_data):
        """Test advanced fixture usage."""
        assert len(sample_data["numbers"]) == 5
        assert sample_data["nested"]["inner"]["value"] == 42

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Test setup and teardown functionality."""
        # Setup
        self.test_value = "initialized"
        
        yield
        
        # Teardown
        self.test_value = None

    def test_autouse_fixture(self):
        """Test that autouse fixtures work."""
        assert hasattr(self, 'test_value')
        assert self.test_value == "initialized"

    def test_context_manager_testing(self):
        """Test context manager functionality."""
        class TestContextManager:
            def __enter__(self):
                return "context_value"
            
            def __exit__(self, exc_type, exc_val, exc_tb):
                return False
        
        with TestContextManager() as value:
            assert value == "context_value"

    def test_generator_testing(self):
        """Test generator functionality."""
        def test_generator():
            for i in range(3):
                yield i * 2
        
        results = list(test_generator())
        assert results == [0, 2, 4]

    @pytest.mark.slow
    def test_slow_test_marker(self):
        """Test that slow test markers work."""
        import time
        time.sleep(0.01)  # Minimal sleep to simulate slow test
        assert True