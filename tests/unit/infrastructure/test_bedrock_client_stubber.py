"""Comprehensive stubber-based tests for AWS Bedrock client functionality.

This module provides realistic testing using boto3's Stubber to mock AWS Bedrock API responses
without making actual API calls. This approach provides better integration testing while
maintaining test isolation and speed.
"""

import json
import pytest
import boto3
from botocore.stub import Stubber
from botocore.exceptions import ClientError, BotoCoreError
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

from src.llm_judge.infrastructure.config.config import LLMConfig
from src.llm_judge.infrastructure.clients.bedrock_client import (
    BedrockClient,
    BedrockResponse,
    BedrockError,
    RateLimitError,
)


@pytest.fixture
def test_config():
    """Create test configuration with AWS credentials."""
    return LLMConfig(
        aws_access_key_id="AKIATEST123456789",
        aws_secret_access_key="test-secret-access-key-12345",
        aws_region="us-east-1",
        bedrock_model="amazon.nova-pro-v1:0",
        default_provider="bedrock",
        bedrock_request_timeout=30,
        bedrock_connect_timeout=10,
        request_timeout=30,
        max_retries=3,
        bedrock_temperature=0.1,
    )


@pytest.fixture
def anthropic_config():
    """Create test configuration for Anthropic models."""
    return LLMConfig(
        aws_access_key_id="AKIATEST123456789",
        aws_secret_access_key="test-secret-access-key-12345",
        aws_region="us-east-1",
        bedrock_model="anthropic.claude-3-sonnet-20240229-v1:0",
        default_provider="bedrock",
        bedrock_request_timeout=30,
        bedrock_connect_timeout=10,
        request_timeout=30,
        max_retries=3,
        bedrock_temperature=0.1,
    )


@pytest.fixture
def bedrock_client_with_stubber(test_config):
    """Create a Bedrock client with stubber for testing."""
    with patch(
        "src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE", True
    ):
        # Create real boto3 session and client for stubbing
        session = boto3.Session(
            aws_access_key_id=test_config.aws_access_key_id,
            aws_secret_access_key=test_config.aws_secret_access_key,
            region_name=test_config.aws_region,
        )
        client = session.client("bedrock-runtime")
        stubber = Stubber(client)

        # Create BedrockClient with the real client
        bedrock_client = BedrockClient(test_config)
        bedrock_client.client = client  # Replace with stubbed client

        yield bedrock_client, stubber

        # Clean up
        stubber.deactivate()


@pytest.fixture
def anthropic_client_with_stubber(anthropic_config):
    """Create an Anthropic Bedrock client with stubber for testing."""
    with patch(
        "src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE", True
    ):
        # Create real boto3 session and client for stubbing
        session = boto3.Session(
            aws_access_key_id=anthropic_config.aws_access_key_id,
            aws_secret_access_key=anthropic_config.aws_secret_access_key,
            region_name=anthropic_config.aws_region,
        )
        client = session.client("bedrock-runtime")
        stubber = Stubber(client)

        # Create BedrockClient with the real client
        bedrock_client = BedrockClient(anthropic_config)
        bedrock_client.client = client  # Replace with stubbed client

        yield bedrock_client, stubber

        # Clean up
        stubber.deactivate()


class TestBedrockClientStubberInitialization:
    """Test Bedrock client initialization with stubber."""

    def test_client_initialization_with_stubber(self, test_config):
        """Test that Bedrock client initializes correctly with stubber."""
        with patch(
            "src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE", True
        ):
            session = boto3.Session(
                aws_access_key_id=test_config.aws_access_key_id,
                aws_secret_access_key=test_config.aws_secret_access_key,
                region_name=test_config.aws_region,
            )
            client = session.client("bedrock-runtime")
            stubber = Stubber(client)

            try:
                bedrock_client = BedrockClient(test_config)
                bedrock_client.client = client

                assert bedrock_client.config == test_config
                assert bedrock_client.client == client
                assert hasattr(bedrock_client, "_retry_manager")
                assert hasattr(bedrock_client, "_timeout_manager")

            finally:
                stubber.deactivate()


