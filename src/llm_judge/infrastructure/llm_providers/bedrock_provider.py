"""
AWS Bedrock LLM Provider implementation.
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
class BedrockProviderConfig:
    """Configuration for Bedrock provider."""

    region_name: str = "us-east-1"
    model: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    max_tokens: int = 1000
    temperature: float = 0.7
    timeout: float = 30.0
    max_retries: int = 3


class BedrockProvider(LLMProvider):
    """AWS Bedrock LLM provider implementation."""

    def __init__(self, config: BedrockProviderConfig):
        self.config = config
        self._client = None

    async def initialize(self) -> None:
        """Initialize the Bedrock client."""
        try:
            import boto3

            self._client = boto3.client(
                "bedrock-runtime",
                region_name=self.config.region_name,
            )
        except ImportError:
            raise LLMProviderError("boto3 library not installed")

    async def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMProviderResponse:
        """Generate a response using Bedrock."""
        if not self._client:
            await self.initialize()

        try:
            # Prepare the request body based on the model
            if "claude" in self.config.model:
                body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": self.config.max_tokens,
                    "temperature": self.config.temperature,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                }
                if system_prompt:
                    body["system"] = system_prompt
            else:
                # Default format for other models
                body = {
                    "prompt": prompt,
                    "max_tokens_to_sample": self.config.max_tokens,
                    "temperature": self.config.temperature,
                }

            response = self._client.invoke_model(
                modelId=self.config.model,
                body=body,
            )

            # Parse response based on model type
            if "claude" in self.config.model:
                import json

                response_body = json.loads(response["body"].read())
                content = response_body["content"][0]["text"]
            else:
                import json

                response_body = json.loads(response["body"].read())
                content = response_body["completion"]

            return LLMProviderResponse(
                content=content,
                model=self.config.model,
                provider="bedrock",
                usage={},
                metadata={
                    "response_id": response.get("ResponseMetadata", {}).get(
                        "RequestId"
                    ),
                },
            )

        except Exception as e:
            logger.error(f"Bedrock API error: {e}")
            raise LLMProviderError(f"Bedrock API error: {e}")

    async def close(self) -> None:
        """Close the provider."""
        # Bedrock client doesn't need explicit closing
        pass
