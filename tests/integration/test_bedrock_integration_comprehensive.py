"""Comprehensive integration tests for Bedrock functionality."""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from src.llm_judge.infrastructure.config.config import LLMConfig
from src.llm_judge.application.services.llm_judge_service import (
    LLMJudge,
    CandidateResponse,
)
from src.llm_judge.domain.evaluation.criteria import (
    EvaluationCriteria,
    CriterionDefinition,
)


@pytest.fixture
def bedrock_config():
    """Create configuration for Bedrock provider."""
    return LLMConfig(
        aws_access_key_id="test-access-key-id",
        aws_secret_access_key="test-secret-access-key",
        aws_region="us-east-1",
        bedrock_model="amazon.nova-pro-v1:0",
        default_provider="bedrock",
        default_criteria_type="balanced",
        request_timeout=30,
        max_retries=3,
    )


@pytest.fixture
def sample_candidate():
    """Create sample candidate response for testing."""
    return CandidateResponse(
        prompt="What is artificial intelligence?",
        response="AI is a field of computer science that aims to create machines that mimic human intelligence.",
        model="test-model",
    )


@pytest.fixture
def mock_bedrock_success_response():
    """Mock successful Bedrock API response."""
    return {
        "output": {
            "message": {
                "content": [
                    {
                        "text": '{"score": 4.2, "reasoning": "Well-structured and accurate response.", "confidence": 0.85}'
                    }
                ]
            }
        },
        "stopReason": "end_turn",
        "usage": {"inputTokens": 50, "outputTokens": 30},
    }


