#!/usr/bin/env python3
"""
Minimal LLM-as-a-Judge Implementation
Based on https://www.evidentlyai.com/llm-guide/llm-as-a-judge
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import logging
import asyncio

from ...infrastructure.config.config import load_config, setup_logging
from ...infrastructure.clients.openai_client import OpenAIClient
from ...infrastructure.clients.anthropic_client import AnthropicClient
from ...infrastructure.clients.bedrock_client import BedrockClient
from ...infrastructure.clients.multi_criteria_client import (
    MultiCriteriaAnthropicClient,
    MultiCriteriaOpenAIClient,
    MultiCriteriaBedrockClient,
    MockMultiCriteriaClient,
)
from ...infrastructure.resilience.fallback_manager import (
    get_fallback_manager,
    FallbackResponse,
)
from ...domain.evaluation.criteria import EvaluationCriteria, DefaultCriteria
from ...domain.evaluation.results import MultiCriteriaResult


@dataclass
class CandidateResponse:
    """Response to be evaluated."""

    prompt: str
    response: str
    model: str = "unknown"


@dataclass
class EvaluationResult:
    """Result of evaluation."""

    score: float
    reasoning: str
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class LLMJudge:
    """Minimal LLM-as-a-Judge system."""

    def __init__(self, config=None, judge_model: str = None):
        self.config = config or load_config()

        # Use configured model based on provider
        if judge_model is None:
            if self.config.default_provider == "openai":
                self.judge_model = self.config.openai_model
            elif self.config.default_provider == "anthropic":
                self.judge_model = self.config.anthropic_model
            elif self.config.default_provider == "bedrock":
                self.judge_model = self.config.bedrock_model
            else:
                self.judge_model = "claude-sonnet-4-20250514"  # fallback
        else:
            self.judge_model = judge_model

        # Initialize clients (will be created when needed)
        self._openai_client = None
        self._anthropic_client = None
        self._bedrock_client = None

        # Initialize multi-criteria clients
        self._multi_criteria_openai = None
        self._multi_criteria_anthropic = None
        self._multi_criteria_bedrock = None
        self._multi_criteria_mock = None

        # Initialize fallback manager
        self._fallback_manager = get_fallback_manager(self.config)

        # Determine if we can use real LLM based on provider and API key
        if self.config.default_provider == "openai":
            self._use_real_llm = self.config.openai_api_key is not None
        elif self.config.default_provider == "anthropic":
            self._use_real_llm = self.config.anthropic_api_key is not None
        elif self.config.default_provider == "bedrock":
            self._use_real_llm = (
                self.config.aws_access_key_id is not None
                and self.config.aws_secret_access_key is not None
            )
        else:
            self._use_real_llm = False

        # Always initialize mock client for fallback
        from ...infrastructure.clients.multi_criteria_client import MockMultiCriteriaClient
        self._multi_criteria_mock = MockMultiCriteriaClient()

        # Log initialization (without exposing API keys)
        mode = "real LLM" if self._use_real_llm else "mock"
        logging.info(
            f"Initialized LLM Judge with provider: {self.config.default_provider}, model: {self.judge_model}, mode: {mode}"
        )

    def _get_default_criteria(self, criteria_type: str) -> EvaluationCriteria:
        """Get default criteria based on type."""
        if criteria_type == "comprehensive":
            return DefaultCriteria.comprehensive()
        elif criteria_type == "basic":
            return DefaultCriteria.basic()
        elif criteria_type == "technical":
            return DefaultCriteria.technical()
        elif criteria_type == "creative":
            return DefaultCriteria.creative()
        else:
            logging.warning(
                f"Unknown criteria type '{criteria_type}', falling back to comprehensive"
            )
            return DefaultCriteria.comprehensive()

    async def evaluate_response(
        self,
        candidate: CandidateResponse,
        criteria: str = "overall quality",
        use_multi_criteria: bool = True,
    ) -> EvaluationResult:
        """Evaluate a single response with fallback mechanisms."""
        # If multi-criteria is requested, use comprehensive evaluation
        if use_multi_criteria:
            multi_result = await self.evaluate_multi_criteria(candidate)
            # Convert to legacy format for backward compatibility
            return EvaluationResult(
                score=multi_result.aggregated.overall_score,
                reasoning=multi_result.overall_reasoning
                or f"Multi-criteria evaluation: {multi_result.aggregated.overall_score:.1f}/5 across {len(multi_result.criterion_scores)} criteria",
                confidence=multi_result.aggregated.confidence,
            )

        # Legacy single-criteria evaluation
        if self._use_real_llm:
            await self._ensure_clients_initialized()
            await self._fallback_manager.initialize()

            # Prepare context for fallback manager
            context = {
                "type": "evaluation",
                "prompt": candidate.prompt,
                "response": candidate.response,
                "criteria": criteria,
            }

            # Define evaluation operation with provider fallback
            async def evaluation_operation(provider: str):
                if provider == "openai" and self._openai_client:
                    return await self._openai_client.evaluate_with_openai(
                        prompt=candidate.prompt,
                        response_text=candidate.response,
                        criteria=criteria,
                        model=self.judge_model,
                    )
                elif provider == "anthropic" and self._anthropic_client:
                    return await self._anthropic_client.evaluate_with_anthropic(
                        prompt=candidate.prompt,
                        response_text=candidate.response,
                        criteria=criteria,
                        model=self.judge_model,
                    )
                elif provider == "bedrock" and self._bedrock_client:
                    return await self._bedrock_client.evaluate_with_bedrock(
                        prompt=candidate.prompt,
                        response_text=candidate.response,
                        criteria=criteria,
                        model=self.judge_model,
                    )
                else:
                    raise ValueError(f"Provider {provider} not available")

            try:
                # Execute with fallback mechanisms
                fallback_response = await self._fallback_manager.execute_with_fallback(
                    evaluation_operation,
                    context,
                    preferred_provider=self.config.default_provider,
                )

                # Handle different response types
                if isinstance(fallback_response.content, dict):
                    result = fallback_response.content

                    return EvaluationResult(
                        score=float(result.get("score", 3.0)),
                        reasoning=result.get("reasoning", "Evaluation completed"),
                        confidence=float(
                            result.get("confidence", fallback_response.confidence)
                        ),
                    )
                else:
                    # Handle error response
                    return EvaluationResult(
                        score=3.0,
                        reasoning="Service temporarily unavailable",
                        confidence=0.1,
                    )
            except Exception as e:
                logging.error(
                    f"{self.config.default_provider.title()} evaluation failed: {e}"
                )
                # Fall back to mock
                result = self._mock_llm_call(f"Evaluating {criteria}")
        else:
            # Use mock evaluation
            result = self._mock_llm_call(f"Evaluating {criteria}")

        return EvaluationResult(
            score=result.get("score", 3.0),
            reasoning=result.get("reasoning", "Mock evaluation"),
            confidence=result.get("confidence", 0.8),
        )

    async def compare_responses(
        self, response_a: CandidateResponse, response_b: CandidateResponse
    ) -> Dict[str, Any]:
        """Compare two responses pairwise with fallback mechanisms."""
        if response_a.prompt != response_b.prompt:
            raise ValueError("Cannot compare responses to different prompts")

        if self._use_real_llm:
            await self._ensure_clients_initialized()
            await self._fallback_manager.initialize()

            # Prepare context for fallback manager
            context = {
                "type": "comparison",
                "prompt": response_a.prompt,
                "response_a": response_a.response,
                "response_b": response_b.response,
            }

            # Define comparison operation with provider fallback
            async def comparison_operation(provider: str):
                if provider == "openai" and self._openai_client:
                    return await self._openai_client.compare_with_openai(
                        prompt=response_a.prompt,
                        response_a=response_a.response,
                        response_b=response_b.response,
                        model=self.judge_model,
                    )
                elif provider == "anthropic" and self._anthropic_client:
                    return await self._anthropic_client.compare_with_anthropic(
                        prompt=response_a.prompt,
                        response_a=response_a.response,
                        response_b=response_b.response,
                        model=self.judge_model,
                    )
                elif provider == "bedrock" and self._bedrock_client:
                    return await self._bedrock_client.compare_with_bedrock(
                        prompt=response_a.prompt,
                        response_a=response_a.response,
                        response_b=response_b.response,
                        model=self.judge_model,
                    )
                else:
                    raise ValueError(f"Provider {provider} not available")

            try:
                # Execute with fallback mechanisms
                fallback_response = await self._fallback_manager.execute_with_fallback(
                    comparison_operation,
                    context,
                    preferred_provider=self.config.default_provider,
                )

                # Handle different response types
                if isinstance(fallback_response.content, dict):
                    result = fallback_response.content

                    return {
                        "winner": result.get("winner", "tie"),
                        "reasoning": result.get("reasoning", "Comparison completed"),
                        "confidence": float(
                            result.get("confidence", fallback_response.confidence)
                        ),
                    }
                else:
                    # Handle error response
                    return {
                        "winner": "tie",
                        "reasoning": "Service temporarily unavailable",
                        "confidence": 0.1,
                    }
            except Exception as e:
                logging.error(
                    f"{self.config.default_provider.title()} comparison failed: {e}"
                )
                # Fall back to mock
                result = self._mock_llm_call("Comparing responses")
        else:
            # Use mock comparison
            result = self._mock_llm_call("Comparing responses")

        return {
            "winner": result.get("winner", "tie"),
            "reasoning": result.get("reasoning", "Mock comparison"),
            "confidence": result.get("confidence", 0.7),
        }

    def _create_evaluation_prompt(
        self, candidate: CandidateResponse, criteria: str
    ) -> str:
        """Create evaluation prompt."""
        return f"""You are an expert evaluator. Rate this response on {criteria} from 1-5.

