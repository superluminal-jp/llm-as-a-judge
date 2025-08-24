"""Test Anthropic client functionality."""

import json
import pytest
from unittest.mock import Mock, AsyncMock, patch
from src.llm_judge.infrastructure.config.config import LLMConfig
from src.llm_judge.infrastructure.clients.anthropic_client import AnthropicClient, AnthropicError, AnthropicResponse, RateLimitError
import anthropic


@pytest.fixture
def test_config():
    """Create test configuration with Anthropic API key."""
    config = object.__new__(LLMConfig)
    config.anthropic_api_key = "test-anthropic-key"
    config.anthropic_model = "claude-sonnet-4-20250514"
    config.default_provider = "anthropic"
    config.anthropic_request_timeout = 30
    config.anthropic_connect_timeout = 10
    config.request_timeout = 30
    config.max_retries = 3
    config.anthropic_temperature = 0.1
    config.anthropic_top_p = None
    return config


@pytest.fixture
def mock_anthropic_sdk():
    """Create mock Anthropic SDK client."""
    with patch('anthropic_client.anthropic.Anthropic') as mock_anthropic:
        mock_client = Mock()
        mock_anthropic.return_value = mock_client
        yield mock_client


@pytest.fixture
def anthropic_client(test_config):
    """Create Anthropic client with mocked SDK."""
    with patch('anthropic_client.anthropic.Anthropic'):
        return AnthropicClient(test_config)


class TestAnthropicClient:
    """Test Anthropic client initialization and basic functionality."""
    
    def test_client_initialization(self, test_config):
        """Test Anthropic client initializes correctly."""
        with patch('anthropic_client.anthropic.Anthropic') as mock_anthropic:
            mock_sdk = Mock()
            mock_anthropic.return_value = mock_sdk
            
            client = AnthropicClient(test_config)
            assert client.config == test_config
            assert client.client == mock_sdk
            
            # Verify SDK was initialized with correct parameters
            mock_anthropic.assert_called_once_with(
                api_key="test-anthropic-key",
                timeout=test_config.anthropic_request_timeout,
                max_retries=test_config.max_retries
            )
    
    def test_missing_api_key_raises_error(self):
        """Test that missing API key raises error."""
        config = object.__new__(LLMConfig)
        config.anthropic_api_key = None
        config.openai_api_key = "test-openai"
        config.default_provider = "openai"
        with pytest.raises(ValueError, match="Anthropic API key is required"):
            AnthropicClient(config)


