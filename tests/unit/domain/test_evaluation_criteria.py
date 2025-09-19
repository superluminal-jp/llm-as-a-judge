"""Unit tests for evaluation criteria domain models."""

import pytest
from dataclasses import FrozenInstanceError

from src.llm_judge.domain.evaluation.criteria import (
    CriterionDefinition,
    DefaultCriteria,
    EvaluationCriteria,
)


class TestCriterionDefinition:
    """Test CriterionDefinition domain model."""

    def test_criterion_definition_creation(self):
        """Test basic criterion definition creation."""
        criterion = CriterionDefinition(
            name="accuracy",
            description="Factual correctness of the response",
            weight=0.3,
            scale_min=1,
            scale_max=5,
        )

        assert criterion.name == "accuracy"
        assert criterion.description == "Factual correctness of the response"
        assert criterion.weight == 0.3
        assert criterion.scale_min == 1
        assert criterion.scale_max == 5

    def test_criterion_definition_with_examples(self):
        """Test criterion definition with scoring examples."""
        examples = {
            5: "Completely accurate with verified facts",
            4: "Mostly accurate with minor inaccuracies",
            3: "Generally accurate but some questionable claims",
            2: "Some accuracy but notable errors",
            1: "Mostly inaccurate information",
        }

        criterion = CriterionDefinition(
            name="accuracy",
            description="Factual correctness",
            examples=examples,
        )

        assert len(criterion.examples) == 5
        assert criterion.examples[5] == "Completely accurate with verified facts"
        assert criterion.examples[1] == "Mostly inaccurate information"

    def test_criterion_definition_validation(self):
        """Test criterion definition validation."""
        # Test invalid scale
        with pytest.raises(ValueError, match="scale_min must be less than scale_max"):
            CriterionDefinition(
                name="invalid",
                description="test",
                scale_min=5,
                scale_max=3,
            )

        # Test negative weight
        with pytest.raises(
            ValueError, match="Criterion weight must be between 0 and 1"
        ):
            CriterionDefinition(
                name="invalid",
                description="test",
                weight=-0.1,
            )

    def test_criterion_definition_immutable(self):
        """Test that criterion definitions are immutable."""
        criterion = CriterionDefinition(name="accuracy", description="test")

        # Should not be able to modify after creation
        with pytest.raises(FrozenInstanceError):
            criterion.weight = 0.5


class TestEvaluationCriteria:
    """Test EvaluationCriteria collection."""

    def test_evaluation_criteria_creation(self):
        """Test creating evaluation criteria collection."""
        criteria_list = [
            CriterionDefinition("accuracy", "test", weight=0.4),
            CriterionDefinition("clarity", "test", weight=0.3),
            CriterionDefinition("completeness", "test", weight=0.3),
        ]

        criteria = EvaluationCriteria(
            name="test_criteria",
            description="Test criteria set",
            criteria=criteria_list,
        )

        assert criteria.name == "test_criteria"
        assert len(criteria.criteria) == 3
        assert criteria.total_weight == 1.0

    def test_evaluation_criteria_get_criterion(self):
        """Test getting specific criterion by name."""
        accuracy_def = CriterionDefinition("accuracy", "test")
        clarity_def = CriterionDefinition("clarity", "test")

        criteria = EvaluationCriteria(name="test", criteria=[accuracy_def, clarity_def])

        found_accuracy = criteria.get_criterion("accuracy")
        assert found_accuracy.name == accuracy_def.name
        assert found_accuracy.description == accuracy_def.description

        not_found = criteria.get_criterion("nonexistent")
        assert not_found is None

    def test_evaluation_criteria_add_criterion(self):
        """Test adding criteria to collection."""
        # Start with one criterion to meet minimum requirement
        initial_criterion = CriterionDefinition("initial", "test", weight=0.5)
        criteria = EvaluationCriteria(name="test", criteria=[initial_criterion])

        criterion = CriterionDefinition("accuracy", "test", weight=0.5)
        criteria.add_criterion(criterion)

        assert len(criteria.criteria) == 2
        assert criteria.get_criterion("accuracy") is not None

        # Test adding duplicate criterion
        with pytest.raises(ValueError, match="Criterion 'accuracy' already exists"):
            criteria.add_criterion(criterion)

    def test_evaluation_criteria_weight_validation(self):
        """Test weight validation in criteria collection."""
        # Test weights don't sum to 1 (with tolerance)
        criteria_list = [
            CriterionDefinition("accuracy", "test", weight=0.5),
            CriterionDefinition("clarity", "test", weight=0.6),  # Sum = 1.1
        ]

        # Create with unnormalized weights - should work since normalize_weights=True by default
        criteria = EvaluationCriteria(name="invalid", criteria=criteria_list)

        # Check that weights were normalized
        total_weight = sum(c.weight for c in criteria.criteria)
        assert abs(total_weight - 1.0) < 1e-6

    def test_evaluation_criteria_normalization(self):
        """Test automatic weight normalization."""
        criteria_list = [
            CriterionDefinition("accuracy", "test", weight=0.4),
            CriterionDefinition(
                "clarity", "test", weight=0.6
            ),  # Sum = 1.0 (already normalized)
        ]

        criteria = EvaluationCriteria(
            name="test", criteria=criteria_list, normalize_weights=True
        )

        # Weights should be normalized to sum to 1.0
        assert abs(criteria.total_weight - 1.0) < 0.001
        assert abs(criteria.criteria[0].weight - 0.4) < 0.001  # 2/5
        assert abs(criteria.criteria[1].weight - 0.6) < 0.001  # 3/5


