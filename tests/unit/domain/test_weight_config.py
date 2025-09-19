"""
Tests for weight configuration functionality.
"""

import pytest
from src.llm_judge.domain.evaluation.weight_config import (
    WeightConfig,
    WeightConfigParser,
    CriteriaWeightApplier,
)
from src.llm_judge.domain.evaluation.criteria import DefaultCriteria


class TestWeightConfig:
    """Test WeightConfig class."""

    def test_weight_config_creation(self):
        """Test creating a weight configuration."""
        weights = {"accuracy": 0.4, "clarity": 0.3, "helpfulness": 0.3}
        config = WeightConfig(weights=weights)

        assert config.weights == weights
        assert config.normalize is True

    def test_weight_config_normalization(self):
        """Test weight normalization."""
        weights = {"accuracy": 2.0, "clarity": 1.5, "helpfulness": 0.5}
        config = WeightConfig(weights=weights)

        # Should be normalized to sum to 1.0
        total = sum(config.weights.values())
        assert abs(total - 1.0) < 1e-6
        assert config.weights["accuracy"] == 0.5  # 2.0 / 4.0
        assert config.weights["clarity"] == 0.375  # 1.5 / 4.0
        assert config.weights["helpfulness"] == 0.125  # 0.5 / 4.0

    def test_weight_config_validation(self):
        """Test weight configuration validation."""
        # Empty weights should raise error
        with pytest.raises(ValueError, match="Weight configuration cannot be empty"):
            WeightConfig(weights={})

        # Negative weights should raise error
        with pytest.raises(
            ValueError, match="Weight for 'accuracy' cannot be negative"
        ):
            WeightConfig(weights={"accuracy": -0.1})

    def test_get_weight(self):
        """Test getting weight for a criterion."""
        weights = {"accuracy": 0.4, "clarity": 0.3, "helpfulness": 0.3}
        config = WeightConfig(weights=weights)

        assert config.get_weight("accuracy") == 0.4
        assert config.get_weight("nonexistent") == 0.0

    def test_has_criterion(self):
        """Test checking if criterion exists."""
        weights = {"accuracy": 0.4, "clarity": 0.3}
        config = WeightConfig(weights=weights)

        assert config.has_criterion("accuracy") is True
        assert config.has_criterion("nonexistent") is False


class TestWeightConfigParser:
    """Test WeightConfigParser class."""

    def test_parse_weight_string_valid(self):
        """Test parsing valid weight string."""
        weight_string = "accuracy:0.4,clarity:0.3,helpfulness:0.3"
        config = WeightConfigParser.parse_weight_string(weight_string)

        assert config.weights["accuracy"] == 0.4
        assert config.weights["clarity"] == 0.3
        assert config.weights["helpfulness"] == 0.3

    def test_parse_weight_string_with_integers(self):
        """Test parsing weight string with integer weights."""
        weight_string = "accuracy:4,clarity:3,helpfulness:3"
        config = WeightConfigParser.parse_weight_string(weight_string)

        # Should be normalized
        total = sum(config.weights.values())
        assert abs(total - 1.0) < 1e-6

    def test_parse_weight_string_invalid_format(self):
        """Test parsing invalid weight string format."""
        # Missing colon
        with pytest.raises(ValueError, match="Invalid weight pair format"):
            WeightConfigParser.parse_weight_string("accuracy0.4,clarity:0.3")

        # Empty criterion name
        with pytest.raises(ValueError, match="Criterion name cannot be empty"):
            WeightConfigParser.parse_weight_string(":0.4,clarity:0.3")

        # Invalid weight value
        with pytest.raises(ValueError, match="Invalid weight value"):
            WeightConfigParser.parse_weight_string("accuracy:invalid,clarity:0.3")

        # Negative weight
        with pytest.raises(
            ValueError, match="Weight for 'accuracy' cannot be negative"
        ):
            WeightConfigParser.parse_weight_string("accuracy:-0.1,clarity:0.3")

    def test_create_equal_weights(self):
        """Test creating equal weights."""
        criteria_names = ["accuracy", "clarity", "helpfulness"]
        config = WeightConfigParser.create_equal_weights(criteria_names)

        expected_weight = 1.0 / 3.0
        for name in criteria_names:
            assert abs(config.weights[name] - expected_weight) < 1e-6

    def test_create_equal_weights_empty(self):
        """Test creating equal weights with empty list."""
        with pytest.raises(ValueError, match="Criteria names list cannot be empty"):
            WeightConfigParser.create_equal_weights([])


