"""Tests for structured output functionality across all providers."""

import json
import pytest
from unittest.mock import MagicMock, patch, Mock
from typing import Dict, Any

from src.llm_judge.infrastructure.clients.openai_client import OpenAIClient, OpenAIResponse
from src.llm_judge.infrastructure.clients.anthropic_client import (
    AnthropicClient,
    AnthropicResponse,
)
from src.llm_judge.infrastructure.clients.bedrock_client import (
    BedrockClient,
    BedrockResponse,
)
from src.llm_judge.infrastructure.config.config import LLMConfig


class TestStructuredOutput:
    """Test structured output functionality for all providers."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration for testing."""
        config = MagicMock(spec=LLMConfig)
        config.openai_api_key = "test-openai-key"
        config.anthropic_api_key = "test-anthropic-key"
        config.aws_access_key_id = "test-aws-key"
        config.aws_secret_access_key = "test-aws-secret"
        config.aws_region = "us-east-1"
        config.openai_model = "gpt-4"
        config.anthropic_model = "claude-3-sonnet-20240229"
        config.bedrock_model = "anthropic.claude-3-sonnet-20240229-v1:0"
        config.max_retries = 3
        config.retry_max_attempts = 3
        config.retry_base_delay = 1.0
        config.retry_max_delay = 60.0
        config.retry_backoff_multiplier = 2.0
        config.retry_jitter_enabled = True
        config.openai_request_timeout = 30
        config.anthropic_request_timeout = 30
        config.bedrock_request_timeout = 30
        config.bedrock_connect_timeout = 10
        config.anthropic_temperature = 0.1
        config.anthropic_top_p = None
        config.gpt5_reasoning_effort = "medium"
        return config

    @pytest.mark.asyncio
    async def test_openai_structured_output_evaluation(self, mock_config):
        """Test OpenAI structured output for evaluation."""
        with patch(
            "src.llm_judge.infrastructure.clients.openai_client.OpenAI"
        ) as mock_openai:
            # Mock the OpenAI client
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            # Mock the response
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = (
                '{"score": 4, "reasoning": "Good response", "confidence": 0.8}'
            )
            mock_response.choices[0].finish_reason = "stop"
            mock_response.usage.prompt_tokens = 100
            mock_response.usage.completion_tokens = 50
            mock_response.usage.total_tokens = 150
            mock_response.model = "gpt-4"

            mock_client.chat.completions.create = Mock(return_value=mock_response)

            # Create client and test
            client = OpenAIClient(mock_config)
            result = await client.evaluate_with_openai(
                prompt="Test prompt", response_text="Test response", criteria="quality"
            )

            # Verify the result
            assert result["score"] == 4
            assert result["reasoning"] == "Good response"
            assert result["confidence"] == 0.8

            # Verify that response_format was passed to the API call
            call_args = mock_client.chat.completions.create.call_args
            assert "response_format" in call_args.kwargs
            response_format = call_args.kwargs["response_format"]
            assert response_format["type"] == "json_schema"
            assert "json_schema" in response_format

    @pytest.mark.asyncio
    async def test_openai_structured_output_comparison(self, mock_config):
        """Test OpenAI structured output for comparison."""
        with patch(
            "src.llm_judge.infrastructure.clients.openai_client.OpenAI"
        ) as mock_openai:
            # Mock the OpenAI client
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            # Mock the response
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = (
                '{"winner": "A", "reasoning": "Response A is better", "confidence": 0.9}'
            )
            mock_response.choices[0].finish_reason = "stop"
            mock_response.usage.prompt_tokens = 100
            mock_response.usage.completion_tokens = 50
            mock_response.usage.total_tokens = 150
            mock_response.model = "gpt-4"

            mock_client.chat.completions.create = Mock(return_value=mock_response)

            # Create client and test
            client = OpenAIClient(mock_config)
            result = await client.compare_with_openai(
                prompt="Test prompt", response_a="Response A", response_b="Response B"
            )

            # Verify the result
            assert result["winner"] == "A"
            assert result["reasoning"] == "Response A is better"
            assert result["confidence"] == 0.9

    @pytest.mark.asyncio
    async def test_anthropic_structured_output_evaluation(self, mock_config):
        """Test Anthropic structured output for evaluation."""
        with patch(
            "src.llm_judge.infrastructure.clients.anthropic_client.anthropic.Anthropic"
        ) as mock_anthropic:
            # Mock the Anthropic client
            mock_client = MagicMock()
            mock_anthropic.return_value = mock_client

            # Mock the response
            mock_response = MagicMock()
            mock_response.content = [MagicMock()]
            mock_response.content[0].text = (
                '{"score": 3, "reasoning": "Average response", "confidence": 0.7}'
            )
            mock_response.stop_reason = "end_turn"
            mock_response.usage.input_tokens = 100
            mock_response.usage.output_tokens = 50
            mock_response.model = "claude-3-sonnet-20240229"

            mock_client.messages.create = Mock(return_value=mock_response)

            # Create client and test
            client = AnthropicClient(mock_config)
            result = await client.evaluate_with_anthropic(
                prompt="Test prompt", response_text="Test response", criteria="quality"
            )

            # Verify the result
            assert result["score"] == 3
            assert result["reasoning"] == "Average response"
            assert result["confidence"] == 0.7

            # Verify that response_format was passed to the API call
            call_args = mock_client.messages.create.call_args
            assert "response_format" in call_args.kwargs
            response_format = call_args.kwargs["response_format"]
            assert response_format["type"] == "json_schema"
            assert "json_schema" in response_format

    @pytest.mark.asyncio
    async def test_anthropic_structured_output_comparison(self, mock_config):
        """Test Anthropic structured output for comparison."""
        with patch(
            "src.llm_judge.infrastructure.clients.anthropic_client.anthropic.Anthropic"
        ) as mock_anthropic:
            # Mock the Anthropic client
            mock_client = MagicMock()
            mock_anthropic.return_value = mock_client

            # Mock the response
            mock_response = MagicMock()
            mock_response.content = [MagicMock()]
            mock_response.content[0].text = (
                '{"winner": "tie", "reasoning": "Both responses are similar", "confidence": 0.6}'
            )
            mock_response.stop_reason = "end_turn"
            mock_response.usage.input_tokens = 100
            mock_response.usage.output_tokens = 50
            mock_response.model = "claude-3-sonnet-20240229"

            mock_client.messages.create = Mock(return_value=mock_response)

            # Create client and test
            client = AnthropicClient(mock_config)
            result = await client.compare_with_anthropic(
                prompt="Test prompt", response_a="Response A", response_b="Response B"
            )

            # Verify the result
            assert result["winner"] == "tie"
            assert result["reasoning"] == "Both responses are similar"
            assert result["confidence"] == 0.6

    @pytest.mark.asyncio
    async def test_bedrock_structured_output_evaluation(self, mock_config):
        """Test Bedrock structured output for evaluation."""
        with patch(
            "src.llm_judge.infrastructure.clients.bedrock_client.boto3.Session"
        ) as mock_session:
            # Mock the Bedrock client
            mock_bedrock_client = MagicMock()
            mock_session.return_value.client.return_value = mock_bedrock_client

            # Mock the response
            mock_response = {"body": MagicMock()}
            mock_response["body"].read.return_value = json.dumps(
                {
                    "content": [
                        {
                            "text": '{"score": 5, "reasoning": "Excellent response", "confidence": 0.95}'
                        }
                    ],
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 100, "output_tokens": 50},
                }
            ).encode()

            mock_bedrock_client.invoke_model = Mock(return_value=mock_response)

            # Create client and test
            client = BedrockClient(mock_config)
            result = await client.evaluate_with_bedrock(
                prompt="Test prompt", response_text="Test response", criteria="quality"
            )

            # Verify the result
            assert result["score"] == 5
            assert result["reasoning"] == "Excellent response"
            assert result["confidence"] == 0.95

            # Verify that response_format was passed to the API call
            call_args = mock_bedrock_client.invoke_model.call_args
            body = json.loads(call_args.kwargs["body"])
            assert "response_format" in body
            response_format = body["response_format"]
            assert response_format["type"] == "json_schema"
            assert "json_schema" in response_format

    @pytest.mark.asyncio
    async def test_bedrock_structured_output_comparison(self, mock_config):
        """Test Bedrock structured output for comparison."""
        with patch(
            "src.llm_judge.infrastructure.clients.bedrock_client.boto3.Session"
        ) as mock_session:
            # Mock the Bedrock client
            mock_bedrock_client = MagicMock()
            mock_session.return_value.client.return_value = mock_bedrock_client

            # Mock the response
            mock_response = {"body": MagicMock()}
            mock_response["body"].read.return_value = json.dumps(
                {
                    "content": [
                        {
                            "text": '{"winner": "B", "reasoning": "Response B is superior", "confidence": 0.85}'
                        }
                    ],
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 100, "output_tokens": 50},
                }
            ).encode()

            mock_bedrock_client.invoke_model = Mock(return_value=mock_response)

            # Create client and test
            client = BedrockClient(mock_config)
            result = await client.compare_with_bedrock(
                prompt="Test prompt", response_a="Response A", response_b="Response B"
            )

            # Verify the result
            assert result["winner"] == "B"
            assert result["reasoning"] == "Response B is superior"
            assert result["confidence"] == 0.85

    def test_json_schema_validation(self):
        """Test that JSON schemas are properly structured."""
        # Test evaluation schema structure
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

        # Test comparison schema structure
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
        assert evaluation_schema["type"] == "json_schema"
        assert evaluation_schema["json_schema"]["strict"] is True
        assert "score" in evaluation_schema["json_schema"]["schema"]["properties"]
        assert "reasoning" in evaluation_schema["json_schema"]["schema"]["properties"]
        assert "confidence" in evaluation_schema["json_schema"]["schema"]["properties"]

        assert comparison_schema["type"] == "json_schema"
        assert comparison_schema["json_schema"]["strict"] is True
        assert "winner" in comparison_schema["json_schema"]["schema"]["properties"]
        assert "reasoning" in comparison_schema["json_schema"]["schema"]["properties"]
        assert "confidence" in comparison_schema["json_schema"]["schema"]["properties"]
        assert comparison_schema["json_schema"]["schema"]["properties"]["winner"][
            "enum"
        ] == ["A", "B", "tie"]

    @pytest.mark.asyncio
    async def test_fallback_parsing_on_json_error(self, mock_config):
        """Test that fallback parsing works when structured output fails."""
        with patch(
            "src.llm_judge.infrastructure.clients.openai_client.OpenAI"
        ) as mock_openai:
            # Mock the OpenAI client
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            # Mock a response with invalid JSON
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = (
                "This is an excellent response with outstanding quality."
            )
            mock_response.choices[0].finish_reason = "stop"
            mock_response.usage.prompt_tokens = 100
            mock_response.usage.completion_tokens = 50
            mock_response.usage.total_tokens = 150
            mock_response.model = "gpt-4"

            mock_client.chat.completions.create = Mock(return_value=mock_response)

            # Create client and test
            client = OpenAIClient(mock_config)
            result = await client.evaluate_with_openai(
                prompt="Test prompt", response_text="Test response", criteria="quality"
            )

            # Verify fallback parsing worked
            assert result["score"] == 5  # "excellent" and "outstanding" should map to 5
            assert "Failed to parse structured response" in result["reasoning"]
            assert result["confidence"] == 0.3  # Low confidence for fallback
