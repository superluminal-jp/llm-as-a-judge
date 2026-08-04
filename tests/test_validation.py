"""Tests for src/validation.py — event validation and model resolution.

These exercise the validation functions directly. They previously reached them
through the single-Lambda `lambda_handler`, which meant mocking a provider and an
evaluator just to assert that a malformed field is rejected. Testing the
boundary directly is both simpler and more precise about what is being checked.

Validation runs once per evaluation, in the workflow's prepare step, so a bad
request is rejected before any judge LLM is invoked — these tests are what keep
that guarantee honest.
"""

from __future__ import annotations

import pytest

from src.errors import ConfigurationError, ValidationError
from src.validation import (
    DESCRIPTOR_MAX_LEN,
    SUPPORTED_PROVIDERS,
    default_model,
    normalize_context,
    validate_event,
)


def _config(**overrides):
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
    }
    kwargs.update(overrides)
    return Config(**kwargs)


# ---------------------------------------------------------------------------
# Role text: at least one side must carry content
# ---------------------------------------------------------------------------


class TestRoleText:
    def test_both_roles_present(self) -> None:
        prompt, response, _, _ = validate_event({"prompt": "Q?", "response": "A."})
        assert (prompt, response) == ("Q?", "A.")

    def test_prompt_only_is_allowed(self) -> None:
        prompt, response, _, _ = validate_event({"prompt": "Q?"})
        assert (prompt, response) == ("Q?", "")

    def test_response_only_is_allowed(self) -> None:
        prompt, response, _, _ = validate_event({"response": "A."})
        assert (prompt, response) == ("", "A.")

    def test_whitespace_prompt_allowed_when_response_present(self) -> None:
        prompt, response, _, _ = validate_event({"prompt": "   ", "response": "A."})
        assert (prompt, response) == ("", "A.")

    def test_role_text_is_stripped(self) -> None:
        prompt, response, _, _ = validate_event(
            {"prompt": "  Q?  ", "response": "\n A. \t"}
        )
        assert (prompt, response) == ("Q?", "A.")

    def test_both_empty_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="At least one"):
            validate_event({"prompt": "", "response": ""})

    def test_both_whitespace_only_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="At least one"):
            validate_event({"prompt": "  \t", "response": "\n"})

    def test_missing_both_keys_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="At least one"):
            validate_event({})

    @pytest.mark.parametrize("field", ["prompt", "response"])
    @pytest.mark.parametrize("value", [123, 4.5, ["a"], {"a": 1}, True])
    def test_non_string_role_is_rejected(self, field: str, value: object) -> None:
        event = {"prompt": "Q?", "response": "A.", field: value}
        with pytest.raises(ValidationError, match="must be a string"):
            validate_event(event)


# ---------------------------------------------------------------------------
# Operator descriptors
# ---------------------------------------------------------------------------


class TestDescriptors:
    def test_descriptors_are_returned_stripped(self) -> None:
        _, _, prompt_d, response_d = validate_event(
            {
                "prompt": "Q?",
                "response": "A.",
                "prompt_descriptor": "  note A  ",
                "response_descriptor": "note B",
            }
        )
        assert (prompt_d, response_d) == ("note A", "note B")

    def test_absent_descriptors_are_none(self) -> None:
        _, _, prompt_d, response_d = validate_event({"prompt": "Q?"})
        assert prompt_d is None and response_d is None

    def test_blank_descriptor_becomes_none(self) -> None:
        _, _, prompt_d, _ = validate_event(
            {"prompt": "Q?", "prompt_descriptor": "   "}
        )
        assert prompt_d is None

    def test_at_max_length_is_accepted(self) -> None:
        _, _, prompt_d, _ = validate_event(
            {"prompt": "Q?", "prompt_descriptor": "x" * DESCRIPTOR_MAX_LEN}
        )
        assert prompt_d is not None and len(prompt_d) == DESCRIPTOR_MAX_LEN

    def test_over_max_length_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="maximum length"):
            validate_event(
                {"prompt": "Q?", "prompt_descriptor": "x" * (DESCRIPTOR_MAX_LEN + 1)}
            )

    def test_control_character_is_rejected(self) -> None:
        """Descriptors land in the judge prompt; control bytes must not."""
        with pytest.raises(ValidationError, match="control character"):
            validate_event({"prompt": "Q?", "prompt_descriptor": "bad\x00value"})

    @pytest.mark.parametrize("whitespace", ["\t", "\n", "\r"])
    def test_tab_and_newline_are_permitted(self, whitespace: str) -> None:
        _, _, prompt_d, _ = validate_event(
            {"prompt": "Q?", "prompt_descriptor": f"line1{whitespace}line2"}
        )
        assert prompt_d is not None

    def test_non_string_descriptor_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="must be a string"):
            validate_event({"prompt": "Q?", "prompt_descriptor": 42})


