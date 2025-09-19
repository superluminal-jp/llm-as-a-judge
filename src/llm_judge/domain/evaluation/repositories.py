"""
Evaluation domain repositories.

Contains repository interfaces for evaluation data persistence.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from ..shared_kernel.value_objects import EntityId
from .entities import Evaluation, CriterionDefinition
from .value_objects import EvaluationType, EvaluationStatus


class EvaluationRepository(ABC):
    """Abstract repository for evaluation persistence."""

    @abstractmethod
    async def save(self, evaluation: Evaluation) -> None:
        """Save an evaluation."""
        pass

    @abstractmethod
    async def find_by_id(self, evaluation_id: EntityId) -> Optional[Evaluation]:
        """Find evaluation by ID."""
        pass

    @abstractmethod
    async def find_by_status(
        self,
        status: EvaluationStatus,
        limit: int = 100,
    ) -> List[Evaluation]:
        """Find evaluations by status."""
        pass

    @abstractmethod
    async def find_by_type(
        self,
        evaluation_type: EvaluationType,
        limit: int = 100,
    ) -> List[Evaluation]:
        """Find evaluations by type."""
        pass

    @abstractmethod
    async def find_by_criteria(
        self,
        criteria: Dict[str, Any],
        limit: int = 100,
    ) -> List[Evaluation]:
        """Find evaluations by criteria."""
        pass

    @abstractmethod
    async def delete(self, evaluation_id: EntityId) -> None:
        """Delete an evaluation."""
        pass

    @abstractmethod
    async def count(self) -> int:
        """Count total evaluations."""
        pass


class CriteriaRepository(ABC):
    """Abstract repository for criteria persistence."""

    @abstractmethod
    async def save(self, criteria: CriterionDefinition) -> None:
        """Save a criterion definition."""
        pass

    @abstractmethod
    async def find_by_id(self, criteria_id: EntityId) -> Optional[CriterionDefinition]:
        """Find criterion by ID."""
        pass

    @abstractmethod
    async def find_by_name(self, name: str) -> Optional[CriterionDefinition]:
        """Find criterion by name."""
        pass

    @abstractmethod
    async def find_all(self, limit: int = 100) -> List[CriterionDefinition]:
        """Find all criteria."""
        pass

    @abstractmethod
    async def find_by_type(
        self,
        criterion_type: str,
        limit: int = 100,
    ) -> List[CriterionDefinition]:
        """Find criteria by type."""
        pass

    @abstractmethod
    async def delete(self, criteria_id: EntityId) -> None:
        """Delete a criterion definition."""
        pass

    @abstractmethod
    async def count(self) -> int:
        """Count total criteria."""
        pass
