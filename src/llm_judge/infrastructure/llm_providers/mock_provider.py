"""
Mock LLM Provider implementation for testing.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
import logging
import asyncio

from .base import (
    LLMProvider,
    LLMProviderResponse,
    LLMProviderError,
)

logger = logging.getLogger(__name__)


@dataclass
class MockProviderConfig:
    """Configuration for Mock provider."""

    model: str = "mock-model"
    delay: float = 0.1
    should_fail: bool = False
    failure_rate: float = 0.0


class MockProvider(LLMProvider):
    """Mock LLM provider for testing."""

    def __init__(self, config: MockProviderConfig):
        self.config = config

    async def initialize(self) -> None:
        """Initialize the mock provider."""
        logger.info("Mock provider initialized")

    async def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMProviderResponse:
        """Generate a mock response."""
        # Simulate processing delay
        await asyncio.sleep(self.config.delay)

        # Simulate failure if configured
        if self.config.should_fail or self.config.failure_rate > 0:
            import random

            if random.random() < self.config.failure_rate:
                raise LLMProviderError("Mock provider failure")

        # Generate mock response
        mock_content = f"Mock response to: {prompt[:50]}..."

        return LLMProviderResponse(
            content=mock_content,
            model=self.config.model,
            provider="mock",
            usage={
                "input_tokens": len(prompt.split()),
                "output_tokens": len(mock_content.split()),
            },
            metadata={
                "mock": True,
                "system_prompt": system_prompt,
            },
        )

    async def close(self) -> None:
        """Close the mock provider."""
        logger.info("Mock provider closed")
