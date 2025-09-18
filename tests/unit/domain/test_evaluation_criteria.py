"""Unit tests for evaluation criteria domain models."""

import pytest
from dataclasses import FrozenInstanceError

from src.llm_judge.domain.evaluation.criteria import (
    CriterionDefinition, 
    EvaluationCriteria, 
    DefaultCriteria, 
    CriterionType
)


class TestCriterionDefinition:
    """Test CriterionDefinition domain model."""

    def test_criterion_definition_creation(self):
        """Test basic criterion definition creation."""
        criterion = CriterionDefinition(
            name="accuracy",
            description="Factual correctness of the response",
            criterion_type=CriterionType.FACTUAL,
            weight=0.3,
            scale_min=1,
            scale_max=5
        )
        
        assert criterion.name == "accuracy"
        assert criterion.description == "Factual correctness of the response"
        assert criterion.criterion_type == CriterionType.FACTUAL
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
            1: "Mostly inaccurate information"
        }
        
        criterion = CriterionDefinition(
            name="accuracy",
            description="Factual correctness",
            criterion_type=CriterionType.FACTUAL,
            examples=examples
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
                criterion_type=CriterionType.FACTUAL,
                scale_min=5,
                scale_max=3
            )
        
        # Test negative weight
        with pytest.raises(ValueError, match="Criterion weight must be between 0 and 1"):
            CriterionDefinition(
                name="invalid",
                description="test",
                criterion_type=CriterionType.FACTUAL,
                weight=-0.1
            )

    def test_criterion_definition_immutable(self):
        """Test that criterion definitions are immutable."""
        criterion = CriterionDefinition(
            name="accuracy",
            description="test",
            criterion_type=CriterionType.FACTUAL
        )
        
        # Should not be able to modify after creation
        with pytest.raises(FrozenInstanceError):
            criterion.weight = 0.5


class TestEvaluationCriteria:
    """Test EvaluationCriteria collection."""

    def test_evaluation_criteria_creation(self):
        """Test creating evaluation criteria collection."""
        criteria_list = [
            CriterionDefinition("accuracy", "test", CriterionType.FACTUAL, weight=0.4),
            CriterionDefinition("clarity", "test", CriterionType.QUALITATIVE, weight=0.3),
            CriterionDefinition("completeness", "test", CriterionType.STRUCTURAL, weight=0.3)
        ]
        
        criteria = EvaluationCriteria(
            name="test_criteria",
            description="Test criteria set",
            criteria=criteria_list
        )
        
        assert criteria.name == "test_criteria"
        assert len(criteria.criteria) == 3
        assert criteria.total_weight == 1.0

    def test_evaluation_criteria_get_criterion(self):
        """Test getting specific criterion by name."""
        accuracy_def = CriterionDefinition("accuracy", "test", CriterionType.FACTUAL)
        clarity_def = CriterionDefinition("clarity", "test", CriterionType.QUALITATIVE)
        
        criteria = EvaluationCriteria(
            name="test",
            criteria=[accuracy_def, clarity_def]
        )
        
        found_accuracy = criteria.get_criterion("accuracy")
        assert found_accuracy.name == accuracy_def.name
        assert found_accuracy.description == accuracy_def.description
        assert found_accuracy.criterion_type == accuracy_def.criterion_type
        
        not_found = criteria.get_criterion("nonexistent")
        assert not_found is None

    def test_evaluation_criteria_get_by_type(self):
        """Test getting criteria by type."""
        factual_criterion = CriterionDefinition("accuracy", "test", CriterionType.FACTUAL)
        qualitative_criterion1 = CriterionDefinition("clarity", "test", CriterionType.QUALITATIVE)
        qualitative_criterion2 = CriterionDefinition("helpfulness", "test", CriterionType.QUALITATIVE)
        
        criteria = EvaluationCriteria(
            name="test",
            criteria=[factual_criterion, qualitative_criterion1, qualitative_criterion2]
        )
        
        factual_criteria = criteria.get_criteria_by_type(CriterionType.FACTUAL)
        assert len(factual_criteria) == 1
        assert factual_criteria[0].name == factual_criterion.name
        assert factual_criteria[0].criterion_type == factual_criterion.criterion_type
        
        qualitative_criteria = criteria.get_criteria_by_type(CriterionType.QUALITATIVE)
        assert len(qualitative_criteria) == 2

    def test_evaluation_criteria_weight_validation(self):
        """Test weight validation in criteria collection."""
        # Test weights don't sum to 1 (with tolerance)
        criteria_list = [
            CriterionDefinition("accuracy", "test", CriterionType.FACTUAL, weight=0.5),
            CriterionDefinition("clarity", "test", CriterionType.QUALITATIVE, weight=0.6)  # Sum = 1.1
        ]
        
        # Create with unnormalized weights - should work since normalize_weights=True by default
        criteria = EvaluationCriteria(name="invalid", criteria=criteria_list)
        
        # Check that weights were normalized
        total_weight = sum(c.weight for c in criteria.criteria)
        assert abs(total_weight - 1.0) < 1e-6

    def test_evaluation_criteria_normalization(self):
        """Test automatic weight normalization."""
        criteria_list = [
            CriterionDefinition("accuracy", "test", CriterionType.FACTUAL, weight=0.4),
            CriterionDefinition("clarity", "test", CriterionType.QUALITATIVE, weight=0.6)  # Sum = 1.0 (already normalized)
        ]
        
        criteria = EvaluationCriteria(
            name="test",
            criteria=criteria_list,
            normalize_weights=True
        )
        
        # Weights should be normalized to sum to 1.0
        assert abs(criteria.total_weight - 1.0) < 0.001
        assert abs(criteria.criteria[0].weight - 0.4) < 0.001  # 2/5
        assert abs(criteria.criteria[1].weight - 0.6) < 0.001  # 3/5