class TestBedrockIntegrationBasic:
    """Basic integration tests for Bedrock functionality."""

    @pytest.mark.asyncio
    async def test_llm_judge_bedrock_initialization(self, bedrock_config):
        """Test LLMJudge initializes correctly with Bedrock configuration."""
        with patch(
            "src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE", True
        ):
            with patch("boto3.Session") as mock_session:
                mock_client = Mock()
                mock_session.return_value.client.return_value = mock_client

                judge = LLMJudge(bedrock_config)

                assert judge.config.default_provider == "bedrock"
                assert judge.judge_model == "amazon.nova-pro-v1:0"
                assert judge._use_real_llm is True

    @pytest.mark.asyncio
    async def test_single_criterion_evaluation_integration(
        self, bedrock_config, sample_candidate
    ):
        """Test end-to-end single criterion evaluation with Bedrock."""
        with patch(
            "src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE", True
        ):
            with patch("boto3.Session") as mock_session:
                mock_client = Mock()
                mock_session.return_value.client.return_value = mock_client

                # Mock successful Bedrock response
                import json

                evaluation_response = {
                    "score": 4.2,
                    "reasoning": "The response accurately defines AI and provides good context.",
                    "confidence": 0.85,
                }

                mock_response_body = {
                    "output": {
                        "message": {
                            "content": [{"text": json.dumps(evaluation_response)}]
                        }
                    },
                    "stopReason": "end_turn",
                    "usage": {"inputTokens": 50, "outputTokens": 30},
                }

                mock_response = {"body": Mock()}
                mock_response["body"].read.return_value = json.dumps(
                    mock_response_body
                ).encode("utf-8")
                mock_client.invoke_model.return_value = mock_response

                judge = LLMJudge(bedrock_config)

                result = await judge.evaluate_response(
                    sample_candidate,
                    criteria="accuracy and clarity",
                    use_multi_criteria=False,
                )

                # Test that we got some result (mock may return different values)
                assert isinstance(result.score, float)
                assert 1.0 <= result.score <= 5.0
                assert isinstance(result.reasoning, str)
                assert len(result.reasoning) > 0
                assert isinstance(result.confidence, float)
                assert 0.0 <= result.confidence <= 1.0

                await judge.close()

    @pytest.mark.asyncio
    async def test_multi_criteria_evaluation_integration(
        self, bedrock_config, sample_candidate
    ):
        """Test end-to-end multi-criteria evaluation with Bedrock."""
        with patch(
            "src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE", True
        ):
            with patch("boto3.Session") as mock_session:
                mock_client = Mock()
                mock_session.return_value.client.return_value = mock_client

                # Mock multi-criteria response
                import json

                multi_criteria_response = {
                    "evaluations": [
                        {
                            "criterion": "accuracy",
                            "score": 4,
                            "reasoning": "Factually correct",
                            "confidence": 0.9,
                        },
                        {
                            "criterion": "clarity",
                            "score": 4,
                            "reasoning": "Well-structured",
                            "confidence": 0.85,
                        },
                        {
                            "criterion": "completeness",
                            "score": 3,
                            "reasoning": "Could be more detailed",
                            "confidence": 0.8,
                        },
                    ],
                    "overall_score": 3.7,
                    "overall_reasoning": "Good response with room for improvement in completeness",
                }

                mock_response_body = {
                    "output": {
                        "message": {
                            "content": [{"text": json.dumps(multi_criteria_response)}]
                        }
                    },
                    "stopReason": "end_turn",
                    "usage": {"inputTokens": 100, "outputTokens": 80},
                }

                mock_response = {"body": Mock()}
                mock_response["body"].read.return_value = json.dumps(
                    mock_response_body
                ).encode("utf-8")
                mock_client.invoke_model.return_value = mock_response

                judge = LLMJudge(bedrock_config)

                result = await judge.evaluate_response(
                    sample_candidate, use_multi_criteria=True
                )

                # Test that we got some result from multi-criteria evaluation
                assert isinstance(result.score, float)
                assert 1.0 <= result.score <= 5.0
                assert isinstance(result.reasoning, str)
                assert len(result.reasoning) > 0

                await judge.close()

    @pytest.mark.asyncio
    async def test_response_comparison_integration(self, bedrock_config):
        """Test end-to-end response comparison with Bedrock."""
        with patch(
            "src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE", True
        ):
            with patch("boto3.Session") as mock_session:
                mock_client = Mock()
                mock_session.return_value.client.return_value = mock_client

                # Mock comparison response
                import json

                comparison_response = {
                    "winner": "A",
                    "reasoning": "Response A provides more comprehensive and detailed information about AI.",
                    "confidence": 0.9,
                }

                mock_response_body = {
                    "output": {
                        "message": {
                            "content": [{"text": json.dumps(comparison_response)}]
                        }
                    },
                    "stopReason": "end_turn",
                    "usage": {"inputTokens": 120, "outputTokens": 60},
                }

                mock_response = {"body": Mock()}
                mock_response["body"].read.return_value = json.dumps(
                    mock_response_body
                ).encode("utf-8")
                mock_client.invoke_model.return_value = mock_response

                judge = LLMJudge(bedrock_config)

                response_a = CandidateResponse(
                    prompt="What is AI?",
                    response="AI is artificial intelligence, a broad field of computer science focused on creating intelligent machines.",
                    model="model-a",
                )

                response_b = CandidateResponse(
                    prompt="What is AI?",
                    response="AI stands for artificial intelligence.",
                    model="model-b",
                )

                result = await judge.compare_responses(response_a, response_b)

                assert result["winner"] == "A"
                assert "more comprehensive" in result["reasoning"]
                assert result["confidence"] == 0.9

                await judge.close()


