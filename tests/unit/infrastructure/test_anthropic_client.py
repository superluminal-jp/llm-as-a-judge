"""Test Anthropic client functionality - Fixed version."""

import json
import pytest
from unittest.mock import Mock, AsyncMock, patch
from src.llm_judge.infrastructure.config.config import LLMConfig
from src.llm_judge.infrastructure.clients.anthropic_client import AnthropicClient, AnthropicError, AnthropicResponse
import anthropic


@pytest.fixture
def test_config():
    """Create test configuration with Anthropic API key."""
    return LLMConfig(
        anthropic_api_key="test-anthropic-key",
        anthropic_model="claude-sonnet-4-20250514",
        default_provider="anthropic",
        anthropic_request_timeout=30,
        anthropic_connect_timeout=10,
        request_timeout=30,
        max_retries=3,
        anthropic_temperature=0.1,
        anthropic_top_p=None
    )


class TestAnthropicClient:
    """Test Anthropic client initialization and basic functionality."""
    
    def test_client_initialization(self, test_config):
        """Test Anthropic client initializes correctly."""
        with patch('src.llm_judge.infrastructure.clients.anthropic_client.anthropic.Anthropic') as mock_anthropic_class:
            mock_client = Mock()
            mock_anthropic_class.return_value = mock_client
            
            client = AnthropicClient(test_config)
            assert client.config == test_config
            assert client.client == mock_client
            
            # Verify SDK was initialized with correct parameters
            mock_anthropic_class.assert_called_once_with(
                api_key="test-anthropic-key",
                timeout=test_config.anthropic_request_timeout,
                max_retries=test_config.max_retries
            )
    
    def test_missing_api_key_raises_error(self):
        """Test that missing API key raises error."""
        config = LLMConfig(
            openai_api_key="test-openai",
            default_provider="openai"
        )
        with pytest.raises(ValueError, match="Anthropic API key is required"):
            AnthropicClient(config)


class TestCreateMessage:
    """Test message creation functionality."""
    
    @pytest.mark.asyncio
    async def test_successful_message_creation(self, test_config):
        """Test successful message creation request."""
        with patch('src.llm_judge.infrastructure.clients.anthropic_client.anthropic.Anthropic') as mock_anthropic_class:
            # Mock the Anthropic SDK client
            mock_client = Mock()
            mock_anthropic_class.return_value = mock_client
            
            # Mock the message creation response
            mock_response = Mock()
            mock_response.content = [Mock(type="text", text="This is a test response from Claude")]
            mock_response.stop_reason = "end_turn"
            mock_response.usage.input_tokens = 10
            mock_response.usage.output_tokens = 8
            mock_response.model = "claude-sonnet-4-20250514"
            
            # Anthropic SDK's create method is synchronous
            mock_client.messages.create.return_value = mock_response
            
            # Create client and test
            client = AnthropicClient(test_config)
            messages = [{"role": "user", "content": "Hello Claude"}]
            result = await client.create_message(messages)
            
            assert isinstance(result, AnthropicResponse)
            assert result.content == "This is a test response from Claude"
            assert result.stop_reason == "end_turn"
            assert result.model == "claude-sonnet-4-20250514"
            assert result.usage["output_tokens"] == 8
            
            # Verify the SDK was called correctly
            mock_client.messages.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_authentication_error(self, test_config):
        """Test handling of authentication errors."""
        with patch('src.llm_judge.infrastructure.clients.anthropic_client.anthropic.Anthropic') as mock_anthropic_class:
            mock_client = Mock()
            mock_anthropic_class.return_value = mock_client
            
            # Mock an authentication error - create minimal mock response
            mock_response = Mock()
            mock_response.request = Mock()
            mock_client.messages.create.side_effect = anthropic.AuthenticationError(
                "Invalid API key", response=mock_response, body=None
            )
            
            client = AnthropicClient(test_config)
            messages = [{"role": "user", "content": "Hello Claude"}]
            
            with pytest.raises(AnthropicError):
                await client.create_message(messages)
    
    @pytest.mark.asyncio
    async def test_rate_limit_error(self, test_config):
        """Test handling of rate limit errors."""
        with patch('src.llm_judge.infrastructure.clients.anthropic_client.anthropic.Anthropic') as mock_anthropic_class:
            mock_client = Mock()
            mock_anthropic_class.return_value = mock_client
            
            # Mock a rate limit error - create minimal mock response
            mock_response = Mock()
            mock_response.request = Mock()
            mock_client.messages.create.side_effect = anthropic.RateLimitError(
                "Rate limit exceeded", response=mock_response, body=None
            )
            
            client = AnthropicClient(test_config)
            messages = [{"role": "user", "content": "Hello Claude"}]
            
            with pytest.raises(AnthropicError):
                await client.create_message(messages)


class TestComparison:
    """Test comparison functionality."""
    
    @pytest.mark.asyncio
    async def test_compare_with_anthropic_success(self, test_config):
        """Test successful Anthropic comparison."""
        with patch('src.llm_judge.infrastructure.clients.anthropic_client.anthropic.Anthropic') as mock_anthropic_class:
            mock_client = Mock()
            mock_anthropic_class.return_value = mock_client
            
            # Mock a successful comparison response
            mock_response = Mock()
            mock_response.content = [Mock(type="text", text='{"winner": "B", "reasoning": "Response B is more comprehensive", "confidence": 0.85}')]
            mock_response.stop_reason = "end_turn"
            mock_response.usage.input_tokens = 75
            mock_response.usage.output_tokens = 25
            mock_response.model = "claude-sonnet-4-20250514"
            
            mock_client.messages.create.return_value = mock_response
            
            client = AnthropicClient(test_config)
            
            # Test comparison method directly
            result = await client.compare_with_anthropic(
                prompt="What is AI?",
                response_a="AI is artificial intelligence",
                response_b="AI is machine learning and much more"
            )
            
            assert result["winner"] == "B"
            assert result["reasoning"] == "Response B is more comprehensive"
            assert result["confidence"] == 0.85
            
            # Verify SDK was called
            mock_client.messages.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_compare_with_anthropic_fallback(self, test_config):
        """Test Anthropic comparison with fallback parsing."""
        with patch('src.llm_judge.infrastructure.clients.anthropic_client.anthropic.Anthropic') as mock_anthropic_class:
            mock_client = Mock()
            mock_anthropic_class.return_value = mock_client
            
            # Mock a response that fails JSON parsing
            mock_response = Mock()
            mock_response.content = [Mock(type="text", text="Response B is clearly better than Response A")]
            mock_response.stop_reason = "end_turn"
            mock_response.usage.input_tokens = 50
            mock_response.usage.output_tokens = 10
            mock_response.model = "claude-sonnet-4-20250514"
            
            mock_client.messages.create.return_value = mock_response
            
            client = AnthropicClient(test_config)
            
            result = await client.compare_with_anthropic(
                prompt="Which is better?",
                response_a="Option A",
                response_b="Option B"
            )
            
            # Should fallback to "tie" when parsing fails (current implementation)
            assert result["winner"] == "tie"
            assert "Failed to parse structured response" in result["reasoning"]
            assert result["confidence"] == 0.3