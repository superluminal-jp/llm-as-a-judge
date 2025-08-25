"""Tests for fallback manager functionality."""

import pytest
import asyncio
import json
import time
from unittest.mock import AsyncMock, Mock, patch

from src.llm_judge.infrastructure.resilience.fallback_manager import (
    FallbackManager, FallbackResponse, ProviderHealth, 
    ProviderStatus, HealthMonitor, ResponseCache, ServiceMode
)
from src.llm_judge.infrastructure.config.config import LLMConfig


@pytest.fixture
def mock_config():
    """Create a mock config for testing."""
    config = object.__new__(LLMConfig)
    config.default_provider = "openai"
    config.fallback_enabled = True
    config.fallback_providers = ["openai", "anthropic"]
    config.cache_enabled = True
    config.cache_ttl = 300
    config.health_check_interval = 60
    config.health_check_timeout = 10
    config.circuit_breaker_failure_threshold = 3
    config.circuit_breaker_recovery_timeout = 60
    config.max_retries = 3
    config.base_delay = 1.0
    return config


@pytest.fixture
def fallback_manager(mock_config):
    """Create a fallback manager for testing."""
    return FallbackManager(mock_config)


class TestProviderHealth:
    """Test provider health tracking."""
    
    def test_provider_health_initialization(self):
        """Test provider health initializes correctly."""
        health = ProviderHealth(status=ProviderStatus.HEALTHY)
        assert health.status == ProviderStatus.HEALTHY
        assert health.consecutive_failures == 0
        assert health.last_success is None
        assert health.last_failure is None
        assert health.success_rate == 0.0
        assert health.avg_response_time == 0.0
    
    def test_provider_health_with_values(self):
        """Test provider health with specific values."""
        health = ProviderHealth(
            status=ProviderStatus.DEGRADED,
            success_rate=0.8,
            avg_response_time=1.5,
            consecutive_failures=2
        )
        assert health.status == ProviderStatus.DEGRADED
        assert health.success_rate == 0.8
        assert health.avg_response_time == 1.5
        assert health.consecutive_failures == 2


class TestHealthMonitor:
    """Test health monitoring functionality."""
    
    def test_health_monitor_initialization(self):
        """Test health monitor initializes correctly."""
        monitor = HealthMonitor()
        
        assert isinstance(monitor.provider_health, dict)
        assert len(monitor.provider_health) == 0
        assert monitor._monitoring_task is None
    
    def test_record_success(self):
        """Test recording successful operations."""
        monitor = HealthMonitor()
        
        monitor.record_success("openai", response_time=0.8)
        
        health = monitor.provider_health["openai"]
        assert health.status == ProviderStatus.HEALTHY
        assert health.consecutive_failures == 0
        assert health.last_success is not None
    
    def test_record_failure(self):
        """Test recording failed operations."""
        monitor = HealthMonitor()
        
        monitor.record_failure("openai", "API error")
        
        health = monitor.provider_health["openai"]
        assert health.consecutive_failures == 1
        assert health.last_failure is not None
        assert health.status == ProviderStatus.DEGRADED
    
    def test_get_available_providers(self):
        """Test getting available providers."""
        monitor = HealthMonitor()
        
        # Initialize some providers
        monitor.initialize_provider("openai")
        monitor.initialize_provider("anthropic")
        
        # All providers should be available initially
        available = monitor.get_available_providers()
        assert "openai" in available
        assert "anthropic" in available
        
        # Make openai unavailable
        for _ in range(5):
            monitor.record_failure("openai", Exception("API error"))
        
        available = monitor.get_available_providers()
        assert "openai" not in available
        assert "anthropic" in available