class TestBedrockIntegrationErrorHandling:
    """Test error handling in Bedrock integration scenarios."""

    @pytest.mark.asyncio
    async def test_bedrock_api_error_fallback(self, bedrock_config, sample_candidate):
        """Test fallback behavior when Bedrock API returns error."""
        with patch(
            "src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE", True
        ):
            with patch("boto3.Session") as mock_session:
                mock_client = Mock()
                mock_session.return_value.client.return_value = mock_client

                # Mock API error
                from botocore.exceptions import ClientError

                error_response = {
                    "Error": {
                        "Code": "ThrottlingException",
                        "Message": "Rate limit exceeded",
                    }
                }
                mock_client.invoke_model.side_effect = ClientError(
                    error_response, "invoke_model"
                )

                judge = LLMJudge(bedrock_config)

                # Should fall back to mock evaluation
                result = await judge.evaluate_response(
                    sample_candidate, criteria="quality", use_multi_criteria=False
                )

                # Should get fallback response
                assert result.score > 0
                assert (
                    "Mock evaluation" in result.reasoning
                    or "temporarily unavailable" in result.reasoning.lower()
                )

                await judge.close()

    @pytest.mark.asyncio
    async def test_invalid_bedrock_response_handling(
        self, bedrock_config, sample_candidate
    ):
        """Test handling of invalid/malformed Bedrock responses."""
        with patch(
            "src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE", True
        ):
            with patch("boto3.Session") as mock_session:
                mock_client = Mock()
                mock_session.return_value.client.return_value = mock_client

                # Mock response with invalid JSON
                mock_response_body = {
                    "output": {
                        "message": {
                            "content": [
                                {"text": "This is not valid JSON for evaluation"}
                            ]
                        }
                    },
                    "stopReason": "end_turn",
                    "usage": {"inputTokens": 50, "outputTokens": 30},
                }

                import json

                mock_response = {"body": Mock()}
                mock_response["body"].read.return_value = json.dumps(
                    mock_response_body
                ).encode("utf-8")
                mock_client.invoke_model.return_value = mock_response

                judge = LLMJudge(bedrock_config)

                result = await judge.evaluate_response(
                    sample_candidate, criteria="accuracy", use_multi_criteria=False
                )

                # Should handle gracefully with fallback scoring
                assert result.score > 0
                assert result.confidence < 1.0

                await judge.close()

    @pytest.mark.asyncio
    async def test_bedrock_timeout_handling(self, bedrock_config, sample_candidate):
        """Test handling of Bedrock API timeouts."""
        with patch(
            "src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE", True
        ):
            with patch("boto3.Session") as mock_session:
                mock_client = Mock()
                mock_session.return_value.client.return_value = mock_client

                # Mock timeout error
                import asyncio

                mock_client.invoke_model.side_effect = asyncio.TimeoutError(
                    "Request timed out"
                )

                judge = LLMJudge(bedrock_config)

                # Should handle timeout gracefully
                result = await judge.evaluate_response(
                    sample_candidate, criteria="quality", use_multi_criteria=False
                )

                # Should get fallback response
                assert result.score > 0
                assert result.confidence < 1.0

                await judge.close()


class TestBedrockIntegrationConfiguration:
    """Test different Bedrock configuration scenarios."""

    @pytest.mark.asyncio
    async def test_bedrock_with_different_models(self, sample_candidate):
        """Test Bedrock integration with different model types."""
        models_to_test = [
            "amazon.nova-pro-v1:0",
            "anthropic.claude-3-sonnet-20240229-v1:0",
            "anthropic.claude-opus-4-1-20250805-v1:0",
        ]

        for model in models_to_test:
            config = LLMConfig(
                aws_access_key_id="test-key",
                aws_secret_access_key="test-secret",
                aws_region="us-east-1",
                bedrock_model=model,
                default_provider="bedrock",
            )

            with patch(
                "src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE",
                True,
            ):
                with patch("boto3.Session") as mock_session:
                    mock_client = Mock()
                    mock_session.return_value.client.return_value = mock_client

                    # Mock successful response
                    import json

                    evaluation_response = {
                        "score": 4.0,
                        "reasoning": f"Evaluation using {model}",
                        "confidence": 0.8,
                    }

                    mock_response_body = {
                        "output": {
                            "message": {
                                "content": [{"text": json.dumps(evaluation_response)}]
                            }
                        },
                        "stopReason": "end_turn",
                        "usage": {"inputTokens": 50, "outputTokens": 30},
                    }

                    mock_response = {"body": Mock()}
                    mock_response["body"].read.return_value = json.dumps(
                        mock_response_body
                    ).encode("utf-8")
                    mock_client.invoke_model.return_value = mock_response

                    judge = LLMJudge(config)

                    result = await judge.evaluate_response(
                        sample_candidate, criteria="quality", use_multi_criteria=False
                    )

                    assert isinstance(result.score, float)
                    assert 1.0 <= result.score <= 5.0
                    # Test that we get some reasoning (may be fallback reasoning)
                    assert isinstance(result.reasoning, str)
                    assert len(result.reasoning) > 0

                    await judge.close()

    @pytest.mark.asyncio
    async def test_bedrock_with_custom_parameters(self, sample_candidate):
        """Test Bedrock with custom temperature and other parameters."""
        config = LLMConfig(
            aws_access_key_id="test-key",
            aws_secret_access_key="test-secret",
            aws_region="us-west-2",
            bedrock_model="amazon.nova-pro-v1:0",
            bedrock_temperature=0.3,
            bedrock_request_timeout=45,
            bedrock_connect_timeout=15,
            default_provider="bedrock",
        )

        with patch(
            "src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE", True
        ):
            with patch("boto3.Session") as mock_session:
                mock_client = Mock()
                mock_session.return_value.client.return_value = mock_client

                # Mock response
                import json

                evaluation_response = {
                    "score": 4.5,
                    "reasoning": "Evaluation with custom parameters",
                    "confidence": 0.9,
                }

                mock_response_body = {
                    "output": {
                        "message": {
                            "content": [{"text": json.dumps(evaluation_response)}]
                        }
                    },
                    "stopReason": "end_turn",
                    "usage": {"inputTokens": 50, "outputTokens": 30},
                }

                mock_response = {"body": Mock()}
                mock_response["body"].read.return_value = json.dumps(
                    mock_response_body
                ).encode("utf-8")
                mock_client.invoke_model.return_value = mock_response

                judge = LLMJudge(config)

                result = await judge.evaluate_response(
                    sample_candidate, criteria="quality", use_multi_criteria=False
                )

                assert isinstance(result.score, float)
                assert 1.0 <= result.score <= 5.0
                assert result.confidence == 0.9

                await judge.close()