class TestBedrockClientStubberNovaModels:
    """Test Bedrock client with Nova models using stubber."""

    @pytest.mark.asyncio
    async def test_invoke_nova_model_success(self, bedrock_client_with_stubber):
        """Test successful Nova model invocation with stubber."""
        client, stubber = bedrock_client_with_stubber

        # Prepare expected request
        expected_request = {
            "modelId": "amazon.nova-pro-v1:0",
            "body": json.dumps(
                {
                    "messages": [
                        {"role": "user", "content": [{"text": "Hello Nova!"}]}
                    ],
                    "inferenceConfig": {"maxTokens": 100, "temperature": 0.1},
                }
            ),
            "contentType": "application/json",
        }

        # Prepare successful response
        response_body = {
            "output": {
                "message": {
                    "content": [{"text": "Hello! I am Nova, Amazon's AI assistant."}]
                }
            },
            "stopReason": "end_turn",
            "usage": {"inputTokens": 10, "outputTokens": 20},
        }

        expected_response = {"body": Mock(), "contentType": "application/json"}
        expected_response["body"].read.return_value = json.dumps(response_body).encode(
            "utf-8"
        )

        # Add stub
        stubber.add_response("invoke_model", expected_response, expected_request)
        stubber.activate()

        # Mock retry manager to bypass retry logic
        with patch.object(client._retry_manager, "execute_with_retry") as mock_retry:

            async def mock_execute(func, **kwargs):
                return await func()

            mock_retry.side_effect = mock_execute

            # Execute test
            messages = [{"role": "user", "content": "Hello Nova!"}]
            response = await client.invoke_model(messages, max_tokens=100)

            # Verify response
            assert isinstance(response, BedrockResponse)
            assert response.content == "Hello! I am Nova, Amazon's AI assistant."
            assert response.model == "amazon.nova-pro-v1:0"
            assert response.stop_reason == "end_turn"
            assert response.usage["input_tokens"] == 10
            assert response.usage["output_tokens"] == 20

        # Verify stub was called correctly
        stubber.assert_no_pending_responses()

    @pytest.mark.asyncio
    async def test_invoke_nova_model_with_system_message(
        self, bedrock_client_with_stubber
    ):
        """Test Nova model invocation with system message."""
        client, stubber = bedrock_client_with_stubber

        # Prepare expected request with system message
        expected_request = {
            "modelId": "amazon.nova-pro-v1:0",
            "body": json.dumps(
                {
                    "messages": [
                        {"role": "user", "content": [{"text": "What is AI?"}]}
                    ],
                    "system": [{"text": "You are a helpful AI assistant."}],
                    "inferenceConfig": {"maxTokens": 200, "temperature": 0.1},
                }
            ),
            "contentType": "application/json",
        }

        # Prepare response
        response_body = {
            "output": {
                "message": {
                    "content": [
                        {
                            "text": "AI stands for Artificial Intelligence, which refers to computer systems that can perform tasks typically requiring human intelligence."
                        }
                    ]
                }
            },
            "stopReason": "end_turn",
            "usage": {"inputTokens": 15, "outputTokens": 35},
        }

        expected_response = {"body": Mock(), "contentType": "application/json"}
        expected_response["body"].read.return_value = json.dumps(response_body).encode(
            "utf-8"
        )

        # Add stub
        stubber.add_response("invoke_model", expected_response, expected_request)
        stubber.activate()

        # Mock retry manager
        with patch.object(client._retry_manager, "execute_with_retry") as mock_retry:

            async def mock_execute(func, **kwargs):
                return await func()

            mock_retry.side_effect = mock_execute

            # Execute test
            messages = [
                {"role": "system", "content": "You are a helpful AI assistant."},
                {"role": "user", "content": "What is AI?"},
            ]
            response = await client.invoke_model(messages, max_tokens=200)

            # Verify response
            assert (
                response.content
                == "AI stands for Artificial Intelligence, which refers to computer systems that can perform tasks typically requiring human intelligence."
            )
            assert response.usage["input_tokens"] == 15
            assert response.usage["output_tokens"] == 35

        stubber.assert_no_pending_responses()


