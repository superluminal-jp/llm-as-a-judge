"""Test configuration management."""

import os
import tempfile
import pytest
from pathlib import Path
from src.llm_judge.infrastructure.config.config import load_config, LLMConfig


class TestLLMConfig:
    """Test LLMConfig class."""
    
    def test_missing_api_keys_raises_error(self):
        """Test that missing API keys raise validation error."""
        with pytest.raises(ValueError, match="No API keys configured"):
            LLMConfig()
    
    def test_valid_config_creation(self):
        """Test successful creation with valid parameters."""
        config = LLMConfig(openai_api_key="test_key", default_provider="openai")
        assert config.openai_api_key == "test_key"
        assert config.default_provider == "openai"
        assert config.openai_model == "gpt-5-2025-08-07"
        assert config.anthropic_model == "claude-sonnet-4-20250514"
        assert config.gpt5_reasoning_effort == "medium"
    
    def test_invalid_provider_raises_error(self):
        """Test that invalid provider raises validation error."""
        with pytest.raises(ValueError, match="Invalid default_provider"):
            LLMConfig(openai_api_key="test_key", default_provider="invalid")
    
    def test_provider_key_mismatch_raises_error(self):
        """Test that provider without corresponding key raises error."""
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY is not configured"):
            LLMConfig(anthropic_api_key=None, default_provider="anthropic")
    
    def test_invalid_numeric_values(self):
        """Test validation of numeric configuration values."""
        with pytest.raises(ValueError, match="request_timeout must be positive"):
            LLMConfig(openai_api_key="test", request_timeout=-1)
        
        with pytest.raises(ValueError, match="max_retries must be non-negative"):
            LLMConfig(openai_api_key="test", max_retries=-1)
    
    def test_invalid_log_level(self):
        """Test validation of log level."""
        with pytest.raises(ValueError, match="Invalid log_level"):
            LLMConfig(openai_api_key="test", log_level="INVALID")
    
    def test_invalid_gpt5_reasoning_effort(self):
        """Test validation of GPT-5 reasoning effort."""
        with pytest.raises(ValueError, match="Invalid gpt5_reasoning_effort"):
            LLMConfig(openai_api_key="test", gpt5_reasoning_effort="invalid")


class TestConfigLoading:
    """Test configuration loading from environment."""
    
    def _clear_env_vars(self, monkeypatch):
        """Helper to clear all config-related environment variables."""
        env_vars = [
            "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEFAULT_PROVIDER",
            "OPENAI_MODEL", "ANTHROPIC_MODEL", "GPT5_REASONING_EFFORT",
            "REQUEST_TIMEOUT", "MAX_RETRIES", "RETRY_DELAY", "LOG_LEVEL"
        ]
        for var in env_vars:
            monkeypatch.delenv(var, raising=False)
    
    def test_env_loading(self, monkeypatch, tmp_path):
        """Test loading configuration from environment variables."""
        # Clear all environment variables first
        self._clear_env_vars(monkeypatch)
        # Change to temp directory to avoid any .env files
        monkeypatch.chdir(tmp_path)
        
        monkeypatch.setenv("OPENAI_API_KEY", "test_openai_key")
        monkeypatch.setenv("DEFAULT_PROVIDER", "openai")
        monkeypatch.setenv("REQUEST_TIMEOUT", "45")
        monkeypatch.setenv("OPENAI_MODEL", "gpt-4")
        
        config = load_config()
        assert config.openai_api_key == "test_openai_key"
        assert config.default_provider == "openai"
        assert config.request_timeout == 45
        assert config.openai_model == "gpt-4"
    
    def test_dotenv_loading(self, tmp_path, monkeypatch):
        """Test loading configuration from .env file."""
        # Clear all environment variables first
        self._clear_env_vars(monkeypatch)
        
        # Create temporary .env file
        env_file = tmp_path / ".env"
        env_file.write_text(
            "OPENAI_API_KEY=test_dotenv_key\n"
            "DEFAULT_PROVIDER=openai\n"
            "REQUEST_TIMEOUT=60\n"
            "ANTHROPIC_MODEL=claude-test\n"
        )
        
        # Change to temp directory
        monkeypatch.chdir(tmp_path)
        
        config = load_config()
        assert config.openai_api_key == "test_dotenv_key"
        assert config.default_provider == "openai"
        assert config.request_timeout == 60
        assert config.anthropic_model == "claude-test"
    
    def test_missing_config_raises_error(self, monkeypatch, tmp_path):
        """Test that missing configuration raises appropriate error."""
        # Clear all environment variables
        self._clear_env_vars(monkeypatch)
        # Change to a temp directory to avoid any .env files
        monkeypatch.chdir(tmp_path)
        
        with pytest.raises(ValueError, match="Configuration validation failed"):
            load_config()
    
    def test_default_values(self, monkeypatch, tmp_path):
        """Test that default values are applied correctly."""
        # Clear all environment variables first
        self._clear_env_vars(monkeypatch)
        # Change to temp directory to avoid any .env files
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("OPENAI_API_KEY", "test_key")
        
        config = load_config()
        assert config.default_provider == "openai"
        assert config.request_timeout == 30
        assert config.max_retries == 3
        assert config.retry_delay == 1
        assert config.log_level == "INFO"
        assert config.openai_model == "gpt-5-2025-08-07"
        assert config.anthropic_model == "claude-sonnet-4-20250514"
        assert config.gpt5_reasoning_effort == "medium"