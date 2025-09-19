"""
Persistence use cases for evaluation data.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, List
import logging

from ...domain.evaluation.entities import Evaluation
from ...domain.evaluation.value_objects import EvaluationType, EvaluationStatus
from ...domain.shared_kernel.value_objects import EntityId
from ...domain.shared_kernel.exceptions import DomainException

logger = logging.getLogger(__name__)


@dataclass
class SaveEvaluationCommand:
    """Command for saving an evaluation."""

    evaluation: Evaluation


@dataclass
class SaveEvaluationResult:
    """Result of saving an evaluation."""

    success: bool
    error_message: Optional[str] = None


@dataclass
class RetrieveEvaluationCommand:
    """Command for retrieving an evaluation."""

    evaluation_id: EntityId


@dataclass
class RetrieveEvaluationResult:
    """Result of retrieving an evaluation."""

    evaluation: Optional[Evaluation]
    success: bool
    error_message: Optional[str] = None


@dataclass
class ListEvaluationsCommand:
    """Command for listing evaluations."""

    status: Optional[EvaluationStatus] = None
    evaluation_type: Optional[EvaluationType] = None
    limit: int = 100
    offset: int = 0


@dataclass
class ListEvaluationsResult:
    """Result of listing evaluations."""

    evaluations: List[Evaluation]
    total_count: int
    success: bool
    error_message: Optional[str] = None


@dataclass
class SearchEvaluationsCommand:
    """Command for searching evaluations."""

    criteria: Dict[str, Any]
    limit: int = 100
    offset: int = 0


@dataclass
class SearchEvaluationsResult:
    """Result of searching evaluations."""

    evaluations: List[Evaluation]
    total_count: int
    success: bool
    error_message: Optional[str] = None


class SaveEvaluationUseCase:
    """Use case for saving an evaluation."""

    def __init__(self, evaluation_repository):
        self.evaluation_repository = evaluation_repository

    async def execute(self, command: SaveEvaluationCommand) -> SaveEvaluationResult:
        """Execute evaluation saving."""
        try:
            await self.evaluation_repository.save(command.evaluation)

            return SaveEvaluationResult(
                success=True,
            )

        except Exception as e:
            logger.error(f"Evaluation saving failed: {e}")
            return SaveEvaluationResult(
                success=False,
                error_message=str(e),
            )


class RetrieveEvaluationUseCase:
    """Use case for retrieving an evaluation."""

    def __init__(self, evaluation_repository):
        self.evaluation_repository = evaluation_repository

    async def execute(
        self, command: RetrieveEvaluationCommand
    ) -> RetrieveEvaluationResult:
        """Execute evaluation retrieval."""
        try:
            evaluation = await self.evaluation_repository.find_by_id(
                command.evaluation_id
            )

            return RetrieveEvaluationResult(
                evaluation=evaluation,
                success=True,
            )

        except Exception as e:
            logger.error(f"Evaluation retrieval failed: {e}")
            return RetrieveEvaluationResult(
                evaluation=None,
                success=False,
                error_message=str(e),
            )


class ListEvaluationsUseCase:
    """Use case for listing evaluations."""

    def __init__(self, evaluation_repository):
        self.evaluation_repository = evaluation_repository

    async def execute(self, command: ListEvaluationsCommand) -> ListEvaluationsResult:
        """Execute evaluation listing."""
        try:
            if command.status:
                evaluations = await self.evaluation_repository.find_by_status(
                    command.status,
                    limit=command.limit,
                )
            elif command.evaluation_type:
                evaluations = await self.evaluation_repository.find_by_type(
                    command.evaluation_type,
                    limit=command.limit,
                )
            else:
                # Get all evaluations (implement a find_all method in repository)
                evaluations = []

            total_count = await self.evaluation_repository.count()

            return ListEvaluationsResult(
                evaluations=evaluations,
                total_count=total_count,
                success=True,
            )

        except Exception as e:
            logger.error(f"Evaluation listing failed: {e}")
            return ListEvaluationsResult(
                evaluations=[],
                total_count=0,
                success=False,
                error_message=str(e),
            )


class SearchEvaluationsUseCase:
    """Use case for searching evaluations."""

    def __init__(self, evaluation_repository):
        self.evaluation_repository = evaluation_repository

    async def execute(
        self, command: SearchEvaluationsCommand
    ) -> SearchEvaluationsResult:
        """Execute evaluation search."""
        try:
            evaluations = await self.evaluation_repository.find_by_criteria(
                command.criteria,
                limit=command.limit,
            )

            total_count = await self.evaluation_repository.count()

            return SearchEvaluationsResult(
                evaluations=evaluations,
                total_count=total_count,
                success=True,
            )

        except Exception as e:
            logger.error(f"Evaluation search failed: {e}")
            return SearchEvaluationsResult(
                evaluations=[],
                total_count=0,
                success=False,
                error_message=str(e),
            )
