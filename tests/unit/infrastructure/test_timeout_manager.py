"""Tests for timeout management system."""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
import time

from src.llm_judge.infrastructure.resilience.timeout_manager import TimeoutManager, ProviderTimeoutManager, TimeoutConfig, TimeoutResult, TimeoutType
from src.llm_judge.infrastructure.config.config import LLMConfig


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    config = object.__new__(LLMConfig)
    config.openai_request_timeout = 30
    config.anthropic_request_timeout = 25
    config.openai_connect_timeout = 10
    config.anthropic_connect_timeout = 8
    config.request_timeout = 20
    return config


@pytest.fixture
def timeout_manager():
    """Create a timeout manager for testing."""
    return TimeoutManager("test_provider")


@pytest.fixture
def openai_timeout_manager(mock_config):
    """Create an OpenAI timeout manager for testing."""
    return ProviderTimeoutManager("openai", mock_config)


@pytest.fixture
def anthropic_timeout_manager(mock_config):
    """Create an Anthropic timeout manager for testing."""
    return ProviderTimeoutManager("anthropic", mock_config)


class TestTimeoutConfig:
    """Test timeout configuration."""
    
    def test_timeout_config_creation(self):
        """Test creating timeout configuration."""
        config = TimeoutConfig(
            request_timeout=30.0,
            connect_timeout=10.0,
            read_timeout=20.0
        )
        
        assert config.request_timeout == 30.0
        assert config.connect_timeout == 10.0
        assert config.read_timeout == 20.0
        assert config.cancellation_grace_period == 2.0
    
    def test_timeout_config_defaults(self):
        """Test timeout configuration with defaults."""
        config = TimeoutConfig(
            request_timeout=30.0,
            connect_timeout=10.0
        )
        
        assert config.read_timeout is None
        assert config.cancellation_grace_period == 2.0


class TestTimeoutManager:
    """Test core timeout manager functionality."""
    
    @pytest.mark.asyncio
    async def test_successful_operation(self, timeout_manager):
        """Test successful operation execution."""
        async def mock_operation():
            await asyncio.sleep(0.1)
            return "success"
        
        config = TimeoutConfig(request_timeout=5.0, connect_timeout=2.0)
        result = await timeout_manager.execute_with_timeout(
            mock_operation,
            config,
            "test_operation"
        )
        
        assert result.success is True
        assert result.result == "success"
        assert result.error is None
        assert result.timeout_type is None
        assert 0.1 <= result.duration <= 0.2
        assert result.was_cancelled is False
    
    @pytest.mark.asyncio
    async def test_timeout_operation(self, timeout_manager):
        """Test operation that times out."""
        async def slow_operation():
            await asyncio.sleep(2.0)  # This will timeout
            return "should not reach here"
        
        config = TimeoutConfig(request_timeout=0.5, connect_timeout=2.0)
        result = await timeout_manager.execute_with_timeout(
            slow_operation,
            config,
            "slow_operation"
        )
        
        assert result.success is False
        assert result.result is None
        assert isinstance(result.error, TimeoutError)
        assert result.timeout_type == TimeoutType.REQUEST
        assert 0.5 <= result.duration <= 1.0
        assert result.was_cancelled is True
    
    @pytest.mark.asyncio
    async def test_operation_exception(self, timeout_manager):
        """Test operation that raises an exception."""
        async def failing_operation():
            raise ValueError("test error")
        
        config = TimeoutConfig(request_timeout=5.0, connect_timeout=2.0)
        result = await timeout_manager.execute_with_timeout(
            failing_operation,
            config,
            "failing_operation"
        )
        
        assert result.success is False
        assert result.result is None
        assert isinstance(result.error, ValueError)
        assert str(result.error) == "test error"
        assert result.timeout_type is None
        assert result.was_cancelled is False
    
    @pytest.mark.asyncio
    async def test_sync_operation(self, timeout_manager):
        """Test synchronous operation execution."""
        def sync_operation():
            time.sleep(0.1)
            return "sync_success"
        
        config = TimeoutConfig(request_timeout=5.0, connect_timeout=2.0)
        result = await timeout_manager.execute_with_timeout(
            sync_operation,
            config,
            "sync_operation"
        )
        
        assert result.success is True
        assert result.result == "sync_success"
        assert result.error is None
    
    @pytest.mark.asyncio
    async def test_cancel_all_operations(self, timeout_manager):
        """Test cancelling all active operations."""
        async def long_running_operation():
            await asyncio.sleep(10.0)
            return "finished"
        
        config = TimeoutConfig(request_timeout=20.0, connect_timeout=2.0)
        
        # Start multiple operations
        tasks = [
            asyncio.create_task(
                timeout_manager.execute_with_timeout(
                    long_running_operation,
                    config,
                    f"operation_{i}"
                )
            )
            for i in range(3)
        ]
        
        # Give operations time to start
        await asyncio.sleep(0.1)
        
        # Cancel all operations
        cancellation_results = await timeout_manager.cancel_all_operations()
        
        # Wait for tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check that operations were cancelled
        assert len(cancellation_results) > 0
        for result in results:
            # Results might be CancelledError exceptions or TimeoutResult objects
            if isinstance(result, asyncio.CancelledError):
                # Operation was cancelled successfully
                continue
            elif hasattr(result, 'success'):
                assert not result.success
            else:
                # Should be some kind of exception
                assert isinstance(result, Exception)
    
    @pytest.mark.asyncio
    async def test_health_check(self, timeout_manager):
        """Test timeout manager health check."""
        health = await timeout_manager.health_check()
        
        assert health["provider"] == "test_provider"
        assert health["active_operations"] == 0
        assert health["operation_counter"] == 0
        assert health["status"] == "healthy"
    
    def test_get_active_operations_empty(self, timeout_manager):
        """Test getting active operations when none are running."""
        active_ops = timeout_manager.get_active_operations()
        assert active_ops == {}


