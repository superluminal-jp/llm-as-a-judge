"""Simple tests for structured output functionality."""

import json
import pytest
from typing import Dict, Any


class TestStructuredOutputSchemas:
    """Test structured output schema definitions."""

    def test_evaluation_schema_structure(self):
        """Test that evaluation JSON schema is properly structured."""
        evaluation_schema = {
            "type": "json_schema",
            "json_schema": {
                "name": "evaluation_response",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "score": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 5,
                            "description": "Evaluation score from 1-5",
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "Detailed explanation of the evaluation",
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                            "description": "Confidence level in the evaluation",
                        },
                    },
                    "required": ["score", "reasoning", "confidence"],
                    "additionalProperties": False,
                },
            },
        }

        # Validate schema structure
        assert evaluation_schema["type"] == "json_schema"
        assert evaluation_schema["json_schema"]["strict"] is True
        assert evaluation_schema["json_schema"]["name"] == "evaluation_response"

        schema = evaluation_schema["json_schema"]["schema"]
        assert schema["type"] == "object"
        assert "score" in schema["properties"]
        assert "reasoning" in schema["properties"]
        assert "confidence" in schema["properties"]
        assert schema["required"] == ["score", "reasoning", "confidence"]
        assert schema["additionalProperties"] is False

        # Validate score field
        score_prop = schema["properties"]["score"]
        assert score_prop["type"] == "integer"
        assert score_prop["minimum"] == 1
        assert score_prop["maximum"] == 5

        # Validate reasoning field
        reasoning_prop = schema["properties"]["reasoning"]
        assert reasoning_prop["type"] == "string"

        # Validate confidence field
        confidence_prop = schema["properties"]["confidence"]
        assert confidence_prop["type"] == "number"
        assert confidence_prop["minimum"] == 0.0
        assert confidence_prop["maximum"] == 1.0

    def test_comparison_schema_structure(self):
        """Test that comparison JSON schema is properly structured."""
        comparison_schema = {
            "type": "json_schema",
            "json_schema": {
                "name": "comparison_response",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "winner": {
                            "type": "string",
                            "enum": ["A", "B", "tie"],
                            "description": "Which response is better: A, B, or tie",
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "Detailed explanation of the comparison",
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                            "description": "Confidence level in the comparison",
                        },
                    },
                    "required": ["winner", "reasoning", "confidence"],
                    "additionalProperties": False,
                },
            },
        }

        # Validate schema structure
        assert comparison_schema["type"] == "json_schema"
        assert comparison_schema["json_schema"]["strict"] is True
        assert comparison_schema["json_schema"]["name"] == "comparison_response"

        schema = comparison_schema["json_schema"]["schema"]
        assert schema["type"] == "object"
        assert "winner" in schema["properties"]
        assert "reasoning" in schema["properties"]
        assert "confidence" in schema["properties"]
        assert schema["required"] == ["winner", "reasoning", "confidence"]
        assert schema["additionalProperties"] is False

        # Validate winner field
        winner_prop = schema["properties"]["winner"]
        assert winner_prop["type"] == "string"
        assert winner_prop["enum"] == ["A", "B", "tie"]

        # Validate reasoning field
        reasoning_prop = schema["properties"]["reasoning"]
        assert reasoning_prop["type"] == "string"

        # Validate confidence field
        confidence_prop = schema["properties"]["confidence"]
        assert confidence_prop["type"] == "number"
        assert confidence_prop["minimum"] == 0.0
        assert confidence_prop["maximum"] == 1.0

    def test_schema_json_serialization(self):
        """Test that schemas can be properly serialized to JSON."""
        evaluation_schema = {
            "type": "json_schema",
            "json_schema": {
                "name": "evaluation_response",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "score": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 5,
                            "description": "Evaluation score from 1-5",
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "Detailed explanation of the evaluation",
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                            "description": "Confidence level in the evaluation",
                        },
                    },
                    "required": ["score", "reasoning", "confidence"],
                    "additionalProperties": False,
                },
            },
        }

        # Test JSON serialization
        json_str = json.dumps(evaluation_schema)
        assert isinstance(json_str, str)

        # Test JSON deserialization
        deserialized = json.loads(json_str)
        assert deserialized == evaluation_schema

    def test_valid_evaluation_response(self):
        """Test that a valid evaluation response matches the schema."""
        valid_response = {
            "score": 4,
            "reasoning": "This is a good response with clear explanations.",
            "confidence": 0.8,
        }

        # Validate required fields
        assert "score" in valid_response
        assert "reasoning" in valid_response
        assert "confidence" in valid_response

        # Validate types and ranges
        assert isinstance(valid_response["score"], int)
        assert 1 <= valid_response["score"] <= 5

        assert isinstance(valid_response["reasoning"], str)
        assert len(valid_response["reasoning"]) > 0

        assert isinstance(valid_response["confidence"], (int, float))
        assert 0.0 <= valid_response["confidence"] <= 1.0

    def test_valid_comparison_response(self):
        """Test that a valid comparison response matches the schema."""
        valid_response = {
            "winner": "A",
            "reasoning": "Response A provides more detailed and accurate information.",
            "confidence": 0.9,
        }

        # Validate required fields
        assert "winner" in valid_response
        assert "reasoning" in valid_response
        assert "confidence" in valid_response

        # Validate types and values
        assert valid_response["winner"] in ["A", "B", "tie"]

        assert isinstance(valid_response["reasoning"], str)
        assert len(valid_response["reasoning"]) > 0

        assert isinstance(valid_response["confidence"], (int, float))
        assert 0.0 <= valid_response["confidence"] <= 1.0

    def test_invalid_evaluation_responses(self):
        """Test that invalid evaluation responses are properly identified."""
        # Missing required field
        invalid_response_1 = {
            "score": 4,
            "reasoning": "Good response",
            # Missing confidence
        }
        assert "confidence" not in invalid_response_1

        # Invalid score range
        invalid_response_2 = {
            "score": 6,  # Out of range
            "reasoning": "Good response",
            "confidence": 0.8,
        }
        assert not (1 <= invalid_response_2["score"] <= 5)

        # Invalid confidence range
        invalid_response_3 = {
            "score": 4,
            "reasoning": "Good response",
            "confidence": 1.5,  # Out of range
        }
        assert not (0.0 <= invalid_response_3["confidence"] <= 1.0)

        # Invalid winner value
        invalid_response_4 = {
            "winner": "C",  # Invalid value
            "reasoning": "Response C is better",
            "confidence": 0.8,
        }
        assert invalid_response_4["winner"] not in ["A", "B", "tie"]

    def test_fallback_parsing_logic(self):
        """Test the fallback parsing logic for unstructured responses."""
        # Test positive sentiment words
        positive_content = "This is an excellent response with outstanding quality and remarkable insights."
        content_lower = positive_content.lower()

        fallback_score = 3
        if "excellent" in content_lower or "outstanding" in content_lower:
            fallback_score = 5
        elif "good" in content_lower or "well" in content_lower:
            fallback_score = 4
        elif "poor" in content_lower or "bad" in content_lower:
            fallback_score = 2
        elif "terrible" in content_lower or "awful" in content_lower:
            fallback_score = 1

        assert fallback_score == 5

        # Test negative sentiment words
        negative_content = "This is a terrible response with awful quality."
        content_lower = negative_content.lower()

        fallback_score = 3
        if "excellent" in content_lower or "outstanding" in content_lower:
            fallback_score = 5
        elif "good" in content_lower or "well" in content_lower:
            fallback_score = 4
        elif "poor" in content_lower or "bad" in content_lower:
            fallback_score = 2
        elif "terrible" in content_lower or "awful" in content_lower:
            fallback_score = 1

        assert fallback_score == 1

        # Test neutral content
        neutral_content = "This is an average response with moderate quality."
        content_lower = neutral_content.lower()

        fallback_score = 3
        if "excellent" in content_lower or "outstanding" in content_lower:
            fallback_score = 5
        elif "good" in content_lower or "well" in content_lower:
            fallback_score = 4
        elif "poor" in content_lower or "bad" in content_lower:
            fallback_score = 2
        elif "terrible" in content_lower or "awful" in content_lower:
            fallback_score = 1

        assert fallback_score == 3  # Default fallback
