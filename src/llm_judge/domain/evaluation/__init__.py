"""
Evaluation domain models for comprehensive multi-criteria assessment.

This module contains the core evaluation logic and criteria definitions
for the LLM-as-a-Judge system.
"""

from .criteria import EvaluationCriteria, CriterionDefinition, DefaultCriteria
from .results import MultiCriteriaResult, CriterionScore, AggregatedScore

__all__ = [
    "EvaluationCriteria",
    "CriterionDefinition", 
    "DefaultCriteria",
    "MultiCriteriaResult",
    "CriterionScore",
    "AggregatedScore"
]