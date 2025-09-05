"""
Multi-criteria evaluation results and aggregation.

Contains the result models for comprehensive multi-dimensional evaluations.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
import statistics

from .criteria import CriterionDefinition, EvaluationCriteria


@dataclass
class CriterionScore:
    """Score for a single evaluation criterion."""
    
    criterion_name: str
    score: float
    reasoning: str
    confidence: float = 0.0
    
    # Additional metadata
    max_score: int = 5
    min_score: int = 1
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate criterion score."""
        if not self.min_score <= self.score <= self.max_score:
            raise ValueError(f"Score {self.score} must be between {self.min_score} and {self.max_score}")
        if not 0 <= self.confidence <= 1:
            raise ValueError(f"Confidence {self.confidence} must be between 0 and 1")
        if not self.reasoning.strip():
            raise ValueError("Reasoning cannot be empty")
    
    @property
    def normalized_score(self) -> float:
        """Normalize score to 0-1 range."""
        return (self.score - self.min_score) / (self.max_score - self.min_score)
    
    @property
    def weighted_score(self) -> float:
        """Get the weighted score."""
        return self.score * self.weight
    
    @property
    def percentage_score(self) -> float:
        """Get score as percentage."""
        return self.normalized_score * 100


@dataclass 
class AggregatedScore:
    """Aggregated score across multiple criteria."""
    
    overall_score: float
    weighted_score: float
    confidence: float
    
    # Score statistics
    mean_score: float = 0.0
    median_score: float = 0.0
    score_std: float = 0.0
    min_score: float = 0.0
    max_score: float = 0.0
    
    # Weighting information
    total_weight: float = 1.0
    criteria_count: int = 0
    
    def __post_init__(self):
        """Validate aggregated score."""
        if not 1 <= self.overall_score <= 5:
            raise ValueError("Overall score must be between 1 and 5")
        if not 0 <= self.confidence <= 1:
            raise ValueError("Confidence must be between 0 and 1")