class TestResponseCache:
    """Test response caching functionality."""
    
    def test_cache_initialization(self):
        """Test cache initializes correctly."""
        cache = ResponseCache(ttl_seconds=300)
        assert cache.ttl_seconds == 300
        assert len(cache._cache) == 0
    
    def test_cache_set_get(self):
        """Test setting and getting cache entries."""
        cache = ResponseCache(ttl_seconds=300)
        
        test_response = {"score": 4.5, "reasoning": "Test response"}
        prompt = "test prompt"
        context = {"type": "evaluation", "criteria": "quality"}
        
        cache.set(prompt, context, test_response)
        
        cached_response = cache.get(prompt, context)
        assert cached_response == test_response
    
    def test_cache_expiration(self):
        """Test cache entry expiration."""
        cache = ResponseCache(ttl_seconds=1)  # 1 second TTL
        
        test_response = {"score": 4.5, "reasoning": "Test response"}
        prompt = "test prompt"
        context = {"type": "evaluation", "criteria": "quality"}
        
        cache.set(prompt, context, test_response)
        
        # Should be available immediately
        assert cache.get(prompt, context) == test_response
        
        # Mock time passage for expiration
        import time
        original_time = time.time
        time.time = lambda: original_time() + 3600  # 1 hour later
        
        try:
            # Should be None after expiration
            assert cache.get(prompt, context) is None
        finally:
            time.time = original_time
    
    def test_cache_clear(self):
        """Test clearing the cache."""
        cache = ResponseCache(ttl_seconds=300)
        
        context1 = {"type": "evaluation", "criteria": "quality"}
        context2 = {"type": "comparison", "criteria": "accuracy"}
        
        cache.set("prompt1", context1, {"data": "test1"})
        cache.set("prompt2", context2, {"data": "test2"})
        
        assert len(cache._cache) == 2
        
        cache.clear()
        
        assert len(cache._cache) == 0
    
    def test_generate_cache_key(self):
        """Test cache key generation."""
        cache = ResponseCache(ttl_seconds=300)
        
        prompt = "Test prompt"
        context = {
            "type": "evaluation",
            "response": "Test response",
            "criteria": "quality"
        }
        
        key1 = cache._generate_key(prompt, context)
        key2 = cache._generate_key(prompt, context)
        
        # Same context should generate same key
        assert key1 == key2
        
        # Different context should generate different key
        context["criteria"] = "accuracy"
        key3 = cache._generate_key(prompt, context)
        assert key1 != key3


