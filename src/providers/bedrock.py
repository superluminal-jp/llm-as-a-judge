"""Synchronous Amazon Bedrock provider for LLM-as-a-Judge.

Uses the Bedrock Runtime ``converse`` API via boto3. Authentication is provided
by the Lambda execution role — no API key is required. The boto3 client is
constructed once per Lambda container lifetime and reused across invocations.

The ``converse`` API provides a provider-agnostic message interface compatible
with all Bedrock foundation models, including Amazon Nova and Anthropic Claude.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import boto3
import botocore.exceptions
from aws_lambda_powertools import Logger

if TYPE_CHECKING:
    from src.config import Config

logger = Logger(service="llm-judge")


class BedrockProvider:
    """Synchronous Bedrock Runtime client using the Converse API.

    Attributes:
        _client: boto3 ``bedrock-runtime`` client, initialised once at
                 construction time and reused for all calls.
    """

    def __init__(self, config: "Config") -> None:
        """Initialise the Bedrock Runtime client.

        Args:
            config: Application configuration (used for region/timeout
                    context; Bedrock uses IAM auth from the execution role).
        """
        # Cold-start: Bedrock client initialized once per Lambda container.
        # IAM credentials are obtained from the Lambda execution role via the
        # instance metadata service, which is also cached by botocore.
        self._client = boto3.client("bedrock-runtime")
        logger.debug("BedrockProvider initialised")

    def complete(
        self,
        messages: list[dict],
        model: str,
        timeout: int,
    ) -> str:
        """Send messages to a Bedrock foundation model and return the text response.

        Converts the standard ``{"role", "content"}`` message format to the
        Bedrock Converse API schema and extracts the text from the response.

        Args:
            messages: Conversation history as a list of
                      ``{"role": str, "content": str}`` dicts.
            model:    Bedrock model ID (e.g. ``"amazon.nova-premier-v1:0"``).
            timeout:  Unused — Bedrock timeout is configured at the botocore
                      session level. Accepted for interface compatibility.

        Returns:
            Raw text content from the first content block of the response.

        Raises:
            ProviderError: If the Bedrock API call fails (throttling, model
                not found, permission denied, etc.).
        """
        from src.handler import ProviderError

        # Convert to Bedrock Converse API message format.
        bedrock_messages = [
            {"role": msg["role"], "content": [{"text": msg["content"]}]}
            for msg in messages
        ]

        try:
            response = self._client.converse(
                modelId=model,
                messages=bedrock_messages,
            )
            text: str = response["output"]["message"]["content"][0]["text"]
            logger.debug(
                "Bedrock converse call succeeded",
                extra={"model": model, "response_length": len(text)},
            )
            return text

        except botocore.exceptions.ClientError as exc:
            error_code = exc.response["Error"]["Code"]
            error_message = exc.response["Error"]["Message"]
            logger.error(
                "Bedrock API error",
                extra={"model": model, "error_code": error_code},
                exc_info=True,
            )
            raise ProviderError(
                f"Bedrock API error [{error_code}]: {error_message}"
            ) from exc
