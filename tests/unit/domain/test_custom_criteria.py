"""
Tests for custom criteria functionality.
"""

import json
import pytest
import tempfile
from pathlib import Path

from src.llm_judge.domain.evaluation.custom_criteria import (
    CustomCriteriaDefinition,
    CustomCriteriaParser,
    CustomCriteriaBuilder,
    get_available_criterion_types,
    create_criteria_template,
    save_criteria_template,
)
from src.llm_judge.domain.evaluation.criteria import CriterionType


class TestCustomCriteriaDefinition:
    """Test CustomCriteriaDefinition class."""

    def test_custom_criteria_definition_creation(self):
        """Test creating a custom criteria definition."""
        definition = CustomCriteriaDefinition(
            name="accuracy",
            description="Factual correctness",
            criterion_type="factual",
            weight=0.4,
        )

        assert definition.name == "accuracy"
        assert definition.description == "Factual correctness"
        assert definition.criterion_type == "factual"
        assert definition.weight == 0.4

    def test_to_criterion_definition(self):
        """Test conversion to CriterionDefinition."""
        definition = CustomCriteriaDefinition(
            name="accuracy",
            description="Factual correctness",
            criterion_type="factual",
            weight=0.4,
        )

        criterion_def = definition.to_criterion_definition()

        assert criterion_def.name == "accuracy"
        assert criterion_def.description == "Factual correctness"
        assert criterion_def.criterion_type == CriterionType.FACTUAL
        assert criterion_def.weight == 0.4

    def test_invalid_criterion_type(self):
        """Test invalid criterion type raises error."""
        definition = CustomCriteriaDefinition(
            name="test", description="Test description", criterion_type="invalid_type"
        )

        with pytest.raises(ValueError, match="Invalid criterion type: invalid_type"):
            definition.to_criterion_definition()