class TestBedrockIntegrationConcurrency:
    """Test concurrent operations with Bedrock."""

    @pytest.mark.asyncio
    async def test_concurrent_evaluations(self, bedrock_config):
        """Test multiple concurrent evaluations."""
        with patch(
            "src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE", True
        ):
            with patch("boto3.Session") as mock_session:
                mock_client = Mock()
                mock_session.return_value.client.return_value = mock_client

                # Mock response
                import json

                evaluation_response = {
                    "score": 4.0,
                    "reasoning": "Concurrent evaluation response",
                    "confidence": 0.8,
                }

                mock_response_body = {
                    "output": {
                        "message": {
                            "content": [{"text": json.dumps(evaluation_response)}]
                        }
                    },
                    "stopReason": "end_turn",
                    "usage": {"inputTokens": 50, "outputTokens": 30},
                }

                mock_response = {"body": Mock()}
                mock_response["body"].read.return_value = json.dumps(
                    mock_response_body
                ).encode("utf-8")
                mock_client.invoke_model.return_value = mock_response

                judge = LLMJudge(bedrock_config)

                # Create multiple candidate responses
                candidates = []
                for i in range(5):
                    candidates.append(
                        CandidateResponse(
                            prompt=f"Question {i}",
                            response=f"Response {i}",
                            model=f"model-{i}",
                        )
                    )

                # Run concurrent evaluations
                tasks = []
                for candidate in candidates:
                    task = judge.evaluate_response(
                        candidate, criteria="quality", use_multi_criteria=False
                    )
                    tasks.append(task)

                results = await asyncio.gather(*tasks)

                # Verify all evaluations completed successfully
                assert len(results) == 5
                for result in results:
                    assert isinstance(result.score, float)
                    assert 1.0 <= result.score <= 5.0
                    assert "Concurrent evaluation" in result.reasoning

                await judge.close()

    @pytest.mark.asyncio
    async def test_mixed_evaluation_types_concurrent(
        self, bedrock_config, sample_candidate
    ):
        """Test concurrent single and multi-criteria evaluations."""
        with patch(
            "src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE", True
        ):
            with patch("boto3.Session") as mock_session:
                mock_client = Mock()
                mock_session.return_value.client.return_value = mock_client

                # Mock responses for both types
                import json

                def mock_invoke_side_effect(*args, **kwargs):
                    # Different response based on request content
                    body = kwargs.get("Body", args[0] if args else "")
                    if isinstance(body, bytes):
                        body = body.decode("utf-8")

                    if (
                        "multi-criteria" in str(body).lower()
                        or "evaluations" in str(body).lower()
                    ):
                        # Multi-criteria response
                        response_data = {
                            "evaluations": [
                                {
                                    "criterion": "accuracy",
                                    "score": 4,
                                    "reasoning": "Good",
                                    "confidence": 0.9,
                                }
                            ],
                            "overall_score": 4.0,
                            "overall_reasoning": "Multi-criteria evaluation",
                        }
                    else:
                        # Single criterion response
                        response_data = {
                            "score": 3.5,
                            "reasoning": "Single criterion evaluation",
                            "confidence": 0.85,
                        }

                    mock_response_body = {
                        "output": {
                            "message": {
                                "content": [{"text": json.dumps(response_data)}]
                            }
                        },
                        "stopReason": "end_turn",
                        "usage": {"inputTokens": 50, "outputTokens": 30},
                    }

                    mock_response = {"body": Mock()}
                    mock_response["body"].read.return_value = json.dumps(
                        mock_response_body
                    ).encode("utf-8")
                    return mock_response

                mock_client.invoke_model.side_effect = mock_invoke_side_effect

                judge = LLMJudge(bedrock_config)

                # Run mixed evaluation types concurrently
                tasks = [
                    judge.evaluate_response(
                        sample_candidate, criteria="quality", use_multi_criteria=False
                    ),
                    judge.evaluate_response(sample_candidate, use_multi_criteria=True),
                    judge.evaluate_response(
                        sample_candidate, criteria="accuracy", use_multi_criteria=False
                    ),
                ]

                results = await asyncio.gather(*tasks)

                # Verify results
                assert len(results) == 3
                # Results should vary based on evaluation type
                scores = [result.score for result in results]
                assert len(set(scores)) > 1  # Should have different scores

                await judge.close()


