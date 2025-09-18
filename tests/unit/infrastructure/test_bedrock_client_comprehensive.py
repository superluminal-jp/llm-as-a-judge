"""Comprehensive test suite for AWS Bedrock client functionality."""

import json
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from src.llm_judge.infrastructure.config.config import LLMConfig


@pytest.fixture
def test_config():
    """Create test configuration with AWS credentials."""
    return LLMConfig(
        aws_access_key_id="AKIATEST123456",
        aws_secret_access_key="test-secret-key",
        aws_region="us-east-1",
        bedrock_model="amazon.nova-pro-v1:0",
        default_provider="bedrock",
        bedrock_request_timeout=30,
        bedrock_connect_timeout=10,
        request_timeout=30,
        max_retries=3,
        bedrock_temperature=0.1
    )


@pytest.fixture
def test_config_missing_credentials():
    """Create test configuration without AWS credentials."""
    return LLMConfig(
        openai_api_key="test-openai",
        anthropic_api_key="test-anthropic",
        default_provider="bedrock"
    )


@pytest.fixture
def mock_boto3_session():
    """Mock boto3 session for testing."""
    with patch.dict('sys.modules', {
        'boto3': Mock(),
        'botocore': Mock(),
        'botocore.config': Mock(),
        'botocore.exceptions': Mock()
    }):
        import sys
        mock_boto3 = sys.modules['boto3']
        mock_botocore_exceptions = sys.modules['botocore.exceptions']
        
        # Mock session and client
        mock_session = Mock()
        mock_client = Mock()
        mock_session.client.return_value = mock_client
        mock_boto3.Session.return_value = mock_session
        
        # Mock exceptions
        mock_botocore_exceptions.ClientError = Exception
        mock_botocore_exceptions.BotoCoreError = Exception
        
        yield mock_session, mock_client


class TestBedrockClientInitialization:
    """Test Bedrock client initialization and configuration."""
    
    def test_client_initialization_success(self, test_config, mock_boto3_session):
        """Test successful Bedrock client initialization."""
        from src.llm_judge.infrastructure.clients.bedrock_client import BedrockClient
        
        mock_session, mock_client = mock_boto3_session
        
        with patch('src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE', True):
            client = BedrockClient(test_config)
            assert client.config == test_config
            mock_session.client.assert_called_once_with('bedrock-runtime', config=pytest.approx(object))
    
    def test_missing_boto3_dependency(self, test_config):
        """Test ImportError when boto3 is not available."""
        from src.llm_judge.infrastructure.clients.bedrock_client import BedrockClient
        
        with patch('src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE', False):
            with pytest.raises(ImportError, match="boto3 is required"):
                BedrockClient(test_config)
    
    def test_missing_aws_credentials(self, test_config_missing_credentials):
        """Test ValueError when AWS credentials are missing."""
        from src.llm_judge.infrastructure.clients.bedrock_client import BedrockClient
        
        with patch('src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE', True):
            with pytest.raises(ValueError, match="AWS credentials are required"):
                BedrockClient(test_config_missing_credentials)
    
    def test_partial_aws_credentials(self):
        """Test error when only partial AWS credentials are provided."""
        from src.llm_judge.infrastructure.clients.bedrock_client import BedrockClient
        
        config_partial = LLMConfig(
            aws_access_key_id="AKIATEST123456",
            # Missing aws_secret_access_key
            aws_region="us-east-1",
            bedrock_model="amazon.nova-pro-v1:0",
            default_provider="bedrock"
        )
        
        with patch('src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE', True):
            with pytest.raises(ValueError, match="AWS credentials are required"):
                BedrockClient(config_partial)


