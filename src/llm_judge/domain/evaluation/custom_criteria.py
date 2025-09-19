"""
Custom criteria definition and parsing utilities.

Provides functionality to define, parse, and validate custom evaluation criteria
from various input formats including CLI strings and JSON files.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

from .criteria import CriterionDefinition, CriterionType, EvaluationCriteria


@dataclass
class CustomCriteriaDefinition:
    """Definition for a custom criterion."""

    name: str
    description: str
    criterion_type: str  # Will be converted to CriterionType
    weight: float = 1.0
    evaluation_prompt: str = ""
    examples: Dict[int, str] = field(default_factory=dict)
    domain_specific: bool = False
    requires_context: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_criterion_definition(self) -> CriterionDefinition:
        """Convert to CriterionDefinition."""
        try:
            criterion_type = CriterionType(self.criterion_type.lower())
        except ValueError:
            raise ValueError(f"Invalid criterion type: {self.criterion_type}")

        return CriterionDefinition(
            name=self.name,
            description=self.description,
            criterion_type=criterion_type,
            weight=self.weight,
            evaluation_prompt=self.evaluation_prompt,
            examples=self.examples,
            domain_specific=self.domain_specific,
            requires_context=self.requires_context,
            metadata=self.metadata,
        )


class CustomCriteriaParser:
    """Parser for custom criteria definitions."""

    @staticmethod
    def parse_criteria_string(criteria_string: str) -> List[CustomCriteriaDefinition]:
        """
        Parse criteria definition string.

        Format: 'name:description:type:weight,name2:description2:type2:weight2'
        Example: 'accuracy:Factual correctness:factual:0.4,clarity:How clear the response is:linguistic:0.3'

        Args:
            criteria_string: String containing criterion definitions

        Returns:
            List of CustomCriteriaDefinition objects

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
                    f"Invalid criterion format: '{criterion_string}'. Expected 'name:description:type:weight'"
                )

            parts = criterion_string.split(":")
            if len(parts) < 4:
                raise ValueError(
                    f"Invalid criterion format: '{criterion_string}'. Expected 'name:description:type:weight'"
                )

            name = parts[0].strip()
            description = parts[1].strip()
            criterion_type = parts[2].strip()
            weight_str = parts[3].strip()

            if not name:
                raise ValueError("Criterion name cannot be empty")
            if not description:
                raise ValueError("Criterion description cannot be empty")
            if not criterion_type:
                raise ValueError("Criterion type cannot be empty")

            try:
                weight = float(weight_str)
            except ValueError:
                raise ValueError(
                    f"Invalid weight value for '{name}': '{weight_str}'. Must be a number."
                )

            if weight < 0:
                raise ValueError(f"Weight for '{name}' cannot be negative: {weight}")

            criteria_definitions.append(
                CustomCriteriaDefinition(
                    name=name,
                    description=description,
                    criterion_type=criterion_type,
                    weight=weight,
                )
            )

        return criteria_definitions

    @staticmethod
    def parse_criteria_file(
        file_path: Union[str, Path],
    ) -> List[CustomCriteriaDefinition]:
        """
        Parse criteria definitions from JSON file.

        Args:
            file_path: Path to JSON file containing criteria definitions

        Returns:
            List of CustomCriteriaDefinition objects

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
            required_fields = ["name", "description", "criterion_type"]
            for field in required_fields:
                if field not in criterion_data:
                    raise ValueError(f"Criterion {i} missing required field: {field}")

            # Parse criterion
            try:
                criterion_def = CustomCriteriaDefinition(
                    name=criterion_data["name"],
                    description=criterion_data["description"],
                    criterion_type=criterion_data["criterion_type"],
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


class CustomCriteriaBuilder:
    """Builder for creating custom evaluation criteria."""

    def __init__(self):
        self.criteria_definitions: List[CustomCriteriaDefinition] = []
        self.name = "Custom Evaluation"
        self.description = "Custom evaluation criteria"

    def add_criterion(
        self,
        name: str,
        description: str,
        criterion_type: str,
        weight: float = 1.0,
        evaluation_prompt: str = "",
        examples: Optional[Dict[int, str]] = None,
        domain_specific: bool = False,
        requires_context: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "CustomCriteriaBuilder":
        """Add a custom criterion."""
        self.criteria_definitions.append(
            CustomCriteriaDefinition(
                name=name,
                description=description,
                criterion_type=criterion_type,
                weight=weight,
                evaluation_prompt=evaluation_prompt,
                examples=examples or {},
                domain_specific=domain_specific,
                requires_context=requires_context,
                metadata=metadata or {},
            )
        )
        return self

    def set_name(self, name: str) -> "CustomCriteriaBuilder":
        """Set the criteria collection name."""
        self.name = name
        return self

    def set_description(self, description: str) -> "CustomCriteriaBuilder":
        """Set the criteria collection description."""
        self.description = description
        return self

    def build(self, normalize_weights: bool = False) -> EvaluationCriteria:
        """Build the evaluation criteria."""
        if not self.criteria_definitions:
            raise ValueError("No criteria defined")

        criterion_definitions = [
            cd.to_criterion_definition() for cd in self.criteria_definitions
        ]

        return EvaluationCriteria(
            criteria=criterion_definitions,
            name=self.name,
            description=self.description,
            normalize_weights=normalize_weights,
        )


def get_available_criterion_types() -> List[str]:
    """Get list of available criterion types."""
    return [ct.value for ct in CriterionType]


def create_criteria_template() -> Dict[str, Any]:
    """Create a template for criteria configuration file."""
    return {
        "name": "Custom Evaluation Criteria",
        "description": "Custom evaluation criteria for specific use case",
        "criteria": [
            {
                "name": "accuracy",
                "description": "Factual correctness and truthfulness of the response",
                "criterion_type": "factual",
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
                "criterion_type": "linguistic",
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
