"""
Evaluation Use Cases.

Use cases for handling evaluation operations following Clean Architecture
and DDD principles.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
import asyncio
import logging

from ...domain.evaluation.entities import (
    Evaluation,
    MultiCriteriaResult,
    CriterionScore,
    AggregatedScore,
    CriterionDefinition,
)
from ...domain.evaluation.value_objects import (
    EvaluationType,
    EvaluationStatus,
    EvaluationPrompt,
    EvaluationResponse,
    EvaluationCriteria,
)
from ...domain.shared_kernel.value_objects import (
    EvaluationId,
    ModelName,
    ProviderName,
    Score,
    Confidence,
)
from ...domain.shared_kernel.exceptions import (
    EvaluationException,
    EvaluationTimeoutException,
    EvaluationRateLimitException,
)
from ...infrastructure.llm_providers.base import LLMProvider, LLMProviderError
from ...infrastructure.resilience.retry_strategies import EnhancedRetryManager
from ...infrastructure.resilience.timeout_manager import TimeoutManager


logger = logging.getLogger(__name__)


@dataclass
class EvaluateResponseCommand:
    """Command for evaluating a single response."""

    prompt: str
    response: str
    model: str
    criteria: str = "overall quality"
    evaluation_type: EvaluationType = EvaluationType.SINGLE
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class EvaluateResponseResult:
    """Result of evaluating a single response."""

    evaluation_id: EvaluationId
    score: float
    reasoning: str
    confidence: float
    processing_duration_ms: float
    provider_used: str
    model_used: str
    metadata: Dict[str, Any]


@dataclass
class CompareResponsesCommand:
    """Command for comparing two responses."""

    prompt: str
    response_a: str
    response_b: str
    model_a: str
    model_b: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class CompareResponsesResult:
    """Result of comparing two responses."""

    evaluation_id: EvaluationId
    winner: str  # "A", "B", or "tie"
    reasoning: str
    confidence: float
    processing_duration_ms: float
    provider_used: str
    model_used: str
    metadata: Dict[str, Any]


@dataclass
class MultiCriteriaEvaluationCommand:
    """Command for multi-criteria evaluation."""

    prompt: str
    response: str
    model: str
    criteria: Optional[List[CriterionDefinition]] = None
    criteria_type: str = "comprehensive"
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class MultiCriteriaEvaluationResult:
    """Result of multi-criteria evaluation."""

    evaluation_id: EvaluationId
    result: MultiCriteriaResult
    processing_duration_ms: float
    provider_used: str
    model_used: str
    metadata: Dict[str, Any]


class EvaluateResponseUseCase:
    """Use case for evaluating a single response."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        retry_manager: EnhancedRetryManager,
        timeout_manager: TimeoutManager,
    ):
        self.llm_provider = llm_provider
        self.retry_manager = retry_manager
        self.timeout_manager = timeout_manager
        self.logger = logging.getLogger(__name__)

    async def execute(self, command: EvaluateResponseCommand) -> EvaluateResponseResult:
        """Execute the evaluation use case."""
        start_time = asyncio.get_event_loop().time()

        try:
            self.logger.info(f"Starting evaluation for model: {command.model}")

            # Create evaluation entity
            evaluation = Evaluation(
                evaluation_type=command.evaluation_type,
                prompt=EvaluationPrompt(text=command.prompt),
                response=EvaluationResponse(text=command.response, model=command.model),
                metadata=command.metadata or {},
            )

            # Start evaluation
            evaluation.start_evaluation()

            # Execute evaluation with retry and timeout
            result = await self.retry_manager.execute_with_retry(
                operation=self._perform_evaluation,
                service_name=self.llm_provider.provider_name,
                operation_name="evaluate_response",
                evaluation=evaluation,
                criteria=command.criteria,
            )

            # Complete evaluation
            evaluation.complete_evaluation(result)

            end_time = asyncio.get_event_loop().time()
            processing_duration = (end_time - start_time) * 1000

            return EvaluateResponseResult(
                evaluation_id=evaluation.id,
                score=result.aggregated.overall_score if result.aggregated else 0.0,
                reasoning=result.overall_reasoning or "Evaluation completed",
                confidence=result.aggregated.confidence if result.aggregated else 0.0,
                processing_duration_ms=processing_duration,
                provider_used=self.llm_provider.provider_name,
                model_used=command.model,
                metadata=command.metadata or {},
            )

        except Exception as e:
            self.logger.error(f"Evaluation failed: {e}")
            if hasattr(evaluation, "fail_evaluation"):
                evaluation.fail_evaluation(str(e))
            raise EvaluationException(
                message=f"Evaluation failed: {e}",
                evaluation_id=str(evaluation.id) if "evaluation" in locals() else None,
                provider=self.llm_provider.provider_name,
                model=command.model,
            )

    async def _perform_evaluation(
        self, evaluation: Evaluation, criteria: str
    ) -> MultiCriteriaResult:
        """Perform the actual evaluation using the LLM provider."""
        try:
            result = await self.llm_provider.evaluate_response(
                prompt=evaluation.prompt.text,
                response=evaluation.response.text,
                criteria=criteria,
                model=evaluation.response.model,
            )

            # Convert to domain result
            return self._convert_to_multi_criteria_result(result, evaluation)

        except LLMProviderError as e:
            self.logger.error(f"LLM provider error: {e}")
            raise EvaluationException(
                message=f"LLM provider error: {e.message}",
                evaluation_id=str(evaluation.id),
                provider=e.provider,
                model=e.model,
            )

    def _convert_to_multi_criteria_result(
        self, result: Dict[str, Any], evaluation: Evaluation
    ) -> MultiCriteriaResult:
        """Convert provider result to domain result."""
        # This is a simplified conversion - in practice, you'd have more sophisticated logic
        score = result.get("score", 3.0)
        reasoning = result.get("reasoning", "Evaluation completed")
        confidence = result.get("confidence", 0.8)

        # Create criterion score
        criterion_score = CriterionScore(
            criterion_name="overall_quality",
            score=int(score),
            reasoning=reasoning,
            confidence=confidence,
        )

        # Create aggregated score
        aggregated = AggregatedScore(
            overall_score=score,
            weighted_score=score,
            confidence=confidence,
            mean_score=score,
            median_score=score,
            criteria_count=1,
        )

        # Create multi-criteria result
        return MultiCriteriaResult(
            evaluation_id=evaluation.id,
            criterion_scores=[criterion_score],
            aggregated=aggregated,
            overall_reasoning=reasoning,
            judge_model=ModelName(evaluation.response.model),
        )


