"""
Anthropic LLM Provider implementation.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
import logging

from .base import (
    LLMProvider,
    LLMProviderResponse,
    LLMProviderError,
)

logger = logging.getLogger(__name__)


@dataclass
class AnthropicProviderConfig:
    """Configuration for Anthropic provider."""

    api_key: str
    model: str = "claude-3-sonnet-20240229"
    max_tokens: int = 1000
    temperature: float = 0.7
    timeout: float = 30.0
    max_retries: int = 3


class AnthropicProvider(LLMProvider):
    """Anthropic LLM provider implementation."""

    def __init__(self, config: AnthropicProviderConfig):
        self.config = config
        self._client = None

    async def initialize(self) -> None:
        """Initialize the Anthropic client."""
        try:
            import anthropic

            self._client = anthropic.AsyncAnthropic(
                api_key=self.config.api_key,
                timeout=self.config.timeout,
            )
        except ImportError:
            raise LLMProviderError("Anthropic library not installed")

    async def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMProviderResponse:
        """Generate a response using Anthropic."""
        if not self._client:
            await self.initialize()

        try:
            response = await self._client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                system=system_prompt or "",
                messages=[{"role": "user", "content": prompt}],
                **kwargs,
            )

            return LLMProviderResponse(
                content=response.content[0].text,
                model=self.config.model,
                provider="anthropic",
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
                metadata={
                    "stop_reason": response.stop_reason,
                    "response_id": response.id,
                },
            )

        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise LLMProviderError(f"Anthropic API error: {e}")

    async def close(self) -> None:
        """Close the provider."""
        if self._client:
            await self._client.close()