class TestDefaultCriteria:
    """Test default criteria factory methods."""

    def test_default_comprehensive_criteria(self):
        """Test comprehensive default criteria."""
        criteria = DefaultCriteria.comprehensive()
        
        assert criteria.name == "Comprehensive Default Evaluation"
        assert len(criteria.criteria) == 7
        
        # Check that all expected criteria are present
        criterion_names = {c.name for c in criteria.criteria}
        expected_names = {
            "accuracy", "completeness", "clarity", "relevance", 
            "helpfulness", "coherence", "appropriateness"
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
        criteria = DefaultCriteria.comprehensive()
        
        for criterion in criteria.criteria:
            assert len(criterion.examples) > 0
            # Check that examples cover the score range
            example_scores = set(criterion.examples.keys())
            assert min(example_scores) >= criterion.scale_min
            assert max(example_scores) <= criterion.scale_max

    def test_default_criteria_types_distribution(self):
        """Test that default criteria cover different criterion types."""
        criteria = DefaultCriteria.comprehensive()
        
        criterion_types = {c.criterion_type for c in criteria.criteria}
        
        # Should have multiple types represented
        assert CriterionType.FACTUAL in criterion_types
        assert CriterionType.QUALITATIVE in criterion_types
        assert CriterionType.STRUCTURAL in criterion_types

    def test_custom_criteria_creation(self):
        """Test creating custom criteria using builder pattern."""
        # Test the builder pattern for custom criteria
        builder = DefaultCriteria.builder()
        builder.add_factual_criterion("accuracy", "Test accuracy", weight=0.4)
        builder.add_quality_criterion("clarity", "Test clarity", weight=0.3)
        builder.add_quality_criterion("creativity", "Test creativity", weight=0.3)
        custom_criteria = builder.build()
        
        assert custom_criteria.name == "Custom Evaluation"
        assert len(custom_criteria.criteria) == 3
        
        # Check weights sum to 1.0 (normalized)
        total_weight = sum(c.weight for c in custom_criteria.criteria)
        assert abs(total_weight - 1.0) < 1e-6
        
        criterion_names = {c.name for c in custom_criteria.criteria}
        assert criterion_names == {"accuracy", "clarity", "creativity"}


class TestCriterionType:
    """Test CriterionType enum."""

    def test_criterion_type_values(self):
        """Test criterion type enum values."""
        assert CriterionType.FACTUAL.value == "factual"
        assert CriterionType.QUALITATIVE.value == "qualitative"
        assert CriterionType.STRUCTURAL.value == "structural"
        assert CriterionType.CONTEXTUAL.value == "contextual"
        assert CriterionType.LINGUISTIC.value == "linguistic"
        assert CriterionType.ETHICAL.value == "ethical"

    def test_criterion_type_from_string(self):
        """Test creating criterion type from string."""
        assert CriterionType("factual") == CriterionType.FACTUAL
        assert CriterionType("qualitative") == CriterionType.QUALITATIVE
        
        with pytest.raises(ValueError):
            CriterionType("invalid_type")