class TestCreateMessage:
    """Test message creation functionality."""
    
    @pytest.mark.asyncio
    async def test_successful_message_creation(self, anthropic_client, mock_http_client):
        """Test successful message creation request."""
        # Mock successful response
        response_data = {
            "content": [{
                "type": "text",
                "text": "This is a test response from Claude"
            }],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 8},
            "model": "claude-sonnet-4-20250514"
        }
        
        mock_http_client.request.return_value = HTTPResponse(
            status_code=200,
            content=json.dumps(response_data),
            headers={"content-type": "application/json"},
            request_duration=1.5
        )
        
        messages = [{"role": "user", "content": "Hello Claude"}]
        result = await anthropic_client.create_message(messages)
        
        assert isinstance(result, AnthropicResponse)
        assert result.content == "This is a test response from Claude"
        assert result.stop_reason == "end_turn"
        assert result.model == "claude-sonnet-4-20250514"
        assert result.usage["output_tokens"] == 8
        
        # Verify HTTP request was made correctly
        mock_http_client.request.assert_called_once()
        call_args = mock_http_client.request.call_args
        assert call_args[1]["method"] == "POST"
        assert "/messages" in call_args[1]["url"]
        assert call_args[1]["headers"]["x-api-key"] == "test-anthropic-key"
    
    @pytest.mark.asyncio
    async def test_system_message_handling(self, anthropic_client, mock_http_client):
        """Test proper handling of system messages."""
        response_data = {
            "content": [{"type": "text", "text": "System message handled correctly"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 15, "output_tokens": 6},
            "model": "claude-sonnet-4-20250514"
        }
        
        mock_http_client.request.return_value = HTTPResponse(
            status_code=200,
            content=json.dumps(response_data),
            headers={"content-type": "application/json"},
            request_duration=1.2
        )
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello"}
        ]
        
        result = await anthropic_client.create_message(messages)
        
        # Check that system message was handled correctly
        call_args = mock_http_client.request.call_args
        payload = call_args[1]["json_data"]
        assert "system" in payload
        assert payload["system"] == "You are a helpful assistant"
        assert len(payload["messages"]) == 1  # Only user message in messages array
        assert payload["messages"][0]["role"] == "user"
    
    @pytest.mark.asyncio
    async def test_multiple_content_blocks(self, anthropic_client, mock_http_client):
        """Test handling of multiple content blocks."""
        response_data = {
            "content": [
                {"type": "text", "text": "First part "},
                {"type": "text", "text": "second part "},
                {"type": "text", "text": "third part"}
            ],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 12},
            "model": "claude-sonnet-4-20250514"
        }
        
        mock_http_client.request.return_value = HTTPResponse(
            status_code=200,
            content=json.dumps(response_data),
            headers={"content-type": "application/json"},
            request_duration=1.0
        )
        
        messages = [{"role": "user", "content": "Test multiple blocks"}]
        result = await anthropic_client.create_message(messages)
        
        assert result.content == "First part second part third part"
    
    @pytest.mark.asyncio
    async def test_authentication_error(self, anthropic_client, mock_http_client):
        """Test authentication error handling."""
        error_data = {
            "error": {
                "type": "authentication_error",
                "message": "Invalid API key"
            }
        }
        
        mock_http_client.request.return_value = HTTPResponse(
            status_code=401,
            content=json.dumps(error_data),
            headers={"content-type": "application/json"},
            request_duration=0.5
        )
        
        messages = [{"role": "user", "content": "Hello"}]
        with pytest.raises(AnthropicError, match="Authentication failed"):
            await anthropic_client.create_message(messages)
    
    @pytest.mark.asyncio
    async def test_rate_limit_error(self, anthropic_client, mock_http_client):
        """Test rate limit error handling."""
        error_data = {
            "error": {
                "type": "rate_limit_error",
                "message": "Rate limit exceeded"
            }
        }
        
        mock_http_client.request.return_value = HTTPResponse(
            status_code=429,
            content=json.dumps(error_data),
            headers={"content-type": "application/json"},
            request_duration=0.5
        )
        
        messages = [{"role": "user", "content": "Hello"}]
        with pytest.raises(RateLimitError, match="Rate limit exceeded"):
            await anthropic_client.create_message(messages)
    
    @pytest.mark.asyncio
    async def test_invalid_json_response(self, anthropic_client, mock_http_client):
        """Test handling of invalid JSON response."""
        mock_http_client.request.return_value = HTTPResponse(
            status_code=200,
            content="Invalid JSON response",
            headers={"content-type": "application/json"},
            request_duration=1.0
        )
        
        messages = [{"role": "user", "content": "Hello"}]
        with pytest.raises(AnthropicError, match="Invalid JSON response"):
            await anthropic_client.create_message(messages)
    
    @pytest.mark.asyncio
    async def test_http_client_error(self, anthropic_client, mock_http_client):
        """Test HTTP client error handling."""
        mock_http_client.request.side_effect = HTTPClientError("Network error")
        
        messages = [{"role": "user", "content": "Hello"}]
        with pytest.raises(AnthropicError, match="HTTP error"):
            await anthropic_client.create_message(messages)


