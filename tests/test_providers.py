"""Tests for LLM provider implementations (src/providers/).

Covers:
- AnthropicProvider: successful completion, auth/rate-limit error mapping,
  cold-start caching.
- OpenAIProvider: successful completion, error mapping, caching.
- BedrockProvider: successful completion via converse API, ClientError mapping.
- get_provider() factory: caching, unknown provider name.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, call, patch

import pytest

from src.handler import ConfigurationError, ProviderError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(
    *,
    anthropic_api_key: str = "test-anthropic-key",
    anthropic_model: str = "claude-sonnet-4-6",
    openai_api_key: str = "test-openai-key",
    openai_model: str = "gpt-4o",
    bedrock_model: str = "amazon.nova-premier-v1:0",
    request_timeout: int = 30,
    default_provider: str = "anthropic",
):
    from src.config import Config

    return Config(
        default_provider=default_provider,
        anthropic_api_key=anthropic_api_key,
        anthropic_model=anthropic_model,
        openai_api_key=openai_api_key,
        openai_model=openai_model,
        bedrock_model=bedrock_model,
        request_timeout=request_timeout,
        log_level="INFO",
    )


MESSAGES = [{"role": "user", "content": "Rate this response."}]
MODEL = "test-model"
TIMEOUT = 30

EVAL_JSON = json.dumps(
    {
        "criterion_scores": {"accuracy": 4.0},
        "reasoning": "Accurate.",
    }
)


# ---------------------------------------------------------------------------
# AnthropicProvider
# ---------------------------------------------------------------------------


class TestAnthropicProvider:
    def test_complete_returns_text(self):
        """complete() extracts text from the Anthropic message response."""
        from src.providers.anthropic import AnthropicProvider

        config = _make_config()
        provider = AnthropicProvider(config)

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=EVAL_JSON)]

        with patch.object(provider._client, "messages") as mock_messages:
            mock_messages.create.return_value = mock_message
            result = provider.complete(MESSAGES, MODEL, TIMEOUT)

        assert result == EVAL_JSON
        mock_messages.create.assert_called_once()

    def test_auth_error_raises_provider_error(self):
        """anthropic.AuthenticationError is mapped to ProviderError."""
        import anthropic

        from src.providers.anthropic import AnthropicProvider

        config = _make_config()
        provider = AnthropicProvider(config)

        with patch.object(provider._client, "messages") as mock_messages:
            mock_messages.create.side_effect = anthropic.AuthenticationError(
                message="Invalid key",
                response=MagicMock(status_code=401, headers={}),
                body={},
            )
            with pytest.raises(ProviderError, match="Authentication"):
                provider.complete(MESSAGES, MODEL, TIMEOUT)

    def test_rate_limit_raises_provider_error(self):
        """anthropic.RateLimitError is mapped to ProviderError."""
        import anthropic

        from src.providers.anthropic import AnthropicProvider

        config = _make_config()
        provider = AnthropicProvider(config)

        with patch.object(provider._client, "messages") as mock_messages:
            mock_messages.create.side_effect = anthropic.RateLimitError(
                message="Rate limited",
                response=MagicMock(status_code=429, headers={}),
                body={},
            )
            with pytest.raises(ProviderError, match="Rate limit"):
                provider.complete(MESSAGES, MODEL, TIMEOUT)

    def test_client_created_once_per_provider_instance(self):
        """The internal Anthropic client is constructed once at __init__ time."""
        from src.providers.anthropic import AnthropicProvider

        config = _make_config()
        with patch("src.providers.anthropic.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value = MagicMock()
            mock_cls.return_value.messages = MagicMock()
            mock_cls.return_value.messages.create.return_value = MagicMock(
                content=[MagicMock(text=EVAL_JSON)]
            )

            provider = AnthropicProvider(config)
            provider.complete(MESSAGES, MODEL, TIMEOUT)
            provider.complete(MESSAGES, MODEL, TIMEOUT)

        # Anthropic() constructor called exactly once (cold-start caching).
        mock_cls.assert_called_once()


# ---------------------------------------------------------------------------
# OpenAIProvider
# ---------------------------------------------------------------------------


class TestOpenAIProvider:
    def test_complete_returns_text(self):
        """complete() extracts text from the OpenAI chat completion response."""
        from src.providers.openai import OpenAIProvider

        config = _make_config()
        provider = OpenAIProvider(config)

        choice = MagicMock()
        choice.message.content = EVAL_JSON
        mock_response = MagicMock()
        mock_response.choices = [choice]

        with patch.object(provider._client.chat.completions, "create", return_value=mock_response):
            result = provider.complete(MESSAGES, MODEL, TIMEOUT)

        assert result == EVAL_JSON

    def test_auth_error_raises_provider_error(self):
        """openai.AuthenticationError is mapped to ProviderError."""
        import openai

        from src.providers.openai import OpenAIProvider

        config = _make_config()
        provider = OpenAIProvider(config)

        with patch.object(
            provider._client.chat.completions,
            "create",
            side_effect=openai.AuthenticationError(
                message="Bad key",
                response=MagicMock(status_code=401, headers={}),
                body={},
            ),
        ):
            with pytest.raises(ProviderError, match="Authentication"):
                provider.complete(MESSAGES, MODEL, TIMEOUT)

    def test_rate_limit_raises_provider_error(self):
        """openai.RateLimitError is mapped to ProviderError."""
        import openai

        from src.providers.openai import OpenAIProvider

        config = _make_config()
        provider = OpenAIProvider(config)

        with patch.object(
            provider._client.chat.completions,
            "create",
            side_effect=openai.RateLimitError(
                message="Rate limited",
                response=MagicMock(status_code=429, headers={}),
                body={},
            ),
        ):
            with pytest.raises(ProviderError, match="Rate limit"):
                provider.complete(MESSAGES, MODEL, TIMEOUT)

    def test_client_created_once_per_provider_instance(self):
        from src.providers.openai import OpenAIProvider

        config = _make_config()
        with patch("src.providers.openai.openai.OpenAI") as mock_cls:
            mock_client = MagicMock()
            choice = MagicMock()
            choice.message.content = EVAL_JSON
            mock_client.chat.completions.create.return_value = MagicMock(choices=[choice])
            mock_cls.return_value = mock_client

            provider = OpenAIProvider(config)
            provider.complete(MESSAGES, MODEL, TIMEOUT)
            provider.complete(MESSAGES, MODEL, TIMEOUT)

        mock_cls.assert_called_once()


# ---------------------------------------------------------------------------
# BedrockProvider
# ---------------------------------------------------------------------------


class TestBedrockProvider:
    def test_complete_returns_text(self):
        """complete() extracts text from the Bedrock converse response."""
        from src.providers.bedrock import BedrockProvider

        config = _make_config()

        mock_bedrock_client = MagicMock()
        mock_bedrock_client.converse.return_value = {
            "output": {"message": {"content": [{"text": EVAL_JSON}]}}
        }

        with patch("src.providers.bedrock.boto3.client", return_value=mock_bedrock_client):
            provider = BedrockProvider(config)
            result = provider.complete(MESSAGES, MODEL, TIMEOUT)

        assert result == EVAL_JSON

    def test_client_error_raises_provider_error(self):
        """botocore.exceptions.ClientError is mapped to ProviderError."""
        import botocore.exceptions

        from src.providers.bedrock import BedrockProvider

        config = _make_config()

        mock_bedrock_client = MagicMock()
        mock_bedrock_client.converse.side_effect = botocore.exceptions.ClientError(
            error_response={"Error": {"Code": "ThrottlingException", "Message": "Throttled"}},
            operation_name="Converse",
        )

        with patch("src.providers.bedrock.boto3.client", return_value=mock_bedrock_client):
            provider = BedrockProvider(config)
            with pytest.raises(ProviderError, match="Bedrock"):
                provider.complete(MESSAGES, MODEL, TIMEOUT)

    def test_client_created_once_per_provider_instance(self):
        from src.providers.bedrock import BedrockProvider

        config = _make_config()

        with patch("src.providers.bedrock.boto3.client") as mock_boto3:
            mock_client = MagicMock()
            mock_client.converse.return_value = {
                "output": {"message": {"content": [{"text": EVAL_JSON}]}}
            }
            mock_boto3.return_value = mock_client

            provider = BedrockProvider(config)
            provider.complete(MESSAGES, MODEL, TIMEOUT)
            provider.complete(MESSAGES, MODEL, TIMEOUT)

        # boto3.client() called once (cold-start caching).
        mock_boto3.assert_called_once()


# ---------------------------------------------------------------------------
# get_provider() factory and cache
# ---------------------------------------------------------------------------


class TestGetProvider:
    def setup_method(self):
        """Clear the provider cache before each test."""
        import src.providers as providers_mod

        providers_mod._cache.clear()

    def test_unknown_provider_raises_configuration_error(self):
        from src.providers import get_provider

        config = _make_config()
        with pytest.raises(ConfigurationError, match="Unknown provider"):
            get_provider("nonexistent", config)

    def test_provider_cached_across_calls(self):
        """get_provider() returns the same instance on repeated calls."""
        from src.providers import get_provider
        from src.providers.anthropic import AnthropicProvider

        config = _make_config()

        with patch("src.providers.anthropic.anthropic.Anthropic"):
            p1 = get_provider("anthropic", config)
            p2 = get_provider("anthropic", config)

        assert p1 is p2
