"""Anthropic API client implementation."""

import json
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

import anthropic

from ..config.config import LLMConfig
from ..resilience.retry_strategies import EnhancedRetryManager, with_enhanced_retry
from ..resilience.timeout_manager import ProviderTimeoutManager


@dataclass
class AnthropicResponse:
    """Standardized Anthropic API response."""

    content: str
    usage: Dict[str, int]
    model: str
    stop_reason: str


class AnthropicError(Exception):
    """Base exception for Anthropic API errors."""

    pass


class RateLimitError(AnthropicError):
    """Exception for rate limit errors."""

    pass


class AnthropicClient:
    """Anthropic API client with error handling and response formatting."""

    def __init__(self, config: LLMConfig):
        self.config = config
        try:
            from logging_config import get_logger

            self.logger = get_logger(__name__)
        except ImportError:
            self.logger = logging.getLogger(__name__)

        if not config.anthropic_api_key:
            raise ValueError("Anthropic API key is required but not configured")

        # Initialize official Anthropic client with provider-specific timeout
        self.client = anthropic.Anthropic(
            api_key=config.anthropic_api_key,
            timeout=config.anthropic_request_timeout,
            max_retries=config.max_retries,
        )

        # Initialize enhanced retry manager and timeout manager
        self._retry_manager = EnhancedRetryManager(config)
        self._timeout_manager = ProviderTimeoutManager("anthropic", config)

        self.logger.info(
            f"Initialized Anthropic client for model: {config.anthropic_model}"
        )

    async def create_message(
        self,
        messages: list,
        model: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        response_format: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> AnthropicResponse:
        """Create a message using the Anthropic API."""

        model = model or self.config.anthropic_model

        # Convert OpenAI-style messages to Anthropic format
        anthropic_messages = []
        system_message = None

        for message in messages:
            role = message.get("role")
            content = message.get("content", "")

            if role == "system":
                system_message = content
            elif role == "user":
                anthropic_messages.append({"role": "user", "content": content})
            elif role == "assistant":
                anthropic_messages.append({"role": "assistant", "content": content})

        # Prepare parameters for SDK call
        params = {
            "model": model,
            "max_tokens": max_tokens,  # Required parameter
            "messages": anthropic_messages,
            **kwargs,
        }

        # Add system message if present (top-level parameter)
        if system_message:
            params["system"] = system_message

        # Add response format if provided (for structured output)
        if response_format is not None:
            params["response_format"] = response_format

        # Add temperature or top_p (mutually exclusive according to docs)
        # Use provided parameters first, then fall back to config defaults
        config_temperature = self.config.anthropic_temperature
        config_top_p = self.config.anthropic_top_p

        if temperature is not None and top_p is not None:
            self.logger.warning(
                "Both temperature and top_p specified in parameters. Using temperature only."
            )
            params["temperature"] = temperature
        elif temperature is not None:
            params["temperature"] = temperature
        elif top_p is not None:
            params["top_p"] = top_p
        elif config_temperature is not None and config_top_p is not None:
            self.logger.warning(
                "Both temperature and top_p configured. Using temperature only."
            )
            params["temperature"] = config_temperature
        elif config_temperature is not None:
            params["temperature"] = config_temperature
        elif config_top_p is not None:
            params["top_p"] = config_top_p
        else:
            # Default to reasonable temperature if nothing specified
            params["temperature"] = 0.1

        async def _make_message():
            """Inner function for the actual API call that can be retried."""
            self.logger.debug(
                f"Anthropic message request: model={model}, messages={len(anthropic_messages)}"
            )

            # Use official SDK
            response = self.client.messages.create(**params)

            # Extract response data
            if not response.content:
                raise AnthropicError("No content returned in response")

            # Combine all text content blocks
            content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    content += block.text

            stop_reason = response.stop_reason or "unknown"
            usage = {
                "input_tokens": response.usage.input_tokens if response.usage else 0,
                "output_tokens": response.usage.output_tokens if response.usage else 0,
            }

            self.logger.debug(
                f"Anthropic response: {len(content)} chars, stop_reason={stop_reason}"
            )

            return AnthropicResponse(
                content=content,
                usage=usage,
                model=response.model,
                stop_reason=stop_reason,
            )

        # Execute with timeout management and enhanced retry logic
        try:
            # Set correlation ID for request tracing
            if hasattr(self.logger, "set_correlation_id"):
                correlation_id = self.logger.set_correlation_id()

            # Execute the operation with retry logic directly (timeout is handled by SDK)
            result = await self._retry_manager.execute_with_retry(
                _make_message, service_name="anthropic", operation_name="create_message"
            )

            # Log successful API call
            if hasattr(self.logger, "log_api_call"):
                self.logger.log_api_call(
                    "anthropic",
                    "create_message",
                    0,
                    True,
                    model=model,
                    message_count=len(anthropic_messages),
                )

            return result

        except anthropic.AuthenticationError as e:
            if hasattr(self.logger, "log_api_call"):
                self.logger.log_api_call(
                    "anthropic",
                    "create_message",
                    0,
                    False,
                    error_type="authentication",
                    error=str(e),
                )
            raise AnthropicError(f"Authentication failed: {e}")
        except anthropic.RateLimitError as e:
            if hasattr(self.logger, "log_api_call"):
                self.logger.log_api_call(
                    "anthropic",
                    "create_message",
                    0,
                    False,
                    error_type="rate_limit",
                    error=str(e),
                )
            raise RateLimitError(f"Rate limit exceeded: {e}")
        except anthropic.APIError as e:
            if hasattr(self.logger, "log_api_call"):
                self.logger.log_api_call(
                    "anthropic",
                    "create_message",
                    0,
                    False,
                    error_type="api_error",
                    error=str(e),
                )
            raise AnthropicError(f"Anthropic API error: {e}")
        except TimeoutError as e:
            if hasattr(self.logger, "log_api_call"):
                self.logger.log_api_call(
                    "anthropic",
                    "create_message",
                    0,
                    False,
                    error_type="timeout",
                    error=str(e),
                )
            raise AnthropicError(f"Request timed out: {e}")
        except Exception as e:
            if hasattr(self.logger, "log_api_call"):
                self.logger.log_api_call(
                    "anthropic",
                    "create_message",
                    0,
                    False,
                    error_type="unknown",
                    error=str(e),
                )
            raise AnthropicError(f"Unexpected error: {e}")

    async def generate(
        self,
        messages: list,
        model: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        response_format: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> AnthropicResponse:
        """Unified generation method - delegates to create_message."""
        return await self.create_message(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            response_format=response_format,
            **kwargs,
        )

    async def evaluate_with_anthropic(
        self,
        prompt: str,
        response_text: str,
        criteria: str = "overall quality",
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Evaluate a response using Anthropic with structured output."""

        # Define the JSON schema for structured output
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "evaluation_response",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "score": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 5,
                            "description": "Evaluation score from 1-5",
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "Detailed explanation of the evaluation",
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                            "description": "Confidence level in the evaluation",
                        },
                    },
                    "required": ["score", "reasoning", "confidence"],
                    "additionalProperties": False,
                },
            },
        }

        messages = [
            {
                "role": "system",
                "content": "You are an expert evaluator. Your task is to evaluate responses based on given criteria. You must respond with valid JSON in the exact format specified.",
            },
            {
                "role": "user",
                "content": f"""Evaluate this response on {criteria} from 1-5.

Original Question: {prompt}

Response to Evaluate: {response_text}

Provide your evaluation in JSON format with the following structure:
- score: A number between 1-5
- reasoning: A detailed explanation of your evaluation
- confidence: A number between 0.0-1.0 indicating your confidence in this evaluation

Be thorough and fair in your evaluation.""",
            },
        ]

        try:
            response = await self.create_message(
                messages=messages,
                model=model,
                max_tokens=500,
                temperature=0.1,  # Low temperature for consistent evaluations
                response_format=response_format,
            )

            # Parse JSON from response content (handle code blocks)
            try:
                content = response.content.strip()
                # Remove code block markers if present
                if content.startswith("```json"):
                    content = content[7:]  # Remove ```json
                if content.endswith("```"):
                    content = content[:-3]  # Remove ```
                content = content.strip()

                evaluation = json.loads(content)

                # Validate required fields
                required_fields = ["score", "reasoning", "confidence"]
                for field in required_fields:
                    if field not in evaluation:
                        raise ValueError(f"Missing required field: {field}")

                # Validate types and ranges
                score = evaluation["score"]
                if not isinstance(score, int) or not (1 <= score <= 5):
                    raise ValueError(
                        f"Score must be an integer between 1-5, got: {score}"
                    )

                confidence = evaluation["confidence"]
                if not isinstance(confidence, (int, float)) or not (
                    0 <= confidence <= 1
                ):
                    raise ValueError(
                        f"Confidence must be between 0-1, got: {confidence}"
                    )

                if not isinstance(evaluation["reasoning"], str):
                    raise ValueError("Reasoning must be a string")

                self.logger.debug(
                    f"Anthropic evaluation: score={score}, confidence={confidence}"
                )
                return evaluation

            except (json.JSONDecodeError, ValueError) as e:
                self.logger.warning(
                    f"Failed to parse Anthropic evaluation response: {e}"
                )
                self.logger.warning(f"Raw response: {response.content}")

                # Fallback: extract score from text if possible
                content = response.content.lower()
                fallback_score = 3

                if "excellent" in content or "outstanding" in content:
                    fallback_score = 5
                elif "good" in content or "well" in content:
                    fallback_score = 4
                elif "poor" in content or "bad" in content:
                    fallback_score = 2
                elif "terrible" in content or "awful" in content:
                    fallback_score = 1

                return {
                    "score": fallback_score,
                    "reasoning": f"Failed to parse structured response. Raw content: {response.content[:200]}...",
                    "confidence": 0.3,
                }

        except AnthropicError as e:
            self.logger.error(f"Anthropic evaluation failed: {e}")
            raise

    async def compare_with_anthropic(
        self, prompt: str, response_a: str, response_b: str, model: Optional[str] = None
    ) -> Dict[str, Any]:
        """Compare two responses using Anthropic."""

        # Define the JSON schema for structured output
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "comparison_response",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "winner": {
                            "type": "string",
                            "enum": ["A", "B", "tie"],
                            "description": "Which response is better: A, B, or tie",
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "Detailed explanation of the comparison",
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                            "description": "Confidence level in the comparison",
                        },
                    },
                    "required": ["winner", "reasoning", "confidence"],
                    "additionalProperties": False,
                },
            },
        }

        messages = [
            {
                "role": "system",
                "content": "You are an expert evaluator comparing responses. You must respond with valid JSON in the exact format specified.",
            },
            {
                "role": "user",
                "content": f"""Compare these two responses and determine which is better.

Question: {prompt}

Response A: {response_a}

Response B: {response_b}

Respond in JSON format with the following structure:
- winner: Either "A", "B", or "tie"
- reasoning: A detailed explanation of your comparison
- confidence: A number between 0.0-1.0 indicating your confidence in this comparison

Be thorough in your comparison.""",
            },
        ]

        try:
            response = await self.create_message(
                messages=messages,
                model=model,
                max_tokens=500,
                temperature=0.1,  # Low temperature for consistent comparisons
                response_format=response_format,
            )

            # Parse JSON response (handle code blocks)
            try:
                content = response.content.strip()
                # Remove code block markers if present
                if content.startswith("```json"):
                    content = content[7:]  # Remove ```json
                if content.endswith("```"):
                    content = content[:-3]  # Remove ```
                content = content.strip()

                comparison = json.loads(content)

                # Validate required fields
                required_fields = ["winner", "reasoning", "confidence"]
                for field in required_fields:
                    if field not in comparison:
                        raise ValueError(f"Missing required field: {field}")

                # Validate winner value
                winner = comparison["winner"]
                if winner not in ["A", "B", "tie"]:
                    raise ValueError(
                        f"Winner must be 'A', 'B', or 'tie', got: {winner}"
                    )

                # Validate confidence
                confidence = comparison["confidence"]
                if not isinstance(confidence, (int, float)) or not (
                    0 <= confidence <= 1
                ):
                    raise ValueError(
                        f"Confidence must be between 0-1, got: {confidence}"
                    )

                if not isinstance(comparison["reasoning"], str):
                    raise ValueError("Reasoning must be a string")

                self.logger.debug(
                    f"Anthropic comparison: winner={winner}, confidence={confidence}"
                )
                return comparison

            except (json.JSONDecodeError, ValueError) as e:
                self.logger.warning(
                    f"Failed to parse Anthropic comparison response: {e}"
                )
                self.logger.warning(f"Raw response: {response.content}")

                # Fallback comparison
                return {
                    "winner": "tie",
                    "reasoning": f"Failed to parse structured response. Raw content: {response.content[:200]}...",
                    "confidence": 0.3,
                }

        except AnthropicError as e:
            self.logger.error(f"Anthropic comparison failed: {e}")
            raise

    async def close(self):
        """Close the Anthropic client and clean up timeout management."""
        # Clean up timeout manager
        if hasattr(self, "_timeout_manager"):
            await self._timeout_manager.close()

        # The official SDK handles cleanup automatically