# ---------------------------------------------------------------------------
# system_prompt / contexts / provider / criteria_file
# ---------------------------------------------------------------------------


class TestSystemPrompt:
    def test_string_is_accepted(self) -> None:
        validate_event({"prompt": "Q?", "system_prompt": "You are an expert."})

    def test_empty_string_is_accepted(self) -> None:
        validate_event({"prompt": "Q?", "system_prompt": ""})

    @pytest.mark.parametrize("value", [123, ["a"], {"a": 1}])
    def test_non_string_is_rejected(self, value: object) -> None:
        with pytest.raises(ValidationError, match="system_prompt"):
            validate_event({"prompt": "Q?", "system_prompt": value})


class TestContextsField:
    def test_string_is_accepted(self) -> None:
        validate_event({"prompt": "Q?", "contexts": "one document"})

    def test_list_of_strings_is_accepted(self) -> None:
        validate_event({"prompt": "Q?", "contexts": ["doc1", "doc2"]})

    @pytest.mark.parametrize("value", [123, {"a": 1}])
    def test_wrong_type_is_rejected(self, value: object) -> None:
        with pytest.raises(ValidationError, match="contexts"):
            validate_event({"prompt": "Q?", "contexts": value})

    def test_list_with_non_string_element_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="list of strings"):
            validate_event({"prompt": "Q?", "contexts": ["ok", 42]})


class TestProviderField:
    @pytest.mark.parametrize("provider", sorted(SUPPORTED_PROVIDERS))
    def test_supported_providers_accepted(self, provider: str) -> None:
        validate_event({"prompt": "Q?", "provider": provider})

    def test_unknown_provider_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Unsupported provider"):
            validate_event({"prompt": "Q?", "provider": "gemini"})

    def test_absent_provider_is_allowed(self) -> None:
        """Omitting it falls back to DEFAULT_PROVIDER downstream."""
        validate_event({"prompt": "Q?"})


class TestCriteriaFileField:
    def test_s3_uri_is_accepted(self) -> None:
        validate_event({"prompt": "Q?", "criteria_file": "s3://bucket/key.json"})

    @pytest.mark.parametrize(
        "value", ["https://example.com/c.json", "/local/path.json", "bucket/key", 42]
    )
    def test_non_s3_uri_is_rejected(self, value: object) -> None:
        with pytest.raises(ValidationError, match="S3 URI"):
            validate_event({"prompt": "Q?", "criteria_file": value})


# ---------------------------------------------------------------------------
# normalize_context
# ---------------------------------------------------------------------------


class TestNormalizeContext:
    def test_none_returns_none(self) -> None:
        assert normalize_context(None) is None

    def test_empty_string_returns_none(self) -> None:
        assert normalize_context("") is None

    def test_whitespace_only_string_returns_none(self) -> None:
        assert normalize_context("   ") is None

    def test_string_becomes_single_item_list(self) -> None:
        assert normalize_context("one") == ["one"]

    def test_empty_list_returns_none(self) -> None:
        assert normalize_context([]) is None

    def test_all_blank_entries_return_none(self) -> None:
        assert normalize_context(["", "  ", "\n"]) is None

    def test_blank_entries_are_filtered_out(self) -> None:
        assert normalize_context(["a", "", "  ", "b"]) == ["a", "b"]

    def test_list_of_strings_passes_through(self) -> None:
        assert normalize_context(["a", "b"]) == ["a", "b"]


# ---------------------------------------------------------------------------
# default_model
# ---------------------------------------------------------------------------


class TestDefaultModel:
    @pytest.mark.parametrize(
        ("provider", "expected"),
        [
            ("anthropic", "claude-sonnet-4-6"),
            ("openai", "gpt-4o"),
            ("bedrock", "jp.anthropic.claude-sonnet-4-6"),
        ],
    )
    def test_returns_provider_specific_default(
        self, provider: str, expected: str
    ) -> None:
        assert default_model(_config(), provider) == expected

    def test_unknown_provider_is_a_configuration_error(self) -> None:
        with pytest.raises(ConfigurationError, match="No default model"):
            default_model(_config(), "gemini")

    def test_blank_model_is_a_configuration_error(self) -> None:
        with pytest.raises(ConfigurationError, match="_MODEL"):
            default_model(_config(openai_model=""), "openai")
