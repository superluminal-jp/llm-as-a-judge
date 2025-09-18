"""AWS Bedrock API client implementation."""

import json
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError, BotoCoreError

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

from ..config.config import LLMConfig
from ..resilience.retry_strategies import EnhancedRetryManager, with_enhanced_retry
from ..resilience.timeout_manager import ProviderTimeoutManager


@dataclass
class BedrockResponse:
    """Standardized Bedrock API response."""

    content: str
    usage: Dict[str, int]
    model: str
    stop_reason: str


class BedrockError(Exception):
    """Base exception for Bedrock API errors."""

    pass


class RateLimitError(BedrockError):
    """Exception for rate limit errors."""

    pass


class BedrockClient:
    """AWS Bedrock API client with error handling and response formatting."""

    def __init__(self, config: LLMConfig):
        if not BOTO3_AVAILABLE:
            raise ImportError(
                "boto3 is required for Bedrock support. Install it with: pip install boto3"
            )

        self.config = config
        try:
            from logging_config import get_logger

            self.logger = get_logger(__name__)
        except ImportError:
            self.logger = logging.getLogger(__name__)

        # Validate required AWS configuration
        if not config.aws_access_key_id or not config.aws_secret_access_key:
            raise ValueError("AWS credentials are required but not configured")

        # Initialize Bedrock client with provider-specific timeout and configuration
        bedrock_config = Config(
            read_timeout=config.bedrock_request_timeout,
            connect_timeout=config.bedrock_connect_timeout,
            retries={"max_attempts": config.max_retries, "mode": "adaptive"},
            region_name=config.aws_region,
        )

        session = boto3.Session(
            aws_access_key_id=config.aws_access_key_id,
            aws_secret_access_key=config.aws_secret_access_key,
            aws_session_token=config.aws_session_token,  # Optional for temporary credentials
            region_name=config.aws_region,
        )

        self.client = session.client("bedrock-runtime", config=bedrock_config)

        # Initialize enhanced retry manager and timeout manager
        self._retry_manager = EnhancedRetryManager(config)
        self._timeout_manager = ProviderTimeoutManager("bedrock", config)

        self.logger.info(
            f"Initialized Bedrock client for model: {config.bedrock_model}"
        )

    async def invoke_model(
        self,
        messages: list,
        model: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        response_format: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> BedrockResponse:
        """Invoke a model using the Bedrock API."""

        model_id = model or self.config.bedrock_model

        # Convert OpenAI-style messages to model-specific format
        if "anthropic" in model_id.lower():
            body = self._prepare_anthropic_body(
                messages, max_tokens, temperature, top_p, response_format, **kwargs
            )
        elif "amazon.nova" in model_id.lower():
            body = self._prepare_nova_body(
                messages, max_tokens, temperature, top_p, response_format, **kwargs
            )
        else:
            # Default to Anthropic format for unknown models
            body = self._prepare_anthropic_body(
                messages, max_tokens, temperature, top_p, response_format, **kwargs
            )

        async def _make_request():
            """Inner function for the actual API call that can be retried."""
            self.logger.debug(
                f"Bedrock invoke request: model={model_id}, messages={len(messages)}"
            )

            try:
                response = self.client.invoke_model(
                    modelId=model_id,
                    body=json.dumps(body),
                    contentType="application/json",
                )

                # Parse response based on model provider
                response_body = json.loads(response["body"].read())

                if "anthropic" in model_id.lower():
                    return self._parse_anthropic_response(response_body, model_id)
                elif "amazon.nova" in model_id.lower():
                    return self._parse_nova_response(response_body, model_id)
                else:
                    # Default to Anthropic format
                    return self._parse_anthropic_response(response_body, model_id)

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                error_message = e.response.get("Error", {}).get("Message", str(e))

                if error_code == "ThrottlingException":
                    raise RateLimitError(f"Rate limit exceeded: {error_message}")
                elif error_code in ["ValidationException", "AccessDeniedException"]:
                    raise BedrockError(f"Client error ({error_code}): {error_message}")
                else:
                    raise BedrockError(
                        f"Bedrock API error ({error_code}): {error_message}"
                    )

            except BotoCoreError as e:
                raise BedrockError(f"AWS SDK error: {e}")

        # Execute with timeout management and enhanced retry logic
        try:
            # Set correlation ID for request tracing
            if hasattr(self.logger, "set_correlation_id"):
                correlation_id = self.logger.set_correlation_id()

            # Execute the operation with retry logic
            result = await self._retry_manager.execute_with_retry(
                _make_request, service_name="bedrock", operation_name="invoke_model"
            )

            # Log successful API call
            if hasattr(self.logger, "log_api_call"):
                self.logger.log_api_call(
                    "bedrock",
                    "invoke_model",
                    0,
                    True,
                    model=model_id,
                    message_count=len(messages),
                )

            return result

        except RateLimitError as e:
            if hasattr(self.logger, "log_api_call"):
                self.logger.log_api_call(
                    "bedrock",
                    "invoke_model",
                    0,
                    False,
                    error_type="rate_limit",
                    error=str(e),
                )
            raise
        except BedrockError as e:
            if hasattr(self.logger, "log_api_call"):
                self.logger.log_api_call(
                    "bedrock",
                    "invoke_model",
                    0,
                    False,
                    error_type="api_error",
                    error=str(e),
                )
            raise
        except TimeoutError as e:
            if hasattr(self.logger, "log_api_call"):
                self.logger.log_api_call(
                    "bedrock",
                    "invoke_model",
                    0,
                    False,
                    error_type="timeout",
                    error=str(e),
                )
            raise BedrockError(f"Request timed out: {e}")
        except Exception as e:
            if hasattr(self.logger, "log_api_call"):
                self.logger.log_api_call(
                    "bedrock",
                    "invoke_model",
                    0,
                    False,
                    error_type="unknown",
                    error=str(e),
                )
            raise BedrockError(f"Unexpected error: {e}")

    async def generate(
        self,
        messages: list,
        model: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        response_format: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> BedrockResponse:
        """Unified generation method - delegates to invoke_model."""
        return await self.invoke_model(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            response_format=response_format,
            **kwargs,
        )

    def _prepare_anthropic_body(
        self,
        messages: list,
        max_tokens: int,
        temperature: Optional[float],
        top_p: Optional[float],
        response_format: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Prepare request body for Anthropic models on Bedrock."""
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

        body = {"max_tokens": max_tokens, "messages": anthropic_messages, **kwargs}

        # Add system message if present
        if system_message:
            body["system"] = system_message

        # Add temperature or top_p (mutually exclusive)
        if temperature is not None and top_p is not None:
            self.logger.warning(
                "Both temperature and top_p specified. Using temperature only."
            )
            body["temperature"] = temperature
        elif temperature is not None:
            body["temperature"] = temperature
        elif top_p is not None:
            body["top_p"] = top_p
        else:
            # Use config defaults
            if (
                hasattr(self.config, "bedrock_temperature")
                and self.config.bedrock_temperature is not None
            ):
                body["temperature"] = self.config.bedrock_temperature
            else:
                body["temperature"] = 0.1  # Default

        # Anthropic-specific parameters
        body["anthropic_version"] = "bedrock-2023-05-31"

        # Add response format if provided (for structured output)
        if response_format is not None:
            body["response_format"] = response_format

        return body

    def _prepare_nova_body(
        self,
        messages: list,
        max_tokens: int,
        temperature: Optional[float],
        top_p: Optional[float],
        response_format: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Prepare request body for Amazon Nova models."""
        # Convert to Nova format
        nova_messages = []
        system_message = None

        for message in messages:
            role = message.get("role")
            content = message.get("content", "")

            if role == "system":
                system_message = content
            elif role in ["user", "assistant"]:
                nova_messages.append({"role": role, "content": [{"text": content}]})

        body = {"messages": nova_messages, **kwargs}

        # Add system message if present
        if system_message:
            body["system"] = [{"text": system_message}]

        # Add inference parameters (including maxTokens)
        inference_config = {
            "maxTokens": max_tokens  # Nova uses maxTokens in inferenceConfig
        }

        if temperature is not None:
            inference_config["temperature"] = temperature
        elif top_p is not None:
            inference_config["topP"] = top_p
        elif (
            hasattr(self.config, "bedrock_temperature")
            and self.config.bedrock_temperature is not None
        ):
            inference_config["temperature"] = self.config.bedrock_temperature
        else:
            inference_config["temperature"] = 0.1

        body["inferenceConfig"] = inference_config

        # Add response format if provided (for structured output)
        if response_format is not None:
            body["responseFormat"] = response_format

        return body

    def _parse_anthropic_response(
        self, response_body: Dict, model_id: str
    ) -> BedrockResponse:
        """Parse response from Anthropic models on Bedrock."""
        if not response_body.get("content"):
            raise BedrockError("No content returned in response")

        # Combine all text content blocks
        content = ""
        for block in response_body["content"]:
            if "text" in block:
                content += block["text"]

        stop_reason = response_body.get("stop_reason", "unknown")
        usage = {
            "input_tokens": response_body.get("usage", {}).get("input_tokens", 0),
            "output_tokens": response_body.get("usage", {}).get("output_tokens", 0),
        }

        self.logger.debug(
            f"Bedrock Anthropic response: {len(content)} chars, stop_reason={stop_reason}"
        )

        return BedrockResponse(
            content=content, usage=usage, model=model_id, stop_reason=stop_reason
        )

    def _parse_nova_response(
        self, response_body: Dict, model_id: str
    ) -> BedrockResponse:
        """Parse response from Amazon Nova models."""
        if not response_body.get("output", {}).get("message", {}).get("content"):
            raise BedrockError("No content returned in response")

        # Extract text from Nova response format
        content = ""
        message_content = response_body["output"]["message"]["content"]
        for block in message_content:
            if "text" in block:
                content += block["text"]

        stop_reason = response_body.get("stopReason", "unknown")
        usage = {
            "input_tokens": response_body.get("usage", {}).get("inputTokens", 0),
            "output_tokens": response_body.get("usage", {}).get("outputTokens", 0),
        }

        self.logger.debug(
            f"Bedrock Nova response: {len(content)} chars, stop_reason={stop_reason}"
        )

        return BedrockResponse(
            content=content, usage=usage, model=model_id, stop_reason=stop_reason
        )

    async def evaluate_with_bedrock(
        self,
        prompt: str,
        response_text: str,
        criteria: str = "overall quality",
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Evaluate a response using Bedrock with structured output."""

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
            response = await self.invoke_model(
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
                if not isinstance(score, (int, float)) or not (1 <= score <= 5):
                    raise ValueError(
                        f"Score must be a number between 1-5, got: {score}"
                    )
                # Convert to integer
                score = int(round(float(score)))

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
                    f"Bedrock evaluation: score={score}, confidence={confidence}"
                )
                # Return evaluation with integer score
                evaluation["score"] = score
                return evaluation

            except (json.JSONDecodeError, ValueError) as e:
                self.logger.warning(f"Failed to parse Bedrock evaluation response: {e}")
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

        except BedrockError as e:
            self.logger.error(f"Bedrock evaluation failed: {e}")
            raise

    async def compare_with_bedrock(
        self, prompt: str, response_a: str, response_b: str, model: Optional[str] = None
    ) -> Dict[str, Any]:
        """Compare two responses using Bedrock."""

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
            response = await self.invoke_model(
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
                    f"Bedrock comparison: winner={winner}, confidence={confidence}"
                )
                return comparison

            except (json.JSONDecodeError, ValueError) as e:
                self.logger.warning(f"Failed to parse Bedrock comparison response: {e}")
                self.logger.warning(f"Raw response: {response.content}")

                # Fallback comparison
                return {
                    "winner": "tie",
                    "reasoning": f"Failed to parse structured response. Raw content: {response.content[:200]}...",
                    "confidence": 0.3,
                }

        except BedrockError as e:
            self.logger.error(f"Bedrock comparison failed: {e}")
            raise

    async def close(self):
        """Close the Bedrock client and clean up timeout management."""
        # Clean up timeout manager
        if hasattr(self, "_timeout_manager"):
            await self._timeout_manager.close()

        # No explicit cleanup needed for boto3 client
