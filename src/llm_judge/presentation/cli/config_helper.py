"""
Configuration helper for CLI operations.

Provides utilities for loading and validating CLI configurations.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

from ...infrastructure.config.config import LLMConfig


class CLIConfigManager:
    """Manages CLI configuration loading and validation."""
    
    @staticmethod
    def load_from_file(config_path: Path) -> LLMConfig:
        """Load configuration from a JSON file."""
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        try:
            with open(config_path) as f:
                config_data = json.load(f)
            
            return LLMConfig(**config_data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file: {e}")
        except Exception as e:
            raise ValueError(f"Error loading configuration: {e}")
    
    @staticmethod
    def create_sample_config() -> Dict[str, Any]:
        """Create a sample configuration dictionary."""
        return {
            "openai_api_key": "sk-your-openai-key-here",
            "anthropic_api_key": "sk-ant-your-anthropic-key-here",
            "default_provider": "openai",
            "openai_model": "gpt-5-2025-08-07",
            "anthropic_model": "claude-sonnet-4-20250514",
            "request_timeout": 30,
            "max_retries": 3,
            "log_level": "INFO"
        }
    
    @staticmethod
    def save_sample_config(output_path: Path) -> None:
        """Save a sample configuration file."""
        config_data = CLIConfigManager.create_sample_config()
        
        with open(output_path, 'w') as f:
            json.dump(config_data, f, indent=2)
    
    @staticmethod
    def validate_config(config: LLMConfig) -> None:
        """Validate configuration for CLI usage."""
        if not config.openai_api_key and not config.anthropic_api_key:
            raise ValueError(
                "At least one API key must be provided. Set OPENAI_API_KEY or ANTHROPIC_API_KEY "
                "environment variables, or provide them in configuration file."
            )
        
        if config.default_provider == "openai" and not config.openai_api_key:
            raise ValueError("OpenAI API key required when using OpenAI as default provider")
        
        if config.default_provider == "anthropic" and not config.anthropic_api_key:
            raise ValueError("Anthropic API key required when using Anthropic as default provider")
    
    @staticmethod
    def get_available_providers(config: LLMConfig) -> list[str]:
        """Get list of available providers based on configuration."""
        providers = []
        
        if config.openai_api_key:
            providers.append("openai")
        
        if config.anthropic_api_key:
            providers.append("anthropic")
        
        return providers
    
    @staticmethod
    def suggest_provider(config: LLMConfig) -> str:
        """Suggest the best provider to use based on configuration."""
        available = CLIConfigManager.get_available_providers(config)
        
        if not available:
            raise ValueError("No API keys available. Please configure at least one provider.")
        
        # Use configured default if available
        if config.default_provider in available:
            return config.default_provider
        
        # Otherwise use the first available
        return available[0]