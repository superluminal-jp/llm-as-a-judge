"""Test OpenAI client functionality - Fixed version."""

import json
import pytest
from unittest.mock import Mock, AsyncMock, patch
from src.llm_judge.infrastructure.config.config import LLMConfig
from src.llm_judge.infrastructure.clients.openai_client import OpenAIClient, OpenAIError, OpenAIResponse
import openai


@pytest.fixture
def test_config():
    """Create test configuration with OpenAI API key."""
    return LLMConfig(
        openai_api_key="test-openai-key",
        openai_model="gpt-4",
        default_provider="openai",
        openai_request_timeout=30,
        openai_connect_timeout=10,
        request_timeout=30,
        max_retries=3
    )


class TestOpenAIClient:
    """Test OpenAI client initialization and basic functionality."""
    
    def test_client_initialization(self, test_config):
        """Test OpenAI client initializes correctly."""
        with patch('src.llm_judge.infrastructure.clients.openai_client.OpenAI') as mock_openai_class:
            mock_client = Mock()
            mock_openai_class.return_value = mock_client
            
            client = OpenAIClient(test_config)
            assert client.config == test_config
            assert client.client == mock_client
            
            # Verify SDK was initialized with correct parameters
            mock_openai_class.assert_called_once_with(
                api_key="test-openai-key",
                timeout=test_config.openai_request_timeout,
                max_retries=test_config.max_retries
            )
    
    def test_missing_api_key_raises_error(self):
        """Test that missing API key raises error."""
        config = LLMConfig(
            anthropic_api_key="test-anthropic",
            default_provider="anthropic"
        )
        with pytest.raises(ValueError, match="OpenAI API key is required"):
            OpenAIClient(config)


class TestChatCompletion:
    """Test chat completion functionality."""
    
    @pytest.mark.asyncio
    async def test_successful_chat_completion(self, test_config):
        """Test successful chat completion request."""
        with patch('src.llm_judge.infrastructure.clients.openai_client.OpenAI') as mock_openai_class:
            # Mock the OpenAI SDK client
            mock_client = Mock()
            mock_openai_class.return_value = mock_client
            
            # Mock the chat completion response
            mock_choice = Mock()
            mock_choice.message.content = "This is a test response from GPT-4"
            mock_choice.finish_reason = "stop"
            
            mock_response = Mock()
            mock_response.choices = [mock_choice]
            mock_response.usage.prompt_tokens = 10
            mock_response.usage.completion_tokens = 8
            mock_response.model = "gpt-4"
            
            # OpenAI SDK's create method is synchronous, not async
            mock_client.chat.completions.create.return_value = mock_response
            
            # Create client and test
            client = OpenAIClient(test_config)
            messages = [{"role": "user", "content": "Hello GPT"}]
            result = await client.chat_completion(messages)
            
            assert isinstance(result, OpenAIResponse)
            assert result.content == "This is a test response from GPT-4"
            assert result.stop_reason == "stop"
            assert result.model == "gpt-4"
            assert result.usage["completion_tokens"] == 8
            
            # Verify the SDK was called correctly
            mock_client.chat.completions.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_authentication_error(self, test_config):
        """Test handling of authentication errors."""
        with patch('src.llm_judge.infrastructure.clients.openai_client.OpenAI') as mock_openai_class:
            mock_client = Mock()
            mock_openai_class.return_value = mock_client
            
            # Mock an authentication error - create minimal mock response
            mock_response = Mock()
            mock_response.request = Mock()
            mock_client.chat.completions.create.side_effect = openai.AuthenticationError(
                "Invalid API key", response=mock_response, body=None
            )
            
            client = OpenAIClient(test_config)
            messages = [{"role": "user", "content": "Hello GPT"}]
            
            with pytest.raises(OpenAIError):
                await client.chat_completion(messages)
    
    @pytest.mark.asyncio
    async def test_rate_limit_error(self, test_config):
        """Test handling of rate limit errors."""
        with patch('src.llm_judge.infrastructure.clients.openai_client.OpenAI') as mock_openai_class:
            mock_client = Mock()
            mock_openai_class.return_value = mock_client
            
            # Mock a rate limit error - create minimal mock response
            mock_response = Mock()
            mock_response.request = Mock()
            mock_client.chat.completions.create.side_effect = openai.RateLimitError(
                "Rate limit exceeded", response=mock_response, body=None
            )
            
            client = OpenAIClient(test_config)
            messages = [{"role": "user", "content": "Hello GPT"}]
            
            with pytest.raises(OpenAIError):
                await client.chat_completion(messages)


