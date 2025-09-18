"""Fallback mechanisms for high availability and degraded service modes."""

import asyncio
import time
import logging
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import json
import hashlib

try:
    from ..config.logging_config import get_logger
except ImportError:
    def get_logger(name: str) -> logging.Logger:
        return logging.getLogger(name)


class ServiceMode(Enum):
    """Service operation modes."""
    FULL = "full"                    # All providers available
    DEGRADED = "degraded"           # Some providers unavailable
    FALLBACK = "fallback"           # Using cached/simplified responses
    MAINTENANCE = "maintenance"     # Planned maintenance mode


class ProviderStatus(Enum):
    """Provider availability status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    MAINTENANCE = "maintenance"


@dataclass
class ProviderHealth:
    """Health information for a provider."""
    status: ProviderStatus
    success_rate: float = 0.0
    avg_response_time: float = 0.0
    last_success: Optional[float] = None
    last_failure: Optional[float] = None
    consecutive_failures: int = 0
    total_requests: int = 0
    failed_requests: int = 0


@dataclass
class FallbackResponse:
    """Response from fallback mechanism."""
    content: Any
    mode: ServiceMode
    provider_used: Optional[str] = None
    is_cached: bool = False
    is_simplified: bool = False
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class ResponseCache:
    """Simple in-memory response cache for fallback scenarios."""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}
        self.logger = get_logger(f"{__name__}.cache")
    
    def _generate_key(self, prompt: str, context: Dict[str, Any]) -> str:
        """Generate cache key from prompt and context."""
        # Create a hash of the prompt and relevant context
        key_data = {
            "prompt": prompt.strip().lower(),
            "type": context.get("type", "evaluation"),
            "criteria": context.get("criteria", "overall")
        }
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def get(self, prompt: str, context: Dict[str, Any]) -> Optional[Any]:
        """Retrieve cached response if available and not expired."""
        key = self._generate_key(prompt, context)
        
        if key not in self._cache:
            return None
        
        cached_item = self._cache[key]
        
        # Check if expired
        if time.time() - cached_item["timestamp"] > self.ttl_seconds:
            del self._cache[key]
            self.logger.debug(f"Cache entry expired: {key}")
            return None
        
        self.logger.debug(f"Cache hit: {key}")
        return cached_item["response"]
    
    def set(self, prompt: str, context: Dict[str, Any], response: Any) -> None:
        """Cache a response."""
        key = self._generate_key(prompt, context)
        
        # Implement simple LRU eviction if cache is full
        if len(self._cache) >= self.max_size:
            # Remove oldest entry
            oldest_key = min(self._cache.keys(), 
                           key=lambda k: self._cache[k]["timestamp"])
            del self._cache[oldest_key]
            self.logger.debug(f"Cache evicted: {oldest_key}")
        
        self._cache[key] = {
            "response": response,
            "timestamp": time.time()
        }
        
        self.logger.debug(f"Cache set: {key}")
    
    def clear(self) -> None:
        """Clear all cached responses."""
        self._cache.clear()
        self.logger.info("Cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        current_time = time.time()
        expired_count = sum(1 for item in self._cache.values() 
                          if current_time - item["timestamp"] > self.ttl_seconds)
        
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "expired_entries": expired_count,
            "ttl_seconds": self.ttl_seconds
        }


class HealthMonitor:
    """Monitors provider health and system status."""
    
    def __init__(self):
        self.logger = get_logger(f"{__name__}.health")
        self.provider_health: Dict[str, ProviderHealth] = {}
        self._monitoring_interval = 60  # seconds
        self._monitoring_task: Optional[asyncio.Task] = None
    
    def initialize_provider(self, provider_name: str) -> None:
        """Initialize health tracking for a provider."""
        if provider_name not in self.provider_health:
            self.provider_health[provider_name] = ProviderHealth(
                status=ProviderStatus.HEALTHY
            )
            self.logger.info(f"Initialized health monitoring for {provider_name}")
    
    def record_success(self, provider_name: str, response_time: float) -> None:
        """Record a successful request."""
        self.initialize_provider(provider_name)
        health = self.provider_health[provider_name]
        
        health.last_success = time.time()
        health.consecutive_failures = 0
        health.total_requests += 1
        
        # Update success rate
        health.success_rate = ((health.total_requests - health.failed_requests) / 
                             health.total_requests)
        
        # Update average response time (simple moving average)
        if health.avg_response_time == 0:
            health.avg_response_time = response_time
        else:
            health.avg_response_time = (health.avg_response_time * 0.8 + response_time * 0.2)
        
        # Update status based on performance
        self._update_provider_status(provider_name)
        
        self.logger.debug(f"Recorded success for {provider_name}: {response_time:.2f}s")
    
    def record_failure(self, provider_name: str, error: Exception) -> None:
        """Record a failed request."""
        self.initialize_provider(provider_name)
        health = self.provider_health[provider_name]
        
        health.last_failure = time.time()
        health.consecutive_failures += 1
        health.total_requests += 1
        health.failed_requests += 1
        
        # Update success rate
        health.success_rate = ((health.total_requests - health.failed_requests) / 
                             health.total_requests)
        
        # Update status based on failures
        self._update_provider_status(provider_name)
        
        self.logger.warning(f"Recorded failure for {provider_name}: {error}")
    
    def _update_provider_status(self, provider_name: str) -> None:
        """Update provider status based on health metrics."""
        health = self.provider_health[provider_name]
        old_status = health.status
        
        # Determine new status
        if health.consecutive_failures >= 5:
            health.status = ProviderStatus.UNAVAILABLE
        elif health.consecutive_failures >= 3 or health.success_rate < 0.5:
            health.status = ProviderStatus.DEGRADED
        elif health.success_rate >= 0.9 and health.consecutive_failures == 0:
            health.status = ProviderStatus.HEALTHY
        
        # Log status changes
        if old_status != health.status:
            self.logger.warning(f"Provider {provider_name} status changed: {old_status.value} -> {health.status.value}")
    
    def get_provider_health(self, provider_name: str) -> Optional[ProviderHealth]:
        """Get health information for a provider."""
        return self.provider_health.get(provider_name)
    
    def get_healthy_providers(self) -> List[str]:
        """Get list of healthy providers."""
        return [name for name, health in self.provider_health.items() 
                if health.status == ProviderStatus.HEALTHY]
    
    def get_available_providers(self) -> List[str]:
        """Get list of available providers (healthy or degraded)."""
        return [name for name, health in self.provider_health.items() 
                if health.status in [ProviderStatus.HEALTHY, ProviderStatus.DEGRADED]]
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health summary."""
        if not self.provider_health:
            return {
                "status": "unknown",
                "providers": {},
                "overall_success_rate": 0.0
            }
        
        healthy_count = len(self.get_healthy_providers())
        available_count = len(self.get_available_providers())
        total_count = len(self.provider_health)
        
        # Calculate overall success rate
        total_requests = sum(health.total_requests for health in self.provider_health.values())
        total_failures = sum(health.failed_requests for health in self.provider_health.values())
        overall_success_rate = ((total_requests - total_failures) / total_requests) if total_requests > 0 else 0.0
        
        # Determine system status
        if healthy_count == total_count:
            system_status = "healthy"
        elif available_count > 0:
            system_status = "degraded"
        else:
            system_status = "unavailable"
        
        return {
            "status": system_status,
            "providers": {name: health for name, health in self.provider_health.items()},
            "healthy_providers": healthy_count,
            "available_providers": available_count,
            "total_providers": total_count,
            "overall_success_rate": overall_success_rate
        }
    
    async def start_monitoring(self) -> None:
        """Start background health monitoring."""
        if self._monitoring_task is not None:
            return
        
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        self.logger.info("Started health monitoring")
    
    async def stop_monitoring(self) -> None:
        """Stop background health monitoring."""
        if self._monitoring_task is not None:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None
            self.logger.info("Stopped health monitoring")
    
    async def _monitoring_loop(self) -> None:
        """Background monitoring loop."""
        while True:
            try:
                await asyncio.sleep(self._monitoring_interval)
                
                # Perform health checks and cleanup
                current_time = time.time()
                
                for provider_name, health in self.provider_health.items():
                    # Check for stale providers (no activity in 10 minutes)
                    last_activity = max(
                        health.last_success or 0,
                        health.last_failure or 0
                    )
                    
                    if current_time - last_activity > 600:  # 10 minutes
                        if health.status != ProviderStatus.MAINTENANCE:
                            old_status = health.status
                            health.status = ProviderStatus.UNAVAILABLE
                            if old_status != health.status:
                                self.logger.warning(f"Provider {provider_name} marked as unavailable due to inactivity")
                
                # Log system health summary
                system_health = self.get_system_health()
                self.logger.info(f"System health check: {system_health['status']} "
                               f"({system_health['healthy_providers']}/{system_health['total_providers']} healthy)")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in health monitoring loop: {e}")