class TestProviderTimeoutManager:
    """Test provider-specific timeout manager."""
    
    def test_openai_timeout_config(self, openai_timeout_manager):
        """Test OpenAI timeout configuration."""
        config = openai_timeout_manager.timeout_config
        assert config.request_timeout == 30
        assert config.connect_timeout == 10
    
    def test_anthropic_timeout_config(self, anthropic_timeout_manager):
        """Test Anthropic timeout configuration."""
        config = anthropic_timeout_manager.timeout_config
        assert config.request_timeout == 25
        assert config.connect_timeout == 8
    
    def test_unknown_provider_timeout_config(self, mock_config):
        """Test unknown provider falls back to general config."""
        manager = ProviderTimeoutManager("unknown", mock_config)
        config = manager.timeout_config
        assert config.request_timeout == 20  # Falls back to general request_timeout
        assert config.connect_timeout == 10.0  # Default connect timeout
    
    @pytest.mark.asyncio
    async def test_execute_api_call_success(self, openai_timeout_manager):
        """Test successful API call execution."""
        async def mock_api_call():
            return {"result": "success", "tokens": 100}
        
        result = await openai_timeout_manager.execute_api_call(
            mock_api_call,
            "test_api_call"
        )
        
        assert result.success is True
        assert result.result == {"result": "success", "tokens": 100}
    
    @pytest.mark.asyncio
    async def test_execute_api_call_timeout(self, openai_timeout_manager):
        """Test API call that times out."""
        # Temporarily reduce timeout for testing
        openai_timeout_manager.timeout_config.request_timeout = 0.1
        
        async def slow_api_call():
            await asyncio.sleep(1.0)
            return "should not reach here"
        
        result = await openai_timeout_manager.execute_api_call(
            slow_api_call,
            "slow_api_call"
        )
        
        assert result.success is False
        assert result.timeout_type == TimeoutType.REQUEST
    
    @pytest.mark.asyncio
    async def test_handle_partial_response_success(self, openai_timeout_manager):
        """Test handling successful response."""
        timeout_result = TimeoutResult(
            success=True,
            result={"content": "test response"},
            duration=1.0
        )
        
        result = await openai_timeout_manager.handle_partial_response(
            timeout_result,
            "test_operation"
        )
        
        assert result == {"content": "test response"}
    
    @pytest.mark.asyncio
    async def test_handle_partial_response_timeout_no_partial(self, openai_timeout_manager):
        """Test handling timeout with no partial response."""
        timeout_result = TimeoutResult(
            success=False,
            error=TimeoutError("Operation timed out"),
            timeout_type=TimeoutType.REQUEST,
            duration=30.0
        )
        
        with pytest.raises(TimeoutError, match="Operation timed out"):
            await openai_timeout_manager.handle_partial_response(
                timeout_result,
                "test_operation"
            )
    
    @pytest.mark.asyncio
    async def test_handle_partial_response_with_partial_data(self, openai_timeout_manager):
        """Test handling timeout with partial response data."""
        # Create a mock timeout error with partial response
        timeout_error = TimeoutError("Request timed out")
        timeout_error.partial_response = "Partial content..."
        
        timeout_result = TimeoutResult(
            success=False,
            error=timeout_error,
            timeout_type=TimeoutType.REQUEST,
            duration=30.0
        )
        
        result = await openai_timeout_manager.handle_partial_response(
            timeout_result,
            "test_operation"
        )
        
        assert result["content"] == "Partial content..."
        assert result["partial"] is True
        assert result["timeout_duration"] == 30.0
    
    @pytest.mark.asyncio
    async def test_close_cleanup(self, openai_timeout_manager):
        """Test cleanup on close."""
        # Start a long-running operation
        async def long_operation():
            await asyncio.sleep(10.0)
            return "done"
        
        # Start the operation (don't await it)
        task = asyncio.create_task(
            openai_timeout_manager.execute_api_call(
                long_operation,
                "long_operation"
            )
        )
        
        # Give it time to start
        await asyncio.sleep(0.1)
        
        # Close the manager (should cancel operations)
        await openai_timeout_manager.close()
        
        # The task should complete (with cancellation)
        try:
            result = await task
            # If we get a result, it should indicate failure due to cancellation
            assert not result.success
        except asyncio.CancelledError:
            # This is also acceptable - the operation was cancelled
            pass
    
    def test_get_timeout_stats(self, openai_timeout_manager):
        """Test getting timeout statistics."""
        stats = openai_timeout_manager.get_timeout_stats()
        
        assert stats["provider"] == "openai"
        assert stats["timeout_config"]["request_timeout"] == 30
        assert stats["timeout_config"]["connect_timeout"] == 10
        assert isinstance(stats["active_operations"], dict)


