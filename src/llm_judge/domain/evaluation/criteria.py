"""
Evaluation criteria definitions and configurations.

Defines the comprehensive set of evaluation criteria used for assessing
LLM responses across multiple dimensions.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod


class CriterionType(Enum):
    """Types of evaluation criteria."""

    FACTUAL = "factual"  # Factual accuracy, correctness
    QUALITATIVE = "qualitative"  # Subjective quality measures
    STRUCTURAL = "structural"  # Format, organization, structure
    CONTEXTUAL = "contextual"  # Relevance, appropriateness
    LINGUISTIC = "linguistic"  # Language quality, clarity
    ETHICAL = "ethical"  # Safety, bias, appropriateness


@dataclass(frozen=True)
class CriterionDefinition:
    """Definition of a single evaluation criterion."""

    name: str
    description: str
    criterion_type: CriterionType
    weight: float = 1.0
    scale_min: int = 1
    scale_max: int = 5

    # Detailed guidance for judges
    evaluation_prompt: str = ""
    examples: Dict[int, str] = field(default_factory=dict)  # score -> example

    # Metadata
    domain_specific: bool = False
    requires_context: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate criterion definition."""
        if not 0 < self.weight <= 1:
            raise ValueError("Criterion weight must be between 0 and 1")
        if self.scale_min >= self.scale_max:
            raise ValueError("scale_min must be less than scale_max")
        if not self.name.strip():
            raise ValueError("Criterion name cannot be empty")


@dataclass
class EvaluationCriteria:
    """Collection of evaluation criteria for comprehensive assessment."""

    criteria: List[CriterionDefinition] = field(default_factory=list)
    name: str = "Default Evaluation"
    description: str = "Comprehensive multi-criteria evaluation"

    # Aggregation settings
    normalize_weights: bool = True
    minimum_criteria: int = 1

    def __post_init__(self):
        """Validate and normalize criteria collection."""
        if len(self.criteria) < self.minimum_criteria:
            raise ValueError(f"Must have at least {self.minimum_criteria} criteria")

        if self.normalize_weights:
            self._normalize_weights()

    def _normalize_weights(self):
        """Normalize weights to sum to 1.0."""
        total_weight = sum(c.weight for c in self.criteria)
        if total_weight > 0 and abs(total_weight - 1.0) > 1e-6:
            # Create new criterion definitions with normalized weights
            normalized_criteria = []
            for criterion in self.criteria:
                normalized_weight = criterion.weight / total_weight
                # Create a new instance with normalized weight using object.__setattr__ for frozen dataclass
                new_criterion = CriterionDefinition(
                    name=criterion.name,
                    description=criterion.description,
                    criterion_type=criterion.criterion_type,
                    weight=normalized_weight,
                    scale_min=criterion.scale_min,
                    scale_max=criterion.scale_max,
                    evaluation_prompt=criterion.evaluation_prompt,
                    examples=criterion.examples,
                    domain_specific=criterion.domain_specific,
                    requires_context=criterion.requires_context,
                    metadata=criterion.metadata,
                )
                normalized_criteria.append(new_criterion)

            # Replace criteria with normalized versions
            object.__setattr__(self, "criteria", normalized_criteria)

    def get_criterion(self, name: str) -> Optional[CriterionDefinition]:
        """Get criterion by name."""
        return next((c for c in self.criteria if c.name == name), None)

    def add_criterion(self, criterion: CriterionDefinition):
        """Add a new criterion."""
        if self.get_criterion(criterion.name):
            raise ValueError(f"Criterion '{criterion.name}' already exists")
        self.criteria.append(criterion)
        if self.normalize_weights:
            self._normalize_weights()

    def remove_criterion(self, name: str) -> bool:
        """Remove criterion by name."""
        criterion = self.get_criterion(name)
        if criterion:
            self.criteria.remove(criterion)
            if self.normalize_weights:
                self._normalize_weights()
            return True
        return False

    @property
    def total_weight(self) -> float:
        """Total weight of all criteria."""
        return sum(c.weight for c in self.criteria)

    def get_criteria_by_type(
        self, criterion_type: CriterionType
    ) -> List[CriterionDefinition]:
        """Get all criteria of a specific type."""
        return [c for c in self.criteria if c.criterion_type == criterion_type]


