"""
Weight configuration utilities for multi-criteria evaluation.

Provides functionality to parse, validate, and apply custom weight configurations
for evaluation criteria.
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from .criteria import EvaluationCriteria, CriterionDefinition


@dataclass
class WeightConfig:
    """Configuration for custom criteria weights."""

    weights: Dict[str, float]
    normalize: bool = True

    def __post_init__(self):
        """Validate weight configuration."""
        if not self.weights:
            raise ValueError("Weight configuration cannot be empty")

        # Validate weight values
        for criterion_name, weight in self.weights.items():
            if not isinstance(weight, (int, float)):
                raise ValueError(f"Weight for '{criterion_name}' must be a number")
            if weight < 0:
                raise ValueError(f"Weight for '{criterion_name}' cannot be negative")

        # Normalize if requested
        if self.normalize:
            self._normalize_weights()

    def _normalize_weights(self):
        """Normalize weights to sum to 1.0."""
        total_weight = sum(self.weights.values())
        if total_weight > 0:
            self.weights = {
                name: weight / total_weight for name, weight in self.weights.items()
            }

    def get_weight(self, criterion_name: str) -> float:
        """Get weight for a specific criterion."""
        return self.weights.get(criterion_name, 0.0)

    def has_criterion(self, criterion_name: str) -> bool:
        """Check if criterion has a custom weight."""
        return criterion_name in self.weights


class WeightConfigParser:
    """Parser for weight configuration strings."""

    @staticmethod
    def parse_weight_string(weight_string: str) -> WeightConfig:
        """
        Parse weight configuration string.

        Format: 'criterion1:weight1,criterion2:weight2'
        Example: 'accuracy:0.3,clarity:0.2,helpfulness:0.5'

        Args:
            weight_string: String containing criterion:weight pairs

        Returns:
            WeightConfig object with parsed weights

        Raises:
            ValueError: If format is invalid or weights are invalid
        """
        if not weight_string.strip():
            raise ValueError("Weight string cannot be empty")

        weights = {}

        # Split by comma and parse each pair
        pairs = [pair.strip() for pair in weight_string.split(",")]

        for pair in pairs:
            if ":" not in pair:
                raise ValueError(
                    f"Invalid weight pair format: '{pair}'. Expected 'criterion:weight'"
                )

            criterion_name, weight_str = pair.split(":", 1)
            criterion_name = criterion_name.strip()
            weight_str = weight_str.strip()

            if not criterion_name:
                raise ValueError("Criterion name cannot be empty")

            try:
                weight = float(weight_str)
            except ValueError:
                raise ValueError(
                    f"Invalid weight value for '{criterion_name}': '{weight_str}'. Must be a number."
                )

            if weight < 0:
                raise ValueError(
                    f"Weight for '{criterion_name}' cannot be negative: {weight}"
                )

            weights[criterion_name] = weight

        return WeightConfig(weights=weights)

    @staticmethod
    def create_equal_weights(criteria_names: List[str]) -> WeightConfig:
        """
        Create equal weights for all criteria.

        Args:
            criteria_names: List of criterion names

        Returns:
            WeightConfig with equal weights for all criteria
        """
        if not criteria_names:
            raise ValueError("Criteria names list cannot be empty")

        equal_weight = 1.0 / len(criteria_names)
        weights = {name: equal_weight for name in criteria_names}

        return WeightConfig(weights=weights, normalize=False)


class CriteriaWeightApplier:
    """Applies weight configurations to evaluation criteria."""

    @staticmethod
    def apply_weights(
        criteria: EvaluationCriteria, weight_config: Optional[WeightConfig] = None
    ) -> EvaluationCriteria:
        """
        Apply custom weights to evaluation criteria.

        Args:
            criteria: Original evaluation criteria
            weight_config: Custom weight configuration (optional)

        Returns:
            New EvaluationCriteria with applied weights

        Raises:
            ValueError: If weight config references non-existent criteria
        """
        if weight_config is None:
            return criteria

        # Validate that all weight config criteria exist
        existing_criteria_names = {c.name for c in criteria.criteria}
        for criterion_name in weight_config.weights.keys():
            if criterion_name not in existing_criteria_names:
                raise ValueError(
                    f"Criterion '{criterion_name}' in weight config not found in criteria. "
                    f"Available criteria: {', '.join(existing_criteria_names)}"
                )

        # Create new criteria with updated weights
        new_criteria = []
        for criterion in criteria.criteria:
            new_weight = weight_config.get_weight(criterion.name)

            # Create new criterion with updated weight
            new_criterion = CriterionDefinition(
                name=criterion.name,
                description=criterion.description,
                weight=new_weight,
                scale_min=criterion.scale_min,
                scale_max=criterion.scale_max,
                evaluation_prompt=criterion.evaluation_prompt,
                examples=criterion.examples,
                domain_specific=criterion.domain_specific,
                requires_context=criterion.requires_context,
                metadata=criterion.metadata,
            )
            new_criteria.append(new_criterion)

        # Create new EvaluationCriteria with updated weights
        return EvaluationCriteria(
            criteria=new_criteria,
            name=criteria.name,
            description=criteria.description,
            normalize_weights=False,  # Weights are already normalized in WeightConfig
        )

    @staticmethod
    def get_available_criteria_names(criteria_type: str = "default") -> List[str]:
        """
        Get available criteria names for a given criteria type.

        Args:
            criteria_type: Type of criteria ('default', 'balanced', 'basic', 'technical', 'creative')

        Returns:
            List of criterion names
        """
        from .criteria import DefaultCriteria

        # Try to load from criteria file first
        if criteria_type.endswith('.json'):
            from pathlib import Path
            criteria_file_path = Path(criteria_type)
            if criteria_file_path.exists():
                from ..presentation.cli.main import load_unified_config
                custom_criteria, config_data = load_unified_config(criteria_file_path)
                if custom_criteria:
                    criteria = custom_criteria
                else:
                    raise ValueError(f"Could not load criteria from file: {criteria_type}")
            else:
                raise ValueError(f"Criteria file not found: {criteria_type}")
        else:
            # Try to find in criteria directory
            from pathlib import Path
            criteria_file_path = Path(f"criteria/{criteria_type}.json")
            if criteria_file_path.exists():
                from ..presentation.cli.main import load_unified_config
                custom_criteria, config_data = load_unified_config(criteria_file_path)
                if custom_criteria:
                    criteria = custom_criteria
                else:
                    raise ValueError(f"Could not load criteria from file: {criteria_type}")
            else:
                # Fall back to predefined types
                if criteria_type == "default":
                    criteria = DefaultCriteria.default()
                elif criteria_type == "balanced":
                    criteria = DefaultCriteria.balanced()
                elif criteria_type == "basic":
                    criteria = DefaultCriteria.basic()
                elif criteria_type == "technical":
                    criteria = DefaultCriteria.technical()
                elif criteria_type == "creative":
                    criteria = DefaultCriteria.creative()
                else:
                    raise ValueError(f"Unknown criteria type: {criteria_type}")

        return [c.name for c in criteria.criteria]


def format_weight_config_help(criteria_type: str = "default") -> str:
    """
    Generate help text for weight configuration.

    Args:
        criteria_type: Type of criteria to show help for

    Returns:
        Formatted help text
    """
    try:
        criteria_names = CriteriaWeightApplier.get_available_criteria_names(
            criteria_type
        )

        help_text = f"Available criteria for '{criteria_type}' type:\n"
        for name in criteria_names:
            help_text += f"  - {name}\n"

        help_text += "\nExample usage:\n"
        if criteria_names:
            # Create example with first few criteria
            example_pairs = []
            for i, name in enumerate(criteria_names[:3]):
                weight = 0.3 if i == 0 else 0.2
                example_pairs.append(f"{name}:{weight}")

            help_text += f"  --criteria-weights '{','.join(example_pairs)}'\n"

        return help_text
    except ValueError:
        return f"Unknown criteria type: {criteria_type}"
