"""
Value Objects for the Shared Kernel.

Value objects are immutable objects that are defined by their attributes
rather than their identity. They represent concepts in the domain.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4, UUID
import re


@dataclass(frozen=True)
class EntityId:
    """Base class for entity identifiers."""

    value: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self):
        """Validate entity ID format."""
        if not self.value or not isinstance(self.value, str):
            raise ValueError("Entity ID must be a non-empty string")
        if len(self.value) < 3:
            raise ValueError("Entity ID must be at least 3 characters long")

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.value})"


@dataclass(frozen=True)
class Timestamp:
    """Immutable timestamp value object."""

    value: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        """Ensure timestamp is timezone-aware."""
        if self.value.tzinfo is None:
            object.__setattr__(self, "value", self.value.replace(tzinfo=timezone.utc))

    @property
    def iso_format(self) -> str:
        """Get ISO format string."""
        return self.value.isoformat()

    @property
    def unix_timestamp(self) -> float:
        """Get Unix timestamp."""
        return self.value.timestamp()

    def __str__(self) -> str:
        return self.iso_format


@dataclass(frozen=True)
class Score:
    """Score value object with validation."""

    value: float
    min_value: float = 1.0
    max_value: float = 5.0

    def __post_init__(self):
        """Validate score range."""
        if not isinstance(self.value, (int, float)):
            raise ValueError("Score must be a number")
        if not self.min_value <= self.value <= self.max_value:
            raise ValueError(
                f"Score must be between {self.min_value} and {self.max_value}"
            )

    @property
    def normalized(self) -> float:
        """Get normalized score (0-1 range)."""
        return (self.value - self.min_value) / (self.max_value - self.min_value)

    @property
    def percentage(self) -> float:
        """Get score as percentage."""
        return self.normalized * 100

    def __str__(self) -> str:
        return f"{self.value:.1f}"


@dataclass(frozen=True)
class Confidence:
    """Confidence value object with validation."""

    value: float
    min_value: float = 0.0
    max_value: float = 1.0

    def __post_init__(self):
        """Validate confidence range."""
        if not isinstance(self.value, (int, float)):
            raise ValueError("Confidence must be a number")
        if not self.min_value <= self.value <= self.max_value:
            raise ValueError(
                f"Confidence must be between {self.min_value} and {self.max_value}"
            )

    @property
    def percentage(self) -> float:
        """Get confidence as percentage."""
        return self.value * 100

    @property
    def is_high(self) -> bool:
        """Check if confidence is high (>0.8)."""
        return self.value > 0.8

    @property
    def is_low(self) -> bool:
        """Check if confidence is low (<0.3)."""
        return self.value < 0.3

    def __str__(self) -> str:
        return f"{self.percentage:.1f}%"


@dataclass(frozen=True)
class ModelName:
    """Model name value object with validation."""

    value: str

    def __post_init__(self):
        """Validate model name format."""
        if not self.value or not isinstance(self.value, str):
            raise ValueError("Model name must be a non-empty string")
        if len(self.value) < 2:
            raise ValueError("Model name must be at least 2 characters long")
        if len(self.value) > 100:
            raise ValueError("Model name must be less than 100 characters")
        # Check for valid characters (alphanumeric, hyphens, underscores, dots)
        if not re.match(r"^[a-zA-Z0-9._-]+$", self.value):
            raise ValueError("Model name contains invalid characters")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class ProviderName:
    """Provider name value object with validation."""

    value: str

    VALID_PROVIDERS = {"openai", "anthropic", "bedrock", "mock"}

    def __post_init__(self):
        """Validate provider name."""
        if not self.value or not isinstance(self.value, str):
            raise ValueError("Provider name must be a non-empty string")
        if self.value.lower() not in self.VALID_PROVIDERS:
            raise ValueError(
                f"Provider must be one of: {', '.join(self.VALID_PROVIDERS)}"
            )
        # Normalize to lowercase
        object.__setattr__(self, "value", self.value.lower())

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class EvaluationId(EntityId):
    """Evaluation identifier."""

    pass


@dataclass(frozen=True)
class BatchId(EntityId):
    """Batch identifier."""

    pass


@dataclass(frozen=True)
class SessionId(EntityId):
    """Session identifier."""

    pass


@dataclass(frozen=True)
class CriteriaHash:
    """Hash value object for criteria identification."""

    value: str

    def __post_init__(self):
        """Validate hash format."""
        if not self.value or not isinstance(self.value, str):
            raise ValueError("Criteria hash must be a non-empty string")
        if len(self.value) != 64:  # SHA-256 hash length
            raise ValueError(
                "Criteria hash must be a valid SHA-256 hash (64 characters)"
            )
        if not re.match(r"^[a-f0-9]+$", self.value):
            raise ValueError("Criteria hash must contain only hexadecimal characters")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Weight:
    """Weight value object for criteria weighting."""

    value: float
    min_value: float = 0.0
    max_value: float = 1.0

    def __post_init__(self):
        """Validate weight range."""
        if not isinstance(self.value, (int, float)):
            raise ValueError("Weight must be a number")
        if not self.min_value <= self.value <= self.max_value:
            raise ValueError(
                f"Weight must be between {self.min_value} and {self.max_value}"
            )

    @property
    def percentage(self) -> float:
        """Get weight as percentage."""
        return self.value * 100

    def __str__(self) -> str:
        return f"{self.percentage:.1f}%"


@dataclass(frozen=True)
class Priority:
    """Priority value object for task prioritization."""

    value: int
    min_value: int = 0
    max_value: int = 10

    def __post_init__(self):
        """Validate priority range."""
        if not isinstance(self.value, int):
            raise ValueError("Priority must be an integer")
        if not self.min_value <= self.value <= self.max_value:
            raise ValueError(
                f"Priority must be between {self.min_value} and {self.max_value}"
            )

    @property
    def is_high(self) -> bool:
        """Check if priority is high (>=8)."""
        return self.value >= 8

    @property
    def is_low(self) -> bool:
        """Check if priority is low (<=2)."""
        return self.value <= 2

    def __str__(self) -> str:
        return str(self.value)
