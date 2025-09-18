"""Simplified stubber-based tests for AWS Bedrock client functionality.

This module provides a focused set of stubber-based tests that demonstrate
the key functionality without complex edge cases.
"""

import json
import pytest
import boto3
from botocore.stub import Stubber
from unittest.mock import Mock, patch

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


class TestBedrockClientStubberBasic:
    """Basic stubber-based tests for Bedrock client."""

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

    @pytest.mark.asyncio
    async def test_invoke_nova_model_success(self, bedrock_client_with_stubber):
        """Test successful Nova model invocation with stubber."""
        client, stubber = bedrock_client_with_stubber

        # Prepare expected request (matching actual client format)
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
                    "inferenceConfig": {"maxTokens": 100, "temperature": 0.1},
                }
            ),
            "contentType": "application/json",
        }

        # Add stub for throttling error
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
    async def test_evaluate_with_bedrock_success(self, bedrock_client_with_stubber):
        """Test successful evaluation with stubber."""
        client, stubber = bedrock_client_with_stubber

        # Prepare expected request for evaluation
        expected_request = {
            "modelId": "amazon.nova-pro-v1:0",
            "body": json.dumps(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "text": 'Evaluate this response for accuracy: "AI is artificial intelligence"'
                                }
                            ],
                        }
                    ],
                    "inferenceConfig": {"maxTokens": 200, "temperature": 0.1},
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
            assert result["score"] == 4.5
            assert (
                result["reasoning"]
                == "The response is factually accurate and provides a clear definition of AI."
            )
            assert result["confidence"] == 0.9

        stubber.assert_no_pending_responses()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
