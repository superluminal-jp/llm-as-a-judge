"""
Value Objects for the Evaluation Bounded Context.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional, List
import re

from ..shared_kernel.value_objects import Score, Confidence, Weight


class EvaluationType(Enum):
    """Types of evaluation that can be performed."""

    SINGLE = "single"  # Single response evaluation
    COMPARISON = "comparison"  # Pairwise comparison
    MULTI_CRITERIA = "multi_criteria"  # Multi-criteria evaluation


class EvaluationStatus(Enum):
    """Status of an evaluation."""

    PENDING = "pending"  # Evaluation not started
    IN_PROGRESS = "in_progress"  # Evaluation in progress
    COMPLETED = "completed"  # Evaluation completed successfully
    FAILED = "failed"  # Evaluation failed
    CANCELLED = "cancelled"  # Evaluation was cancelled


@dataclass(frozen=True)
class EvaluationMetadata:
    """Metadata for an evaluation."""

    session_id: Optional[str] = None
    batch_id: Optional[str] = None
    user_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    notes: Optional[str] = None
    custom_attributes: Dict[str, Any] = field(default_factory=dict)

    def add_tag(self, tag: str) -> "EvaluationMetadata":
        """Add a tag to the metadata."""
        if not tag or not isinstance(tag, str):
            raise ValueError("Tag must be a non-empty string")
        if len(tag) > 50:
            raise ValueError("Tag must be less than 50 characters")
        if not re.match(r"^[a-zA-Z0-9_-]+$", tag):
            raise ValueError("Tag contains invalid characters")

        new_tags = list(self.tags)
        if tag not in new_tags:
            new_tags.append(tag)

        return EvaluationMetadata(
            session_id=self.session_id,
            batch_id=self.batch_id,
            user_id=self.user_id,
            tags=new_tags,
            notes=self.notes,
            custom_attributes=self.custom_attributes,
        )

    def remove_tag(self, tag: str) -> "EvaluationMetadata":
        """Remove a tag from the metadata."""
        new_tags = [t for t in self.tags if t != tag]
        return EvaluationMetadata(
            session_id=self.session_id,
            batch_id=self.batch_id,
            user_id=self.user_id,
            tags=new_tags,
            notes=self.notes,
            custom_attributes=self.custom_attributes,
        )

    def set_notes(self, notes: str) -> "EvaluationMetadata":
        """Set notes for the evaluation."""
        if notes and len(notes) > 1000:
            raise ValueError("Notes must be less than 1000 characters")

        return EvaluationMetadata(
            session_id=self.session_id,
            batch_id=self.batch_id,
            user_id=self.user_id,
            tags=self.tags,
            notes=notes,
            custom_attributes=self.custom_attributes,
        )

    def add_custom_attribute(self, key: str, value: Any) -> "EvaluationMetadata":
        """Add a custom attribute."""
        if not key or not isinstance(key, str):
            raise ValueError("Key must be a non-empty string")
        if len(key) > 50:
            raise ValueError("Key must be less than 50 characters")
        if not re.match(r"^[a-zA-Z0-9_-]+$", key):
            raise ValueError("Key contains invalid characters")

        new_attributes = dict(self.custom_attributes)
        new_attributes[key] = value

        return EvaluationMetadata(
            session_id=self.session_id,
            batch_id=self.batch_id,
            user_id=self.user_id,
            tags=self.tags,
            notes=self.notes,
            custom_attributes=new_attributes,
        )


@dataclass(frozen=True)
class EvaluationPrompt:
    """Value object representing an evaluation prompt."""

    text: str
    context: Optional[str] = None
    instructions: Optional[str] = None

    def __post_init__(self):
        """Validate prompt text."""
        if not self.text or not isinstance(self.text, str):
            raise ValueError("Prompt text must be a non-empty string")
        if len(self.text) > 10000:
            raise ValueError("Prompt text must be less than 10000 characters")

        if self.context and len(self.context) > 5000:
            raise ValueError("Context must be less than 5000 characters")

        if self.instructions and len(self.instructions) > 2000:
            raise ValueError("Instructions must be less than 2000 characters")

    @property
    def full_prompt(self) -> str:
        """Get the full prompt with context and instructions."""
        parts = [self.text]

        if self.context:
            parts.insert(0, f"Context: {self.context}")

        if self.instructions:
            parts.append(f"Instructions: {self.instructions}")

        return "\n\n".join(parts)


@dataclass(frozen=True)
class EvaluationResponse:
    """Value object representing a response to be evaluated."""

    text: str
    model: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate response text."""
        if not self.text or not isinstance(self.text, str):
            raise ValueError("Response text must be a non-empty string")
        if len(self.text) > 50000:
            raise ValueError("Response text must be less than 50000 characters")

        if not self.model or not isinstance(self.model, str):
            raise ValueError("Model must be a non-empty string")
        if len(self.model) > 100:
            raise ValueError("Model name must be less than 100 characters")


@dataclass(frozen=True)
class EvaluationCriteria:
    """Value object representing evaluation criteria configuration."""

    name: str
    description: str
    weight: Weight
    scale_min: int = 1
    scale_max: int = 5
    evaluation_prompt: str = ""
    examples: Dict[int, str] = field(default_factory=dict)
    domain_specific: bool = False
    requires_context: bool = False

    def __post_init__(self):
        """Validate criteria configuration."""
        if not self.name or not isinstance(self.name, str):
            raise ValueError("Criteria name must be a non-empty string")
        if len(self.name) > 100:
            raise ValueError("Criteria name must be less than 100 characters")

        if not self.description or not isinstance(self.description, str):
            raise ValueError("Criteria description must be a non-empty string")
        if len(self.description) > 500:
            raise ValueError("Criteria description must be less than 500 characters")

        if not isinstance(self.scale_min, int) or not isinstance(self.scale_max, int):
            raise ValueError("Scale values must be integers")
        if self.scale_min >= self.scale_max:
            raise ValueError("Scale minimum must be less than maximum")
        if self.scale_min < 1 or self.scale_max > 10:
            raise ValueError("Scale values must be between 1 and 10")

        if self.evaluation_prompt and len(self.evaluation_prompt) > 2000:
            raise ValueError("Evaluation prompt must be less than 2000 characters")

        # Validate examples
        for score, example in self.examples.items():
            if not isinstance(score, int):
                raise ValueError("Example scores must be integers")
            if not self.scale_min <= score <= self.scale_max:
                raise ValueError(f"Example score {score} must be within scale range")
            if not isinstance(example, str) or len(example) > 500:
                raise ValueError(
                    "Example text must be a string less than 500 characters"
                )

    @property
    def scale_range(self) -> int:
        """Get the scale range (max - min + 1)."""
        return self.scale_max - self.scale_min + 1

    def get_example_for_score(self, score: int) -> Optional[str]:
        """Get example text for a specific score."""
        return self.examples.get(score)


@dataclass(frozen=True)
class EvaluationResult:
    """Value object representing the result of an evaluation."""

    score: Score
    confidence: Confidence
    reasoning: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate evaluation result."""
        if not self.reasoning or not isinstance(self.reasoning, str):
            raise ValueError("Reasoning must be a non-empty string")
        if len(self.reasoning) > 2000:
            raise ValueError("Reasoning must be less than 2000 characters")

    @property
    def is_high_confidence(self) -> bool:
        """Check if the result has high confidence."""
        return self.confidence.is_high

    @property
    def is_low_confidence(self) -> bool:
        """Check if the result has low confidence."""
        return self.confidence.is_low