class TestBedrockClientStubberAnthropicModels:
    """Test Bedrock client with Anthropic models using stubber."""

    @pytest.mark.asyncio
    async def test_invoke_anthropic_model_success(self, anthropic_client_with_stubber):
        """Test successful Anthropic model invocation with stubber."""
        client, stubber = anthropic_client_with_stubber

        # Prepare expected request for Anthropic format
        expected_request = {
            "modelId": "anthropic.claude-3-sonnet-20240229-v1:0",
            "body": json.dumps(
                {
                    "max_tokens": 100,
                    "messages": [{"role": "user", "content": "Hello Claude!"}],
                    "temperature": 0.1,
                    "anthropic_version": "bedrock-2023-05-31",
                }
            ),
            "contentType": "application/json",
        }

        # Prepare successful response in Anthropic format
        response_body = {
            "content": [
                {"text": "Hello! I'm Claude, an AI assistant created by Anthropic."}
            ],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 12, "output_tokens": 18},
        }

        expected_response = {"body": Mock(), "contentType": "application/json"}
        expected_response["body"].read.return_value = json.dumps(response_body).encode(
            "utf-8"
        )

        # Add stub
        stubber.add_response("invoke_model", expected_response, expected_request)
        stubber.activate()

        # Mock retry manager
        with patch.object(client._retry_manager, "execute_with_retry") as mock_retry:

            async def mock_execute(func, **kwargs):
                return await func()

            mock_retry.side_effect = mock_execute

            # Execute test
            messages = [{"role": "user", "content": "Hello Claude!"}]
            response = await client.invoke_model(messages, max_tokens=100)

            # Verify response
            assert isinstance(response, BedrockResponse)
            assert (
                response.content
                == "Hello! I'm Claude, an AI assistant created by Anthropic."
            )
            assert response.model == "anthropic.claude-3-sonnet-20240229-v1:0"
            assert response.stop_reason == "end_turn"
            assert response.usage["input_tokens"] == 12
            assert response.usage["output_tokens"] == 18

        stubber.assert_no_pending_responses()

    @pytest.mark.asyncio
    async def test_invoke_anthropic_model_with_system_message(
        self, anthropic_client_with_stubber
    ):
        """Test Anthropic model invocation with system message."""
        client, stubber = anthropic_client_with_stubber

        # Prepare expected request with system message
        expected_request = {
            "modelId": "anthropic.claude-3-sonnet-20240229-v1:0",
            "body": json.dumps(
                {
                    "max_tokens": 300,
                    "messages": [
                        {
                            "role": "user",
                            "content": "Explain machine learning",
                        }
                    ],
                    "system": "You are a technical expert who explains complex topics clearly.",
                    "temperature": 0.1,
                    "anthropic_version": "bedrock-2023-05-31",
                }
            ),
            "contentType": "application/json",
        }

        # Prepare response
        response_body = {
            "content": [
                {
                    "text": "Machine learning is a subset of artificial intelligence that enables computers to learn and improve from experience without being explicitly programmed for every task."
                }
            ],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 20, "output_tokens": 45},
        }

        expected_response = {"body": Mock(), "contentType": "application/json"}
        expected_response["body"].read.return_value = json.dumps(response_body).encode(
            "utf-8"
        )

        # Add stub
        stubber.add_response("invoke_model", expected_response, expected_request)
        stubber.activate()

        # Mock retry manager
        with patch.object(client._retry_manager, "execute_with_retry") as mock_retry:

            async def mock_execute(func, **kwargs):
                return await func()

            mock_retry.side_effect = mock_execute

            # Execute test
            messages = [
                {
                    "role": "system",
                    "content": "You are a technical expert who explains complex topics clearly.",
                },
                {"role": "user", "content": "Explain machine learning"},
            ]
            response = await client.invoke_model(messages, max_tokens=300)

            # Verify response
            assert (
                "Machine learning is a subset of artificial intelligence"
                in response.content
            )
            assert response.usage["input_tokens"] == 20
            assert response.usage["output_tokens"] == 45

        stubber.assert_no_pending_responses()


