"""
LLM Provider Factory for creating provider instances.
"""

from typing import Dict, Any, Optional, List
from enum import Enum
import logging

from .base import LLMProvider, LLMProviderError
from .openai_provider import OpenAIProvider, OpenAIProviderConfig
from .anthropic_provider import AnthropicProvider, AnthropicProviderConfig
from .bedrock_provider import BedrockProvider, BedrockProviderConfig
from .mock_provider import MockProvider, MockProviderConfig

logger = logging.getLogger(__name__)


class ProviderType(Enum):
    """Supported provider types."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    BEDROCK = "bedrock"
    MOCK = "mock"


class LLMProviderFactory:
    """Factory for creating LLM provider instances."""

    @staticmethod
    def create_provider(
        provider_type: str,
        config: Dict[str, Any],
    ) -> LLMProvider:
        """Create a provider instance based on type and configuration."""

        provider_type_enum = ProviderType(provider_type.lower())

        if provider_type_enum == ProviderType.OPENAI:
            openai_config = OpenAIProviderConfig(**config)
            return OpenAIProvider(openai_config)

        elif provider_type_enum == ProviderType.ANTHROPIC:
            anthropic_config = AnthropicProviderConfig(**config)
            return AnthropicProvider(anthropic_config)

        elif provider_type_enum == ProviderType.BEDROCK:
            bedrock_config = BedrockProviderConfig(**config)
            return BedrockProvider(bedrock_config)

        elif provider_type_enum == ProviderType.MOCK:
            mock_config = MockProviderConfig(**config)
            return MockProvider(mock_config)

        else:
            raise LLMProviderError(f"Unsupported provider type: {provider_type}")

    @staticmethod
    def get_available_providers() -> List[str]:
        """Get list of available provider types."""
        return [provider.value for provider in ProviderType]

    @staticmethod
    def validate_config(provider_type: str, config: Dict[str, Any]) -> bool:
        """Validate configuration for a provider type."""
        try:
            provider_type_enum = ProviderType(provider_type.lower())

            if provider_type_enum == ProviderType.OPENAI:
                OpenAIProviderConfig(**config)
            elif provider_type_enum == ProviderType.ANTHROPIC:
                AnthropicProviderConfig(**config)
            elif provider_type_enum == ProviderType.BEDROCK:
                BedrockProviderConfig(**config)
            elif provider_type_enum == ProviderType.MOCK:
                MockProviderConfig(**config)
            else:
                return False

            return True

        except Exception as e:
            logger.error(f"Config validation failed: {e}")
            return False


# Convenience functions
def create_provider(provider_type: str, config: Dict[str, Any]) -> LLMProvider:
    """Create a provider instance."""
    return LLMProviderFactory.create_provider(provider_type, config)


def get_available_providers() -> List[str]:
    """Get list of available provider types."""
    return LLMProviderFactory.get_available_providers()