class TestDefaultCriteria:
    """Test default criteria factory methods."""

    def test_default_balanced_criteria(self):
        """Test balanced default criteria."""
        criteria = DefaultCriteria.balanced()

        assert criteria.name == "Balanced Default Evaluation"
        assert len(criteria.criteria) == 7

        # Check that all expected criteria are present
        criterion_names = {c.name for c in criteria.criteria}
        expected_names = {
            "accuracy",
            "completeness",
            "clarity",
            "relevance",
            "helpfulness",
            "coherence",
            "appropriateness",
        }
        assert criterion_names == expected_names

        # Check total weight sums to 1.0
        assert abs(criteria.total_weight - 1.0) < 0.001

    def test_default_basic_criteria(self):
        """Test basic default criteria."""
        criteria = DefaultCriteria.basic()

        assert criteria.name == "Basic Evaluation"
        assert len(criteria.criteria) == 3

        criterion_names = {c.name for c in criteria.criteria}
        expected_names = {"accuracy", "clarity", "helpfulness"}
        assert criterion_names == expected_names

    def test_default_technical_criteria(self):
        """Test technical default criteria."""
        criteria = DefaultCriteria.technical()

        assert criteria.name == "Technical Evaluation"
        assert len(criteria.criteria) > 0

        # Should include technical-focused criteria
        criterion_names = {c.name for c in criteria.criteria}
        assert "technical_accuracy" in criterion_names
        assert "completeness" in criterion_names

    def test_default_creative_criteria(self):
        """Test creative default criteria."""
        criteria = DefaultCriteria.creative()

        assert criteria.name == "Creative Evaluation"
        assert len(criteria.criteria) > 0

        # Should include creativity-focused criteria
        criterion_names = {c.name for c in criteria.criteria}
        assert "creativity" in criterion_names
        assert "engagement" in criterion_names

    def test_default_criteria_have_examples(self):
        """Test that default criteria include scoring examples."""
        criteria = DefaultCriteria.balanced()

        for criterion in criteria.criteria:
            assert len(criterion.examples) > 0
            # Check that examples cover the score range
            example_scores = set(criterion.examples.keys())
            assert min(example_scores) >= criterion.scale_min
            assert max(example_scores) <= criterion.scale_max

    def test_default_criteria_domain_specific_distribution(self):
        """Test that default criteria have appropriate domain-specific flags."""
        criteria = DefaultCriteria.balanced()

        # Most criteria should not be domain-specific
        domain_specific_count = sum(1 for c in criteria.criteria if c.domain_specific)
        assert domain_specific_count == 0  # Balanced criteria are general-purpose

    def test_custom_criteria_creation(self):
        """Test creating custom criteria using builder pattern."""
        # Test the builder pattern for custom criteria
        builder = DefaultCriteria.builder()
        builder.add_criterion("accuracy", "Test accuracy", weight=0.4)
        builder.add_criterion("clarity", "Test clarity", weight=0.3)
        builder.add_criterion("creativity", "Test creativity", weight=0.3)
        custom_criteria = builder.build()

        assert custom_criteria.name == "Custom Evaluation"
        assert len(custom_criteria.criteria) == 3

        # Check weights sum to 1.0 (normalized)
        total_weight = sum(c.weight for c in custom_criteria.criteria)
        assert abs(total_weight - 1.0) < 1e-6

        criterion_names = {c.name for c in custom_criteria.criteria}
        assert criterion_names == {"accuracy", "clarity", "creativity"}


class TestCriteriaParser:
    """Test CriteriaParser functionality."""

    def test_parse_criteria_string_valid(self):
        """Test parsing valid criteria string."""
        criteria_string = (
            "accuracy:Factual correctness:0.4,clarity:How clear the response is:0.3"
        )
        from src.llm_judge.domain.evaluation.criteria import CriteriaParser

        criteria = CriteriaParser.parse_criteria_string(criteria_string)

        assert len(criteria) == 2
        assert criteria[0].name == "accuracy"
        assert criteria[0].description == "Factual correctness"
        assert criteria[0].weight == 0.4
        assert criteria[1].name == "clarity"
        assert criteria[1].description == "How clear the response is"
        assert criteria[1].weight == 0.3

    def test_parse_criteria_string_invalid(self):
        """Test parsing invalid criteria string."""
        from src.llm_judge.domain.evaluation.criteria import CriteriaParser

        with pytest.raises(ValueError, match="Invalid criterion format"):
            CriteriaParser.parse_criteria_string("invalid_format")

        with pytest.raises(ValueError, match="Criterion name cannot be empty"):
            CriteriaParser.parse_criteria_string(":description:0.5")

        with pytest.raises(ValueError, match="Criterion description cannot be empty"):
            CriteriaParser.parse_criteria_string("name::0.5")
