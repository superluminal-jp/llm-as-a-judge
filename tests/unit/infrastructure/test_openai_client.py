"""Test OpenAI client functionality."""

import json
import pytest
from unittest.mock import Mock, AsyncMock
from src.llm_judge.infrastructure.config.config import LLMConfig
from src.llm_judge.infrastructure.clients.openai_client import OpenAIClient, OpenAIError, OpenAIResponse
from src.llm_judge.infrastructure.clients.http_client import HTTPResponse, HTTPClientError, RateLimitError


@pytest.fixture
def test_config():
    """Create test configuration with OpenAI API key."""
    return LLMConfig(
        openai_api_key="test-openai-key",
        openai_model="gpt-4",
        default_provider="openai"
    )


@pytest.fixture
def mock_http_client():
    """Create mock HTTP client."""
    client = Mock()
    client.request = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def openai_client(test_config, mock_http_client):
    """Create OpenAI client with mock HTTP client."""
    return OpenAIClient(test_config, mock_http_client)


class TestOpenAIClient:
    """Test OpenAI client initialization and basic functionality."""
    
    def test_client_initialization(self, test_config, mock_http_client):
        """Test OpenAI client initializes correctly."""
        client = OpenAIClient(test_config, mock_http_client)
        assert client.config == test_config
        assert client.http_client == mock_http_client
        assert "Bearer test-openai-key" in client.headers["Authorization"]
        assert client.headers["Content-Type"] == "application/json"
    
    def test_missing_api_key_raises_error(self, mock_http_client):
        """Test that missing API key raises error."""
        config = LLMConfig(anthropic_api_key="test-anthropic", default_provider="anthropic")
        with pytest.raises(ValueError, match="OpenAI API key is required"):
            OpenAIClient(config, mock_http_client)