class TestBedrockClientStubberErrorScenarios:
    """Test error scenarios using stubber."""

    @pytest.mark.asyncio
    async def test_throttling_exception(self, bedrock_client_with_stubber):
        """Test handling of throttling exception."""
        client, stubber = bedrock_client_with_stubber

        # Prepare expected request
        expected_request = {
            "modelId": "amazon.nova-pro-v1:0",
            "body": json.dumps(
                {
                    "messages": [
                        {"role": "user", "content": [{"text": "Test message"}]}
                    ],
                    "inferenceConfig": {
                        "maxTokens": 100,
                        "temperature": 0.1,
                    },
                }
            ),
            "contentType": "application/json",
        }

        # Prepare throttling error response
        error_response = {
            "Error": {
                "Code": "ThrottlingException",
                "Message": "Rate limit exceeded. Please try again later.",
            }
        }

        # Add stub for error
        stubber.add_client_error(
            "invoke_model",
            "ThrottlingException",
            "Rate limit exceeded. Please try again later.",
            expected_params=expected_request,
        )
        stubber.activate()

        # Mock retry manager
        with patch.object(client._retry_manager, "execute_with_retry") as mock_retry:

            async def mock_execute(func, **kwargs):
                return await func()

            mock_retry.side_effect = mock_execute

            # Execute test and expect RateLimitError
            messages = [{"role": "user", "content": "Test message"}]
            with pytest.raises(RateLimitError, match="Rate limit exceeded"):
                await client.invoke_model(messages, max_tokens=100)

        stubber.assert_no_pending_responses()

    @pytest.mark.asyncio
    async def test_validation_exception(self, bedrock_client_with_stubber):
        """Test handling of validation exception."""
        client, stubber = bedrock_client_with_stubber

        # Prepare expected request
        expected_request = {
            "modelId": "amazon.nova-pro-v1:0",
            "body": json.dumps(
                {
                    "messages": [
                        {"role": "user", "content": [{"text": "Test message"}]}
                    ],
                    "inferenceConfig": {
                        "maxTokens": 100,
                        "temperature": 0.1,
                    },
                }
            ),
            "contentType": "application/json",
        }

        # Add stub for validation error
        stubber.add_client_error(
            "invoke_model",
            "ValidationException",
            "Invalid request parameters.",
            expected_params=expected_request,
        )
        stubber.activate()

        # Mock retry manager
        with patch.object(client._retry_manager, "execute_with_retry") as mock_retry:

            async def mock_execute(func, **kwargs):
                return await func()

            mock_retry.side_effect = mock_execute

            # Execute test and expect BedrockError
            messages = [{"role": "user", "content": "Test message"}]
            with pytest.raises(BedrockError, match="Client error.*ValidationException"):
                await client.invoke_model(messages, max_tokens=100)

        stubber.assert_no_pending_responses()

    @pytest.mark.asyncio
    async def test_access_denied_exception(self, bedrock_client_with_stubber):
        """Test handling of access denied exception."""
        client, stubber = bedrock_client_with_stubber

        # Prepare expected request
        expected_request = {
            "modelId": "amazon.nova-pro-v1:0",
            "body": json.dumps(
                {
                    "messages": [
                        {"role": "user", "content": [{"text": "Test message"}]}
                    ],
                    "inferenceConfig": {
                        "maxTokens": 100,
                        "temperature": 0.1,
                    },
                }
            ),
            "contentType": "application/json",
        }

        # Add stub for access denied error
        stubber.add_client_error(
            "invoke_model",
            "AccessDeniedException",
            "You do not have permission to access this resource.",
            expected_params=expected_request,
        )
        stubber.activate()

        # Mock retry manager
        with patch.object(client._retry_manager, "execute_with_retry") as mock_retry:

            async def mock_execute(func, **kwargs):
                return await func()

            mock_retry.side_effect = mock_execute

            # Execute test and expect BedrockError
            messages = [{"role": "user", "content": "Test message"}]
            with pytest.raises(
                BedrockError, match="Client error.*AccessDeniedException"
            ):
                await client.invoke_model(messages, max_tokens=100)

        stubber.assert_no_pending_responses()

    @pytest.mark.asyncio
    async def test_internal_server_error(self, bedrock_client_with_stubber):
        """Test handling of internal server error."""
        client, stubber = bedrock_client_with_stubber

        # Prepare expected request
        expected_request = {
            "modelId": "amazon.nova-pro-v1:0",
            "body": json.dumps(
                {
                    "messages": [
                        {"role": "user", "content": [{"text": "Test message"}]}
                    ],
                    "inferenceConfig": {
                        "maxTokens": 100,
                        "temperature": 0.1,
                    },
                }
            ),
            "contentType": "application/json",
        }

        # Add stub for internal server error
        stubber.add_client_error(
            "invoke_model",
            "InternalServerError",
            "An internal server error occurred.",
            expected_params=expected_request,
        )
        stubber.activate()

        # Mock retry manager
        with patch.object(client._retry_manager, "execute_with_retry") as mock_retry:

            async def mock_execute(func, **kwargs):
                return await func()

            mock_retry.side_effect = mock_execute

            # Execute test and expect BedrockError
            messages = [{"role": "user", "content": "Test message"}]
            with pytest.raises(
                BedrockError, match="Bedrock API error.*InternalServerError"
            ):
                await client.invoke_model(messages, max_tokens=100)

        stubber.assert_no_pending_responses()


