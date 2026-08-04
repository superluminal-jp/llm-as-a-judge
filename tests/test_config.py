"""Tests for src/config.py — configuration loading and API key resolution.

Covers the environment-variable → Secrets Manager fallback introduced so that
API keys no longer need to live in Lambda environment variables.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from src.errors import ConfigurationError


def _make_config(**overrides):
    from src.config import Config

    kwargs = {
        "default_provider": "bedrock",
        "anthropic_api_key": "",
        "anthropic_model": "claude-sonnet-4-6",
        "openai_api_key": "",
        "openai_model": "gpt-4o",
        "bedrock_model": "jp.anthropic.claude-sonnet-4-6",
        "request_timeout": 30,
        "log_level": "INFO",
        "api_keys_secret_name": "",
    }
    kwargs.update(overrides)
    return Config(**kwargs)


# ---------------------------------------------------------------------------
# _load_config
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_reads_new_environment_variables(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.config import _load_config

        monkeypatch.setenv("API_KEYS_SECRET_NAME", "llm-judge-dev/api-keys")
        monkeypatch.setenv("REQUEST_TIMEOUT", "60")

        config = _load_config()

        assert config.api_keys_secret_name == "llm-judge-dev/api-keys"
        assert config.request_timeout == 60

    def test_defaults_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.config import _load_config

        for name in ("API_KEYS_SECRET_NAME", "REQUEST_TIMEOUT"):
            monkeypatch.delenv(name, raising=False)

        config = _load_config()

        assert config.api_keys_secret_name == ""
        assert config.request_timeout == 30

    def test_invalid_integers_fall_back_to_defaults(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.config import _load_config

        monkeypatch.setenv("REQUEST_TIMEOUT", "")

        config = _load_config()

        assert config.request_timeout == 30



# ---------------------------------------------------------------------------
# get_api_key
# ---------------------------------------------------------------------------


class TestGetApiKey:
    def test_environment_variable_wins(self) -> None:
        from src.config import get_api_key

        config = _make_config(
            anthropic_api_key="from-env", api_keys_secret_name="some-secret"
        )
        with patch("aws_lambda_powertools.utilities.parameters.get_secret") as mock:
            assert get_api_key(config, "anthropic") == "from-env"
        mock.assert_not_called()

    def test_falls_back_to_secrets_manager(self) -> None:
        from src.config import get_api_key

        config = _make_config(api_keys_secret_name="llm-judge-dev/api-keys")
        secret = {"ANTHROPIC_API_KEY": "sk-ant-secret", "OPENAI_API_KEY": ""}
        with patch(
            "aws_lambda_powertools.utilities.parameters.get_secret",
            return_value=secret,
        ) as mock:
            assert get_api_key(config, "anthropic") == "sk-ant-secret"
        mock.assert_called_once_with("llm-judge-dev/api-keys", transform="json")

    def test_bedrock_never_reads_a_secret(self) -> None:
        """Bedrock authenticates with the execution role; no key exists."""
        from src.config import get_api_key

        config = _make_config(api_keys_secret_name="llm-judge-dev/api-keys")
        with patch("aws_lambda_powertools.utilities.parameters.get_secret") as mock:
            assert get_api_key(config, "bedrock") == ""
        mock.assert_not_called()

    def test_no_secret_configured_returns_empty(self) -> None:
        from src.config import get_api_key

        config = _make_config(api_keys_secret_name="")
        with patch("aws_lambda_powertools.utilities.parameters.get_secret") as mock:
            assert get_api_key(config, "openai") == ""
        mock.assert_not_called()

    def test_secret_fetch_failure_is_contained(self) -> None:
        """A Secrets Manager outage must not raise out of key resolution."""
        from src.config import get_api_key

        config = _make_config(api_keys_secret_name="llm-judge-dev/api-keys")
        with patch(
            "aws_lambda_powertools.utilities.parameters.get_secret",
            side_effect=RuntimeError("boom"),
        ):
            assert get_api_key(config, "anthropic") == ""

    def test_non_object_secret_is_rejected(self) -> None:
        from src.config import get_api_key

        config = _make_config(api_keys_secret_name="llm-judge-dev/api-keys")
        with patch(
            "aws_lambda_powertools.utilities.parameters.get_secret",
            return_value=json.dumps("plain string"),
        ):
            assert get_api_key(config, "anthropic") == ""

    def test_missing_key_in_secret_returns_empty(self) -> None:
        from src.config import get_api_key

        config = _make_config(api_keys_secret_name="llm-judge-dev/api-keys")
        with patch(
            "aws_lambda_powertools.utilities.parameters.get_secret",
            return_value={"OPENAI_API_KEY": "sk-openai"},
        ):
            assert get_api_key(config, "anthropic") == ""
            assert get_api_key(config, "openai") == "sk-openai"


# ---------------------------------------------------------------------------
# validate_for_provider
# ---------------------------------------------------------------------------


class TestValidateForProvider:
    def test_bedrock_needs_no_key(self) -> None:
        from src.config import validate_for_provider

        validate_for_provider(_make_config(), "bedrock")

    def test_accepts_key_supplied_by_secret(self) -> None:
        from src.config import validate_for_provider

        config = _make_config(api_keys_secret_name="llm-judge-dev/api-keys")
        with patch(
            "aws_lambda_powertools.utilities.parameters.get_secret",
            return_value={"ANTHROPIC_API_KEY": "sk-ant-secret"},
        ):
            validate_for_provider(config, "anthropic")

    def test_raises_when_no_source_has_the_key(self) -> None:
        from src.config import validate_for_provider

        config = _make_config(api_keys_secret_name="llm-judge-dev/api-keys")
        with patch(
            "aws_lambda_powertools.utilities.parameters.get_secret",
            return_value={"ANTHROPIC_API_KEY": ""},
        ):
            with pytest.raises(ConfigurationError, match="ANTHROPIC_API_KEY"):
                validate_for_provider(config, "anthropic")

    def test_error_message_names_the_secret(self) -> None:
        from src.config import validate_for_provider

        config = _make_config(api_keys_secret_name="llm-judge-prod/api-keys")
        with patch(
            "aws_lambda_powertools.utilities.parameters.get_secret",
            return_value={},
        ):
            with pytest.raises(ConfigurationError, match="llm-judge-prod/api-keys"):
                validate_for_provider(config, "openai")