class TestEvaluation:
    """Test evaluation functionality."""
    
    @pytest.mark.asyncio
    async def test_basic_evaluation(self, test_config):
        """Test basic evaluation functionality."""
        with patch('src.llm_judge.infrastructure.clients.openai_client.OpenAI') as mock_openai_class:
            mock_client = Mock()
            mock_openai_class.return_value = mock_client
            
            # Mock a successful evaluation response
            mock_choice = Mock()
            mock_choice.message.content = '{"score": 4, "reasoning": "Good response"}'
            mock_choice.finish_reason = "stop"
            
            mock_response = Mock()
            mock_response.choices = [mock_choice]
            mock_response.usage.prompt_tokens = 50
            mock_response.usage.completion_tokens = 20
            mock_response.model = "gpt-4"
            
            # OpenAI SDK's create method is synchronous
            mock_client.chat.completions.create.return_value = mock_response
            
            client = OpenAIClient(test_config)
            
            # Test evaluation (simplified)
            messages = [{"role": "user", "content": "Rate this response"}]
            result = await client.chat_completion(messages)
            
            assert isinstance(result, OpenAIResponse)
            assert result.content == '{"score": 4, "reasoning": "Good response"}'


class TestComparison:
    """Test comparison functionality."""
    
    @pytest.mark.asyncio
    async def test_compare_with_openai_success(self, test_config):
        """Test successful OpenAI comparison."""
        with patch('src.llm_judge.infrastructure.clients.openai_client.OpenAI') as mock_openai_class:
            mock_client = Mock()
            mock_openai_class.return_value = mock_client
            
            # Mock a successful comparison response
            mock_choice = Mock()
            mock_choice.message.content = '{"winner": "A", "reasoning": "Response A is more comprehensive", "confidence": 0.8}'
            mock_choice.finish_reason = "stop"
            
            mock_response = Mock()
            mock_response.choices = [mock_choice]
            mock_response.usage.prompt_tokens = 75
            mock_response.usage.completion_tokens = 25
            mock_response.model = "gpt-4"
            
            mock_client.chat.completions.create.return_value = mock_response
            
            client = OpenAIClient(test_config)
            
            # Test comparison method directly
            result = await client.compare_with_openai(
                prompt="What is AI?",
                response_a="AI is artificial intelligence",
                response_b="AI is machine learning"
            )
            
            assert result["winner"] == "A"
            assert result["reasoning"] == "Response A is more comprehensive"
            assert result["confidence"] == 0.8
            
            # Verify SDK was called
            mock_client.chat.completions.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_compare_with_openai_fallback(self, test_config):
        """Test OpenAI comparison with fallback parsing."""
        with patch('src.llm_judge.infrastructure.clients.openai_client.OpenAI') as mock_openai_class:
            mock_client = Mock()
            mock_openai_class.return_value = mock_client
            
            # Mock a response that fails JSON parsing
            mock_choice = Mock()
            mock_choice.message.content = "Response A is better than Response B"
            mock_choice.finish_reason = "stop"
            
            mock_response = Mock()
            mock_response.choices = [mock_choice]
            mock_response.usage.prompt_tokens = 50
            mock_response.usage.completion_tokens = 10
            mock_response.model = "gpt-4"
            
            mock_client.chat.completions.create.return_value = mock_response
            
            client = OpenAIClient(test_config)
            
            result = await client.compare_with_openai(
                prompt="Which is better?",
                response_a="Option A",
                response_b="Option B"
            )
            
            # Should fallback to "tie" when parsing fails (current implementation)
            assert result["winner"] == "tie"
            assert "Failed to parse structured response" in result["reasoning"]
            assert result["confidence"] == 0.3