class TestBedrockClientStubberEvaluation:
    """Test evaluation functionality using stubber."""

    @pytest.mark.asyncio
    async def test_evaluate_with_bedrock_success(self, bedrock_client_with_stubber):
        """Test successful evaluation with stubber."""
        client, stubber = bedrock_client_with_stubber

        # Prepare expected request for evaluation - matches actual evaluate_with_bedrock method
        expected_request = {
            "modelId": "amazon.nova-pro-v1:0",
            "body": json.dumps(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "text": "Evaluate this response on accuracy from 1-5.\n\nOriginal Question: What is AI?\n\nResponse to Evaluate: AI is artificial intelligence\n\nProvide your evaluation in JSON format with the following structure:\n- score: A number between 1-5\n- reasoning: A detailed explanation of your evaluation\n- confidence: A number between 0.0-1.0 indicating your confidence in this evaluation\n\nBe thorough and fair in your evaluation."
                                }
                            ],
                        }
                    ],
                    "system": [
                        {
                            "text": "You are an expert evaluator. Your task is to evaluate responses based on given criteria. You must respond with valid JSON in the exact format specified."
                        }
                    ],
                    "inferenceConfig": {"maxTokens": 500, "temperature": 0.1},
                    "responseFormat": {
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
                    },
                }
            ),
            "contentType": "application/json",
        }

        # Prepare successful evaluation response
        evaluation_response = {
            "score": 4.5,
            "reasoning": "The response is factually accurate and provides a clear definition of AI.",
            "confidence": 0.9,
        }

        response_body = {
            "output": {
                "message": {"content": [{"text": json.dumps(evaluation_response)}]}
            },
            "stopReason": "end_turn",
            "usage": {"inputTokens": 50, "outputTokens": 80},
        }

        expected_response = {"body": Mock(), "contentType": "application/json"}
        expected_response["body"].read.return_value = json.dumps(response_body).encode(
            "utf-8"
        )

        # Add stub
        stubber.add_response("invoke_model", expected_response, expected_request)
        stubber.activate()

        # Mock retry manager
        with patch.object(client._retry_manager, "execute_with_retry") as mock_retry:

            async def mock_execute(func, **kwargs):
                return await func()

            mock_retry.side_effect = mock_execute

            # Execute test
            result = await client.evaluate_with_bedrock(
                prompt="What is AI?",
                response_text="AI is artificial intelligence",
                criteria="accuracy",
            )

            # Verify result
            assert result["score"] == 4  # Score is converted to integer
            assert (
                result["reasoning"]
                == "The response is factually accurate and provides a clear definition of AI."
            )
            assert result["confidence"] == 0.9

        stubber.assert_no_pending_responses()

    @pytest.mark.asyncio
    async def test_evaluate_with_bedrock_json_parse_error(
        self, bedrock_client_with_stubber
    ):
        """Test evaluation with JSON parsing fallback."""
        client, stubber = bedrock_client_with_stubber

        # Prepare expected request - matches actual evaluate_with_bedrock method
        expected_request = {
            "modelId": "amazon.nova-pro-v1:0",
            "body": json.dumps(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "text": "Evaluate this response on quality from 1-5.\n\nOriginal Question: What is AI?\n\nResponse to Evaluate: This is a good response\n\nProvide your evaluation in JSON format with the following structure:\n- score: A number between 1-5\n- reasoning: A detailed explanation of your evaluation\n- confidence: A number between 0.0-1.0 indicating your confidence in this evaluation\n\nBe thorough and fair in your evaluation."
                                }
                            ],
                        }
                    ],
                    "system": [
                        {
                            "text": "You are an expert evaluator. Your task is to evaluate responses based on given criteria. You must respond with valid JSON in the exact format specified."
                        }
                    ],
                    "inferenceConfig": {"maxTokens": 500, "temperature": 0.1},
                    "responseFormat": {
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
                    },
                }
            ),
            "contentType": "application/json",
        }

        # Prepare response with invalid JSON (triggers fallback)
        response_body = {
            "output": {
                "message": {
                    "content": [
                        {
                            "text": "This response is good and well-written with clear explanations."
                        }
                    ]
                }
            },
            "stopReason": "end_turn",
            "usage": {"inputTokens": 45, "outputTokens": 15},
        }

        expected_response = {"body": Mock(), "contentType": "application/json"}
        expected_response["body"].read.return_value = json.dumps(response_body).encode(
            "utf-8"
        )

        # Add stub
        stubber.add_response("invoke_model", expected_response, expected_request)
        stubber.activate()

        # Mock retry manager
        with patch.object(client._retry_manager, "execute_with_retry") as mock_retry:

            async def mock_execute(func, **kwargs):
                return await func()

            mock_retry.side_effect = mock_execute

            # Execute test
            result = await client.evaluate_with_bedrock(
                prompt="What is AI?",
                response_text="This is a good response",
                criteria="quality",
            )

            # Verify fallback result
            assert result["score"] == 4.0  # "good" keyword triggers score of 4
            assert "Failed to parse structured response" in result["reasoning"]
            assert result["confidence"] == 0.3

        stubber.assert_no_pending_responses()


