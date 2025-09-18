"""OpenAI API client implementation."""

import json
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

from openai import OpenAI
import openai

from ..config.config import LLMConfig
from ..resilience.retry_strategies import EnhancedRetryManager, with_enhanced_retry
from ..resilience.timeout_manager import ProviderTimeoutManager


@dataclass
class OpenAIResponse:
    """Standardized OpenAI API response."""

    content: str
    usage: Dict[str, int]
    model: str
    stop_reason: str  # Standardized to match other providers


class OpenAIError(Exception):
    """Base exception for OpenAI API errors."""

    pass


class RateLimitError(OpenAIError):
    """Exception for rate limit errors."""

    pass


class OpenAIClient:
    """OpenAI API client with error handling and response formatting."""

    def __init__(self, config: LLMConfig):
        self.config = config
        try:
            from logging_config import get_logger

            self.logger = get_logger(__name__)
        except ImportError:
            self.logger = logging.getLogger(__name__)

        if not config.openai_api_key:
            raise ValueError("OpenAI API key is required but not configured")

        # Initialize official OpenAI client with provider-specific timeout
        self.client = OpenAI(
            api_key=config.openai_api_key,
            timeout=config.openai_request_timeout,
            max_retries=config.max_retries,
        )

        # Initialize enhanced retry manager and timeout manager
        self._retry_manager = EnhancedRetryManager(config)
        self._timeout_manager = ProviderTimeoutManager("openai", config)

        self.logger.info(f"Initialized OpenAI client for model: {config.openai_model}")

    async def chat_completion(
        self,
        messages: list,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        reasoning_effort: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> OpenAIResponse:
        """Create a chat completion using the OpenAI API."""

        async def _make_completion():
            """Inner function for the actual API call that can be retried."""
            model_name = model or self.config.openai_model

            # Prepare parameters for SDK call
            params = {"model": model_name, "messages": messages, **kwargs}

            # Add response format if provided (for structured output)
            if response_format is not None:
                params["response_format"] = response_format

            # Handle model-specific parameters
            is_gpt5 = "gpt-5" in model_name.lower()

            if is_gpt5:
                # GPT-5 uses reasoning_effort instead of temperature
                if reasoning_effort is not None:
                    if reasoning_effort in ["low", "medium", "high"]:
                        params["reasoning_effort"] = reasoning_effort
                    else:
                        self.logger.warning(
                            f"Invalid reasoning_effort '{reasoning_effort}' for GPT-5. Using default."
                        )
                # GPT-5 doesn't support temperature parameter at all
            else:
                # Older models support temperature
                params["temperature"] = temperature

            if max_tokens is not None:
                # GPT-5 and GPT-4o use max_completion_tokens
                if is_gpt5 or "gpt-4o" in model_name.lower():
                    params["max_completion_tokens"] = max_tokens
                else:
                    params["max_tokens"] = max_tokens

            self.logger.debug(
                f"OpenAI chat completion request: model={model_name}, messages={len(messages)}"
            )

            # Use official SDK
            response = self.client.chat.completions.create(**params)

            # Extract response data
            if not response.choices:
                raise OpenAIError("No choices returned in response")

            choice = response.choices[0]
            content = choice.message.content or ""
            finish_reason = choice.finish_reason or "unknown"

            usage = {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": (
                    response.usage.completion_tokens if response.usage else 0
                ),
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            }

            self.logger.debug(
                f"OpenAI response: {len(content)} chars, finish_reason={finish_reason}"
            )

            return OpenAIResponse(
                content=content,
                usage=usage,
                model=response.model,
                stop_reason=finish_reason,
            )

        # Execute with timeout management and enhanced retry logic
        try:
            # Set correlation ID for request tracing
            if hasattr(self.logger, "set_correlation_id"):
                correlation_id = self.logger.set_correlation_id()

            # Execute the operation with retry logic directly (timeout is handled by SDK)
            result = await self._retry_manager.execute_with_retry(
                _make_completion,
                service_name="openai",
                operation_name="chat_completion",
            )

            # Log successful API call
            if hasattr(self.logger, "log_api_call"):
                self.logger.log_api_call(
                    "openai",
                    "chat_completion",
                    0,
                    True,
                    model=model or self.config.openai_model,
                    message_count=len(messages),
                )

            return result

        except openai.AuthenticationError as e:
            if hasattr(self.logger, "log_api_call"):
                self.logger.log_api_call(
                    "openai",
                    "chat_completion",
                    0,
                    False,
                    error_type="authentication",
                    error=str(e),
                )
            raise OpenAIError(f"Authentication failed: {e}")
        except openai.RateLimitError as e:
            if hasattr(self.logger, "log_api_call"):
                self.logger.log_api_call(
                    "openai",
                    "chat_completion",
                    0,
                    False,
                    error_type="rate_limit",
                    error=str(e),
                )
            raise RateLimitError(f"Rate limit exceeded: {e}")
        except openai.APIError as e:
            if hasattr(self.logger, "log_api_call"):
                self.logger.log_api_call(
                    "openai",
                    "chat_completion",
                    0,
                    False,
                    error_type="api_error",
                    error=str(e),
                )
            raise OpenAIError(f"OpenAI API error: {e}")
        except TimeoutError as e:
            if hasattr(self.logger, "log_api_call"):
                self.logger.log_api_call(
                    "openai",
                    "chat_completion",
                    0,
                    False,
                    error_type="timeout",
                    error=str(e),
                )
            raise OpenAIError(f"Request timed out: {e}")
        except Exception as e:
            if hasattr(self.logger, "log_api_call"):
                self.logger.log_api_call(
                    "openai",
                    "chat_completion",
                    0,
                    False,
                    error_type="unknown",
                    error=str(e),
                )
            raise OpenAIError(f"Unexpected error: {e}")

    async def generate(
        self,
        messages: list,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.1,
        reasoning_effort: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> OpenAIResponse:
        """Unified generation method - delegates to chat_completion."""
        return await self.chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            reasoning_effort=reasoning_effort,
            response_format=response_format,
            **kwargs,
        )

    async def evaluate_with_openai(
        self,
        prompt: str,
        response_text: str,
        criteria: str = "overall quality",
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Evaluate a response using OpenAI with structured output."""

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
            # Use appropriate parameters based on model type
            if model and "gpt-5" in model.lower():
                response = await self.chat_completion(
                    messages=messages,
                    model=model,
                    reasoning_effort=self.config.gpt5_reasoning_effort,
                    max_tokens=500,
                    response_format=response_format,
                )
            else:
                response = await self.chat_completion(
                    messages=messages,
                    model=model,
                    temperature=0.1,
                    max_tokens=500,
                    response_format=response_format,
                )

            # Parse JSON from response content (structured output should be valid JSON)
            try:
                evaluation = json.loads(response.content.strip())

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
                    f"OpenAI evaluation: score={score}, confidence={confidence}"
                )
                return evaluation

            except (json.JSONDecodeError, ValueError) as e:
                self.logger.warning(f"Failed to parse OpenAI evaluation response: {e}")
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

        except OpenAIError as e:
            self.logger.error(f"OpenAI evaluation failed: {e}")
            raise

    async def compare_with_openai(
        self, prompt: str, response_a: str, response_b: str, model: Optional[str] = None
    ) -> Dict[str, Any]:
        """Compare two responses using OpenAI."""

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
            # Use appropriate parameters based on model type
            if model and "gpt-5" in model.lower():
                response = await self.chat_completion(
                    messages=messages,
                    model=model,
                    reasoning_effort=self.config.gpt5_reasoning_effort,
                    max_tokens=500,
                    response_format=response_format,
                )
            else:
                response = await self.chat_completion(
                    messages=messages,
                    model=model,
                    temperature=0.1,
                    max_tokens=500,
                    response_format=response_format,
                )

            # Parse JSON response (structured output should be valid JSON)
            try:
                comparison = json.loads(response.content.strip())

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
                    f"OpenAI comparison: winner={winner}, confidence={confidence}"
                )
                return comparison

            except (json.JSONDecodeError, ValueError) as e:
                self.logger.warning(f"Failed to parse OpenAI comparison response: {e}")
                self.logger.warning(f"Raw response: {response.content}")

                # Fallback comparison
                return {
                    "winner": "tie",
                    "reasoning": f"Failed to parse structured response. Raw content: {response.content[:200]}...",
                    "confidence": 0.3,
                }

        except OpenAIError as e:
            self.logger.error(f"OpenAI comparison failed: {e}")
            raise

    async def close(self):
        """Close the OpenAI client and clean up timeout management."""
        # Clean up timeout manager
        if hasattr(self, "_timeout_manager"):
            await self._timeout_manager.close()

        # The official SDK handles cleanup automatically