class TestChatCompletion:
    """Test chat completion functionality."""
    
    @pytest.mark.asyncio
    async def test_successful_chat_completion(self, openai_client, mock_http_client):
        """Test successful chat completion request."""
        # Mock successful response
        response_data = {
            "choices": [{
                "message": {"content": "This is a test response"},
                "finish_reason": "stop"
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "model": "gpt-4"
        }
        
        mock_http_client.request.return_value = HTTPResponse(
            status_code=200,
            content=json.dumps(response_data),
            headers={"content-type": "application/json"},
            request_duration=1.0
        )
        
        messages = [{"role": "user", "content": "Hello"}]
        result = await openai_client.chat_completion(messages)
        
        assert isinstance(result, OpenAIResponse)
        assert result.content == "This is a test response"
        assert result.finish_reason == "stop"
        assert result.model == "gpt-4"
        assert result.usage["total_tokens"] == 15
        
        # Verify HTTP request was made correctly
        mock_http_client.request.assert_called_once()
        call_args = mock_http_client.request.call_args
        assert call_args[1]["method"] == "POST"
        assert "/chat/completions" in call_args[1]["url"]
        assert "Bearer test-openai-key" in call_args[1]["headers"]["Authorization"]
    
    @pytest.mark.asyncio
    async def test_authentication_error(self, openai_client, mock_http_client):
        """Test authentication error handling."""
        error_data = {
            "error": {
                "message": "Invalid API key",
                "code": "invalid_api_key"
            }
        }
        
        mock_http_client.request.return_value = HTTPResponse(
            status_code=401,
            content=json.dumps(error_data),
            headers={"content-type": "application/json"},
            request_duration=0.5
        )
        
        messages = [{"role": "user", "content": "Hello"}]
        with pytest.raises(OpenAIError, match="Authentication failed"):
            await openai_client.chat_completion(messages)
    
    @pytest.mark.asyncio
    async def test_rate_limit_error(self, openai_client, mock_http_client):
        """Test rate limit error handling."""
        error_data = {
            "error": {
                "message": "Rate limit exceeded",
                "code": "rate_limit_exceeded"
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
            await openai_client.chat_completion(messages)
    
    @pytest.mark.asyncio
    async def test_invalid_json_response(self, openai_client, mock_http_client):
        """Test handling of invalid JSON response."""
        mock_http_client.request.return_value = HTTPResponse(
            status_code=200,
            content="Invalid JSON response",
            headers={"content-type": "application/json"},
            request_duration=1.0
        )
        
        messages = [{"role": "user", "content": "Hello"}]
        with pytest.raises(OpenAIError, match="Invalid JSON response"):
            await openai_client.chat_completion(messages)
    
    @pytest.mark.asyncio
    async def test_http_client_error(self, openai_client, mock_http_client):
        """Test HTTP client error handling."""
        mock_http_client.request.side_effect = HTTPClientError("Network error")
        
        messages = [{"role": "user", "content": "Hello"}]
        with pytest.raises(OpenAIError, match="HTTP error"):
            await openai_client.chat_completion(messages)


class TestEvaluation:
    """Test evaluation functionality."""
    
    @pytest.mark.asyncio
    async def test_successful_evaluation(self, openai_client, mock_http_client):
        """Test successful response evaluation."""
        # Mock evaluation response
        evaluation_result = {
            "score": 4,
            "reasoning": "Well-structured response with good clarity",
            "confidence": 0.85
        }
        
        response_data = {
            "choices": [{
                "message": {"content": json.dumps(evaluation_result)},
                "finish_reason": "stop"
            }],
            "usage": {"total_tokens": 100},
            "model": "gpt-4"
        }
        
        mock_http_client.request.return_value = HTTPResponse(
            status_code=200,
            content=json.dumps(response_data),
            headers={"content-type": "application/json"},
            request_duration=2.0
        )
        
        result = await openai_client.evaluate_with_openai(
            prompt="What is AI?",
            response_text="AI is artificial intelligence",
            criteria="accuracy"
        )
        
        assert result["score"] == 4
        assert result["reasoning"] == "Well-structured response with good clarity"
        assert result["confidence"] == 0.85
    
    @pytest.mark.asyncio
    async def test_evaluation_fallback(self, openai_client, mock_http_client):
        """Test evaluation fallback when JSON parsing fails."""
        response_data = {
            "choices": [{
                "message": {"content": "This is a good response with excellent quality"},
                "finish_reason": "stop"
            }],
            "usage": {"total_tokens": 50},
            "model": "gpt-4"
        }
        
        mock_http_client.request.return_value = HTTPResponse(
            status_code=200,
            content=json.dumps(response_data),
            headers={"content-type": "application/json"},
            request_duration=1.5
        )
        
        result = await openai_client.evaluate_with_openai(
            prompt="Test question",
            response_text="Test response"
        )
        
        assert result["score"] == 5.0  # Should detect "excellent" keyword
        assert "Failed to parse structured response" in result["reasoning"]
        assert result["confidence"] == 0.3


class TestComparison:
    """Test comparison functionality."""
    
    @pytest.mark.asyncio
    async def test_successful_comparison(self, openai_client, mock_http_client):
        """Test successful response comparison."""
        comparison_result = {
            "winner": "A",
            "reasoning": "Response A provides more detailed information",
            "confidence": 0.75
        }
        
        response_data = {
            "choices": [{
                "message": {"content": json.dumps(comparison_result)},
                "finish_reason": "stop"
            }],
            "usage": {"total_tokens": 120},
            "model": "gpt-4"
        }
        
        mock_http_client.request.return_value = HTTPResponse(
            status_code=200,
            content=json.dumps(response_data),
            headers={"content-type": "application/json"},
            request_duration=2.5
        )
        
        result = await openai_client.compare_with_openai(
            prompt="Explain quantum computing",
            response_a="Quantum computing uses quantum bits",
            response_b="Quantum computers use qubits"
        )
        
        assert result["winner"] == "A"
        assert result["reasoning"] == "Response A provides more detailed information"
        assert result["confidence"] == 0.75
    
    @pytest.mark.asyncio
    async def test_comparison_fallback(self, openai_client, mock_http_client):
        """Test comparison fallback when JSON parsing fails."""
        response_data = {
            "choices": [{
                "message": {"content": "Both responses are similar in quality"},
                "finish_reason": "stop"
            }],
            "usage": {"total_tokens": 80},
            "model": "gpt-4"
        }
        
        mock_http_client.request.return_value = HTTPResponse(
            status_code=200,
            content=json.dumps(response_data),
            headers={"content-type": "application/json"},
            request_duration=1.8
        )
        
        result = await openai_client.compare_with_openai(
            prompt="Test question",
            response_a="Response A",
            response_b="Response B"
        )
        
        assert result["winner"] == "tie"  # Fallback default
        assert "Failed to parse structured response" in result["reasoning"]
        assert result["confidence"] == 0.3
    
    @pytest.mark.asyncio
    async def test_invalid_winner_value(self, openai_client, mock_http_client):
        """Test handling of invalid winner value."""
        comparison_result = {
            "winner": "invalid",  # Should be A, B, or tie
            "reasoning": "Test reasoning",
            "confidence": 0.8
        }
        
        response_data = {
            "choices": [{
                "message": {"content": json.dumps(comparison_result)},
                "finish_reason": "stop"
            }],
            "usage": {"total_tokens": 100},
            "model": "gpt-4"
        }
        
        mock_http_client.request.return_value = HTTPResponse(
            status_code=200,
            content=json.dumps(response_data),
            headers={"content-type": "application/json"},
            request_duration=2.0
        )
        
        result = await openai_client.compare_with_openai(
            prompt="Test question",
            response_a="Response A",
            response_b="Response B"
        )
        
        # Should fallback to tie due to validation error
        assert result["winner"] == "tie"
        assert "Failed to parse structured response" in result["reasoning"]