@dataclass
class MultiCriteriaResult:
    """Comprehensive result of multi-criteria evaluation."""
    
    # Individual criterion scores
    criterion_scores: List[CriterionScore] = field(default_factory=list)
    
    # Aggregated results
    aggregated: Optional[AggregatedScore] = None
    
    # Evaluation metadata
    criteria_used: Optional[EvaluationCriteria] = None
    evaluation_timestamp: datetime = field(default_factory=datetime.now)
    judge_model: str = "unknown"
    processing_duration: Optional[float] = None
    
    # Overall assessment
    overall_reasoning: str = ""
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate aggregated scores if not provided."""
        if self.criterion_scores and not self.aggregated:
            self.aggregated = self._calculate_aggregated_score()
    
    def _calculate_aggregated_score(self) -> AggregatedScore:
        """Calculate aggregated score from individual criterion scores."""
        if not self.criterion_scores:
            raise ValueError("Cannot calculate aggregated score without criterion scores")
        
        scores = [cs.score for cs in self.criterion_scores]
        weights = [cs.weight for cs in self.criterion_scores]
        confidences = [cs.confidence for cs in self.criterion_scores]
        
        # Calculate weighted score
        weighted_score = sum(score * weight for score, weight in zip(scores, weights))
        total_weight = sum(weights)
        
        if total_weight > 0:
            weighted_score = weighted_score / total_weight
        else:
            weighted_score = sum(scores) / len(scores)
        
        # Calculate statistics
        mean_score = statistics.mean(scores)
        median_score = statistics.median(scores)
        score_std = statistics.stdev(scores) if len(scores) > 1 else 0.0
        min_score = min(scores)
        max_score = max(scores)
        
        # Calculate overall confidence (weighted average)
        if confidences and total_weight > 0:
            overall_confidence = sum(conf * weight for conf, weight in zip(confidences, weights)) / total_weight
        else:
            overall_confidence = statistics.mean(confidences) if confidences else 0.0
        
        return AggregatedScore(
            overall_score=weighted_score,
            weighted_score=weighted_score,
            confidence=overall_confidence,
            mean_score=mean_score,
            median_score=median_score,
            score_std=score_std,
            min_score=min_score,
            max_score=max_score,
            total_weight=total_weight,
            criteria_count=len(self.criterion_scores)
        )
    
    def get_criterion_score(self, criterion_name: str) -> Optional[CriterionScore]:
        """Get score for a specific criterion."""
        return next((cs for cs in self.criterion_scores if cs.criterion_name == criterion_name), None)
    
    def add_criterion_score(self, criterion_score: CriterionScore):
        """Add a criterion score and recalculate aggregated score."""
        # Check for duplicates
        if self.get_criterion_score(criterion_score.criterion_name):
            raise ValueError(f"Criterion '{criterion_score.criterion_name}' already has a score")
        
        self.criterion_scores.append(criterion_score)
        self.aggregated = self._calculate_aggregated_score()
    
    def update_criterion_score(self, criterion_name: str, score: float, reasoning: str, confidence: float = 0.0):
        """Update an existing criterion score."""
        criterion_score = self.get_criterion_score(criterion_name)
        if not criterion_score:
            raise ValueError(f"Criterion '{criterion_name}' not found")
        
        criterion_score.score = score
        criterion_score.reasoning = reasoning
        criterion_score.confidence = confidence
        
        # Recalculate aggregated score
        self.aggregated = self._calculate_aggregated_score()
    
    def get_scores_by_type(self, criterion_type) -> List[CriterionScore]:
        """Get all scores for criteria of a specific type."""
        if not self.criteria_used:
            return []
        
        type_criteria = self.criteria_used.get_criteria_by_type(criterion_type)
        type_names = {c.name for c in type_criteria}
        
        return [cs for cs in self.criterion_scores if cs.criterion_name in type_names]
    
    @property
    def is_complete(self) -> bool:
        """Check if all criteria have been scored."""
        if not self.criteria_used:
            return len(self.criterion_scores) > 0
        
        expected_criteria = {c.name for c in self.criteria_used.criteria}
        actual_criteria = {cs.criterion_name for cs in self.criterion_scores}
        
        return expected_criteria.issubset(actual_criteria)
    
    @property
    def missing_criteria(self) -> List[str]:
        """Get list of criteria that haven't been scored yet."""
        if not self.criteria_used:
            return []
        
        expected_criteria = {c.name for c in self.criteria_used.criteria}
        actual_criteria = {cs.criterion_name for cs in self.criterion_scores}
        
        return list(expected_criteria - actual_criteria)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a comprehensive summary of the evaluation results."""
        summary = {
            "overall_score": self.aggregated.overall_score if self.aggregated else None,
            "confidence": self.aggregated.confidence if self.aggregated else None,
            "criteria_count": len(self.criterion_scores),
            "is_complete": self.is_complete,
            "judge_model": self.judge_model,
            "evaluation_timestamp": self.evaluation_timestamp.isoformat(),
        }
        
        if self.aggregated:
            summary.update({
                "weighted_score": self.aggregated.weighted_score,
                "mean_score": self.aggregated.mean_score,
                "median_score": self.aggregated.median_score,
                "score_std": self.aggregated.score_std,
                "score_range": [self.aggregated.min_score, self.aggregated.max_score],
            })
        
        # Add individual criterion scores
        summary["criterion_scores"] = {}
        for cs in self.criterion_scores:
            summary["criterion_scores"][cs.criterion_name] = {
                "score": cs.score,
                "confidence": cs.confidence,
                "weight": cs.weight,
                "percentage": cs.percentage_score
            }
        
        # Add qualitative insights
        if self.overall_reasoning:
            summary["overall_reasoning"] = self.overall_reasoning
        if self.strengths:
            summary["strengths"] = self.strengths
        if self.weaknesses:
            summary["weaknesses"] = self.weaknesses
        if self.suggestions:
            summary["suggestions"] = self.suggestions
        
        return summary
    
    def to_legacy_format(self) -> Dict[str, Any]:
        """Convert to legacy single-score format for backward compatibility."""
        if not self.aggregated:
            raise ValueError("Cannot convert to legacy format without aggregated score")
        
        return {
            "score": self.aggregated.overall_score,
            "reasoning": self.overall_reasoning or f"Multi-criteria evaluation with {len(self.criterion_scores)} criteria",
            "confidence": self.aggregated.confidence,
            "metadata": {
                "multi_criteria": True,
                "criteria_count": len(self.criterion_scores),
                "weighted_score": self.aggregated.weighted_score,
                "individual_scores": {
                    cs.criterion_name: {"score": cs.score, "reasoning": cs.reasoning}
                    for cs in self.criterion_scores
                }
            }
        }