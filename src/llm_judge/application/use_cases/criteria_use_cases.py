"""
Criteria management use cases.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, List
import logging

from ...domain.evaluation.entities import CriterionDefinition
from ...domain.evaluation.value_objects import CriterionType
from ...domain.shared_kernel.value_objects import EntityId
from ...domain.shared_kernel.exceptions import DomainException

logger = logging.getLogger(__name__)


@dataclass
class CreateCriteriaCommand:
    """Command for creating criteria."""

    name: str
    description: str
    criterion_type: CriterionType
    weight: float = 1.0
    scale_min: int = 1
    scale_max: int = 5
    evaluation_prompt: str = ""
    examples: Optional[Dict[int, str]] = None
    domain_specific: bool = False
    requires_context: bool = False
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class CreateCriteriaResult:
    """Result of criteria creation."""

    criterion: Optional[CriterionDefinition]
    success: bool
    error_message: Optional[str] = None


@dataclass
class UpdateCriteriaCommand:
    """Command for updating criteria."""

    criteria_id: EntityId
    name: Optional[str] = None
    description: Optional[str] = None
    weight: Optional[float] = None
    evaluation_prompt: Optional[str] = None
    examples: Optional[Dict[int, str]] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class UpdateCriteriaResult:
    """Result of criteria update."""

    criterion: Optional[CriterionDefinition]
    success: bool
    error_message: Optional[str] = None


@dataclass
class DeleteCriteriaCommand:
    """Command for deleting criteria."""

    criteria_id: EntityId


@dataclass
class DeleteCriteriaResult:
    """Result of criteria deletion."""

    success: bool
    error_message: Optional[str] = None


@dataclass
class ListCriteriaCommand:
    """Command for listing criteria."""

    criterion_type: Optional[CriterionType] = None
    limit: int = 100
    offset: int = 0


@dataclass
class ListCriteriaResult:
    """Result of criteria listing."""

    criteria: List[CriterionDefinition]
    total_count: int
    success: bool
    error_message: Optional[str] = None


class CreateCriteriaUseCase:
    """Use case for creating criteria."""

    def __init__(self, criteria_repository):
        self.criteria_repository = criteria_repository

    async def execute(self, command: CreateCriteriaCommand) -> CreateCriteriaResult:
        """Execute criteria creation."""
        try:
            criterion = CriterionDefinition(
                name=command.name,
                description=command.description,
                criterion_type=command.criterion_type,
                weight=command.weight,
                scale_min=command.scale_min,
                scale_max=command.scale_max,
                evaluation_prompt=command.evaluation_prompt,
                examples=command.examples or {},
                domain_specific=command.domain_specific,
                requires_context=command.requires_context,
                metadata=command.metadata or {},
            )

            await self.criteria_repository.save(criterion)

            return CreateCriteriaResult(
                criterion=criterion,
                success=True,
            )

        except Exception as e:
            logger.error(f"Criteria creation failed: {e}")
            return CreateCriteriaResult(
                criterion=None,
                success=False,
                error_message=str(e),
            )


class UpdateCriteriaUseCase:
    """Use case for updating criteria."""

    def __init__(self, criteria_repository):
        self.criteria_repository = criteria_repository

    async def execute(self, command: UpdateCriteriaCommand) -> UpdateCriteriaResult:
        """Execute criteria update."""
        try:
            criterion = await self.criteria_repository.find_by_id(command.criteria_id)
            if not criterion:
                return UpdateCriteriaResult(
                    criterion=None,
                    success=False,
                    error_message="Criteria not found",
                )

            # Update fields if provided
            if command.name is not None:
                criterion = criterion._replace(name=command.name)
            if command.description is not None:
                criterion = criterion._replace(description=command.description)
            if command.weight is not None:
                criterion = criterion._replace(weight=command.weight)
            if command.evaluation_prompt is not None:
                criterion = criterion._replace(
                    evaluation_prompt=command.evaluation_prompt
                )
            if command.examples is not None:
                criterion = criterion._replace(examples=command.examples)
            if command.metadata is not None:
                criterion = criterion._replace(metadata=command.metadata)

            await self.criteria_repository.save(criterion)

            return UpdateCriteriaResult(
                criterion=criterion,
                success=True,
            )

        except Exception as e:
            logger.error(f"Criteria update failed: {e}")
            return UpdateCriteriaResult(
                criterion=None,
                success=False,
                error_message=str(e),
            )


class DeleteCriteriaUseCase:
    """Use case for deleting criteria."""

    def __init__(self, criteria_repository):
        self.criteria_repository = criteria_repository

    async def execute(self, command: DeleteCriteriaCommand) -> DeleteCriteriaResult:
        """Execute criteria deletion."""
        try:
            await self.criteria_repository.delete(command.criteria_id)

            return DeleteCriteriaResult(
                success=True,
            )

        except Exception as e:
            logger.error(f"Criteria deletion failed: {e}")
            return DeleteCriteriaResult(
                success=False,
                error_message=str(e),
            )


class ListCriteriaUseCase:
    """Use case for listing criteria."""

    def __init__(self, criteria_repository):
        self.criteria_repository = criteria_repository

    async def execute(self, command: ListCriteriaCommand) -> ListCriteriaResult:
        """Execute criteria listing."""
        try:
            if command.criterion_type:
                criteria = await self.criteria_repository.find_by_type(
                    command.criterion_type.value,
                    limit=command.limit,
                )
            else:
                criteria = await self.criteria_repository.find_all(
                    limit=command.limit,
                )

            total_count = await self.criteria_repository.count()

            return ListCriteriaResult(
                criteria=criteria,
                total_count=total_count,
                success=True,
            )

        except Exception as e:
            logger.error(f"Criteria listing failed: {e}")
            return ListCriteriaResult(
                criteria=[],
                total_count=0,
                success=False,
                error_message=str(e),
            )
