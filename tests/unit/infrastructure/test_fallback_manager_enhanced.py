"""Enhanced test suite for Fallback Manager functionality."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from src.llm_judge.infrastructure.config.config import LLMConfig
from src.llm_judge.infrastructure.resilience.fallback_manager import (
    FallbackManager, ServiceMode, ProviderStatus, FallbackResponse, 
    ResponseCache, HealthMonitor
)


@pytest.fixture
def test_config():
    """Create test configuration for fallback manager."""
    return LLMConfig(
        openai_api_key="test-openai-key",
        anthropic_api_key="test-anthropic-key",
        aws_access_key_id="test-aws-key",
        aws_secret_access_key="test-aws-secret",
        aws_region="us-east-1",
        default_provider="anthropic"
    )


@pytest.fixture
def fallback_manager(test_config):
    """Create fallback manager instance."""
    return FallbackManager(test_config)


class TestFallbackManagerInitialization:
    """Test fallback manager initialization and configuration."""
    
    def test_fallback_manager_initialization(self, test_config):
        """Test fallback manager initializes with correct providers."""
        manager = FallbackManager(test_config)
        
        assert manager.config == test_config
        assert manager.current_mode == ServiceMode.FULL
        assert "anthropic" in manager.provider_priority
        assert "openai" in manager.provider_priority
        assert "bedrock" in manager.provider_priority
        assert manager.enable_caching is True
        assert manager.enable_simplified_responses is True
    
    @pytest.mark.asyncio
    async def test_initialize_providers(self, fallback_manager):
        """Test provider initialization based on available credentials."""
        await fallback_manager.initialize()
        
        # Check that providers with credentials were initialized
        assert "anthropic" in fallback_manager.health_monitor.provider_health
        assert "openai" in fallback_manager.health_monitor.provider_health
        assert "bedrock" in fallback_manager.health_monitor.provider_health
        
        # Verify all providers start as healthy
        for provider_name, health in fallback_manager.health_monitor.provider_health.items():
            assert health.status == ProviderStatus.HEALTHY
    
    def test_provider_priority_order(self, fallback_manager):
        """Test that provider priority follows expected order."""
        expected_order = ["anthropic", "openai", "bedrock"]
        assert fallback_manager.provider_priority == expected_order


class TestFallbackManagerExecution:
    """Test fallback execution logic."""
    
    @pytest.mark.asyncio
    async def test_execute_with_fallback_success_first_provider(self, fallback_manager):
        """Test successful execution on first provider attempt."""
        await fallback_manager.initialize()
        
        # Mock operation that succeeds on first try
        mock_operation = AsyncMock(return_value={"result": "success", "provider": "anthropic"})
        
        context = {"type": "evaluation", "prompt": "test prompt"}
        
        result = await fallback_manager.execute_with_fallback(
            mock_operation,
            context,
            preferred_provider="anthropic"
        )
        
        assert isinstance(result, FallbackResponse)
        assert result.content == {"result": "success", "provider": "anthropic"}
        assert result.provider_used == "anthropic"
        assert result.success is True
        assert result.attempts_made == 1
        
        # Verify operation was called with anthropic provider
        mock_operation.assert_called_once_with("anthropic")
    
    @pytest.mark.asyncio
    async def test_execute_with_fallback_provider_failover(self, fallback_manager):
        """Test failover to next provider when first fails."""
        await fallback_manager.initialize()
        
        # Mock operation that fails on anthropic but succeeds on openai
        def mock_operation_side_effect(provider):
            if provider == "anthropic":
                raise Exception("Anthropic service unavailable")
            elif provider == "openai":
                return {"result": "success", "provider": "openai"}
            else:
                raise Exception(f"Unknown provider: {provider}")
        
        mock_operation = AsyncMock(side_effect=mock_operation_side_effect)
        
        context = {"type": "evaluation", "prompt": "test prompt"}
        
        result = await fallback_manager.execute_with_fallback(
            mock_operation,
            context,
            preferred_provider="anthropic"
        )
        
        assert result.content == {"result": "success", "provider": "openai"}
        assert result.provider_used == "openai"
        assert result.success is True
        assert result.attempts_made == 2
        
        # Verify both providers were tried
        assert mock_operation.call_count == 2
        mock_operation.assert_any_call("anthropic")
        mock_operation.assert_any_call("openai")
    
    @pytest.mark.asyncio
    async def test_execute_with_fallback_all_providers_fail(self, fallback_manager):
        """Test behavior when all providers fail."""
        await fallback_manager.initialize()
        
        # Mock operation that fails for all providers
        mock_operation = AsyncMock(side_effect=Exception("All services unavailable"))
        
        context = {"type": "evaluation", "prompt": "test prompt"}
        
        result = await fallback_manager.execute_with_fallback(
            mock_operation,
            context,
            preferred_provider="anthropic"
        )
        
        assert result.success is False
        assert result.attempts_made > 0
        assert "fallback" in result.metadata
        
        # Should have tried all providers
        assert mock_operation.call_count == len(fallback_manager.provider_priority)
    
    @pytest.mark.asyncio
    async def test_execute_with_preferred_provider_not_available(self, fallback_manager):
        """Test execution when preferred provider is not in available list."""
        await fallback_manager.initialize()
        
        # Mock operation
        mock_operation = AsyncMock(return_value={"result": "success", "provider": "anthropic"})
        
        context = {"type": "evaluation", "prompt": "test prompt"}
        
        # Request non-existent provider
        result = await fallback_manager.execute_with_fallback(
            mock_operation,
            context,
            preferred_provider="nonexistent"
        )
        
        # Should fall back to default priority order
        assert result.success is True
        assert result.provider_used in fallback_manager.provider_priority


class TestHealthMonitor:
    """Test health monitoring functionality."""
    
    def test_initialize_provider(self):
        """Test provider initialization in health monitor."""
        monitor = HealthMonitor()
        
        monitor.initialize_provider("test_provider")
        
        assert "test_provider" in monitor.provider_health
        assert monitor.provider_health["test_provider"].status == ProviderStatus.HEALTHY
        assert monitor.provider_health["test_provider"].consecutive_failures == 0
    
    def test_record_success(self):
        """Test recording successful requests."""
        monitor = HealthMonitor()
        monitor.initialize_provider("test_provider")
        
        # Record multiple successes
        monitor.record_success("test_provider", 0.5)
        monitor.record_success("test_provider", 1.0)
        monitor.record_success("test_provider", 0.3)
        
        health = monitor.provider_health["test_provider"]
        assert health.total_requests == 3
        assert health.failed_requests == 0
        assert health.success_rate == 1.0
        assert health.consecutive_failures == 0
        assert health.last_success > 0
    
    def test_record_failure(self):
        """Test recording failed requests."""
        monitor = HealthMonitor()
        monitor.initialize_provider("test_provider")
        
        # Record some successes first
        monitor.record_success("test_provider", 0.5)
        monitor.record_success("test_provider", 1.0)
        
        # Then record failures
        monitor.record_failure("test_provider", Exception("Test error"))
        monitor.record_failure("test_provider", Exception("Another error"))
        
        health = monitor.provider_health["test_provider"]
        assert health.total_requests == 4
        assert health.failed_requests == 2
        assert health.success_rate == 0.5  # 2 successes out of 4 total
        assert health.consecutive_failures == 2
        assert health.last_failure > 0
    
    def test_get_healthy_providers(self):
        """Test getting list of healthy providers."""
        monitor = HealthMonitor()
        monitor.initialize_provider("healthy_provider")
        monitor.initialize_provider("failing_provider")
        
        # Mark one provider as degraded
        for _ in range(5):  # Simulate multiple failures
            monitor.record_failure("failing_provider", Exception("Test error"))
        
        healthy_providers = monitor.get_healthy_providers()
        assert "healthy_provider" in healthy_providers
        assert "failing_provider" not in healthy_providers
    
    def test_get_available_providers(self):
        """Test getting list of available providers."""
        monitor = HealthMonitor()
        monitor.initialize_provider("provider1")
        monitor.initialize_provider("provider2")
        
        available = monitor.get_available_providers()
        assert "provider1" in available
        assert "provider2" in available
        assert len(available) == 2


class TestResponseCache:
    """Test response caching functionality."""
    
    def test_cache_set_and_get(self):
        """Test setting and getting cached responses."""
        cache = ResponseCache()
        
        context = {"type": "evaluation", "criteria": "quality"}
        response = {"score": 4.5, "reasoning": "Good response"}
        
        # Cache a response
        cache.set("test prompt", context, response)
        
        # Retrieve cached response
        cached_response = cache.get("test prompt", context)
        
        assert cached_response == response
    
    def test_cache_miss(self):
        """Test cache miss scenario."""
        cache = ResponseCache()
        
        context = {"type": "evaluation", "criteria": "quality"}
        
        # Try to get non-existent cache entry
        cached_response = cache.get("non-existent prompt", context)
        
        assert cached_response is None
    
    def test_cache_key_generation(self):
        """Test that cache key generation is consistent."""
        cache = ResponseCache()
        
        context1 = {"type": "evaluation", "criteria": "quality"}
        context2 = {"type": "evaluation", "criteria": "quality"}  # Same context
        context3 = {"type": "evaluation", "criteria": "accuracy"}  # Different context
        
        key1 = cache._generate_key("test prompt", context1)
        key2 = cache._generate_key("test prompt", context2)
        key3 = cache._generate_key("test prompt", context3)
        
        # Same prompt and context should generate same key
        assert key1 == key2
        # Different context should generate different key
        assert key1 != key3
    
    def test_cache_expiration(self):
        """Test cache expiration functionality."""
        # Create cache with short TTL
        cache = ResponseCache(ttl_seconds=0)  # Expire immediately
        
        context = {"type": "evaluation", "criteria": "quality"}
        response = {"score": 4.5}
        
        # Cache and immediately try to retrieve
        cache.set("test prompt", context, response)
        
        # Since TTL is 0, should be expired
        cached_response = cache.get("test prompt", context)
        assert cached_response is None


class TestFallbackManagerIntegration:
    """Integration tests for fallback manager components."""
    
    @pytest.mark.asyncio
    async def test_health_monitoring_affects_provider_selection(self, fallback_manager):
        """Test that health monitoring affects provider selection."""
        await fallback_manager.initialize()
        
        # Mark anthropic as failing
        for _ in range(10):
            fallback_manager.health_monitor.record_failure("anthropic", Exception("Test error"))
        
        # Mock operation that works for any provider
        mock_operation = AsyncMock(return_value={"result": "success"})
        
        context = {"type": "evaluation", "prompt": "test"}
        
        result = await fallback_manager.execute_with_fallback(
            mock_operation,
            context,
            preferred_provider="anthropic"
        )
        
        # Should have used a different provider due to anthropic being unhealthy
        assert result.provider_used in ["openai", "bedrock"]
        assert result.success is True
    
    @pytest.mark.asyncio 
    async def test_caching_prevents_duplicate_requests(self, fallback_manager):
        """Test that caching prevents duplicate API requests."""
        await fallback_manager.initialize()
        
        # Mock operation
        mock_operation = AsyncMock(return_value={"score": 4.5, "reasoning": "Cached response"})
        
        context = {"type": "evaluation", "prompt": "What is AI?", "criteria": "accuracy"}
        
        # First request - should call the operation
        result1 = await fallback_manager.execute_with_fallback(
            mock_operation,
            context,
            preferred_provider="anthropic"
        )
        
        # Second request with same context - should use cache
        result2 = await fallback_manager.execute_with_fallback(
            mock_operation,
            context,
            preferred_provider="anthropic"
        )
        
        # Operation should only be called once (first request)
        mock_operation.assert_called_once()
        
        # Both results should be the same
        assert result1.content == result2.content
    
    @pytest.mark.asyncio
    async def test_service_mode_determination(self, fallback_manager):
        """Test service mode determination based on provider health."""
        await fallback_manager.initialize()
        
        # Initially all providers healthy - should be FULL mode
        mode = fallback_manager._determine_service_mode()
        assert mode == ServiceMode.FULL
        
        # Mark some providers as failing
        for _ in range(5):
            fallback_manager.health_monitor.record_failure("anthropic", Exception("Test error"))
        
        # Should now be in DEGRADED mode
        mode = fallback_manager._determine_service_mode()
        assert mode == ServiceMode.DEGRADED
        
        # Mark all providers as failing
        for provider in fallback_manager.provider_priority:
            for _ in range(10):
                fallback_manager.health_monitor.record_failure(provider, Exception("All failing"))
        
        # Should now be in FALLBACK mode
        mode = fallback_manager._determine_service_mode()
        assert mode == ServiceMode.FALLBACK


class TestFallbackManagerErrorScenarios:
    """Test error scenarios and edge cases."""
    
    @pytest.mark.asyncio
    async def test_cleanup_on_shutdown(self, fallback_manager):
        """Test proper cleanup when shutting down."""
        await fallback_manager.initialize()
        
        # Mock health monitor with cleanup method
        fallback_manager.health_monitor.stop_monitoring = AsyncMock()
        
        await fallback_manager.cleanup()
        
        # Verify cleanup was called
        fallback_manager.health_monitor.stop_monitoring.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, fallback_manager):
        """Test handling of concurrent requests."""
        await fallback_manager.initialize()
        
        mock_operation = AsyncMock(return_value={"result": "success"})
        
        context = {"type": "evaluation", "prompt": "test"}
        
        # Create multiple concurrent requests
        tasks = []
        for i in range(5):
            task = fallback_manager.execute_with_fallback(
                mock_operation,
                {**context, "request_id": i},
                preferred_provider="anthropic"
            )
            tasks.append(task)
        
        # Wait for all to complete
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        for result in results:
            assert result.success is True
        
        # Operation should be called for each request
        assert mock_operation.call_count == 5
    
    def test_provider_priority_with_no_preferred(self, fallback_manager):
        """Test provider order when no preferred provider is specified."""
        provider_order = fallback_manager._get_provider_order(None)
        
        # Should return all providers in default priority order
        assert provider_order == fallback_manager.provider_priority
    
    def test_provider_priority_with_invalid_preferred(self, fallback_manager):
        """Test provider order when invalid preferred provider is specified."""
        provider_order = fallback_manager._get_provider_order("invalid_provider")
        
        # Should return default priority order (invalid provider ignored)
        assert provider_order == fallback_manager.provider_priority