class TestBedrockClientStubberComparison:
    """Test comparison functionality using stubber."""

    @pytest.mark.asyncio
    async def test_compare_with_bedrock_success(self, bedrock_client_with_stubber):
        """Test successful comparison with stubber."""
        client, stubber = bedrock_client_with_stubber

        # Prepare expected request for comparison - matches actual compare_with_bedrock method
        expected_request = {
            "modelId": "amazon.nova-pro-v1:0",
            "body": json.dumps(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "text": 'Compare these two responses and determine which is better.\n\nQuestion: What is AI?\n\nResponse A: AI is artificial intelligence\n\nResponse B: AI is a field of computer science focused on creating intelligent machines\n\nRespond in JSON format with the following structure:\n- winner: Either "A", "B", or "tie"\n- reasoning: A detailed explanation of your comparison\n- confidence: A number between 0.0-1.0 indicating your confidence in this comparison\n\nBe thorough in your comparison.'
                                }
                            ],
                        }
                    ],
                    "system": [
                        {
                            "text": "You are an expert evaluator comparing responses. You must respond with valid JSON in the exact format specified."
                        }
                    ],
                    "inferenceConfig": {"maxTokens": 500, "temperature": 0.1},
                    "responseFormat": {
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
                    },
                }
            ),
            "contentType": "application/json",
        }

        # Prepare successful comparison response
        comparison_response = {
            "winner": "B",
            "reasoning": "Response B provides more comprehensive and detailed information about AI.",
            "confidence": 0.85,
        }

        response_body = {
            "output": {
                "message": {"content": [{"text": json.dumps(comparison_response)}]}
            },
            "stopReason": "end_turn",
            "usage": {"inputTokens": 80, "outputTokens": 60},
        }

        expected_response = {"body": Mock(), "contentType": "application/json"}
        expected_response["body"].read.return_value = json.dumps(response_body).encode(
            "utf-8"
        )

        # Add stub
        stubber.add_response("invoke_model", expected_response, expected_request)
        stubber.activate()

        # Mock retry manager
        with patch.object(client._retry_manager, "execute_with_retry") as mock_retry:

            async def mock_execute(func, **kwargs):
                return await func()

            mock_retry.side_effect = mock_execute

            # Execute test
            result = await client.compare_with_bedrock(
                prompt="What is AI?",
                response_a="AI is artificial intelligence",
                response_b="AI is a field of computer science focused on creating intelligent machines",
            )

            # Verify result
            assert result["winner"] == "B"
            assert (
                result["reasoning"]
                == "Response B provides more comprehensive and detailed information about AI."
            )
            assert result["confidence"] == 0.85

        stubber.assert_no_pending_responses()


