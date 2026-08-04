"""Event validation and model resolution for LLM-as-a-Judge.

Validation runs once per evaluation, in the workflow's prepare step, so that a
malformed request fails before any judge LLM is invoked and before work fans out
across criteria. Rejecting early is what keeps a bad request from costing N
model calls.

These helpers previously lived in ``src/handler.py`` alongside the single-Lambda
entry point that has since been removed. They are public here (no leading
underscore) because they are now a module boundary rather than internals of a
handler.
"""

from __future__ import annotations

from src.errors import ConfigurationError, ValidationError

SUPPORTED_PROVIDERS = frozenset({"anthropic", "openai", "bedrock"})

DESCRIPTOR_MAX_LEN = 256


def _normalize_role_text(raw: object, field: str) -> str:
    """Return stripped role text, or empty string if absent or blank."""
    if raw is None:
        return ""
    if not isinstance(raw, str):
        raise ValidationError(
            f"Event field '{field}' must be a string when provided."
        )
    return raw.strip()


def _normalize_optional_descriptor(raw: object, field: str) -> str | None:
    """Validate optional free-form descriptor; return None if absent or blank."""
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValidationError(
            f"Event field '{field}' must be a string when provided."
        )
    s = raw.strip()
    if not s:
        return None
    if len(s) > DESCRIPTOR_MAX_LEN:
        raise ValidationError(
            f"Event field '{field}' exceeds maximum length {DESCRIPTOR_MAX_LEN}."
        )
    for char in s:
        code = ord(char)
        if code < 32 and char not in "\t\n\r":
            raise ValidationError(
                f"Event field '{field}' contains a disallowed control character."
            )
    return s


def normalize_context(value: object) -> list[str] | None:
    """Normalise the raw ``contexts`` event field to a list of non-empty strings.

    Accepts a bare string (treated as a single-item list) or a list of strings
    (already validated). Empty strings and whitespace-only strings are filtered
    out. Returns ``None`` when the result would be empty.

    Args:
        value: Raw value from the invocation event (string, list, or None).

    Returns:
        A non-empty list of non-empty strings, or ``None`` if nothing remains
        after filtering.
    """
    if value is None:
        return None
    items: list[str] = [value] if isinstance(value, str) else list(value)
    filtered = [s for s in items if s and s.strip()]
    return filtered if filtered else None


def validate_event(event: dict) -> tuple[str, str, str | None, str | None]:
    """Validate the invocation event and return normalised text and descriptors.

    Args:
        event: Raw invocation event dict. See ``contracts/lambda-event.json``.

    Returns:
        ``(prompt_text, response_text, prompt_descriptor, response_descriptor)``.
        Each role text is stripped; may be empty when the other role is present.

    Raises:
        ValidationError: If both roles are empty, types are invalid, or
            descriptors violate length/control-character rules.
    """
    prompt_text = _normalize_role_text(event.get("prompt"), "prompt")
    response_text = _normalize_role_text(event.get("response"), "response")
    if not prompt_text and not response_text:
        raise ValidationError(
            "At least one of 'prompt' or 'response' must be a non-empty string "
            "after trimming whitespace."
        )

    prompt_descriptor = _normalize_optional_descriptor(
        event.get("prompt_descriptor"), "prompt_descriptor"
    )
    response_descriptor = _normalize_optional_descriptor(
        event.get("response_descriptor"), "response_descriptor"
    )

    system_prompt = event.get("system_prompt")
    if system_prompt is not None and not isinstance(system_prompt, str):
        raise ValidationError(
            "Event field 'system_prompt' must be a string when provided."
        )

    contexts = event.get("contexts")
    if contexts is not None:
        if isinstance(contexts, list):
            if not all(isinstance(item, str) for item in contexts):
                raise ValidationError(
                    "Event field 'contexts' must be a list of strings; "
                    "all elements must be strings."
                )
        elif not isinstance(contexts, str):
            raise ValidationError(
                "Event field 'contexts' must be a string or list of strings when provided."
            )

    provider = event.get("provider")
    if provider is not None and provider not in SUPPORTED_PROVIDERS:
        raise ValidationError(
            f"Unsupported provider '{provider}'. "
            f"Valid values: {sorted(SUPPORTED_PROVIDERS)}."
        )

    criteria_file = event.get("criteria_file")
    if criteria_file is not None:
        if not isinstance(criteria_file, str) or not criteria_file.startswith("s3://"):
            raise ValidationError(
                "Field 'criteria_file' must be an S3 URI starting with 's3://'."
            )

    return (prompt_text, response_text, prompt_descriptor, response_descriptor)


def default_model(config, provider_name: str) -> str:
    """Return the default judge model for the given provider.

    Args:
        config: Loaded :class:`~src.config.Config` instance.
        provider_name: Provider identifier (``"anthropic"``, ``"openai"``,
            or ``"bedrock"``).

    Returns:
        Model name string from the matching config field.

    Raises:
        ConfigurationError: If the provider name is unrecognised.
    """
    mapping = {
        "anthropic": config.anthropic_model,
        "openai": config.openai_model,
        "bedrock": config.bedrock_model,
    }
    model = mapping.get(provider_name)
    if not model:
        raise ConfigurationError(
            f"No default model configured for provider '{provider_name}'. "
            f"Set the corresponding *_MODEL environment variable."
        )
    return model