class DefaultCriteria:
    """Factory for default evaluation criteria sets."""

    @staticmethod
    def comprehensive() -> EvaluationCriteria:
        """Create comprehensive default criteria covering all major dimensions with equal weights."""
        criteria = [
            # Factual criteria
            CriterionDefinition(
                name="accuracy",
                description="Factual correctness and truthfulness of the response",
                criterion_type=CriterionType.FACTUAL,
                weight=1.0,  # Equal weight - will be normalized to 1/7
                evaluation_prompt="Evaluate the factual accuracy of the response. Are the claims correct and verifiable?",
                examples={
                    1: "Contains major factual errors or misinformation",
                    2: "Some factual inaccuracies present",
                    3: "Mostly accurate with minor errors",
                    4: "Accurate with no significant factual issues",
                    5: "Completely accurate and well-supported with evidence",
                },
            ),
            # Qualitative criteria
            CriterionDefinition(
                name="completeness",
                description="How thoroughly the response addresses all aspects of the question",
                criterion_type=CriterionType.QUALITATIVE,
                weight=1.0,  # Equal weight - will be normalized to 1/7
                evaluation_prompt="Assess how completely the response addresses all aspects of the original question or prompt.",
                examples={
                    1: "Addresses very few aspects of the question",
                    2: "Covers some but misses important aspects",
                    3: "Addresses most aspects adequately",
                    4: "Comprehensive coverage with minor gaps",
                    5: "Thoroughly addresses all aspects with appropriate depth",
                },
            ),
            # Linguistic criteria
            CriterionDefinition(
                name="clarity",
                description="How clear, understandable, and well-articulated the response is",
                criterion_type=CriterionType.LINGUISTIC,
                weight=1.0,  # Equal weight - will be normalized to 1/7
                evaluation_prompt="Evaluate the clarity and understandability of the response. Is it well-articulated and easy to follow?",
                examples={
                    1: "Confusing, unclear, or difficult to understand",
                    2: "Somewhat unclear with areas of confusion",
                    3: "Generally clear with minor unclear points",
                    4: "Clear and well-articulated throughout",
                    5: "Exceptionally clear, concise, and well-explained",
                },
            ),
            # Contextual criteria
            CriterionDefinition(
                name="relevance",
                description="How well the response relates to and addresses the original prompt",
                criterion_type=CriterionType.CONTEXTUAL,
                weight=1.0,  # Equal weight - will be normalized to 1/7
                evaluation_prompt="Assess how relevant the response is to the original question or prompt.",
                examples={
                    1: "Largely irrelevant or off-topic",
                    2: "Somewhat relevant but with significant tangents",
                    3: "Generally relevant with minor deviations",
                    4: "Highly relevant and on-topic",
                    5: "Perfectly relevant and directly addresses the prompt",
                },
            ),
            # Qualitative criteria
            CriterionDefinition(
                name="helpfulness",
                description="How useful and actionable the response is for the user",
                criterion_type=CriterionType.QUALITATIVE,
                weight=1.0,  # Equal weight - will be normalized to 1/7
                evaluation_prompt="Evaluate how helpful and useful this response would be for someone seeking this information.",
                examples={
                    1: "Not helpful or potentially misleading",
                    2: "Limited helpfulness",
                    3: "Moderately helpful",
                    4: "Very helpful and useful",
                    5: "Exceptionally helpful with actionable insights",
                },
            ),
            # Structural criteria
            CriterionDefinition(
                name="coherence",
                description="Logical flow and consistency of ideas throughout the response",
                criterion_type=CriterionType.STRUCTURAL,
                weight=1.0,  # Equal weight - will be normalized to 1/7
                evaluation_prompt="Assess the logical flow and coherence of ideas in the response.",
                examples={
                    1: "Incoherent or contradictory",
                    2: "Some logical inconsistencies",
                    3: "Generally coherent with minor issues",
                    4: "Logically consistent and well-structured",
                    5: "Perfectly coherent with excellent logical flow",
                },
            ),
            # Linguistic criteria
            CriterionDefinition(
                name="appropriateness",
                description="Suitability of tone, style, and content for the context and audience",
                criterion_type=CriterionType.ETHICAL,
                weight=1.0,  # Equal weight - will be normalized to 1/7
                evaluation_prompt="Evaluate whether the tone, style, and content are appropriate for the context.",
                examples={
                    1: "Inappropriate tone or content",
                    2: "Somewhat inappropriate for context",
                    3: "Generally appropriate",
                    4: "Well-suited for the context",
                    5: "Perfectly appropriate and well-calibrated",
                },
            ),
        ]

        return EvaluationCriteria(
            criteria=criteria,
            name="Comprehensive Default Evaluation",
            description="Complete multi-dimensional assessment with equal weights across all criteria",
        )

    @staticmethod
    def basic() -> EvaluationCriteria:
        """Create basic criteria for simple evaluations with equal weights."""
        criteria = [
            CriterionDefinition(
                name="accuracy",
                description="Factual correctness of the response",
                criterion_type=CriterionType.FACTUAL,
                weight=1.0,  # Equal weight - will be normalized to 1/3
            ),
            CriterionDefinition(
                name="clarity",
                description="How clear and understandable the response is",
                criterion_type=CriterionType.LINGUISTIC,
                weight=1.0,  # Equal weight - will be normalized to 1/3
            ),
            CriterionDefinition(
                name="helpfulness",
                description="How useful the response is for the user",
                criterion_type=CriterionType.QUALITATIVE,
                weight=1.0,  # Equal weight - will be normalized to 1/3
            ),
        ]

        return EvaluationCriteria(
            criteria=criteria,
            name="Basic Evaluation",
            description="Simple three-dimensional assessment with equal weights across all criteria",
        )

    @staticmethod
    def technical() -> EvaluationCriteria:
        """Create criteria optimized for technical content evaluation with equal weights."""
        criteria = [
            CriterionDefinition(
                name="technical_accuracy",
                description="Correctness of technical information and concepts",
                criterion_type=CriterionType.FACTUAL,
                weight=1.0,  # Equal weight - will be normalized to 1/5
                domain_specific=True,
            ),
            CriterionDefinition(
                name="implementation_feasibility",
                description="Whether proposed solutions are practically implementable",
                criterion_type=CriterionType.CONTEXTUAL,
                weight=1.0,  # Equal weight - will be normalized to 1/5
                domain_specific=True,
            ),
            CriterionDefinition(
                name="best_practices",
                description="Adherence to established best practices and standards",
                criterion_type=CriterionType.QUALITATIVE,
                weight=1.0,  # Equal weight - will be normalized to 1/5
                domain_specific=True,
            ),
            CriterionDefinition(
                name="completeness",
                description="Thoroughness of technical explanation or solution",
                criterion_type=CriterionType.QUALITATIVE,
                weight=1.0,  # Equal weight - will be normalized to 1/5
            ),
            CriterionDefinition(
                name="clarity",
                description="Technical clarity and understandability",
                criterion_type=CriterionType.LINGUISTIC,
                weight=1.0,  # Equal weight - will be normalized to 1/5
            ),
        ]

        return EvaluationCriteria(
            criteria=criteria,
            name="Technical Evaluation",
            description="Specialized evaluation for technical content with equal weights across all criteria",
        )

    @staticmethod
    def creative() -> EvaluationCriteria:
        """Create criteria for creative and subjective content with equal weights."""
        criteria = [
            CriterionDefinition(
                name="creativity",
                description="Originality and creative value of the response",
                criterion_type=CriterionType.QUALITATIVE,
                weight=1.0,  # Equal weight - will be normalized to 1/5
                domain_specific=True,
            ),
            CriterionDefinition(
                name="engagement",
                description="How engaging and interesting the response is",
                criterion_type=CriterionType.QUALITATIVE,
                weight=1.0,  # Equal weight - will be normalized to 1/5
                domain_specific=True,
            ),
            CriterionDefinition(
                name="coherence",
                description="Internal consistency and logical flow",
                criterion_type=CriterionType.STRUCTURAL,
                weight=1.0,  # Equal weight - will be normalized to 1/5
            ),
            CriterionDefinition(
                name="relevance",
                description="Relevance to the original prompt or theme",
                criterion_type=CriterionType.CONTEXTUAL,
                weight=1.0,  # Equal weight - will be normalized to 1/5
            ),
            CriterionDefinition(
                name="style",
                description="Writing style and linguistic quality",
                criterion_type=CriterionType.LINGUISTIC,
                weight=1.0,  # Equal weight - will be normalized to 1/5
                domain_specific=True,
            ),
        ]

        return EvaluationCriteria(
            criteria=criteria,
            name="Creative Evaluation",
            description="Evaluation framework for creative and artistic content with equal weights across all criteria",
        )

    @staticmethod
    def builder() -> "CriteriaBuilder":
        """Create a builder for custom criteria."""
        return CriteriaBuilder()


