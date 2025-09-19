"""
Unified evaluation criteria system.

Provides a comprehensive framework for defining, parsing, and managing
evaluation criteria from various sources including JSON files and CLI strings.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from abc import ABC, abstractmethod


@dataclass(frozen=True)
class CriterionDefinition:
    """Definition of a single evaluation criterion."""

    name: str
    description: str
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


class CriteriaParser:
    """Parser for criteria definitions from various sources."""

    @staticmethod
    def parse_criteria_string(criteria_string: str) -> List[CriterionDefinition]:
        """
        Parse criteria definition string.

        Format: 'name:description:weight,name2:description2:weight2'
        Example: 'accuracy:Factual correctness:0.4,clarity:How clear the response is:0.3'

        Args:
            criteria_string: String containing criterion definitions

        Returns:
            List of CriterionDefinition objects

        Raises:
            ValueError: If format is invalid or criteria are invalid
        """
        if not criteria_string.strip():
            raise ValueError("Criteria string cannot be empty")

        criteria_definitions = []

        # Split by comma and parse each criterion
        criterion_strings = [s.strip() for s in criteria_string.split(",")]

        for criterion_string in criterion_strings:
            if ":" not in criterion_string:
                raise ValueError(
                    f"Invalid criterion format: '{criterion_string}'. Expected 'name:description:weight'"
                )

            parts = criterion_string.split(":")
            if len(parts) < 3:
                raise ValueError(
                    f"Invalid criterion format: '{criterion_string}'. Expected 'name:description:weight'"
                )

            name = parts[0].strip()
            description = parts[1].strip()
            weight_str = parts[2].strip()

            if not name:
                raise ValueError("Criterion name cannot be empty")
            if not description:
                raise ValueError("Criterion description cannot be empty")

            try:
                weight = float(weight_str)
            except ValueError:
                raise ValueError(
                    f"Invalid weight value for '{name}': '{weight_str}'. Must be a number."
                )

            if weight < 0:
                raise ValueError(f"Weight for '{name}' cannot be negative: {weight}")

            criteria_definitions.append(
                CriterionDefinition(
                    name=name,
                    description=description,
                    weight=weight,
                )
            )

        return criteria_definitions

    @staticmethod
    def parse_criteria_file(
        file_path: Union[str, Path],
    ) -> List[CriterionDefinition]:
        """
        Parse criteria definitions from JSON file.

        Args:
            file_path: Path to JSON file containing criteria definitions

        Returns:
            List of CriterionDefinition objects

        Raises:
            ValueError: If file format is invalid or criteria are invalid
            FileNotFoundError: If file doesn't exist
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Criteria file not found: {file_path}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in criteria file: {e}")

        if not isinstance(data, dict):
            raise ValueError("Criteria file must contain a JSON object")

        if "criteria" not in data:
            raise ValueError("Criteria file must contain a 'criteria' array")

        if not isinstance(data["criteria"], list):
            raise ValueError("'criteria' must be an array")

        criteria_definitions = []
        for i, criterion_data in enumerate(data["criteria"]):
            if not isinstance(criterion_data, dict):
                raise ValueError(f"Criterion {i} must be an object")

            # Validate required fields
            required_fields = ["name", "description"]
            for field in required_fields:
                if field not in criterion_data:
                    raise ValueError(f"Criterion {i} missing required field: {field}")

            # Parse criterion
            try:
                criterion_def = CriterionDefinition(
                    name=criterion_data["name"],
                    description=criterion_data["description"],
                    weight=criterion_data.get("weight", 1.0),
                    evaluation_prompt=criterion_data.get("evaluation_prompt", ""),
                    examples={
                        int(k): v for k, v in criterion_data.get("examples", {}).items()
                    },
                    domain_specific=criterion_data.get("domain_specific", False),
                    requires_context=criterion_data.get("requires_context", False),
                    metadata=criterion_data.get("metadata", {}),
                )
                criteria_definitions.append(criterion_def)
            except Exception as e:
                raise ValueError(f"Error parsing criterion {i}: {e}")

        return criteria_definitions

    @staticmethod
    def parse_unified_config_file(
        file_path: Union[str, Path],
    ) -> tuple[List[CriterionDefinition], Dict[str, Any]]:
        """
        Parse unified configuration file containing both criteria and system configuration.

        Args:
            file_path: Path to JSON file containing unified configuration

        Returns:
            Tuple of (criteria_definitions, config_data)

        Raises:
            ValueError: If file format is invalid or criteria are invalid
            FileNotFoundError: If file doesn't exist
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file: {e}")

        if not isinstance(data, dict):
            raise ValueError("Configuration file must contain a JSON object")

        if "criteria" not in data:
            raise ValueError("Configuration file must contain a 'criteria' array")

        if not isinstance(data["criteria"], list):
            raise ValueError("'criteria' must be an array")

        # Parse criteria
        criteria_definitions = []
        for i, criterion_data in enumerate(data["criteria"]):
            if not isinstance(criterion_data, dict):
                raise ValueError(f"Criterion {i} must be an object")

            # Validate required fields
            required_fields = ["name", "description"]
            for field in required_fields:
                if field not in criterion_data:
                    raise ValueError(f"Criterion {i} missing required field: {field}")

            # Parse criterion
            try:
                criterion_def = CriterionDefinition(
                    name=criterion_data["name"],
                    description=criterion_data["description"],
                    weight=criterion_data.get("weight", 1.0),
                    evaluation_prompt=criterion_data.get("evaluation_prompt", ""),
                    examples={
                        int(k): v for k, v in criterion_data.get("examples", {}).items()
                    },
                    domain_specific=criterion_data.get("domain_specific", False),
                    requires_context=criterion_data.get("requires_context", False),
                    metadata=criterion_data.get("metadata", {}),
                )
                criteria_definitions.append(criterion_def)
            except Exception as e:
                raise ValueError(f"Error parsing criterion {i}: {e}")

        # Extract configuration data (excluding criteria)
        config_data = {k: v for k, v in data.items() if k != "criteria"}

        return criteria_definitions, config_data


class CriteriaBuilder:
    """Builder for creating custom evaluation criteria."""

    def __init__(self):
        self.criteria_definitions: List[CriterionDefinition] = []
        self.name = "Custom Evaluation"
        self.description = "Custom evaluation criteria"

    def add_criterion(
        self,
        name: str,
        description: str,
        weight: float = 1.0,
        evaluation_prompt: str = "",
        examples: Optional[Dict[int, str]] = None,
        domain_specific: bool = False,
        requires_context: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "CriteriaBuilder":
        """Add a custom criterion."""
        self.criteria_definitions.append(
            CriterionDefinition(
                name=name,
                description=description,
                weight=weight,
                evaluation_prompt=evaluation_prompt,
                examples=examples or {},
                domain_specific=domain_specific,
                requires_context=requires_context,
                metadata=metadata or {},
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

    def build(self, normalize_weights: bool = False) -> EvaluationCriteria:
        """Build the evaluation criteria."""
        if not self.criteria_definitions:
            raise ValueError("No criteria defined")

        return EvaluationCriteria(
            criteria=self.criteria_definitions,
            name=self.name,
            description=self.description,
            normalize_weights=normalize_weights,
        )


class DefaultCriteria:
    """Factory for default evaluation criteria sets."""

    @staticmethod
    def balanced() -> EvaluationCriteria:
        """Create balanced default criteria covering all major dimensions with equal weights."""
        criteria = [
            # Factual criteria
            CriterionDefinition(
                name="accuracy",
                description="Factual correctness and truthfulness of the response",
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
            name="Balanced Default Evaluation",
            description="Complete multi-dimensional assessment with equal weights across all criteria",
        )

    @staticmethod
    def default() -> EvaluationCriteria:
        """Load default evaluation criteria from criteria/default.json file."""
        try:
            criteria_definitions, config_data = (
                CriteriaParser.parse_unified_config_file("criteria/default.json")
            )
            builder = CriteriaBuilder()

            # Set name and description from config if available
            if "name" in config_data:
                builder.set_name(config_data["name"])
            if "description" in config_data:
                builder.set_description(config_data["description"])

            for cd in criteria_definitions:
                builder.add_criterion(
                    name=cd.name,
                    description=cd.description,
                    weight=cd.weight,
                    evaluation_prompt=cd.evaluation_prompt,
                    examples=cd.examples,
                    domain_specific=cd.domain_specific,
                    requires_context=cd.requires_context,
                    metadata=cd.metadata,
                )

            return builder.build(normalize_weights=True)
        except Exception as e:
            # Fallback to balanced criteria if default.json is not available
            return DefaultCriteria.balanced()

    @staticmethod
    def basic() -> EvaluationCriteria:
        """Create basic criteria for simple evaluations with equal weights."""
        criteria = [
            CriterionDefinition(
                name="accuracy",
                description="Factual correctness of the response",
                weight=1.0,  # Equal weight - will be normalized to 1/3
            ),
            CriterionDefinition(
                name="clarity",
                description="How clear and understandable the response is",
                weight=1.0,  # Equal weight - will be normalized to 1/3
            ),
            CriterionDefinition(
                name="helpfulness",
                description="How useful the response is for the user",
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
                weight=1.0,  # Equal weight - will be normalized to 1/5
                domain_specific=True,
            ),
            CriterionDefinition(
                name="implementation_feasibility",
                description="Whether proposed solutions are practically implementable",
                weight=1.0,  # Equal weight - will be normalized to 1/5
                domain_specific=True,
            ),
            CriterionDefinition(
                name="best_practices",
                description="Adherence to established best practices and standards",
                weight=1.0,  # Equal weight - will be normalized to 1/5
                domain_specific=True,
            ),
            CriterionDefinition(
                name="completeness",
                description="Thoroughness of technical explanation or solution",
                weight=1.0,  # Equal weight - will be normalized to 1/5
            ),
            CriterionDefinition(
                name="clarity",
                description="Technical clarity and understandability",
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
                weight=1.0,  # Equal weight - will be normalized to 1/5
                domain_specific=True,
            ),
            CriterionDefinition(
                name="engagement",
                description="How engaging and interesting the response is",
                weight=1.0,  # Equal weight - will be normalized to 1/5
                domain_specific=True,
            ),
            CriterionDefinition(
                name="coherence",
                description="Internal consistency and logical flow",
                weight=1.0,  # Equal weight - will be normalized to 1/5
            ),
            CriterionDefinition(
                name="relevance",
                description="Relevance to the original prompt or theme",
                weight=1.0,  # Equal weight - will be normalized to 1/5
            ),
            CriterionDefinition(
                name="style",
                description="Writing style and linguistic quality",
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
    def builder() -> CriteriaBuilder:
        """Create a builder for custom criteria."""
        return CriteriaBuilder()


def create_criteria_template() -> Dict[str, Any]:
    """Create a template for criteria configuration file."""
    return {
        "name": "Custom Evaluation Criteria",
        "description": "Custom evaluation criteria for specific use case",
        "criteria": [
            {
                "name": "accuracy",
                "description": "Factual correctness and truthfulness of the response",
                "weight": 1.0,
                "evaluation_prompt": "Evaluate the factual accuracy of the response. Are the claims correct and verifiable?",
                "examples": {
                    1: "Contains major factual errors or misinformation",
                    2: "Some factual inaccuracies present",
                    3: "Mostly accurate with minor errors",
                    4: "Accurate with no significant factual issues",
                    5: "Completely accurate and well-supported with evidence",
                },
                "domain_specific": False,
                "requires_context": False,
                "metadata": {},
            },
            {
                "name": "clarity",
                "description": "How clear and understandable the response is",
                "weight": 1.0,
                "evaluation_prompt": "Evaluate the clarity and understandability of the response.",
                "examples": {
                    1: "Confusing, unclear, or difficult to understand",
                    2: "Somewhat unclear with areas of confusion",
                    3: "Generally clear with minor unclear points",
                    4: "Clear and well-articulated throughout",
                    5: "Exceptionally clear, concise, and well-explained",
                },
                "domain_specific": False,
                "requires_context": False,
                "metadata": {},
            },
        ],
    }


def save_criteria_template(file_path: Union[str, Path]) -> None:
    """Save a criteria template to file."""
    template = create_criteria_template()
    file_path = Path(file_path)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(template, f, indent=2, ensure_ascii=False)
