"""
Batch processing use cases.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Callable
import asyncio
import logging

from ...domain.batch.models import BatchRequest, BatchResult, BatchProgress
from ...domain.batch_processing.value_objects import BatchStatus
from ...domain.shared_kernel.value_objects import BatchId
from ...domain.shared_kernel.exceptions import DomainException

logger = logging.getLogger(__name__)


@dataclass
class ProcessBatchCommand:
    """Command for processing a batch."""

    batch_request: BatchRequest
    progress_callback: Optional[Callable[[BatchProgress], None]] = None


@dataclass
class ProcessBatchResult:
    """Result of batch processing."""

    batch_result: BatchResult
    success: bool
    error_message: Optional[str] = None


@dataclass
class CreateBatchCommand:
    """Command for creating a batch."""

    name: str
    description: Optional[str] = None
    max_concurrent_items: int = 5
    retry_failed_items: bool = True
    max_retries_per_item: int = 3
    continue_on_error: bool = True


@dataclass
class CreateBatchResult:
    """Result of batch creation."""

    batch_request: BatchRequest
    success: bool
    error_message: Optional[str] = None


@dataclass
class MonitorBatchCommand:
    """Command for monitoring a batch."""

    batch_id: BatchId


@dataclass
class MonitorBatchResult:
    """Result of batch monitoring."""

    batch_progress: Optional[BatchProgress]
    success: bool
    error_message: Optional[str] = None


@dataclass
class CancelBatchCommand:
    """Command for cancelling a batch."""

    batch_id: BatchId


@dataclass
class CancelBatchResult:
    """Result of batch cancellation."""

    success: bool
    error_message: Optional[str] = None


class ProcessBatchUseCase:
    """Use case for processing a batch of evaluations."""

    def __init__(self, batch_service):
        self.batch_service = batch_service

    async def execute(self, command: ProcessBatchCommand) -> ProcessBatchResult:
        """Execute batch processing."""
        try:
            logger.info(f"Processing batch: {command.batch_request.batch_id}")

            batch_result = await self.batch_service.process_batch_request(
                command.batch_request,
                progress_callback=command.progress_callback,
            )

            return ProcessBatchResult(
                batch_result=batch_result,
                success=True,
            )

        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            return ProcessBatchResult(
                batch_result=None,
                success=False,
                error_message=str(e),
            )


class CreateBatchUseCase:
    """Use case for creating a new batch."""

    def __init__(self):
        pass

    async def execute(self, command: CreateBatchCommand) -> CreateBatchResult:
        """Execute batch creation."""
        try:
            batch_request = BatchRequest(
                name=command.name,
                description=command.description,
                max_concurrent_items=command.max_concurrent_items,
                retry_failed_items=command.retry_failed_items,
                max_retries_per_item=command.max_retries_per_item,
                continue_on_error=command.continue_on_error,
            )

            return CreateBatchResult(
                batch_request=batch_request,
                success=True,
            )

        except Exception as e:
            logger.error(f"Batch creation failed: {e}")
            return CreateBatchResult(
                batch_request=None,
                success=False,
                error_message=str(e),
            )


class MonitorBatchUseCase:
    """Use case for monitoring batch progress."""

    def __init__(self, batch_service):
        self.batch_service = batch_service

    async def execute(self, command: MonitorBatchCommand) -> MonitorBatchResult:
        """Execute batch monitoring."""
        try:
            batch_progress = self.batch_service.get_batch_progress(command.batch_id)

            return MonitorBatchResult(
                batch_progress=batch_progress,
                success=True,
            )

        except Exception as e:
            logger.error(f"Batch monitoring failed: {e}")
            return MonitorBatchResult(
                batch_progress=None,
                success=False,
                error_message=str(e),
            )


class CancelBatchUseCase:
    """Use case for cancelling a batch."""

    def __init__(self, batch_service):
        self.batch_service = batch_service

    async def execute(self, command: CancelBatchCommand) -> CancelBatchResult:
        """Execute batch cancellation."""
        try:
            success = self.batch_service.cancel_batch(command.batch_id)

            return CancelBatchResult(
                success=success,
            )

        except Exception as e:
            logger.error(f"Batch cancellation failed: {e}")
            return CancelBatchResult(
                success=False,
                error_message=str(e),
            )
