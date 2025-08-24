"""Test HTTP client functionality."""

import pytest
import pytest_asyncio
from src.llm_judge.infrastructure.config.config import LLMConfig
from src.llm_judge.infrastructure.clients.http_client import create_http_client, HTTPClientError, MockHTTPClient, BaseHTTPClient


@pytest.fixture
def test_config():
    """Create test configuration."""
    return LLMConfig(
        openai_api_key="test_key",
        request_timeout=5,
        max_retries=2,
        retry_delay=1
    )


class TestMockHTTPClient:
    """Test mock HTTP client functionality."""
    
    @pytest.mark.asyncio
    async def test_openai_mock_request(self, test_config):
        """Test mock request for OpenAI API."""
        async with create_http_client(test_config, use_mock=True) as client:
            response = await client.request(
                method="POST",
                url="https://api.openai.com/v1/chat/completions",
                headers={"Authorization": "Bearer test"},
                json_data={"model": "gpt-4", "messages": []}
            )
            
            assert response.status_code == 200
            assert "Mock OpenAI" in response.content
            assert response.headers["content-type"] == "application/json"
            assert response.request_duration > 0
    
    @pytest.mark.asyncio
    async def test_anthropic_mock_request(self, test_config):
        """Test mock request for Anthropic API."""
        async with create_http_client(test_config, use_mock=True) as client:
            response = await client.request(
                method="POST",
                url="https://api.anthropic.com/v1/messages",
                headers={"x-api-key": "test"},
                json_data={"model": "claude-3", "messages": []}
            )
            
            assert response.status_code == 200
            assert "Mock Anthropic" in response.content
            assert response.headers["content-type"] == "application/json"
    
    @pytest.mark.asyncio
    async def test_generic_mock_request(self, test_config):
        """Test mock request for generic URL."""
        async with create_http_client(test_config, use_mock=True) as client:
            response = await client.request(
                method="GET",
                url="https://example.com/api"
            )
            
            assert response.status_code == 200
            assert "mock response" in response.content


class TestHTTPClientFactory:
    """Test HTTP client factory function."""
    
    def test_mock_client_creation(self, test_config):
        """Test creation of mock HTTP client."""
        client = create_http_client(test_config, use_mock=True)
        assert isinstance(client, MockHTTPClient)
    
    def test_real_client_creation(self, test_config):
        """Test creation of real HTTP client."""
        client = create_http_client(test_config, use_mock=False)
        assert isinstance(client, BaseHTTPClient)
    
    @pytest.mark.asyncio
    async def test_client_context_manager(self, test_config):
        """Test that clients work as async context managers."""
        async with create_http_client(test_config, use_mock=True) as client:
            assert client is not None
        
        async with create_http_client(test_config, use_mock=False) as client:
            assert client is not None


class TestBaseHTTPClient:
    """Test real HTTP client functionality."""
    
    def test_client_initialization(self, test_config):
        """Test that HTTP client initializes with correct configuration."""
        client = BaseHTTPClient(test_config)
        assert client.config == test_config
        assert hasattr(client, 'client')  # httpx.AsyncClient
    
    def test_backoff_delay_calculation(self, test_config):
        """Test exponential backoff delay calculation."""
        client = BaseHTTPClient(test_config)
        
        # Test different attempt numbers
        delay_0 = client._calculate_backoff_delay(0)
        delay_1 = client._calculate_backoff_delay(1)
        delay_2 = client._calculate_backoff_delay(2)
        
        # Delays should generally increase (accounting for jitter)
        assert 0 < delay_0 <= 5  # Base delay with jitter
        assert 0 < delay_1 <= 10  # 2x base delay with jitter
        assert 0 < delay_2 <= 20  # 4x base delay with jitter
        
        # Very high attempts should be capped at 60 seconds
        delay_high = client._calculate_backoff_delay(10)
        assert delay_high <= 60
    
    def test_retry_after_parsing(self, test_config):
        """Test parsing of Retry-After headers."""
        client = BaseHTTPClient(test_config)
        
        # Test numeric retry-after
        headers = {"retry-after": "5"}
        assert client._get_retry_after(headers) == 5.0
        
        # Test case-insensitive header
        headers = {"Retry-After": "10"}
        assert client._get_retry_after(headers) == 10.0
        
        # Test missing header (should return default)
        headers = {}
        assert client._get_retry_after(headers) == test_config.retry_delay
        
        # Test invalid value (should return default)
        headers = {"retry-after": "invalid"}
        assert client._get_retry_after(headers) == test_config.retry_delay