Original Question: {candidate.prompt}

Response to Evaluate: {candidate.response}

Provide your evaluation in JSON format:
{{"score": 1-5, "reasoning": "explanation", "confidence": 0.0-1.0}}

Be thorough and fair."""

    def _create_comparison_prompt(
        self, response_a: CandidateResponse, response_b: CandidateResponse
    ) -> str:
        """Create comparison prompt."""
        return f"""Compare these two responses and determine which is better.

Question: {response_a.prompt}

Response A: {response_a.response}

Response B: {response_b.response}

Respond in JSON: {{"winner": "A"/"B"/"tie", "reasoning": "explanation", "confidence": 0.0-1.0}}"""

    def _mock_llm_call(self, prompt: str) -> Dict[str, Any]:
        """Mock LLM API call - replace with real implementation."""
        # Simple mock based on response length and keywords
        if "Comparing" in prompt:
            return {"winner": "tie", "reasoning": "Mock comparison", "confidence": 0.7}
        else:
            return {"score": 3.5, "reasoning": "Mock evaluation", "confidence": 0.8}

    async def evaluate_multi_criteria(
        self,
        candidate: CandidateResponse,
        criteria: Optional[EvaluationCriteria] = None,
        criteria_type: Optional[str] = None,
    ) -> MultiCriteriaResult:
        """
        Perform comprehensive multi-criteria evaluation.

        Args:
            candidate: The response to evaluate
            criteria: Custom evaluation criteria (if None, uses default)
            criteria_type: Type of default criteria to use ("comprehensive", "basic", "technical", "creative")

        Returns:
            MultiCriteriaResult with detailed scores across all criteria
        """
        # Use default criteria if none provided
        if criteria is None:
            criteria_type = criteria_type or self.config.default_criteria_type
            criteria = self._get_default_criteria(criteria_type)

        logging.info(
            f"Starting multi-criteria evaluation with {len(criteria.criteria)} criteria"
        )

        if self._use_real_llm:
            await self._ensure_clients_initialized()

            try:
                # Try primary provider first
                if (
                    self.config.default_provider == "openai"
                    and self._multi_criteria_openai
                ):
                    result = await self._multi_criteria_openai.evaluate_multi_criteria(
                        prompt=candidate.prompt,
                        response_text=candidate.response,
                        criteria=criteria,
                        model=self.judge_model,
                    )
                elif (
                    self.config.default_provider == "anthropic"
                    and self._multi_criteria_anthropic
                ):
                    result = (
                        await self._multi_criteria_anthropic.evaluate_multi_criteria(
                            prompt=candidate.prompt,
                            response_text=candidate.response,
                            criteria=criteria,
                            model=self.judge_model,
                        )
                    )
                elif (
                    self.config.default_provider == "bedrock"
                    and self._multi_criteria_bedrock
                ):
                    result = await self._multi_criteria_bedrock.evaluate_multi_criteria(
                        prompt=candidate.prompt,
                        response_text=candidate.response,
                        criteria=criteria,
                        model=self.judge_model,
                    )
                else:
                    # Fallback to mock
                    result = await self._multi_criteria_mock.evaluate_multi_criteria(
                        prompt=candidate.prompt,
                        response_text=candidate.response,
                        criteria=criteria,
                        model=self.judge_model,
                    )

                logging.info(
                    f"Multi-criteria evaluation completed: {result.aggregated.overall_score:.1f}/5 across {len(result.criterion_scores)} criteria"
                )
                return result

            except Exception as e:
                logging.error(f"Multi-criteria evaluation failed with real LLM: {e}")
                # Fallback to mock
                return await self._multi_criteria_mock.evaluate_multi_criteria(
                    prompt=candidate.prompt,
                    response_text=candidate.response,
                    criteria=criteria,
                    model=f"{self.judge_model}-fallback",
                )
        else:
            # Use mock client
            return await self._multi_criteria_mock.evaluate_multi_criteria(
                prompt=candidate.prompt,
                response_text=candidate.response,
                criteria=criteria,
                model=self.judge_model,
            )

    async def _ensure_clients_initialized(self):
        """Initialize LLM clients if not already done."""
        if self.config.default_provider == "openai" and self._openai_client is None:
            self._openai_client = OpenAIClient(self.config)
            self._multi_criteria_openai = MultiCriteriaOpenAIClient(self.config)
        elif (
            self.config.default_provider == "anthropic"
            and self._anthropic_client is None
        ):
            self._anthropic_client = AnthropicClient(self.config)
            self._multi_criteria_anthropic = MultiCriteriaAnthropicClient(self.config)
        elif self.config.default_provider == "bedrock" and self._bedrock_client is None:
            self._bedrock_client = BedrockClient(self.config)
            self._multi_criteria_bedrock = MultiCriteriaBedrockClient(self.config)

        # Always initialize mock client for fallback
        if self._multi_criteria_mock is None:
            self._multi_criteria_mock = MockMultiCriteriaClient()

    async def close(self):
        """Close LLM clients and cleanup resources."""
        if self._openai_client:
            await self._openai_client.close()
        if self._anthropic_client:
            await self._anthropic_client.close()
        if self._bedrock_client:
            await self._bedrock_client.close()
        if self._multi_criteria_openai:
            await self._multi_criteria_openai.close()
        if self._multi_criteria_anthropic:
            await self._multi_criteria_anthropic.close()
        if self._multi_criteria_bedrock:
            await self._multi_criteria_bedrock.close()
        if self._fallback_manager:
            await self._fallback_manager.cleanup()


async def main():
    """Demo the LLM judge system."""
    try:
        config = load_config()
        logger = setup_logging(config)

        if hasattr(logger, "info"):
            logger.info("Starting LLM Judge demo", extra={"audit": True})

        judge = LLMJudge(config)
    except ValueError as e:
        print(f"Configuration error: {e}")
        print("\nTo fix this:")
        print("1. Copy .env.example to .env")
        print("2. Fill in your API keys in the .env file")
        print("3. Run the script again")
        return
    except Exception as e:
        print(f"Unexpected error: {e}")
        return

    try:
        # Example 1: Single response evaluation
        candidate = CandidateResponse(
            prompt="What is artificial intelligence?",
            response="AI is the simulation of human intelligence in machines.",
            model="gpt-3.5",
        )

        result = await judge.evaluate_response(candidate, "accuracy and clarity")
        print("=== Single Response Evaluation ===")
        print(f"Score: {result.score}/5")
        print(f"Reasoning: {result.reasoning}")
        print(f"Confidence: {result.confidence}")
        print()

        # Example 2: Pairwise comparison
        candidate_a = CandidateResponse(
            prompt="Explain quantum computing",
            response="Quantum computing uses quantum bits that can be in superposition.",
            model="gpt-4",
        )

        candidate_b = CandidateResponse(
            prompt="Explain quantum computing",
            response="Quantum computers leverage quantum mechanical phenomena like superposition and entanglement to process information in fundamentally different ways than classical computers.",
            model="claude-3",
        )

        comparison = await judge.compare_responses(candidate_a, candidate_b)
        print("=== Pairwise Comparison ===")
        print(f"Winner: {comparison['winner']}")
        print(f"Reasoning: {comparison['reasoning']}")
        print(f"Confidence: {comparison['confidence']}")

    finally:
        # Clean up resources
        await judge.close()


if __name__ == "__main__":
    asyncio.run(main())