class TestBedrockClientStubberRequestValidation:
    """Test request validation and formatting with stubber."""

    def test_prepare_nova_body_format(self, bedrock_client_with_stubber):
        """Test Nova request body formatting."""
        client, stubber = bedrock_client_with_stubber

        messages = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello Nova!"},
        ]

        body = client._prepare_nova_body(
            messages, max_tokens=150, temperature=0.3, top_p=0.8
        )

        # Verify Nova-specific format
        assert body["inferenceConfig"]["maxTokens"] == 150
        assert body["inferenceConfig"]["temperature"] == 0.3
        # topP is not included when temperature is provided (mutually exclusive)
        assert body["system"] == [{"text": "You are a helpful assistant"}]
        assert len(body["messages"]) == 1  # System message becomes separate parameter
        assert body["messages"][0]["role"] == "user"
        assert body["messages"][0]["content"] == [{"text": "Hello Nova!"}]

    def test_prepare_anthropic_body_format(self, anthropic_client_with_stubber):
        """Test Anthropic request body formatting."""
        client, stubber = anthropic_client_with_stubber

        messages = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello Claude!"},
        ]

        body = client._prepare_anthropic_body(
            messages, max_tokens=200, temperature=0.2, top_p=0.9
        )

        # Verify Anthropic-specific format
        assert body["max_tokens"] == 200
        assert body["temperature"] == 0.2
        # top_p is not included when temperature is provided (mutually exclusive)
        assert body["system"] == "You are a helpful assistant"
        assert len(body["messages"]) == 1  # System message becomes separate parameter
        assert body["messages"][0]["role"] == "user"
        assert body["messages"][0]["content"] == "Hello Claude!"
        assert body["anthropic_version"] == "bedrock-2023-05-31"

    @pytest.mark.asyncio
    async def test_request_parameter_validation(self, bedrock_client_with_stubber):
        """Test that request parameters are properly validated and formatted."""
        client, stubber = bedrock_client_with_stubber

        # Test with various parameter combinations
        messages = [{"role": "user", "content": "Test message"}]

        # Test with custom temperature and top_p
        expected_request = {
            "modelId": "amazon.nova-pro-v1:0",
            "body": json.dumps(
                {
                    "messages": [
                        {"role": "user", "content": [{"text": "Test message"}]}
                    ],
                    "inferenceConfig": {
                        "maxTokens": 100,
                        "temperature": 0.5,
                    },
                }
            ),
            "contentType": "application/json",
        }

        response_body = {
            "output": {"message": {"content": [{"text": "Test response"}]}},
            "stopReason": "end_turn",
            "usage": {"inputTokens": 5, "outputTokens": 10},
        }

        expected_response = {"body": Mock(), "contentType": "application/json"}
        expected_response["body"].read.return_value = json.dumps(response_body).encode(
            "utf-8"
        )

        # Add stub
        stubber.add_response("invoke_model", expected_response, expected_request)
        stubber.activate()

        # Mock retry manager
        with patch.object(client._retry_manager, "execute_with_retry") as mock_retry:

            async def mock_execute(func, **kwargs):
                return await func()

            mock_retry.side_effect = mock_execute

            # Execute test with custom parameters
            response = await client.invoke_model(
                messages, max_tokens=100, temperature=0.5, top_p=0.7
            )

            assert response.content == "Test response"

        stubber.assert_no_pending_responses()