class TestEvaluation:
    """Test evaluation functionality."""
    
    @pytest.mark.asyncio
    async def test_successful_evaluation(self, anthropic_client, mock_http_client):
        """Test successful response evaluation."""
        # Mock evaluation response
        evaluation_result = {
            "score": 4,
            "reasoning": "Well-structured response with good clarity",
            "confidence": 0.85
        }
        
        response_data = {
            "content": [{
                "type": "text",
                "text": json.dumps(evaluation_result)
            }],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 50, "output_tokens": 30},
            "model": "claude-sonnet-4-20250514"
        }
        
        mock_http_client.request.return_value = HTTPResponse(
            status_code=200,
            content=json.dumps(response_data),
            headers={"content-type": "application/json"},
            request_duration=2.0
        )
        
        result = await anthropic_client.evaluate_with_anthropic(
            prompt="What is AI?",
            response_text="AI is artificial intelligence",
            criteria="accuracy"
        )
        
        assert result["score"] == 4
        assert result["reasoning"] == "Well-structured response with good clarity"
        assert result["confidence"] == 0.85
    
    @pytest.mark.asyncio
    async def test_evaluation_fallback(self, anthropic_client, mock_http_client):
        """Test evaluation fallback when JSON parsing fails."""
        response_data = {
            "content": [{
                "type": "text",
                "text": "This is a good response with excellent quality"
            }],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 30, "output_tokens": 20},
            "model": "claude-sonnet-4-20250514"
        }
        
        mock_http_client.request.return_value = HTTPResponse(
            status_code=200,
            content=json.dumps(response_data),
            headers={"content-type": "application/json"},
            request_duration=1.5
        )
        
        result = await anthropic_client.evaluate_with_anthropic(
            prompt="Test question",
            response_text="Test response"
        )
        
        assert result["score"] == 5.0  # Should detect "excellent" keyword
        assert "Failed to parse structured response" in result["reasoning"]
        assert result["confidence"] == 0.3


class TestComparison:
    """Test comparison functionality."""
    
    @pytest.mark.asyncio
    async def test_successful_comparison(self, anthropic_client, mock_http_client):
        """Test successful response comparison."""
        comparison_result = {
            "winner": "A",
            "reasoning": "Response A provides more detailed information",
            "confidence": 0.75
        }
        
        response_data = {
            "content": [{
                "type": "text",
                "text": json.dumps(comparison_result)
            }],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 80, "output_tokens": 25},
            "model": "claude-sonnet-4-20250514"
        }
        
        mock_http_client.request.return_value = HTTPResponse(
            status_code=200,
            content=json.dumps(response_data),
            headers={"content-type": "application/json"},
            request_duration=2.5
        )
        
        result = await anthropic_client.compare_with_anthropic(
            prompt="Explain quantum computing",
            response_a="Quantum computing uses quantum bits",
            response_b="Quantum computers use qubits"
        )
        
        assert result["winner"] == "A"
        assert result["reasoning"] == "Response A provides more detailed information"
        assert result["confidence"] == 0.75
    
    @pytest.mark.asyncio
    async def test_comparison_fallback(self, anthropic_client, mock_http_client):
        """Test comparison fallback when JSON parsing fails."""
        response_data = {
            "content": [{
                "type": "text",
                "text": "Both responses are similar in quality"
            }],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 60, "output_tokens": 15},
            "model": "claude-sonnet-4-20250514"
        }
        
        mock_http_client.request.return_value = HTTPResponse(
            status_code=200,
            content=json.dumps(response_data),
            headers={"content-type": "application/json"},
            request_duration=1.8
        )
        
        result = await anthropic_client.compare_with_anthropic(
            prompt="Test question",
            response_a="Response A",
            response_b="Response B"
        )
        
        assert result["winner"] == "tie"  # Fallback default
        assert "Failed to parse structured response" in result["reasoning"]
        assert result["confidence"] == 0.3
    
    @pytest.mark.asyncio
    async def test_invalid_winner_value(self, anthropic_client, mock_http_client):
        """Test handling of invalid winner value."""
        comparison_result = {
            "winner": "invalid",  # Should be A, B, or tie
            "reasoning": "Test reasoning",
            "confidence": 0.8
        }
        
        response_data = {
            "content": [{
                "type": "text",
                "text": json.dumps(comparison_result)
            }],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 70, "output_tokens": 20},
            "model": "claude-sonnet-4-20250514"
        }
        
        mock_http_client.request.return_value = HTTPResponse(
            status_code=200,
            content=json.dumps(response_data),
            headers={"content-type": "application/json"},
            request_duration=2.0
        )
        
        result = await anthropic_client.compare_with_anthropic(
            prompt="Test question",
            response_a="Response A",
            response_b="Response B"
        )
        
        # Should fallback to tie due to validation error
        assert result["winner"] == "tie"
        assert "Failed to parse structured response" in result["reasoning"]