"""
OpenAI LLM Provider implementation.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import asyncio
import logging

from .base import (
    LLMProvider,
    LLMProviderResponse,
    LLMProviderError,
    RateLimitError,
    AuthenticationError,
    TimeoutError,
)

logger = logging.getLogger(__name__)


@dataclass
class OpenAIProviderConfig:
    """Configuration for OpenAI provider."""

    api_key: str
    model: str = "gpt-4"
    max_tokens: int = 1000
    temperature: float = 0.7
    timeout: float = 30.0
    max_retries: int = 3
    base_url: Optional[str] = None


class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider implementation."""

    def __init__(self, config: OpenAIProviderConfig):
        self.config = config
        self._client = None

    async def initialize(self) -> None:
        """Initialize the OpenAI client."""
        try:
            import openai

            self._client = openai.AsyncOpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout,
            )
        except ImportError:
            raise LLMProviderError("OpenAI library not installed")

    async def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMProviderResponse:
        """Generate a response using OpenAI."""
        if not self._client:
            await self.initialize()

        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = await self._client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                **kwargs,
            )

            return LLMProviderResponse(
                content=response.choices[0].message.content,
                model=self.config.model,
                provider="openai",
                usage=response.usage.dict() if response.usage else {},
                metadata={
                    "finish_reason": response.choices[0].finish_reason,
                    "response_id": response.id,
                },
            )

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise LLMProviderError(f"OpenAI API error: {e}")

    async def close(self) -> None:
        """Close the provider."""
        if self._client:
            await self._client.close()