class TestCriteriaWeightApplier:
    """Test CriteriaWeightApplier class."""

    def test_apply_weights(self):
        """Test applying weights to criteria."""
        # Get base criteria
        base_criteria = DefaultCriteria.basic()

        # Create weight config
        weight_config = WeightConfig(
            weights={"accuracy": 0.5, "clarity": 0.3, "helpfulness": 0.2}
        )

        # Apply weights
        custom_criteria = CriteriaWeightApplier.apply_weights(
            base_criteria, weight_config
        )

        # Check that weights were applied
        accuracy_criterion = next(
            c for c in custom_criteria.criteria if c.name == "accuracy"
        )
        clarity_criterion = next(
            c for c in custom_criteria.criteria if c.name == "clarity"
        )
        helpfulness_criterion = next(
            c for c in custom_criteria.criteria if c.name == "helpfulness"
        )

        assert accuracy_criterion.weight == 0.5
        assert clarity_criterion.weight == 0.3
        assert helpfulness_criterion.weight == 0.2

    def test_apply_weights_nonexistent_criterion(self):
        """Test applying weights with nonexistent criterion."""
        base_criteria = DefaultCriteria.basic()
        weight_config = WeightConfig(weights={"nonexistent": 0.5, "accuracy": 0.5})

        with pytest.raises(
            ValueError, match="Criterion 'nonexistent' in weight config not found"
        ):
            CriteriaWeightApplier.apply_weights(base_criteria, weight_config)

    def test_get_available_criteria_names(self):
        """Test getting available criteria names."""
        # Test balanced criteria
        names = CriteriaWeightApplier.get_available_criteria_names("balanced")
        assert "accuracy" in names
        assert "clarity" in names
        assert "helpfulness" in names
        assert len(names) == 7

        # Test basic criteria
        names = CriteriaWeightApplier.get_available_criteria_names("basic")
        assert "accuracy" in names
        assert "clarity" in names
        assert "helpfulness" in names
        assert len(names) == 3

        # Test unknown criteria type
        with pytest.raises(ValueError, match="Unknown criteria type"):
            CriteriaWeightApplier.get_available_criteria_names("unknown")


class TestIntegration:
    """Integration tests for weight configuration."""

    def test_end_to_end_weight_configuration(self):
        """Test complete weight configuration workflow."""
        # Parse weight string
        weight_string = "accuracy:0.4,clarity:0.3,helpfulness:0.3"
        weight_config = WeightConfigParser.parse_weight_string(weight_string)

        # Get base criteria
        base_criteria = DefaultCriteria.basic()

        # Apply weights
        custom_criteria = CriteriaWeightApplier.apply_weights(
            base_criteria, weight_config
        )

        # Verify result
        assert len(custom_criteria.criteria) == 3
        total_weight = sum(c.weight for c in custom_criteria.criteria)
        assert abs(total_weight - 1.0) < 1e-6

        # Check individual weights
        accuracy_criterion = next(
            c for c in custom_criteria.criteria if c.name == "accuracy"
        )
        assert accuracy_criterion.weight == 0.4

    def test_equal_weights_workflow(self):
        """Test equal weights workflow."""
        # Get criteria names
        criteria_names = CriteriaWeightApplier.get_available_criteria_names("basic")

        # Create equal weights
        weight_config = WeightConfigParser.create_equal_weights(criteria_names)

        # Get base criteria
        base_criteria = DefaultCriteria.basic()

        # Apply weights
        custom_criteria = CriteriaWeightApplier.apply_weights(
            base_criteria, weight_config
        )

        # Verify all weights are equal
        expected_weight = 1.0 / len(criteria_names)
        for criterion in custom_criteria.criteria:
            assert abs(criterion.weight - expected_weight) < 1e-6