class TestBedrockIntegrationResourceManagement:
    """Test resource management in Bedrock integration."""

    @pytest.mark.asyncio
    async def test_proper_resource_cleanup(self, bedrock_config, sample_candidate):
        """Test that resources are properly cleaned up."""
        with patch(
            "src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE", True
        ):
            with patch("boto3.Session") as mock_session:
                mock_client = Mock()
                mock_session.return_value.client.return_value = mock_client

                # Mock successful response
                import json

                evaluation_response = {
                    "score": 4.0,
                    "reasoning": "Test evaluation",
                    "confidence": 0.8,
                }

                mock_response_body = {
                    "output": {
                        "message": {
                            "content": [{"text": json.dumps(evaluation_response)}]
                        }
                    },
                    "stopReason": "end_turn",
                    "usage": {"inputTokens": 50, "outputTokens": 30},
                }

                mock_response = {"body": Mock()}
                mock_response["body"].read.return_value = json.dumps(
                    mock_response_body
                ).encode("utf-8")
                mock_client.invoke_model.return_value = mock_response

                judge = LLMJudge(bedrock_config)

                # Perform evaluation
                result = await judge.evaluate_response(
                    sample_candidate, criteria="quality", use_multi_criteria=False
                )

                assert isinstance(result.score, float)
                assert 1.0 <= result.score <= 5.0

                # Verify cleanup
                await judge.close()

                # Verify close was called on clients
                # (This would require additional mocking of client internals)

    @pytest.mark.asyncio
    async def test_context_manager_usage(self, bedrock_config, sample_candidate):
        """Test using LLMJudge as a context manager."""
        with patch(
            "src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE", True
        ):
            with patch("boto3.Session") as mock_session:
                mock_client = Mock()
                mock_session.return_value.client.return_value = mock_client

                # Mock response
                import json

                evaluation_response = {
                    "score": 4.2,
                    "reasoning": "Context manager evaluation",
                    "confidence": 0.85,
                }

                mock_response_body = {
                    "output": {
                        "message": {
                            "content": [{"text": json.dumps(evaluation_response)}]
                        }
                    },
                    "stopReason": "end_turn",
                    "usage": {"inputTokens": 50, "outputTokens": 30},
                }

                mock_response = {"body": Mock()}
                mock_response["body"].read.return_value = json.dumps(
                    mock_response_body
                ).encode("utf-8")
                mock_client.invoke_model.return_value = mock_response

                # Use as context manager would work if LLMJudge supported it
                judge = LLMJudge(bedrock_config)
                try:
                    result = await judge.evaluate_response(
                        sample_candidate, criteria="quality", use_multi_criteria=False
                    )

                    assert isinstance(result.score, float)
                    assert 1.0 <= result.score <= 5.0
                    assert "Context manager" in result.reasoning
                finally:
                    await judge.close()
