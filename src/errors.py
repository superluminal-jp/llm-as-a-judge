"""Exception hierarchy for LLM-as-a-Judge.

Single source of truth for error types across every module, so that failures
propagate with consistent meaning regardless of which workflow step raised them.

All errors are raised, never returned: a step that cannot complete its work
fails its Lambda invocation, which is what lets Step Functions apply its retry
policy and record the failure against the specific state that produced it.
Returning ``{"error": ...}`` would look like success to the state machine.

These types previously lived in ``src/handler.py`` alongside the single-Lambda
entry point. That entry point is gone; the hierarchy moved here so that nothing
imports a module named after a handler that no longer exists.
"""

from __future__ import annotations


class LlmJudgeError(Exception):
    """Base exception for all llm-judge errors."""


class ValidationError(LlmJudgeError):
    """Raised when the input event is invalid (missing fields, bad format)."""


class ConfigurationError(LlmJudgeError):
    """Raised when required environment variables or IAM grants are missing."""


class ProviderError(LlmJudgeError):
    """Raised when an LLM provider API call fails (auth, rate limit, timeout)."""


class CriteriaLoadError(LlmJudgeError):
    """Raised when criteria cannot be loaded from S3 (not found, invalid JSON)."""
