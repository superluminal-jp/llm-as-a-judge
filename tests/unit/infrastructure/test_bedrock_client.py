"""Test AWS Bedrock client functionality."""

import json
import pytest
import boto3
from botocore.stub import Stubber
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from src.llm_judge.infrastructure.config.config import LLMConfig
from src.llm_judge.infrastructure.clients.bedrock_client import (
    BedrockClient,
    BedrockResponse,
)


@pytest.fixture
def test_config():
    """Create test configuration with AWS credentials."""
    return LLMConfig(
        aws_access_key_id="AKIATEST123456",
        aws_secret_access_key="test-secret-key",
        aws_region="us-east-1",
        bedrock_model="amazon.nova-premier-v1:0",
        default_provider="bedrock",
        bedrock_request_timeout=30,
        bedrock_connect_timeout=10,
        request_timeout=30,
        max_retries=3,
        bedrock_temperature=0.1,
    )


@pytest.fixture
def bedrock_stubber():
    """Create a Bedrock client with stubber for testing."""
    # Create real boto3 session and client for stubbing
    session = boto3.Session(
        aws_access_key_id="AKIATEST123456",
        aws_secret_access_key="test-secret-key",
        region_name="us-east-1",
    )
    client = session.client("bedrock-runtime")
    stubber = Stubber(client)

    yield client, stubber

    # Clean up
    stubber.deactivate()


@pytest.fixture
def bedrock_client_with_real_stubber(test_config):
    """Create a Bedrock client with real stubber for comprehensive testing."""
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
def mock_boto3():
    """Mock boto3 session for testing."""
    with patch.dict(
        "sys.modules",
        {
            "boto3": Mock(),
            "botocore": Mock(),
            "botocore.config": Mock(),
            "botocore.exceptions": Mock(),
        },
    ):
        import sys

        mock_boto3 = sys.modules["boto3"]
        mock_botocore_exceptions = sys.modules["botocore.exceptions"]

        # Mock session and client
        mock_session = Mock()
        mock_client = Mock()
        mock_session.client.return_value = mock_client
        mock_boto3.Session.return_value = mock_session

        # Mock exceptions
        mock_botocore_exceptions.ClientError = Exception
        mock_botocore_exceptions.BotoCoreError = Exception

        yield mock_session, mock_client