class TestBedrockClientInvocation:
    """Test Bedrock model invocation functionality."""
    
    @pytest.mark.asyncio
    async def test_invoke_nova_model_success(self, test_config, mock_boto3_session):
        """Test successful invocation with Nova model."""
        from src.llm_judge.infrastructure.clients.bedrock_client import BedrockClient, BedrockResponse
        
        mock_session, mock_client = mock_boto3_session
        
        # Mock successful Nova response
        mock_response_body = {
            'output': {
                'message': {
                    'content': [{'text': 'This is a Nova test response'}]
                }
            },
            'stopReason': 'end_turn',
            'usage': {'inputTokens': 15, 'outputTokens': 25}
        }
        
        mock_response = {'body': Mock()}
        mock_response['body'].read.return_value = json.dumps(mock_response_body).encode('utf-8')
        mock_client.invoke_model.return_value = mock_response
        
        with patch('src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE', True):
            client = BedrockClient(test_config)
            
            # Mock retry manager
            with patch.object(client._retry_manager, 'execute_with_retry') as mock_retry:
                async def mock_execute(func, **kwargs):
                    return await func()
                mock_retry.side_effect = mock_execute
                
                messages = [{"role": "user", "content": "Hello Nova!"}]
                response = await client.invoke_model(
                    messages, 
                    model="amazon.nova-pro-v1:0", 
                    max_tokens=100
                )
                
                assert isinstance(response, BedrockResponse)
                assert response.content == "This is a Nova test response"
                assert response.stop_reason == "end_turn"
                assert response.usage["input_tokens"] == 15
                assert response.usage["output_tokens"] == 25
    
    @pytest.mark.asyncio
    async def test_invoke_anthropic_model_success(self, test_config, mock_boto3_session):
        """Test successful invocation with Anthropic model on Bedrock."""
        from src.llm_judge.infrastructure.clients.bedrock_client import BedrockClient, BedrockResponse
        
        mock_session, mock_client = mock_boto3_session
        
        # Mock successful Anthropic response
        mock_response_body = {
            'content': [{'text': 'This is an Anthropic test response'}],
            'stop_reason': 'end_turn',
            'usage': {'input_tokens': 10, 'output_tokens': 20}
        }
        
        mock_response = {'body': Mock()}
        mock_response['body'].read.return_value = json.dumps(mock_response_body).encode('utf-8')
        mock_client.invoke_model.return_value = mock_response
        
        with patch('src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE', True):
            client = BedrockClient(test_config)
            
            with patch.object(client._retry_manager, 'execute_with_retry') as mock_retry:
                async def mock_execute(func, **kwargs):
                    return await func()
                mock_retry.side_effect = mock_execute
                
                messages = [{"role": "user", "content": "Hello Claude!"}]
                response = await client.invoke_model(
                    messages, 
                    model="anthropic.claude-3-sonnet-20240229-v1:0", 
                    max_tokens=100
                )
                
                assert isinstance(response, BedrockResponse)
                assert response.content == "This is an Anthropic test response"
                assert response.stop_reason == "end_turn"
                assert response.usage["input_tokens"] == 10
                assert response.usage["output_tokens"] == 20
    
    @pytest.mark.asyncio
    async def test_invoke_model_with_system_message(self, test_config, mock_boto3_session):
        """Test model invocation with system message."""
        from src.llm_judge.infrastructure.clients.bedrock_client import BedrockClient, BedrockResponse
        
        mock_session, mock_client = mock_boto3_session
        
        mock_response_body = {
            'output': {
                'message': {
                    'content': [{'text': 'Response with system context'}]
                }
            },
            'stopReason': 'end_turn',
            'usage': {'inputTokens': 20, 'outputTokens': 15}
        }
        
        mock_response = {'body': Mock()}
        mock_response['body'].read.return_value = json.dumps(mock_response_body).encode('utf-8')
        mock_client.invoke_model.return_value = mock_response
        
        with patch('src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE', True):
            client = BedrockClient(test_config)
            
            with patch.object(client._retry_manager, 'execute_with_retry') as mock_retry:
                async def mock_execute(func, **kwargs):
                    return await func()
                mock_retry.side_effect = mock_execute
                
                messages = [
                    {"role": "system", "content": "You are a helpful assistant"},
                    {"role": "user", "content": "Hello!"}
                ]
                response = await client.invoke_model(messages, max_tokens=100)
                
                assert response.content == "Response with system context"
    
    @pytest.mark.asyncio
    async def test_invoke_model_invalid_json_response(self, test_config, mock_boto3_session):
        """Test handling of invalid JSON response."""
        from src.llm_judge.infrastructure.clients.bedrock_client import BedrockClient, BedrockError
        
        mock_session, mock_client = mock_boto3_session
        
        # Mock response with invalid JSON
        mock_response = {'body': Mock()}
        mock_response['body'].read.return_value = b"Invalid JSON response"
        mock_client.invoke_model.return_value = mock_response
        
        with patch('src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE', True):
            client = BedrockClient(test_config)
            
            with patch.object(client._retry_manager, 'execute_with_retry') as mock_retry:
                async def mock_execute(func, **kwargs):
                    return await func()
                mock_retry.side_effect = mock_execute
                
                messages = [{"role": "user", "content": "Hello!"}]
                
                with pytest.raises(BedrockError, match="Failed to parse response"):
                    await client.invoke_model(messages, max_tokens=100)
    
    @pytest.mark.asyncio
    async def test_invoke_model_client_error(self, test_config, mock_boto3_session):
        """Test handling of AWS ClientError."""
        from src.llm_judge.infrastructure.clients.bedrock_client import BedrockClient, BedrockError
        
        mock_session, mock_client = mock_boto3_session
        
        # Mock ClientError
        error_response = {
            'Error': {
                'Code': 'ValidationException',
                'Message': 'Invalid model parameters'
            }
        }
        
        with patch('botocore.exceptions.ClientError') as mock_client_error:
            mock_client_error.side_effect = Exception("Client error occurred")
            mock_client.invoke_model.side_effect = mock_client_error.side_effect
            
            with patch('src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE', True):
                client = BedrockClient(test_config)
                
                with patch.object(client._retry_manager, 'execute_with_retry') as mock_retry:
                    async def mock_execute(func, **kwargs):
                        return await func()
                    mock_retry.side_effect = mock_execute
                    
                    messages = [{"role": "user", "content": "Hello!"}]
                    
                    with pytest.raises(BedrockError):
                        await client.invoke_model(messages, max_tokens=100)