class TestBedrockClientStubberIntegration:
    """Integration tests using stubber."""

    @pytest.mark.asyncio
    async def test_multiple_sequential_requests(self, bedrock_client_with_stubber):
        """Test multiple sequential requests with stubber."""
        client, stubber = bedrock_client_with_stubber

        # Prepare multiple requests and responses
        requests_responses = [
            {
                "request": {
                    "modelId": "amazon.nova-pro-v1:0",
                    "body": json.dumps(
                        {
                            "messages": [
                                {"role": "user", "content": [{"text": "First message"}]}
                            ],
                            "inferenceConfig": {"maxTokens": 100, "temperature": 0.1},
                        }
                    ),
                    "contentType": "application/json",
                },
                "response": {"body": Mock()},
            },
            {
                "request": {
                    "modelId": "amazon.nova-pro-v1:0",
                    "body": json.dumps(
                        {
                            "messages": [
                                {
                                    "role": "user",
                                    "content": [{"text": "Second message"}],
                                }
                            ],
                            "inferenceConfig": {"maxTokens": 100, "temperature": 0.1},
                        }
                    ),
                    "contentType": "application/json",
                },
                "response": {"body": Mock()},
            },
        ]

        # Set up responses
        for i, req_resp in enumerate(requests_responses):
            response_body = {
                "output": {"message": {"content": [{"text": f"Response {i+1}"}]}},
                "stopReason": "end_turn",
                "usage": {"inputTokens": 10 + i, "outputTokens": 20 + i},
            }
            req_resp["response"]["body"].read.return_value = json.dumps(
                response_body
            ).encode("utf-8")
            req_resp["response"]["contentType"] = "application/json"
            stubber.add_response(
                "invoke_model", req_resp["response"], req_resp["request"]
            )

        stubber.activate()

        # Mock retry manager
        with patch.object(client._retry_manager, "execute_with_retry") as mock_retry:

            async def mock_execute(func, **kwargs):
                return await func()

            mock_retry.side_effect = mock_execute

            # Execute multiple requests
            messages1 = [{"role": "user", "content": "First message"}]
            response1 = await client.invoke_model(messages1, max_tokens=100)

            messages2 = [{"role": "user", "content": "Second message"}]
            response2 = await client.invoke_model(messages2, max_tokens=100)

            # Verify responses
            assert response1.content == "Response 1"
            assert response2.content == "Response 2"
            assert response1.usage["input_tokens"] == 10
            assert response2.usage["input_tokens"] == 11

        stubber.assert_no_pending_responses()

    @pytest.mark.asyncio
    async def test_error_recovery_sequence(self, bedrock_client_with_stubber):
        """Test error recovery sequence with stubber."""
        client, stubber = bedrock_client_with_stubber

        # First request fails with throttling
        expected_request = {
            "modelId": "amazon.nova-pro-v1:0",
            "body": json.dumps(
                {
                    "messages": [
                        {"role": "user", "content": [{"text": "Test message"}]}
                    ],
                    "inferenceConfig": {
                        "maxTokens": 100,
                        "temperature": 0.1,
                    },
                }
            ),
            "contentType": "application/json",
        }

        # Add throttling errors for all 5 attempts (1 initial + 4 retries for rate limit)
        for _ in range(5):
            stubber.add_client_error(
                "invoke_model",
                "ThrottlingException",
                "Rate limit exceeded.",
                expected_params=expected_request,
            )

        stubber.activate()

        # Execute test - should raise RateLimitError due to throttling
        messages = [{"role": "user", "content": "Test message"}]
        with pytest.raises(RateLimitError, match="Rate limit exceeded"):
            await client.invoke_model(messages, max_tokens=100)

        stubber.assert_no_pending_responses()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
