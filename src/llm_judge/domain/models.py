"""
Core domain models for the LLM-as-a-Judge system.

Contains the fundamental value objects and entities used throughout the domain layer.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class CandidateResponse:
    """A response from an LLM that needs to be evaluated."""
    
    prompt: str
    response: str
    model: str = "unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate the candidate response."""
        if not self.prompt.strip():
            raise ValueError("Prompt cannot be empty")
        if not self.response.strip():
            raise ValueError("Response cannot be empty")


@dataclass
class EvaluationResult:
    """Result of an LLM evaluation."""
    
    score: float
    reasoning: str
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate the evaluation result."""
        if not 0 <= self.score <= 5:
            raise ValueError("Score must be between 0 and 5")
        if not 0 <= self.confidence <= 1:
            raise ValueError("Confidence must be between 0 and 1")
        if not self.reasoning.strip():
            raise ValueError("Reasoning cannot be empty")