class TestBedrockClientEvaluation:
    """Test Bedrock evaluation functionality."""
    
    @pytest.mark.asyncio
    async def test_evaluate_with_bedrock_success(self, test_config, mock_boto3_session):
        """Test successful evaluation with structured JSON response."""
        from src.llm_judge.infrastructure.clients.bedrock_client import BedrockClient
        
        mock_session, mock_client = mock_boto3_session
        
        # Mock successful evaluation response
        evaluation_response = {
            "score": 4.2,
            "reasoning": "The response is accurate and well-structured.",
            "confidence": 0.85
        }
        
        mock_response_body = {
            'output': {
                'message': {
                    'content': [{'text': json.dumps(evaluation_response)}]
                }
            },
            'stopReason': 'end_turn',
            'usage': {'inputTokens': 50, 'outputTokens': 30}
        }
        
        mock_response = {'body': Mock()}
        mock_response['body'].read.return_value = json.dumps(mock_response_body).encode('utf-8')
        mock_client.invoke_model.return_value = mock_response
        
        with patch('src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE', True):
            client = BedrockClient(test_config)
            
            with patch.object(client._retry_manager, 'execute_with_retry') as mock_retry:
                async def mock_execute(func, **kwargs):
                    return await func()
                mock_retry.side_effect = mock_execute
                
                result = await client.evaluate_with_bedrock(
                    prompt="What is AI?",
                    response_text="AI is artificial intelligence",
                    criteria="accuracy"
                )
                
                assert result["score"] == 4.2
                assert result["reasoning"] == "The response is accurate and well-structured."
                assert result["confidence"] == 0.85
    
    @pytest.mark.asyncio
    async def test_evaluate_with_bedrock_fallback_scoring(self, test_config, mock_boto3_session):
        """Test evaluation fallback when JSON parsing fails."""
        from src.llm_judge.infrastructure.clients.bedrock_client import BedrockClient
        
        mock_session, mock_client = mock_boto3_session
        
        # Mock response with non-JSON text that triggers fallback
        mock_response_body = {
            'output': {
                'message': {
                    'content': [{'text': 'This response is excellent and very good quality.'}]
                }
            },
            'stopReason': 'end_turn',
            'usage': {'inputTokens': 50, 'outputTokens': 30}
        }
        
        mock_response = {'body': Mock()}
        mock_response['body'].read.return_value = json.dumps(mock_response_body).encode('utf-8')
        mock_client.invoke_model.return_value = mock_response
        
        with patch('src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE', True):
            client = BedrockClient(test_config)
            
            with patch.object(client._retry_manager, 'execute_with_retry') as mock_retry:
                async def mock_execute(func, **kwargs):
                    return await func()
                mock_retry.side_effect = mock_execute
                
                result = await client.evaluate_with_bedrock(
                    prompt="What is AI?",
                    response_text="AI is artificial intelligence",
                    criteria="quality"
                )
                
                # Should use fallback scoring based on keywords
                assert result["score"] == 5.0  # "excellent" keyword triggers score of 5
                assert "Failed to parse structured response" in result["reasoning"]
                assert result["confidence"] == 0.3