class TestBedrockClient:
    """Test Bedrock client initialization and basic functionality."""

    def test_client_initialization(self, test_config):
        """Test Bedrock client initializes correctly."""
        with patch(
            "src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE", True
        ):
            with patch(
                "src.llm_judge.infrastructure.clients.bedrock_client.boto3.Session"
            ) as mock_session_class:
                mock_session = Mock()
                mock_client = Mock()
                mock_session.client.return_value = mock_client
                mock_session_class.return_value = mock_session

                from src.llm_judge.infrastructure.clients.bedrock_client import (
                    BedrockClient,
                )

                client = BedrockClient(test_config)
                assert client.config == test_config
                # Check session was created with correct parameters
                mock_session.client.assert_called_once()
                call_args = mock_session.client.call_args
                assert call_args[0] == ("bedrock-runtime",)
                assert "config" in call_args[1]

    def test_missing_boto3_raises_import_error(self, test_config):
        """Test that missing boto3 raises ImportError."""
        from src.llm_judge.infrastructure.clients.bedrock_client import BedrockClient

        with patch(
            "src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE", False
        ):
            with pytest.raises(ImportError, match="boto3 is required"):
                BedrockClient(test_config)

    def test_missing_aws_credentials_raises_error(self):
        """Test that missing AWS credentials raises error."""
        config = LLMConfig(
            openai_api_key="test-openai",
            anthropic_api_key="test-anthropic",
            default_provider="openai",  # Use different provider to avoid validation
            aws_access_key_id=None,
            aws_secret_access_key=None,
        )

        with patch(
            "src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE", True
        ):
            with pytest.raises(ValueError, match="AWS credentials are required"):
                from src.llm_judge.infrastructure.clients.bedrock_client import (
                    BedrockClient,
                )

                BedrockClient(config)

    @pytest.mark.asyncio
    async def test_invoke_model_anthropic_success(self, test_config, mock_boto3):
        """Test successful model invocation with Anthropic model."""
        mock_session, mock_client = mock_boto3

        # Mock successful response
        mock_response_body = {
            "content": [{"text": "This is a test response"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 20},
        }

        mock_response = {"body": Mock()}
        mock_response["body"].read.return_value = json.dumps(mock_response_body).encode(
            "utf-8"
        )
        mock_client.invoke_model.return_value = mock_response

        with patch(
            "src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE", True
        ):
            client = BedrockClient(test_config)

            messages = [{"role": "user", "content": "Hello, how are you?"}]

            # Mock the retry manager to directly call the function
            with patch.object(
                client._retry_manager, "execute_with_retry"
            ) as mock_retry:

                async def mock_execute(func, **kwargs):
                    return await func()

                mock_retry.side_effect = mock_execute

                response = await client.invoke_model(messages, max_tokens=100)

                assert isinstance(response, BedrockResponse)
                assert response.content == "This is a test response"
                assert response.model == "amazon.nova-premier-v1:0"
                assert response.stop_reason == "end_turn"
                assert response.usage["input_tokens"] == 10
                assert response.usage["output_tokens"] == 20

    @pytest.mark.asyncio
    async def test_invoke_model_nova_success(self, test_config, mock_boto3):
        """Test successful model invocation with Nova model."""
        mock_session, mock_client = mock_boto3

        # Mock successful Nova response format
        mock_response_body = {
            "output": {
                "message": {"content": [{"text": "This is a Nova test response"}]}
            },
            "stopReason": "end_turn",
            "usage": {"inputTokens": 15, "outputTokens": 25},
        }

        mock_response = {"body": Mock()}
        mock_response["body"].read.return_value = json.dumps(mock_response_body).encode(
            "utf-8"
        )
        mock_client.invoke_model.return_value = mock_response

        with patch(
            "src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE", True
        ):
            client = BedrockClient(test_config)

            messages = [{"role": "user", "content": "Hello Nova!"}]

            # Mock the retry manager to directly call the function
            with patch.object(
                client._retry_manager, "execute_with_retry"
            ) as mock_retry:

                async def mock_execute(func, **kwargs):
                    return await func()

                mock_retry.side_effect = mock_execute

                response = await client.invoke_model(
                    messages, model="amazon.nova-premier-v1:0", max_tokens=100
                )

                assert isinstance(response, BedrockResponse)
                assert response.content == "This is a Nova test response"
                assert response.stop_reason == "end_turn"
                assert response.usage["input_tokens"] == 15
                assert response.usage["output_tokens"] == 25

    @pytest.mark.asyncio
    async def test_invoke_model_client_error_handling(self, test_config, mock_boto3):
        """Test proper handling of AWS ClientError."""
        mock_session, mock_client = mock_boto3

        # Mock ClientError
        from botocore.exceptions import ClientError

        error_response = {
            "Error": {"Code": "ThrottlingException", "Message": "Rate limit exceeded"}
        }
        mock_client.invoke_model.side_effect = ClientError(
            error_response, "invoke_model"
        )

        with patch(
            "src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE", True
        ):
            client = BedrockClient(test_config)

            messages = [{"role": "user", "content": "Test message"}]

            # Mock the retry manager to directly call the function
            with patch.object(
                client._retry_manager, "execute_with_retry"
            ) as mock_retry:

                async def mock_execute(func, **kwargs):
                    return await func()

                mock_retry.side_effect = mock_execute

                with pytest.raises(BedrockError, match="Rate limit exceeded"):
                    await client.invoke_model(messages)

    @pytest.mark.asyncio
    async def test_evaluate_with_bedrock_success(self, test_config, mock_boto3):
        """Test successful evaluation with Bedrock."""
        mock_session, mock_client = mock_boto3

        # Mock successful evaluation response
        evaluation_response = {
            "score": 4.5,
            "reasoning": "This is a good response with clear explanations.",
            "confidence": 0.85,
        }

        mock_response_body = {
            "content": [{"text": json.dumps(evaluation_response)}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 50, "output_tokens": 100},
        }

        mock_response = {"body": Mock()}
        mock_response["body"].read.return_value = json.dumps(mock_response_body).encode(
            "utf-8"
        )
        mock_client.invoke_model.return_value = mock_response

        with patch(
            "src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE", True
        ):
            client = BedrockClient(test_config)

            # Mock the retry manager to directly call the function
            with patch.object(
                client._retry_manager, "execute_with_retry"
            ) as mock_retry:

                async def mock_execute(func, **kwargs):
                    return await func()

                mock_retry.side_effect = mock_execute

                result = await client.evaluate_with_bedrock(
                    prompt="What is AI?",
                    response_text="AI is artificial intelligence",
                    criteria="accuracy",
                )

                assert result["score"] == 4.5
                assert (
                    result["reasoning"]
                    == "This is a good response with clear explanations."
                )
                assert result["confidence"] == 0.85

    @pytest.mark.asyncio
    async def test_evaluate_with_bedrock_json_parse_error(
        self, test_config, mock_boto3
    ):
        """Test evaluation with JSON parsing fallback."""
        mock_session, mock_client = mock_boto3

        # Mock response with invalid JSON that triggers fallback
        mock_response_body = {
            "content": [{"text": "This response is good and well written."}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 50, "output_tokens": 100},
        }

        mock_response = {"body": Mock()}
        mock_response["body"].read.return_value = json.dumps(mock_response_body).encode(
            "utf-8"
        )
        mock_client.invoke_model.return_value = mock_response

        with patch(
            "src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE", True
        ):
            client = BedrockClient(test_config)

            # Mock the retry manager to directly call the function
            with patch.object(
                client._retry_manager, "execute_with_retry"
            ) as mock_retry:

                async def mock_execute(func, **kwargs):
                    return await func()

                mock_retry.side_effect = mock_execute

                result = await client.evaluate_with_bedrock(
                    prompt="What is AI?",
                    response_text="AI is artificial intelligence",
                    criteria="quality",
                )

                # Should use fallback scoring based on keywords
                assert result["score"] == 4.0  # "good" keyword triggers score of 4
                assert "Failed to parse structured response" in result["reasoning"]
                assert result["confidence"] == 0.3

    @pytest.mark.asyncio
    async def test_compare_with_bedrock_success(self, test_config, mock_boto3):
        """Test successful comparison with Bedrock."""
        mock_session, mock_client = mock_boto3

        # Mock successful comparison response
        comparison_response = {
            "winner": "A",
            "reasoning": "Response A provides more detailed and accurate information.",
            "confidence": 0.9,
        }

        mock_response_body = {
            "content": [{"text": json.dumps(comparison_response)}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 75, "output_tokens": 50},
        }

        mock_response = {"body": Mock()}
        mock_response["body"].read.return_value = json.dumps(mock_response_body).encode(
            "utf-8"
        )
        mock_client.invoke_model.return_value = mock_response

        with patch(
            "src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE", True
        ):
            client = BedrockClient(test_config)

            # Mock the retry manager to directly call the function
            with patch.object(
                client._retry_manager, "execute_with_retry"
            ) as mock_retry:

                async def mock_execute(func, **kwargs):
                    return await func()

                mock_retry.side_effect = mock_execute

                result = await client.compare_with_bedrock(
                    prompt="What is machine learning?",
                    response_a="ML is a subset of AI",
                    response_b="Machine learning uses algorithms",
                )

                assert result["winner"] == "A"
                assert (
                    result["reasoning"]
                    == "Response A provides more detailed and accurate information."
                )
                assert result["confidence"] == 0.9

    def test_prepare_anthropic_body(self, test_config, mock_boto3):
        """Test preparation of Anthropic request body."""
        mock_session, mock_client = mock_boto3

        with patch(
            "src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE", True
        ):
            client = BedrockClient(test_config)

            messages = [
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": "Hello!"},
                {"role": "assistant", "content": "Hi there!"},
            ]

            body = client._prepare_anthropic_body(
                messages, max_tokens=100, temperature=0.5, top_p=None
            )

            assert body["max_tokens"] == 100
            assert body["temperature"] == 0.5
            assert body["system"] == "You are a helpful assistant"
            assert (
                len(body["messages"]) == 2
            )  # System message becomes separate parameter
            assert body["messages"][0]["role"] == "user"
            assert body["messages"][1]["role"] == "assistant"
            assert body["anthropic_version"] == "bedrock-2023-05-31"

    def test_prepare_nova_body(self, test_config, mock_boto3):
        """Test preparation of Nova request body."""
        mock_session, mock_client = mock_boto3

        with patch(
            "src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE", True
        ):
            client = BedrockClient(test_config)

            messages = [
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "Hello Nova!"},
            ]

            body = client._prepare_nova_body(
                messages, max_tokens=150, temperature=0.3, top_p=None
            )

            assert body["max_tokens"] == 150
            assert body["inferenceConfig"]["temperature"] == 0.3
            assert body["system"] == [{"text": "You are helpful"}]
            assert (
                len(body["messages"]) == 1
            )  # System message becomes separate parameter
            assert body["messages"][0]["role"] == "user"
            assert body["messages"][0]["content"] == [{"text": "Hello Nova!"}]

    @pytest.mark.asyncio
    async def test_close_client(self, test_config, mock_boto3):
        """Test client cleanup on close."""
        mock_session, mock_client = mock_boto3

        with patch(
            "src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE", True
        ):
            client = BedrockClient(test_config)

            # Mock timeout manager
            client._timeout_manager = Mock()
            client._timeout_manager.close = AsyncMock()

            await client.close()

            # Verify timeout manager cleanup was called
            client._timeout_manager.close.assert_called_once()