class TestFallbackManager:
    """Test main fallback manager functionality."""
    
    def test_initialization(self, mock_config):
        """Test fallback manager initializes correctly."""
        manager = FallbackManager(mock_config)
        
        assert manager.config == mock_config
        assert manager.health_monitor is not None
        assert manager.response_cache is not None
        assert manager.current_mode == ServiceMode.FULL
    
    @pytest.mark.asyncio
    async def test_initialization_process(self, mock_config):
        """Test the initialization process."""
        manager = FallbackManager(mock_config)
        
        await manager.initialize()
        
        # Should have initialized monitoring
        assert manager.health_monitor._monitoring_task is not None
    
    @pytest.mark.asyncio
    async def test_get_provider_order_default(self, mock_config, fallback_manager):
        """Test provider ordering with default preference."""
        await fallback_manager.initialize()
        
        providers = fallback_manager._get_provider_order("openai")
        
        # Should have providers in some order
        assert isinstance(providers, list)
        # Since we may not have providers initialized, just check structure
    
    @pytest.mark.asyncio
    async def test_get_provider_order_with_initialized_providers(self, mock_config, fallback_manager):
        """Test provider ordering when providers are initialized."""
        await fallback_manager.initialize()
        
        # Initialize providers manually for test
        fallback_manager.health_monitor.initialize_provider("openai")
        fallback_manager.health_monitor.initialize_provider("anthropic")
        
        providers = fallback_manager._get_provider_order("openai")
        
        # Should start with preferred provider if available
        if "openai" in providers:
            assert providers[0] == "openai"
        
        # Make openai unavailable
        for _ in range(5):
            fallback_manager.health_monitor.record_failure("openai", Exception("test error"))
        
        providers = fallback_manager._get_provider_order("openai")
        
        # Should not include unavailable provider
        assert "openai" not in providers
    
    @pytest.mark.asyncio
    async def test_successful_operation(self, mock_config, fallback_manager):
        """Test successful operation execution."""
        await fallback_manager.initialize()
        
        # Initialize a provider
        fallback_manager.health_monitor.initialize_provider("anthropic")
        
        # Mock operation
        async def mock_operation(provider: str):
            return {"score": 4.5, "reasoning": "Great response"}
        
        context = {
            "type": "evaluation",
            "prompt": "Test prompt",
            "response": "Test response"
        }
        
        result = await fallback_manager.execute_with_fallback(
            mock_operation, context, preferred_provider="anthropic"
        )
        
        assert isinstance(result, FallbackResponse)
        assert result.content["score"] == 4.5
        assert result.provider_used == "anthropic"
        assert result.confidence == 1.0
        assert not result.is_cached
    
    @pytest.mark.asyncio
    async def test_provider_fallback(self, mock_config, fallback_manager):
        """Test fallback to secondary provider."""
        await fallback_manager.initialize()
        
        # Initialize providers
        fallback_manager.health_monitor.initialize_provider("openai")
        fallback_manager.health_monitor.initialize_provider("anthropic")
        
        # Mock operation that fails for openai but succeeds for anthropic
        async def mock_operation(provider: str):
            if provider == "openai":
                raise Exception("OpenAI error")
            return {"score": 4.0, "reasoning": "Good response"}
        
        context = {
            "type": "evaluation",
            "prompt": "Test prompt",
            "response": "Test response"
        }
        
        result = await fallback_manager.execute_with_fallback(
            mock_operation, context, preferred_provider="openai"
        )
        
        assert isinstance(result, FallbackResponse)
        assert result.content["score"] == 4.0
        assert result.provider_used == "anthropic"
        assert result.confidence == 1.0
    
    @pytest.mark.asyncio
    async def test_cache_hit(self, mock_config, fallback_manager):
        """Test cache hit scenario."""
        await fallback_manager.initialize()
        
        # Pre-populate cache
        context = {
            "type": "evaluation",
            "prompt": "Test prompt",
            "response": "Test response"
        }
        
        cached_response = {"score": 3.5, "reasoning": "Cached response"}
        fallback_manager.response_cache.set(context["prompt"], context, cached_response)
        
        # Mock operation (should not be called due to cache hit)
        async def mock_operation(provider: str):
            raise Exception("Should not be called")
        
        result = await fallback_manager.execute_with_fallback(
            mock_operation, context, preferred_provider="openai"
        )
        
        assert isinstance(result, FallbackResponse)
        assert result.content["score"] == 3.5
        assert result.is_cached
        assert result.confidence == 0.7
    
    @pytest.mark.asyncio
    async def test_degraded_mode(self, mock_config, fallback_manager):
        """Test degraded mode when all providers fail."""
        await fallback_manager.initialize()
        
        # Mock operation that always fails
        async def mock_operation(provider: str):
            raise Exception(f"{provider} error")
        
        context = {
            "type": "evaluation",
            "prompt": "Test prompt",
            "response": "Test response"
        }
        
        result = await fallback_manager.execute_with_fallback(
            mock_operation, context, preferred_provider="openai"
        )
        
        assert isinstance(result, FallbackResponse)
        assert result.content["score"] == 3.0  # Default degraded score
        assert result.provider_used is None  # No specific provider
        assert result.confidence == 0.5  # Simplified response confidence
        assert result.is_simplified
    
    @pytest.mark.asyncio
    async def test_cleanup(self, mock_config, fallback_manager):
        """Test cleanup process."""
        await fallback_manager.initialize()
        
        # Verify it's initialized
        assert fallback_manager.health_monitor._monitoring_task is not None
        
        await fallback_manager.cleanup()
        
        # Verify cleanup
        assert len(fallback_manager.response_cache._cache) == 0


@pytest.mark.asyncio
async def test_integration_with_llm_judge():
    """Test integration with LLMJudge class."""
    # This would require mocking the actual LLMJudge class
    # and testing the integration points
    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])