class TestBedrockClientComparison:
    """Test Bedrock comparison functionality."""
    
    @pytest.mark.asyncio
    async def test_compare_with_bedrock_success(self, test_config, mock_boto3_session):
        """Test successful comparison with structured response."""
        from src.llm_judge.infrastructure.clients.bedrock_client import BedrockClient
        
        mock_session, mock_client = mock_boto3_session
        
        comparison_response = {
            "winner": "A",
            "reasoning": "Response A is more comprehensive and detailed.",
            "confidence": 0.9
        }
        
        mock_response_body = {
            'output': {
                'message': {
                    'content': [{'text': json.dumps(comparison_response)}]
                }
            },
            'stopReason': 'end_turn',
            'usage': {'inputTokens': 75, 'outputTokens': 40}
        }
        
        mock_response = {'body': Mock()}
        mock_response['body'].read.return_value = json.dumps(mock_response_body).encode('utf-8')
        mock_client.invoke_model.return_value = mock_response
        
        with patch('src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE', True):
            client = BedrockClient(test_config)
            
            with patch.object(client._retry_manager, 'execute_with_retry') as mock_retry:
                async def mock_execute(func, **kwargs):
                    return await func()
                mock_retry.side_effect = mock_execute
                
                result = await client.compare_with_bedrock(
                    prompt="What is machine learning?",
                    response_a="ML is a subset of AI that learns from data",
                    response_b="Machine learning uses algorithms"
                )
                
                assert result["winner"] == "A"
                assert result["reasoning"] == "Response A is more comprehensive and detailed."
                assert result["confidence"] == 0.9


class TestBedrockClientRequestFormatting:
    """Test request body formatting for different model types."""
    
    def test_prepare_nova_body_format(self, test_config, mock_boto3_session):
        """Test Nova request body format."""
        from src.llm_judge.infrastructure.clients.bedrock_client import BedrockClient
        
        mock_session, mock_client = mock_boto3_session
        
        with patch('src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE', True):
            client = BedrockClient(test_config)
            
            messages = [
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "Hello!"}
            ]
            
            body = client._prepare_nova_body(
                messages=messages,
                max_tokens=150,
                temperature=0.3,
                top_p=0.9
            )
            
            # Check Nova-specific format
            assert "system" in body
            assert body["system"] == [{"text": "You are helpful"}]
            assert len(body["messages"]) == 1  # System message excluded from messages
            assert body["messages"][0]["content"] == [{"text": "Hello!"}]
            assert body["inferenceConfig"]["maxTokens"] == 150
            assert body["inferenceConfig"]["temperature"] == 0.3
            assert body["inferenceConfig"]["topP"] == 0.9
    
    def test_prepare_anthropic_body_format(self, test_config, mock_boto3_session):
        """Test Anthropic request body format."""
        from src.llm_judge.infrastructure.clients.bedrock_client import BedrockClient
        
        mock_session, mock_client = mock_boto3_session
        
        with patch('src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE', True):
            client = BedrockClient(test_config)
            
            messages = [
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": "Hello!"},
                {"role": "assistant", "content": "Hi there!"}
            ]
            
            body = client._prepare_anthropic_body(
                messages=messages,
                max_tokens=100,
                temperature=0.5,
                top_p=None
            )
            
            # Check Anthropic-specific format
            assert body["max_tokens"] == 100
            assert body["temperature"] == 0.5
            assert body["system"] == "You are a helpful assistant"
            assert len(body["messages"]) == 2  # System message excluded from messages
            assert body["anthropic_version"] == "bedrock-2023-05-31"