class CompareResponsesUseCase:
    """Use case for comparing two responses."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        retry_manager: EnhancedRetryManager,
        timeout_manager: TimeoutManager,
    ):
        self.llm_provider = llm_provider
        self.retry_manager = retry_manager
        self.timeout_manager = timeout_manager
        self.logger = logging.getLogger(__name__)

    async def execute(self, command: CompareResponsesCommand) -> CompareResponsesResult:
        """Execute the comparison use case."""
        start_time = asyncio.get_event_loop().time()

        try:
            self.logger.info(
                f"Starting comparison between {command.model_a} and {command.model_b}"
            )

            # Execute comparison with retry and timeout
            result = await self.retry_manager.execute_with_retry(
                operation=self._perform_comparison,
                service_name=self.llm_provider.provider_name,
                operation_name="compare_responses",
                command=command,
            )

            end_time = asyncio.get_event_loop().time()
            processing_duration = (end_time - start_time) * 1000

            return CompareResponsesResult(
                evaluation_id=EvaluationId(),
                winner=result.get("winner", "tie"),
                reasoning=result.get("reasoning", "Comparison completed"),
                confidence=result.get("confidence", 0.8),
                processing_duration_ms=processing_duration,
                provider_used=self.llm_provider.provider_name,
                model_used=f"{command.model_a} vs {command.model_b}",
                metadata=command.metadata or {},
            )

        except Exception as e:
            self.logger.error(f"Comparison failed: {e}")
            raise EvaluationException(
                message=f"Comparison failed: {e}",
                provider=self.llm_provider.provider_name,
                model=f"{command.model_a} vs {command.model_b}",
            )

    async def _perform_comparison(
        self, command: CompareResponsesCommand
    ) -> Dict[str, Any]:
        """Perform the actual comparison using the LLM provider."""
        try:
            return await self.llm_provider.compare_responses(
                prompt=command.prompt,
                response_a=command.response_a,
                response_b=command.response_b,
                model=command.model_a,  # Use first model as judge
            )

        except LLMProviderError as e:
            self.logger.error(f"LLM provider error: {e}")
            raise EvaluationException(
                message=f"LLM provider error: {e.message}",
                provider=e.provider,
                model=e.model,
            )


class MultiCriteriaEvaluationUseCase:
    """Use case for multi-criteria evaluation."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        retry_manager: EnhancedRetryManager,
        timeout_manager: TimeoutManager,
        criteria_service: Optional[Any] = None,  # CriteriaService from domain
    ):
        self.llm_provider = llm_provider
        self.retry_manager = retry_manager
        self.timeout_manager = timeout_manager
        self.criteria_service = criteria_service
        self.logger = logging.getLogger(__name__)

    async def execute(
        self, command: MultiCriteriaEvaluationCommand
    ) -> MultiCriteriaEvaluationResult:
        """Execute the multi-criteria evaluation use case."""
        start_time = asyncio.get_event_loop().time()

        try:
            self.logger.info(
                f"Starting multi-criteria evaluation for model: {command.model}"
            )

            # Get or create criteria
            criteria = command.criteria
            if not criteria and self.criteria_service:
                criteria = await self.criteria_service.get_default_criteria(
                    command.criteria_type
                )

            if not criteria:
                raise EvaluationException(
                    message="No criteria provided for multi-criteria evaluation",
                    model=command.model,
                )

            # Create evaluation entity
            evaluation = Evaluation(
                evaluation_type=EvaluationType.MULTI_CRITERIA,
                prompt=EvaluationPrompt(text=command.prompt),
                response=EvaluationResponse(text=command.response, model=command.model),
                criteria=criteria,
                metadata=command.metadata or {},
            )

            # Start evaluation
            evaluation.start_evaluation()

            # Execute evaluation with retry and timeout
            result = await self.retry_manager.execute_with_retry(
                operation=self._perform_multi_criteria_evaluation,
                service_name=self.llm_provider.provider_name,
                operation_name="evaluate_multi_criteria",
                evaluation=evaluation,
                criteria=criteria,
            )

            # Complete evaluation
            evaluation.complete_evaluation(result)

            end_time = asyncio.get_event_loop().time()
            processing_duration = (end_time - start_time) * 1000

            return MultiCriteriaEvaluationResult(
                evaluation_id=evaluation.id,
                result=result,
                processing_duration_ms=processing_duration,
                provider_used=self.llm_provider.provider_name,
                model_used=command.model,
                metadata=command.metadata or {},
            )

        except Exception as e:
            self.logger.error(f"Multi-criteria evaluation failed: {e}")
            if hasattr(evaluation, "fail_evaluation"):
                evaluation.fail_evaluation(str(e))
            raise EvaluationException(
                message=f"Multi-criteria evaluation failed: {e}",
                evaluation_id=str(evaluation.id) if "evaluation" in locals() else None,
                provider=self.llm_provider.provider_name,
                model=command.model,
            )

    async def _perform_multi_criteria_evaluation(
        self, evaluation: Evaluation, criteria: List[CriterionDefinition]
    ) -> MultiCriteriaResult:
        """Perform the actual multi-criteria evaluation using the LLM provider."""
        try:
            # Convert criteria to evaluation criteria format
            eval_criteria = EvaluationCriteria(
                name="Multi-criteria Evaluation",
                description="Comprehensive evaluation across multiple criteria",
                criterion_type=(
                    criteria[0].criterion_type
                    if criteria
                    else CriterionType.QUALITATIVE
                ),
                weight=Weight(1.0),
            )

            result = await self.llm_provider.evaluate_multi_criteria(
                prompt=evaluation.prompt.text,
                response=evaluation.response.text,
                criteria=eval_criteria,
                model=evaluation.response.model,
            )

            return result

        except LLMProviderError as e:
            self.logger.error(f"LLM provider error: {e}")
            raise EvaluationException(
                message=f"LLM provider error: {e.message}",
                evaluation_id=str(evaluation.id),
                provider=e.provider,
                model=e.model,
            )
