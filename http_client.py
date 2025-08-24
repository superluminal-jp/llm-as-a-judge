"""HTTP client infrastructure for LLM API calls."""

import asyncio
import logging
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    logging.warning("httpx not installed. HTTP functionality will not be available.")

from config import LLMConfig


@dataclass
class HTTPResponse:
    """Standardized HTTP response."""
    status_code: int
    content: str
    headers: Dict[str, str]
    request_duration: float


class HTTPClientError(Exception):
    """Base exception for HTTP client errors."""
    pass


class RateLimitError(HTTPClientError):
    """Raised when API rate limit is exceeded."""
    pass


class TimeoutError(HTTPClientError):
    """Raised when request times out."""
    pass


class NetworkError(HTTPClientError):
    """Raised when network connectivity fails."""
    pass


class BaseHTTPClient:
    """Base HTTP client with retry logic and connection pooling."""
    
    def __init__(self, config: LLMConfig):
        if not HTTPX_AVAILABLE:
            raise ImportError("httpx is required for HTTP client functionality")
        
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Configure connection limits and timeouts
        limits = httpx.Limits(
            max_keepalive_connections=10,
            max_connections=20,
            keepalive_expiry=30.0
        )
        
        timeout = httpx.Timeout(
            connect=10.0,
            read=config.request_timeout,
            write=10.0,
            pool=30.0
        )
        
        # Create HTTP client with connection pooling
        self.client = httpx.AsyncClient(
            limits=limits,
            timeout=timeout,
            follow_redirects=True,
            http2=True
        )
        
        self.logger.info(f"Initialized HTTP client with timeout: {config.request_timeout}s, retries: {config.max_retries}")
    
    async def request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> HTTPResponse:
        """Make HTTP request with retry logic and error handling."""
        
        start_time = time.time()
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                self.logger.debug(f"HTTP {method} {url} (attempt {attempt + 1}/{self.config.max_retries + 1})")
                
                response = await self.client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json_data,
                    **kwargs
                )
                
                duration = time.time() - start_time
                
                # Handle different HTTP status codes
                if response.status_code == 429:
                    retry_after = self._get_retry_after(response.headers)
                    if attempt < self.config.max_retries:
                        self.logger.warning(f"Rate limit hit, retrying after {retry_after}s")
                        await asyncio.sleep(retry_after)
                        continue
                    else:
                        raise RateLimitError(f"Rate limit exceeded after {self.config.max_retries} retries")
                
                elif 500 <= response.status_code < 600:
                    if attempt < self.config.max_retries:
                        delay = self._calculate_backoff_delay(attempt)
                        self.logger.warning(f"Server error {response.status_code}, retrying after {delay}s")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        raise HTTPClientError(f"Server error {response.status_code} after {self.config.max_retries} retries")
                
                elif response.status_code >= 400:
                    # Client errors (4xx) - don't retry
                    raise HTTPClientError(f"Client error {response.status_code}: {response.text}")
                
                # Success - return response
                return HTTPResponse(
                    status_code=response.status_code,
                    content=response.text,
                    headers=dict(response.headers),
                    request_duration=duration
                )
                
            except httpx.TimeoutException as e:
                last_exception = TimeoutError(f"Request timeout after {self.config.request_timeout}s")
                if attempt < self.config.max_retries:
                    delay = self._calculate_backoff_delay(attempt)
                    self.logger.warning(f"Timeout, retrying after {delay}s")
                    await asyncio.sleep(delay)
                    continue
                    
            except (httpx.NetworkError, httpx.ConnectError) as e:
                last_exception = NetworkError(f"Network error: {str(e)}")
                if attempt < self.config.max_retries:
                    delay = self._calculate_backoff_delay(attempt)
                    self.logger.warning(f"Network error, retrying after {delay}s")
                    await asyncio.sleep(delay)
                    continue
                    
            except Exception as e:
                last_exception = HTTPClientError(f"Unexpected error: {str(e)}")
                if attempt < self.config.max_retries:
                    delay = self._calculate_backoff_delay(attempt)
                    self.logger.warning(f"Unexpected error, retrying after {delay}s")
                    await asyncio.sleep(delay)
                    continue
        
        # All retries exhausted
        self.logger.error(f"All {self.config.max_retries + 1} attempts failed")
        raise last_exception or HTTPClientError("All retry attempts failed")
    
    def _calculate_backoff_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay with jitter."""
        import random
        
        # Exponential backoff: base_delay * (2 ** attempt)
        base_delay = self.config.retry_delay
        exponential_delay = base_delay * (2 ** attempt)
        
        # Add jitter (±25% of delay)
        jitter = exponential_delay * 0.25 * (2 * random.random() - 1)
        
        # Cap at 60 seconds
        return min(exponential_delay + jitter, 60.0)
    
    def _get_retry_after(self, headers: Dict[str, str]) -> float:
        """Extract retry-after value from headers."""
        retry_after = headers.get('retry-after', headers.get('Retry-After', ''))
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass
        
        # Default retry delay if not specified
        return self.config.retry_delay
    
    async def close(self):
        """Close the HTTP client and cleanup connections."""
        await self.client.aclose()
        self.logger.debug("HTTP client closed")
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


class MockHTTPClient:
    """Mock HTTP client for testing without real API calls."""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initialized Mock HTTP client")
    
    async def request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> HTTPResponse:
        """Mock HTTP request that returns simulated responses."""
        
        # Simulate network delay
        await asyncio.sleep(0.1)
        
        # Mock response based on URL patterns
        if "openai" in url.lower():
            content = '{"choices": [{"message": {"content": "{\\"score\\": 4, \\"reasoning\\": \\"Mock OpenAI evaluation\\", \\"confidence\\": 0.85}"}}]}'
        elif "anthropic" in url.lower():
            content = '{"content": [{"text": "{\\"score\\": 4, \\"reasoning\\": \\"Mock Anthropic evaluation\\", \\"confidence\\": 0.85}"}]}'
        else:
            content = '{"result": "mock response"}'
        
        self.logger.debug(f"Mock HTTP {method} {url} -> 200")
        
        return HTTPResponse(
            status_code=200,
            content=content,
            headers={"content-type": "application/json"},
            request_duration=0.1
        )
    
    async def close(self):
        """Mock close method."""
        self.logger.debug("Mock HTTP client closed")
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


def create_http_client(config: LLMConfig, use_mock: bool = False) -> BaseHTTPClient:
    """Factory function to create appropriate HTTP client."""
    if use_mock or not HTTPX_AVAILABLE:
        if not use_mock:
            logging.warning("httpx not available, using mock HTTP client")
        return MockHTTPClient(config)
    else:
        return BaseHTTPClient(config)