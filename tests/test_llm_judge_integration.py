"""Test LLM Judge integration with OpenAI client."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from config import LLMConfig
from llm_judge_simple import LLMJudge, CandidateResponse


@pytest.fixture
def openai_config():
    """Create configuration for OpenAI testing."""
    return LLMConfig(
        openai_api_key="test-openai-key",
        default_provider="openai",
        openai_model="gpt-4"
    )


@pytest.fixture
def anthropic_config():
    """Create configuration for Anthropic testing."""
    return LLMConfig(
        anthropic_api_key="test-anthropic-key",
        default_provider="anthropic",
        anthropic_model="claude-sonnet-4-20250514"
    )


@pytest.fixture
def mock_config():
    """Create configuration for mock testing."""
    # Create config manually to bypass validation
    config = object.__new__(LLMConfig)
    config.openai_api_key = None
    config.anthropic_api_key = None
    config.default_provider = "openai"
    config.openai_model = "gpt-4"
    config.anthropic_model = "claude-sonnet-4-20250514"
    config.gpt5_reasoning_effort = "medium"
    config.request_timeout = 30
    config.max_retries = 3
    config.retry_delay = 1
    config.log_level = "INFO"
    return config


class TestLLMJudgeIntegration:
    """Test LLM Judge integration with real and mock clients."""
    
    def test_initialization_with_openai(self, openai_config):
        """Test LLM Judge initializes correctly with OpenAI config."""
        judge = LLMJudge(openai_config)
        assert judge.config == openai_config
        assert judge.judge_model == "gpt-4"
        assert judge._use_real_llm is True
        assert judge._openai_client is None  # Lazy initialization
        assert judge._anthropic_client is None
    
    def test_initialization_with_anthropic(self, anthropic_config):
        """Test LLM Judge initializes correctly with Anthropic config.""" 
        judge = LLMJudge(anthropic_config)
        assert judge.config == anthropic_config
        assert judge.judge_model == "claude-sonnet-4-20250514"
        assert judge._use_real_llm is True
        assert judge._openai_client is None  # Lazy initialization
        assert judge._anthropic_client is None
    
    def test_initialization_with_mock(self, mock_config):
        """Test LLM Judge initializes correctly for mock mode."""
        judge = LLMJudge(mock_config)
        assert judge.config == mock_config
        assert judge._use_real_llm is False
    
    @pytest.mark.asyncio
    async def test_mock_evaluation(self, mock_config):
        """Test evaluation using mock client."""
        judge = LLMJudge(mock_config)
        
        candidate = CandidateResponse(
            prompt="What is AI?",
            response="AI is artificial intelligence",
            model="test-model"
        )
        
        result = await judge.evaluate_response(candidate, "accuracy")
        
        assert result.score == 3.5  # Mock default
        assert "Mock evaluation" in result.reasoning
        assert result.confidence == 0.8
        
        await judge.close()
    
    @pytest.mark.asyncio 
    async def test_mock_comparison(self, mock_config):
        """Test comparison using mock client."""
        judge = LLMJudge(mock_config)
        
        candidate_a = CandidateResponse(
            prompt="Explain quantum computing",
            response="Response A",
            model="test-model"
        )
        
        candidate_b = CandidateResponse(
            prompt="Explain quantum computing",
            response="Response B", 
            model="test-model"
        )
        
        result = await judge.compare_responses(candidate_a, candidate_b)
        
        assert result["winner"] == "tie"  # Mock default
        assert "Mock comparison" in result["reasoning"]
        assert result["confidence"] == 0.7
        
        await judge.close()
    
    @pytest.mark.asyncio
    async def test_openai_evaluation_success(self, openai_config):
        """Test successful OpenAI evaluation."""
        judge = LLMJudge(openai_config)
        
        # Mock the OpenAI client response
        mock_openai_result = {
            "score": 4,
            "reasoning": "Well-structured and accurate response",
            "confidence": 0.9
        }
        
        with patch.object(judge, '_ensure_clients_initialized') as mock_init, \
             patch.object(judge, '_openai_client') as mock_client:
            
            mock_init.return_value = None
            mock_client.evaluate_with_openai = AsyncMock(return_value=mock_openai_result)
            
            candidate = CandidateResponse(
                prompt="What is machine learning?",
                response="Machine learning is a subset of AI",
                model="gpt-4"
            )
            
            result = await judge.evaluate_response(candidate, "technical accuracy")
            
            assert result.score == 4.0
            assert result.reasoning == "Well-structured and accurate response"
            assert result.confidence == 0.9
            
            # Verify OpenAI client was called correctly
            mock_client.evaluate_with_openai.assert_called_once_with(
                prompt="What is machine learning?",
                response_text="Machine learning is a subset of AI",
                criteria="technical accuracy",
                model="gpt-4"
            )
        
        await judge.close()
    
    @pytest.mark.asyncio
    async def test_openai_evaluation_fallback(self, openai_config):
        """Test OpenAI evaluation with fallback to mock."""
        judge = LLMJudge(openai_config)
        
        with patch.object(judge, '_ensure_clients_initialized') as mock_init, \
             patch.object(judge, '_openai_client') as mock_client:
            
            mock_init.return_value = None
            mock_client.evaluate_with_openai = AsyncMock(side_effect=Exception("API Error"))
            
            candidate = CandidateResponse(
                prompt="Test question",
                response="Test response",
                model="gpt-4"
            )
            
            result = await judge.evaluate_response(candidate, "quality")
            
            # Should fallback to mock values
            assert result.score == 3.5
            assert "Mock evaluation" in result.reasoning
            assert result.confidence == 0.8
        
        await judge.close()
    
    @pytest.mark.asyncio
    async def test_openai_comparison_success(self, openai_config):
        """Test successful OpenAI comparison."""
        judge = LLMJudge(openai_config)
        
        mock_comparison_result = {
            "winner": "A",
            "reasoning": "Response A is more comprehensive",
            "confidence": 0.8
        }
        
        with patch.object(judge, '_ensure_clients_initialized') as mock_init, \
             patch.object(judge, '_openai_client') as mock_client:
            
            mock_init.return_value = None
            mock_client.compare_with_openai = AsyncMock(return_value=mock_comparison_result)
            
            candidate_a = CandidateResponse(
                prompt="Explain neural networks",
                response="Detailed explanation of neural networks",
                model="gpt-4"
            )
            
            candidate_b = CandidateResponse(
                prompt="Explain neural networks",
                response="Brief explanation",
                model="gpt-4"
            )
            
            result = await judge.compare_responses(candidate_a, candidate_b)
            
            assert result["winner"] == "A"
            assert result["reasoning"] == "Response A is more comprehensive"
            assert result["confidence"] == 0.8
            
            # Verify OpenAI client was called correctly
            mock_client.compare_with_openai.assert_called_once_with(
                prompt="Explain neural networks",
                response_a="Detailed explanation of neural networks",
                response_b="Brief explanation",
                model="gpt-4"
            )
        
        await judge.close()
    
    @pytest.mark.asyncio
    async def test_different_prompts_raises_error(self, mock_config):
        """Test that comparing responses with different prompts raises error."""
        judge = LLMJudge(mock_config)
        
        candidate_a = CandidateResponse(
            prompt="Question A",
            response="Response A",
            model="test"
        )
        
        candidate_b = CandidateResponse(
            prompt="Question B", 
            response="Response B",
            model="test"
        )
        
        with pytest.raises(ValueError, match="Cannot compare responses to different prompts"):
            await judge.compare_responses(candidate_a, candidate_b)
        
        await judge.close()
    
    @pytest.mark.asyncio
    async def test_client_initialization(self, openai_config):
        """Test lazy client initialization."""
        judge = LLMJudge(openai_config)
        
        # Clients should be None initially
        assert judge._openai_client is None
        
        # Mock the client creation
        with patch('llm_judge_simple.OpenAIClient') as mock_openai_class:
            
            mock_openai_client = Mock()
            mock_openai_client.close = AsyncMock()
            mock_openai_class.return_value = mock_openai_client
            
            await judge._ensure_clients_initialized()
            
            # Clients should be initialized
            assert judge._openai_client == mock_openai_client
            
            # Verify creation calls
            mock_openai_class.assert_called_once_with(openai_config)
            
            await judge.close()
    
    @pytest.mark.asyncio
    async def test_resource_cleanup(self, openai_config):
        """Test that resources are cleaned up properly."""
        judge = LLMJudge(openai_config)
        
        # Mock clients
        mock_openai_client = Mock()
        mock_openai_client.close = AsyncMock()
        
        judge._openai_client = mock_openai_client
        
        await judge.close()
        
        # Verify cleanup was called
        mock_openai_client.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_anthropic_evaluation_success(self, anthropic_config):
        """Test successful Anthropic evaluation."""
        judge = LLMJudge(anthropic_config)
        
        # Mock the Anthropic client response
        mock_anthropic_result = {
            "score": 4,
            "reasoning": "Well-structured and accurate response",
            "confidence": 0.9
        }
        
        with patch.object(judge, '_ensure_clients_initialized') as mock_init, \
             patch.object(judge, '_anthropic_client') as mock_client:
            
            mock_init.return_value = None
            mock_client.evaluate_with_anthropic = AsyncMock(return_value=mock_anthropic_result)
            
            candidate = CandidateResponse(
                prompt="What is machine learning?",
                response="Machine learning is a subset of AI",
                model="claude-sonnet-4"
            )
            
            result = await judge.evaluate_response(candidate, "technical accuracy")
            
            assert result.score == 4.0
            assert result.reasoning == "Well-structured and accurate response"
            assert result.confidence == 0.9
            
            # Verify Anthropic client was called correctly
            mock_client.evaluate_with_anthropic.assert_called_once_with(
                prompt="What is machine learning?",
                response_text="Machine learning is a subset of AI",
                criteria="technical accuracy",
                model="claude-sonnet-4-20250514"
            )
        
        await judge.close()
    
    @pytest.mark.asyncio
    async def test_anthropic_comparison_success(self, anthropic_config):
        """Test successful Anthropic comparison."""
        judge = LLMJudge(anthropic_config)
        
        mock_comparison_result = {
            "winner": "B",
            "reasoning": "Response B is more comprehensive",
            "confidence": 0.85
        }
        
        with patch.object(judge, '_ensure_clients_initialized') as mock_init, \
             patch.object(judge, '_anthropic_client') as mock_client:
            
            mock_init.return_value = None
            mock_client.compare_with_anthropic = AsyncMock(return_value=mock_comparison_result)
            
            candidate_a = CandidateResponse(
                prompt="Explain neural networks",
                response="Basic explanation of neural networks",
                model="claude-sonnet-4"
            )
            
            candidate_b = CandidateResponse(
                prompt="Explain neural networks",
                response="Comprehensive explanation with examples",
                model="claude-sonnet-4"
            )
            
            result = await judge.compare_responses(candidate_a, candidate_b)
            
            assert result["winner"] == "B"
            assert result["reasoning"] == "Response B is more comprehensive"
            assert result["confidence"] == 0.85
            
            # Verify Anthropic client was called correctly
            mock_client.compare_with_anthropic.assert_called_once_with(
                prompt="Explain neural networks",
                response_a="Basic explanation of neural networks",
                response_b="Comprehensive explanation with examples",
                model="claude-sonnet-4-20250514"
            )
        
        await judge.close()