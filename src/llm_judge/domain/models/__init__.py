"""Domain models for the LLM-as-a-Judge system."""

# For now, we'll import from the models.py file at the parent level
# This maintains backwards compatibility while we transition
from ..models import CandidateResponse, EvaluationResult

__all__ = ["CandidateResponse", "EvaluationResult"]