@pytest.mark.asyncio
async def test_timeout_integration():
    """Integration test for timeout management."""
    # Create a realistic scenario
    config = object.__new__(LLMConfig)
    config.openai_request_timeout = 1  # Short timeout for testing
    config.openai_connect_timeout = 10
    config.anthropic_request_timeout = 2
    config.anthropic_connect_timeout = 10
    config.request_timeout = 5
    
    manager = ProviderTimeoutManager("openai", config)
    
    # Test multiple concurrent operations with different outcomes
    async def fast_operation():
        await asyncio.sleep(0.1)
        return "fast"
    
    async def slow_operation():
        await asyncio.sleep(5.0)  # Will timeout
        return "slow"
    
    async def failing_operation():
        await asyncio.sleep(0.2)
        raise ValueError("failed")
    
    # Execute operations concurrently
    tasks = [
        manager.execute_api_call(fast_operation, "fast"),
        manager.execute_api_call(slow_operation, "slow"),
        manager.execute_api_call(failing_operation, "failing")
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Check results
    assert len(results) == 3
    
    # Fast operation should succeed
    fast_result = results[0]
    assert fast_result.success is True
    
    # Slow operation should timeout
    slow_result = results[1]
    assert slow_result.success is False
    assert slow_result.timeout_type == TimeoutType.REQUEST
    
    # Failing operation should fail with original error
    failing_result = results[2]
    assert failing_result.success is False
    assert "failed" in str(failing_result.error)
    
    # Cleanup
    await manager.close()