class CriteriaBuilder:
    """Builder pattern for creating custom evaluation criteria."""

    def __init__(self):
        self.criteria: List[CriterionDefinition] = []
        self.name = "Custom Evaluation"
        self.description = "Custom evaluation criteria"

    def add_factual_criterion(
        self, name: str, description: str, weight: float = 1.0
    ) -> "CriteriaBuilder":
        """Add a factual accuracy criterion."""
        self.criteria.append(
            CriterionDefinition(
                name=name,
                description=description,
                criterion_type=CriterionType.FACTUAL,
                weight=weight,
            )
        )
        return self

    def add_quality_criterion(
        self, name: str, description: str, weight: float = 1.0
    ) -> "CriteriaBuilder":
        """Add a qualitative criterion."""
        self.criteria.append(
            CriterionDefinition(
                name=name,
                description=description,
                criterion_type=CriterionType.QUALITATIVE,
                weight=weight,
            )
        )
        return self

    def add_linguistic_criterion(
        self, name: str, description: str, weight: float = 1.0
    ) -> "CriteriaBuilder":
        """Add a linguistic quality criterion."""
        self.criteria.append(
            CriterionDefinition(
                name=name,
                description=description,
                criterion_type=CriterionType.LINGUISTIC,
                weight=weight,
            )
        )
        return self

    def set_name(self, name: str) -> "CriteriaBuilder":
        """Set the criteria collection name."""
        self.name = name
        return self

    def set_description(self, description: str) -> "CriteriaBuilder":
        """Set the criteria collection description."""
        self.description = description
        return self

    def build(self) -> EvaluationCriteria:
        """Build the evaluation criteria."""
        return EvaluationCriteria(
            criteria=self.criteria.copy(), name=self.name, description=self.description
        )