class TestBedrockClientErrorScenarios:
    """Test various error scenarios and edge cases."""
    
    @pytest.mark.asyncio
    async def test_empty_messages_list(self, test_config, mock_boto3_session):
        """Test handling of empty messages list."""
        from src.llm_judge.infrastructure.clients.bedrock_client import BedrockClient, BedrockError
        
        mock_session, mock_client = mock_boto3_session
        
        with patch('src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE', True):
            client = BedrockClient(test_config)
            
            # Empty messages should raise an error or handle gracefully
            with pytest.raises((BedrockError, ValueError)):
                await client.invoke_model([], max_tokens=100)
    
    @pytest.mark.asyncio
    async def test_malformed_message_structure(self, test_config, mock_boto3_session):
        """Test handling of malformed message structure."""
        from src.llm_judge.infrastructure.clients.bedrock_client import BedrockClient
        
        mock_session, mock_client = mock_boto3_session
        
        # Mock successful response
        mock_response_body = {
            'output': {
                'message': {
                    'content': [{'text': 'Response despite malformed input'}]
                }
            },
            'stopReason': 'end_turn',
            'usage': {'inputTokens': 10, 'outputTokens': 15}
        }
        
        mock_response = {'body': Mock()}
        mock_response['body'].read.return_value = json.dumps(mock_response_body).encode('utf-8')
        mock_client.invoke_model.return_value = mock_response
        
        with patch('src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE', True):
            client = BedrockClient(test_config)
            
            with patch.object(client._retry_manager, 'execute_with_retry') as mock_retry:
                async def mock_execute(func, **kwargs):
                    return await func()
                mock_retry.side_effect = mock_execute
                
                # Malformed message missing 'content' key
                malformed_messages = [{"role": "user"}]  # Missing content
                
                # Should handle gracefully or raise appropriate error
                try:
                    response = await client.invoke_model(malformed_messages, max_tokens=100)
                    # If it succeeds, verify response structure
                    assert hasattr(response, 'content')
                except (BedrockError, ValueError, KeyError):
                    # Expected to fail with malformed input
                    pass
    
    @pytest.mark.asyncio
    async def test_close_client_cleanup(self, test_config, mock_boto3_session):
        """Test proper cleanup when closing client."""
        from src.llm_judge.infrastructure.clients.bedrock_client import BedrockClient
        
        mock_session, mock_client = mock_boto3_session
        
        with patch('src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE', True):
            client = BedrockClient(test_config)
            
            # Mock timeout manager
            client._timeout_manager = Mock()
            client._timeout_manager.close = AsyncMock()
            
            await client.close()
            
            # Verify cleanup was called
            client._timeout_manager.close.assert_called_once()
    
    @pytest.mark.asyncio 
    async def test_generate_method_delegation(self, test_config, mock_boto3_session):
        """Test unified generate method delegates to invoke_model."""
        from src.llm_judge.infrastructure.clients.bedrock_client import BedrockClient, BedrockResponse
        
        mock_session, mock_client = mock_boto3_session
        
        mock_response_body = {
            'output': {
                'message': {
                    'content': [{'text': 'Generate method response'}]
                }
            },
            'stopReason': 'end_turn',
            'usage': {'inputTokens': 10, 'outputTokens': 15}
        }
        
        mock_response = {'body': Mock()}
        mock_response['body'].read.return_value = json.dumps(mock_response_body).encode('utf-8')
        mock_client.invoke_model.return_value = mock_response
        
        with patch('src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE', True):
            client = BedrockClient(test_config)
            
            with patch.object(client._retry_manager, 'execute_with_retry') as mock_retry:
                async def mock_execute(func, **kwargs):
                    return await func()
                mock_retry.side_effect = mock_execute
                
                messages = [{"role": "user", "content": "Test generate method"}]
                response = await client.generate(messages, max_tokens=100)
                
                assert isinstance(response, BedrockResponse)
                assert response.content == "Generate method response"