class TestCustomCriteriaParser:
    """Test CustomCriteriaParser class."""

    def test_parse_criteria_string_valid(self):
        """Test parsing valid criteria string."""
        criteria_string = "accuracy:Factual correctness:factual:0.4,clarity:How clear the response is:linguistic:0.3"
        definitions = CustomCriteriaParser.parse_criteria_string(criteria_string)

        assert len(definitions) == 2

        assert definitions[0].name == "accuracy"
        assert definitions[0].description == "Factual correctness"
        assert definitions[0].criterion_type == "factual"
        assert definitions[0].weight == 0.4

        assert definitions[1].name == "clarity"
        assert definitions[1].description == "How clear the response is"
        assert definitions[1].criterion_type == "linguistic"
        assert definitions[1].weight == 0.3

    def test_parse_criteria_string_invalid_format(self):
        """Test parsing invalid criteria string format."""
        # Missing colon
        with pytest.raises(ValueError, match="Invalid criterion format"):
            CustomCriteriaParser.parse_criteria_string(
                "accuracy:Factual correctness:factual"
            )

        # Empty name
        with pytest.raises(ValueError, match="Criterion name cannot be empty"):
            CustomCriteriaParser.parse_criteria_string(
                ":Factual correctness:factual:0.4"
            )

        # Empty description
        with pytest.raises(ValueError, match="Criterion description cannot be empty"):
            CustomCriteriaParser.parse_criteria_string("accuracy::factual:0.4")

        # Empty type
        with pytest.raises(ValueError, match="Criterion type cannot be empty"):
            CustomCriteriaParser.parse_criteria_string(
                "accuracy:Factual correctness::0.4"
            )

        # Invalid weight
        with pytest.raises(ValueError, match="Invalid weight value"):
            CustomCriteriaParser.parse_criteria_string(
                "accuracy:Factual correctness:factual:invalid"
            )

        # Negative weight
        with pytest.raises(
            ValueError, match="Weight for 'accuracy' cannot be negative"
        ):
            CustomCriteriaParser.parse_criteria_string(
                "accuracy:Factual correctness:factual:-0.1"
            )

    def test_parse_criteria_file_valid(self):
        """Test parsing valid criteria file."""
        criteria_data = {
            "name": "Test Criteria",
            "description": "Test criteria set",
            "criteria": [
                {
                    "name": "accuracy",
                    "description": "Factual correctness",
                    "criterion_type": "factual",
                    "weight": 0.4,
                    "evaluation_prompt": "Evaluate accuracy",
                    "examples": {1: "Poor", 5: "Excellent"},
                    "domain_specific": False,
                    "requires_context": False,
                    "metadata": {},
                },
                {
                    "name": "clarity",
                    "description": "How clear the response is",
                    "criterion_type": "linguistic",
                    "weight": 0.3,
                },
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(criteria_data, f)
            temp_path = f.name

        try:
            definitions = CustomCriteriaParser.parse_criteria_file(temp_path)

            assert len(definitions) == 2

            assert definitions[0].name == "accuracy"
            assert definitions[0].description == "Factual correctness"
            assert definitions[0].criterion_type == "factual"
            assert definitions[0].weight == 0.4
            assert definitions[0].evaluation_prompt == "Evaluate accuracy"
            assert definitions[0].examples == {1: "Poor", 5: "Excellent"}

            assert definitions[1].name == "clarity"
            assert definitions[1].description == "How clear the response is"
            assert definitions[1].criterion_type == "linguistic"
            assert definitions[1].weight == 0.3
        finally:
            Path(temp_path).unlink()

    def test_parse_criteria_file_invalid(self):
        """Test parsing invalid criteria file."""
        # File not found
        with pytest.raises(FileNotFoundError):
            CustomCriteriaParser.parse_criteria_file("nonexistent.json")

        # Invalid JSON
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("invalid json")
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Invalid JSON in criteria file"):
                CustomCriteriaParser.parse_criteria_file(temp_path)
        finally:
            Path(temp_path).unlink()

        # Missing required fields
        invalid_data = {
            "criteria": [
                {
                    "name": "accuracy",
                    # Missing description and criterion_type
                    "weight": 0.4,
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(invalid_data, f)
            temp_path = f.name

        try:
            with pytest.raises(
                ValueError, match="Criterion 0 missing required field: description"
            ):
                CustomCriteriaParser.parse_criteria_file(temp_path)
        finally:
            Path(temp_path).unlink()


class TestCustomCriteriaBuilder:
    """Test CustomCriteriaBuilder class."""

    def test_builder_creation(self):
        """Test creating a criteria builder."""
        builder = CustomCriteriaBuilder()

        assert builder.criteria_definitions == []
        assert builder.name == "Custom Evaluation"
        assert builder.description == "Custom evaluation criteria"

    def test_add_criterion(self):
        """Test adding criteria to builder."""
        builder = CustomCriteriaBuilder()

        builder.add_criterion(
            name="accuracy",
            description="Factual correctness",
            criterion_type="factual",
            weight=0.4,
        )

        assert len(builder.criteria_definitions) == 1
        assert builder.criteria_definitions[0].name == "accuracy"
        assert builder.criteria_definitions[0].description == "Factual correctness"
        assert builder.criteria_definitions[0].criterion_type == "factual"
        assert builder.criteria_definitions[0].weight == 0.4

    def test_set_name_and_description(self):
        """Test setting name and description."""
        builder = CustomCriteriaBuilder()

        builder.set_name("Academic Evaluation")
        builder.set_description("Criteria for academic content")

        assert builder.name == "Academic Evaluation"
        assert builder.description == "Criteria for academic content"

    def test_build(self):
        """Test building evaluation criteria."""
        builder = CustomCriteriaBuilder()

        builder.add_criterion(
            name="accuracy",
            description="Factual correctness",
            criterion_type="factual",
            weight=0.4,
        )
        builder.add_criterion(
            name="clarity",
            description="How clear the response is",
            criterion_type="linguistic",
            weight=0.3,
        )

        builder.set_name("Test Criteria")
        builder.set_description("Test criteria set")

        criteria = builder.build(normalize_weights=False)

        assert criteria.name == "Test Criteria"
        assert criteria.description == "Test criteria set"
        assert len(criteria.criteria) == 2

        assert criteria.criteria[0].name == "accuracy"
        assert criteria.criteria[0].criterion_type == CriterionType.FACTUAL
        assert criteria.criteria[0].weight == 0.4

        assert criteria.criteria[1].name == "clarity"
        assert criteria.criteria[1].criterion_type == CriterionType.LINGUISTIC
        assert criteria.criteria[1].weight == 0.3

    def test_build_empty_criteria(self):
        """Test building with no criteria raises error."""
        builder = CustomCriteriaBuilder()

        with pytest.raises(ValueError, match="No criteria defined"):
            builder.build()


class TestUtilityFunctions:
    """Test utility functions."""

    def test_get_available_criterion_types(self):
        """Test getting available criterion types."""
        types = get_available_criterion_types()

        expected_types = [
            "factual",
            "qualitative",
            "structural",
            "contextual",
            "linguistic",
            "ethical",
        ]
        assert set(types) == set(expected_types)

    def test_create_criteria_template(self):
        """Test creating criteria template."""
        template = create_criteria_template()

        assert "name" in template
        assert "description" in template
        assert "criteria" in template
        assert isinstance(template["criteria"], list)
        assert len(template["criteria"]) == 2

        # Check first criterion
        first_criterion = template["criteria"][0]
        assert first_criterion["name"] == "accuracy"
        assert first_criterion["criterion_type"] == "factual"
        assert "examples" in first_criterion
        assert "evaluation_prompt" in first_criterion

    def test_save_criteria_template(self):
        """Test saving criteria template to file."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = f.name

        try:
            save_criteria_template(temp_path)

            # Verify file was created and contains valid JSON
            with open(temp_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            assert "name" in data
            assert "description" in data
            assert "criteria" in data
        finally:
            Path(temp_path).unlink()


class TestIntegration:
    """Integration tests for custom criteria."""

    def test_end_to_end_custom_criteria_workflow(self):
        """Test complete custom criteria workflow."""
        # Parse criteria string
        criteria_string = "accuracy:Factual correctness:factual:0.4,clarity:How clear the response is:linguistic:0.3"
        definitions = CustomCriteriaParser.parse_criteria_string(criteria_string)

        # Build criteria
        builder = CustomCriteriaBuilder()
        for definition in definitions:
            builder.add_criterion(
                name=definition.name,
                description=definition.description,
                criterion_type=definition.criterion_type,
                weight=definition.weight,
            )

        builder.set_name("Test Evaluation")
        builder.set_description("Test criteria set")

        # Build final criteria
        criteria = builder.build(normalize_weights=False)

        # Verify result
        assert criteria.name == "Test Evaluation"
        assert criteria.description == "Test criteria set"
        assert len(criteria.criteria) == 2

        # Check individual criteria
        accuracy_criterion = next(c for c in criteria.criteria if c.name == "accuracy")
        assert accuracy_criterion.criterion_type == CriterionType.FACTUAL
        assert accuracy_criterion.weight == 0.4

        clarity_criterion = next(c for c in criteria.criteria if c.name == "clarity")
        assert clarity_criterion.criterion_type == CriterionType.LINGUISTIC
        assert clarity_criterion.weight == 0.3

    def test_file_based_custom_criteria_workflow(self):
        """Test file-based custom criteria workflow."""
        # Create test criteria file
        criteria_data = {
            "name": "Academic Evaluation",
            "description": "Criteria for academic content",
            "criteria": [
                {
                    "name": "accuracy",
                    "description": "Factual correctness and truthfulness",
                    "criterion_type": "factual",
                    "weight": 0.4,
                    "evaluation_prompt": "Evaluate the factual accuracy of the response.",
                    "examples": {
                        1: "Contains major factual errors",
                        5: "Completely accurate and well-supported",
                    },
                },
                {
                    "name": "completeness",
                    "description": "Thoroughness of coverage",
                    "criterion_type": "qualitative",
                    "weight": 0.3,
                },
                {
                    "name": "clarity",
                    "description": "Clarity of expression",
                    "criterion_type": "linguistic",
                    "weight": 0.3,
                },
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(criteria_data, f)
            temp_path = f.name

        try:
            # Parse criteria file
            definitions = CustomCriteriaParser.parse_criteria_file(temp_path)

            # Build criteria
            builder = CustomCriteriaBuilder()
            for definition in definitions:
                builder.add_criterion(
                    name=definition.name,
                    description=definition.description,
                    criterion_type=definition.criterion_type,
                    weight=definition.weight,
                    evaluation_prompt=definition.evaluation_prompt,
                    examples=definition.examples,
                )

            criteria = builder.build(normalize_weights=False)

            # Verify result
            assert len(criteria.criteria) == 3

            # Check accuracy criterion has custom prompt and examples
            accuracy_criterion = next(
                c for c in criteria.criteria if c.name == "accuracy"
            )
            assert (
                accuracy_criterion.evaluation_prompt
                == "Evaluate the factual accuracy of the response."
            )
            assert accuracy_criterion.examples == {
                1: "Contains major factual errors",
                5: "Completely accurate and well-supported",
            }
        finally:
            Path(temp_path).unlink()