class FallbackManager:
    """Manages fallback mechanisms and provider failover."""
    
    def __init__(self, config):
        self.config = config
        self.logger = get_logger(__name__)
        self.health_monitor = HealthMonitor()
        self.response_cache = ResponseCache()
        self.current_mode = ServiceMode.FULL
        
        # Fallback configuration
        self.provider_priority = ["anthropic", "openai", "bedrock"]  # Preferred order
        self.enable_caching = True
        self.enable_simplified_responses = True
        
        self.logger.info("Fallback manager initialized")
    
    async def initialize(self) -> None:
        """Initialize the fallback manager."""
        # Initialize health monitoring for configured providers
        if hasattr(self.config, 'anthropic_api_key') and self.config.anthropic_api_key:
            self.health_monitor.initialize_provider("anthropic")
        
        if hasattr(self.config, 'openai_api_key') and self.config.openai_api_key:
            self.health_monitor.initialize_provider("openai")
        
        if hasattr(self.config, 'aws_access_key_id') and self.config.aws_access_key_id:
            self.health_monitor.initialize_provider("bedrock")
        
        # Start health monitoring
        await self.health_monitor.start_monitoring()
        
        self.logger.info("Fallback manager initialized with health monitoring")
    
    async def execute_with_fallback(
        self,
        operation: Callable,
        context: Dict[str, Any],
        preferred_provider: Optional[str] = None
    ) -> FallbackResponse:
        """Execute an operation with fallback mechanisms."""
        start_time = time.time()
        
        # Determine provider order
        providers_to_try = self._get_provider_order(preferred_provider)
        
        # Try each provider in order
        for provider in providers_to_try:
            try:
                self.logger.debug(f"Attempting operation with {provider}")
                
                # Execute the operation
                result = await operation(provider)
                
                # Record success
                response_time = time.time() - start_time
                self.health_monitor.record_success(provider, response_time)
                
                # Determine service mode
                mode = self._determine_service_mode()
                
                # Cache successful responses
                if self.enable_caching:
                    self._cache_response(context, result)
                
                return FallbackResponse(
                    content=result,
                    mode=mode,
                    provider_used=provider,
                    is_cached=False,
                    is_simplified=False,
                    confidence=1.0,
                    metadata={
                        "response_time": response_time,
                        "attempts": providers_to_try.index(provider) + 1
                    }
                )
                
            except Exception as e:
                self.logger.warning(f"Provider {provider} failed: {e}")
                self.health_monitor.record_failure(provider, e)
                continue
        
        # All providers failed - try fallback mechanisms
        self.logger.warning("All providers failed, attempting fallback")
        
        # Try cached response
        if self.enable_caching:
            cached_response = self._get_cached_response(context)
            if cached_response is not None:
                self.logger.info("Using cached response as fallback")
                return FallbackResponse(
                    content=cached_response,
                    mode=ServiceMode.FALLBACK,
                    provider_used=None,
                    is_cached=True,
                    is_simplified=False,
                    confidence=0.7,
                    metadata={"fallback_reason": "cached_response"}
                )
        
        # Try simplified response
        if self.enable_simplified_responses:
            simplified_response = self._generate_simplified_response(context)
            if simplified_response is not None:
                self.logger.info("Using simplified response as fallback")
                return FallbackResponse(
                    content=simplified_response,
                    mode=ServiceMode.FALLBACK,
                    provider_used=None,
                    is_cached=False,
                    is_simplified=True,
                    confidence=0.5,
                    metadata={"fallback_reason": "simplified_response"}
                )
        
        # Last resort - return error response
        self.logger.error("All fallback mechanisms exhausted")
        return FallbackResponse(
            content=self._generate_error_response(context),
            mode=ServiceMode.MAINTENANCE,
            provider_used=None,
            is_cached=False,
            is_simplified=True,
            confidence=0.0,
            metadata={"fallback_reason": "error_response"}
        )
    
    def _get_provider_order(self, preferred_provider: Optional[str]) -> List[str]:
        """Determine the order of providers to try."""
        available_providers = self.health_monitor.get_available_providers()
        
        if not available_providers:
            # If no providers are marked as available, try all configured providers
            available_providers = list(self.health_monitor.provider_health.keys())
        
        if preferred_provider and preferred_provider in available_providers:
            # Move preferred provider to front
            provider_order = [preferred_provider]
            provider_order.extend([p for p in self.provider_priority if p != preferred_provider and p in available_providers])
        else:
            # Use default priority order
            provider_order = [p for p in self.provider_priority if p in available_providers]
        
        return provider_order
    
    def _determine_service_mode(self) -> ServiceMode:
        """Determine current service mode based on provider health."""
        healthy_providers = self.health_monitor.get_healthy_providers()
        available_providers = self.health_monitor.get_available_providers()
        total_providers = len(self.health_monitor.provider_health)
        
        if len(healthy_providers) == total_providers:
            return ServiceMode.FULL
        elif len(available_providers) > 0:
            return ServiceMode.DEGRADED
        else:
            return ServiceMode.FALLBACK
    
    def _cache_response(self, context: Dict[str, Any], response: Any) -> None:
        """Cache a successful response."""
        if "prompt" in context:
            self.response_cache.set(context["prompt"], context, response)
    
    def _get_cached_response(self, context: Dict[str, Any]) -> Optional[Any]:
        """Get cached response if available."""
        if "prompt" in context:
            return self.response_cache.get(context["prompt"], context)
        return None
    
    def _generate_simplified_response(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Generate a simplified response when providers are unavailable."""
        operation_type = context.get("type", "unknown")
        
        if operation_type == "evaluation":
            return {
                "score": 3.0,
                "reasoning": "Service temporarily unavailable. Using simplified scoring based on basic heuristics.",
                "confidence": 0.5
            }
        elif operation_type == "comparison":
            return {
                "winner": "tie",
                "reasoning": "Service temporarily unavailable. Cannot perform detailed comparison at this time.",
                "confidence": 0.3
            }
        
        return None
    
    def _generate_error_response(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate an error response when all fallbacks fail."""
        return {
            "error": "Service temporarily unavailable",
            "message": "All providers and fallback mechanisms are currently unavailable. Please try again later.",
            "status": "service_unavailable",
            "retry_after": 300  # 5 minutes
        }
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        health_status = self.health_monitor.get_system_health()
        cache_stats = self.response_cache.get_stats()
        
        return {
            "service_mode": self.current_mode.value,
            "health": health_status,
            "cache": cache_stats,
            "fallback_config": {
                "enable_caching": self.enable_caching,
                "enable_simplified_responses": self.enable_simplified_responses,
                "provider_priority": self.provider_priority
            },
            "timestamp": time.time()
        }
    
    async def set_maintenance_mode(self, enabled: bool, reason: Optional[str] = None) -> None:
        """Enable or disable maintenance mode."""
        if enabled:
            self.current_mode = ServiceMode.MAINTENANCE
            self.logger.warning(f"Maintenance mode enabled: {reason or 'No reason specified'}")
        else:
            self.current_mode = self._determine_service_mode()
            self.logger.info("Maintenance mode disabled")
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        await self.health_monitor.stop_monitoring()
        self.response_cache.clear()
        self.logger.info("Fallback manager cleanup complete")


# Global fallback manager instance
_fallback_manager: Optional[FallbackManager] = None

def get_fallback_manager(config=None) -> FallbackManager:
    """Get the global fallback manager instance."""
    global _fallback_manager
    if _fallback_manager is None and config is not None:
        _fallback_manager = FallbackManager(config)
    return _fallback_manager