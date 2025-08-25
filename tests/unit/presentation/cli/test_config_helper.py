"""Unit tests for CLI configuration helper."""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock

from src.llm_judge.presentation.cli.config_helper import CLIConfigManager
from src.llm_judge.infrastructure.config.config import LLMConfig


class TestCLIConfigManager:
    """Test CLI configuration management functionality."""

    def test_load_from_file_success(self):
        """Test successful configuration loading from file."""
        config_data = {
            "openai_api_key": "sk-test123",
            "anthropic_api_key": "sk-ant-test123",
            "default_provider": "openai",
            "request_timeout": 45
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_path = Path(f.name)
        
        try:
            config = CLIConfigManager.load_from_file(config_path)
            assert isinstance(config, LLMConfig)
            assert config.openai_api_key == "sk-test123"
            assert config.anthropic_api_key == "sk-ant-test123"
            assert config.default_provider == "openai"
            assert config.request_timeout == 45
        finally:
            config_path.unlink()

    def test_load_from_file_not_found(self):
        """Test error handling when configuration file doesn't exist."""
        non_existent_path = Path("/non/existent/config.json")
        
        with pytest.raises(FileNotFoundError, match="Configuration file not found"):
            CLIConfigManager.load_from_file(non_existent_path)

    def test_load_from_file_invalid_json(self):
        """Test error handling for invalid JSON content."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json content")
            config_path = Path(f.name)
        
        try:
            with pytest.raises(ValueError, match="Invalid JSON in configuration file"):
                CLIConfigManager.load_from_file(config_path)
        finally:
            config_path.unlink()

    def test_load_from_file_invalid_config_data(self):
        """Test error handling for invalid configuration data."""
        config_data = {
            "invalid_field": "invalid_value",
            "request_timeout": "not_a_number"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_path = Path(f.name)
        
        try:
            with pytest.raises(ValueError, match="Error loading configuration"):
                CLIConfigManager.load_from_file(config_path)
        finally:
            config_path.unlink()

    def test_create_sample_config(self):
        """Test sample configuration creation."""
        sample_config = CLIConfigManager.create_sample_config()
        
        assert isinstance(sample_config, dict)
        assert "openai_api_key" in sample_config
        assert "anthropic_api_key" in sample_config
        assert "default_provider" in sample_config
        assert "request_timeout" in sample_config
        assert "max_retries" in sample_config
        assert "log_level" in sample_config
        
        # Check default values
        assert sample_config["default_provider"] == "openai"
        assert sample_config["request_timeout"] == 30
        assert sample_config["max_retries"] == 3
        assert sample_config["log_level"] == "INFO"

    def test_save_sample_config(self):
        """Test saving sample configuration to file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_path = Path(f.name)
        
        try:
            # File should be empty initially
            config_path.unlink()
            
            CLIConfigManager.save_sample_config(config_path)
            
            # Verify file was created and contains valid JSON
            assert config_path.exists()
            
            with open(config_path) as f:
                loaded_data = json.load(f)
            
            expected_sample = CLIConfigManager.create_sample_config()
            assert loaded_data == expected_sample
            
        finally:
            if config_path.exists():
                config_path.unlink()

    def test_validate_config_valid_openai(self):
        """Test configuration validation with valid OpenAI setup."""
        config = Mock(spec=LLMConfig)
        config.openai_api_key = "sk-test123"
        config.anthropic_api_key = None
        config.default_provider = "openai"
        
        # Should not raise any exception
        CLIConfigManager.validate_config(config)

    def test_validate_config_valid_anthropic(self):
        """Test configuration validation with valid Anthropic setup."""
        config = Mock(spec=LLMConfig)
        config.openai_api_key = None
        config.anthropic_api_key = "sk-ant-test123"
        config.default_provider = "anthropic"
        
        # Should not raise any exception
        CLIConfigManager.validate_config(config)

    def test_validate_config_no_api_keys(self):
        """Test configuration validation with no API keys."""
        config = Mock(spec=LLMConfig)
        config.openai_api_key = None
        config.anthropic_api_key = None
        config.default_provider = "openai"
        
        with pytest.raises(ValueError, match="At least one API key must be provided"):
            CLIConfigManager.validate_config(config)

    def test_validate_config_openai_default_no_key(self):
        """Test validation error when OpenAI is default but no key provided."""
        config = Mock(spec=LLMConfig)
        config.openai_api_key = None
        config.anthropic_api_key = "sk-ant-test123"
        config.default_provider = "openai"
        
        with pytest.raises(ValueError, match="OpenAI API key required"):
            CLIConfigManager.validate_config(config)

    def test_validate_config_anthropic_default_no_key(self):
        """Test validation error when Anthropic is default but no key provided."""
        config = Mock(spec=LLMConfig)
        config.openai_api_key = "sk-test123"
        config.anthropic_api_key = None
        config.default_provider = "anthropic"
        
        with pytest.raises(ValueError, match="Anthropic API key required"):
            CLIConfigManager.validate_config(config)

    def test_get_available_providers_both(self):
        """Test getting available providers when both keys are present."""
        config = Mock(spec=LLMConfig)
        config.openai_api_key = "sk-test123"
        config.anthropic_api_key = "sk-ant-test123"
        
        providers = CLIConfigManager.get_available_providers(config)
        assert "openai" in providers
        assert "anthropic" in providers
        assert len(providers) == 2

    def test_get_available_providers_openai_only(self):
        """Test getting available providers when only OpenAI key is present."""
        config = Mock(spec=LLMConfig)
        config.openai_api_key = "sk-test123"
        config.anthropic_api_key = None
        
        providers = CLIConfigManager.get_available_providers(config)
        assert providers == ["openai"]

    def test_get_available_providers_anthropic_only(self):
        """Test getting available providers when only Anthropic key is present."""
        config = Mock(spec=LLMConfig)
        config.openai_api_key = None
        config.anthropic_api_key = "sk-ant-test123"
        
        providers = CLIConfigManager.get_available_providers(config)
        assert providers == ["anthropic"]

    def test_get_available_providers_none(self):
        """Test getting available providers when no keys are present."""
        config = Mock(spec=LLMConfig)
        config.openai_api_key = None
        config.anthropic_api_key = None
        
        providers = CLIConfigManager.get_available_providers(config)
        assert providers == []

    def test_suggest_provider_use_default(self):
        """Test provider suggestion when default is available."""
        config = Mock(spec=LLMConfig)
        config.openai_api_key = "sk-test123"
        config.anthropic_api_key = "sk-ant-test123"
        config.default_provider = "anthropic"
        
        suggested = CLIConfigManager.suggest_provider(config)
        assert suggested == "anthropic"

    def test_suggest_provider_fallback_to_available(self):
        """Test provider suggestion fallback when default is not available."""
        config = Mock(spec=LLMConfig)
        config.openai_api_key = "sk-test123"
        config.anthropic_api_key = None
        config.default_provider = "anthropic"  # Not available
        
        suggested = CLIConfigManager.suggest_provider(config)
        assert suggested == "openai"

    def test_suggest_provider_no_keys_available(self):
        """Test provider suggestion error when no keys are available."""
        config = Mock(spec=LLMConfig)
        config.openai_api_key = None
        config.anthropic_api_key = None
        config.default_provider = "openai"
        
        with pytest.raises(ValueError, match="No API keys available"):
            CLIConfigManager.suggest_provider(config)