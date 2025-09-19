"""
Domain Events for the Shared Kernel.

Domain events represent something important that happened in the domain.
They are used to decouple different parts of the system and enable
event-driven architecture.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type, Callable
from datetime import datetime, timezone
import asyncio
import logging

from .value_objects import EvaluationId, BatchId, Timestamp


logger = logging.getLogger(__name__)


class DomainEvent(ABC):
    """Base class for all domain events."""

    def __init__(
        self, event_id: str = None, occurred_at: Timestamp = None, version: int = 1
    ):
        self.event_id = event_id or str(id(object()))
        self.occurred_at = occurred_at or Timestamp()
        self.version = version

    @property
    @abstractmethod
    def event_type(self) -> str:
        """Get the event type name."""
        pass

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "occurred_at": self.occurred_at.iso_format,
            "version": self.version,
            **self._get_event_data(),
        }

    @abstractmethod
    def _get_event_data(self) -> Dict[str, Any]:
        """Get event-specific data."""
        pass


class EvaluationCompleted(DomainEvent):
    """Event raised when an evaluation is completed."""

    def __init__(
        self,
        evaluation_id: EvaluationId,
        score: float,
        confidence: float,
        criteria_count: int,
        processing_duration_ms: float,
        provider: str,
        model: str,
        event_id: str = None,
        occurred_at: Timestamp = None,
        version: int = 1,
    ):
        super().__init__(event_id, occurred_at, version)
        self.evaluation_id = evaluation_id
        self.score = score
        self.confidence = confidence
        self.criteria_count = criteria_count
        self.processing_duration_ms = processing_duration_ms
        self.provider = provider
        self.model = model

    @property
    def event_type(self) -> str:
        return "evaluation.completed"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "evaluation_id": str(self.evaluation_id),
            "score": self.score,
            "confidence": self.confidence,
            "criteria_count": self.criteria_count,
            "processing_duration_ms": self.processing_duration_ms,
            "provider": self.provider,
            "model": self.model,
        }


class EvaluationFailed(DomainEvent):
    """Event raised when an evaluation fails."""

    def __init__(
        self,
        evaluation_id: EvaluationId,
        error_type: str,
        error_message: str,
        provider: str,
        model: str,
        retry_count: int = 0,
        event_id: str = None,
        occurred_at: Timestamp = None,
        version: int = 1,
    ):
        super().__init__(event_id, occurred_at, version)
        self.evaluation_id = evaluation_id
        self.error_type = error_type
        self.error_message = error_message
        self.provider = provider
        self.model = model
        self.retry_count = retry_count

    @property
    def event_type(self) -> str:
        return "evaluation.failed"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "evaluation_id": str(self.evaluation_id),
            "error_type": self.error_type,
            "error_message": self.error_message,
            "provider": self.provider,
            "model": self.model,
            "retry_count": self.retry_count,
        }


class BatchProcessingStarted(DomainEvent):
    """Event raised when batch processing starts."""

    def __init__(
        self,
        batch_id: BatchId,
        total_items: int,
        provider: str,
        model: str,
        event_id: str = None,
        occurred_at: Timestamp = None,
        version: int = 1,
    ):
        super().__init__(event_id, occurred_at, version)
        self.batch_id = batch_id
        self.total_items = total_items
        self.provider = provider
        self.model = model

    @property
    def event_type(self) -> str:
        return "batch.processing.started"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "batch_id": str(self.batch_id),
            "total_items": self.total_items,
            "provider": self.provider,
            "model": self.model,
        }


class BatchProcessingCompleted(DomainEvent):
    """Event raised when batch processing completes."""

    def __init__(
        self,
        batch_id: BatchId,
        total_items: int,
        successful_items: int,
        failed_items: int,
        processing_duration_ms: float,
        success_rate: float,
        event_id: str = None,
        occurred_at: Timestamp = None,
        version: int = 1,
    ):
        super().__init__(event_id, occurred_at, version)
        self.batch_id = batch_id
        self.total_items = total_items
        self.successful_items = successful_items
        self.failed_items = failed_items
        self.processing_duration_ms = processing_duration_ms
        self.success_rate = success_rate

    @property
    def event_type(self) -> str:
        return "batch.processing.completed"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "batch_id": str(self.batch_id),
            "total_items": self.total_items,
            "successful_items": self.successful_items,
            "failed_items": self.failed_items,
            "processing_duration_ms": self.processing_duration_ms,
            "success_rate": self.success_rate,
        }


class BatchProcessingFailed(DomainEvent):
    """Event raised when batch processing fails."""

    def __init__(
        self,
        batch_id: BatchId,
        error_type: str,
        error_message: str,
        items_processed: int,
        total_items: int,
        event_id: str = None,
        occurred_at: Timestamp = None,
        version: int = 1,
    ):
        super().__init__(event_id, occurred_at, version)
        self.batch_id = batch_id
        self.error_type = error_type
        self.error_message = error_message
        self.items_processed = items_processed
        self.total_items = total_items

    @property
    def event_type(self) -> str:
        return "batch.processing.failed"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "batch_id": str(self.batch_id),
            "error_type": self.error_type,
            "error_message": self.error_message,
            "items_processed": self.items_processed,
            "total_items": self.total_items,
        }


class CircuitBreakerOpened(DomainEvent):
    """Event raised when a circuit breaker opens."""

    def __init__(
        self,
        service_name: str,
        failure_count: int,
        failure_threshold: int,
        event_id: str = None,
        occurred_at: Timestamp = None,
        version: int = 1,
    ):
        super().__init__(event_id, occurred_at, version)
        self.service_name = service_name
        self.failure_count = failure_count
        self.failure_threshold = failure_threshold

    @property
    def event_type(self) -> str:
        return "circuit.breaker.opened"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "service_name": self.service_name,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
        }


class CircuitBreakerClosed(DomainEvent):
    """Event raised when a circuit breaker closes."""

    def __init__(
        self,
        service_name: str,
        recovery_time_ms: float,
        event_id: str = None,
        occurred_at: Timestamp = None,
        version: int = 1,
    ):
        super().__init__(event_id, occurred_at, version)
        self.service_name = service_name
        self.recovery_time_ms = recovery_time_ms

    @property
    def event_type(self) -> str:
        return "circuit.breaker.closed"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "service_name": self.service_name,
            "recovery_time_ms": self.recovery_time_ms,
        }


class DomainEventHandler(ABC):
    """Base class for domain event handlers."""

    @abstractmethod
    async def handle(self, event: DomainEvent) -> None:
        """Handle a domain event."""
        pass

    @property
    @abstractmethod
    def event_type(self) -> Type[DomainEvent]:
        """Get the event type this handler processes."""
        pass


class DomainEventPublisher:
    """Publishes domain events to registered handlers."""

    def __init__(self):
        self._handlers: Dict[Type[DomainEvent], List[DomainEventHandler]] = {}
        self._logger = logging.getLogger(__name__)

    def subscribe(
        self, event_type: Type[DomainEvent], handler: DomainEventHandler
    ) -> None:
        """Subscribe a handler to an event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        self._logger.debug(
            f"Subscribed handler {handler.__class__.__name__} to {event_type.__name__}"
        )

    def unsubscribe(
        self, event_type: Type[DomainEvent], handler: DomainEventHandler
    ) -> None:
        """Unsubscribe a handler from an event type."""
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
                self._logger.debug(
                    f"Unsubscribed handler {handler.__class__.__name__} from {event_type.__name__}"
                )
            except ValueError:
                pass

    async def publish(self, event: DomainEvent) -> None:
        """Publish a domain event to all registered handlers."""
        event_type = type(event)
        handlers = self._handlers.get(event_type, [])

        if not handlers:
            self._logger.debug(
                f"No handlers registered for event type {event_type.__name__}"
            )
            return

        self._logger.info(
            f"Publishing event {event.event_type} to {len(handlers)} handlers"
        )

        # Execute handlers concurrently
        tasks = []
        for handler in handlers:
            task = asyncio.create_task(self._handle_event(handler, event))
            tasks.append(task)

        # Wait for all handlers to complete
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _handle_event(
        self, handler: DomainEventHandler, event: DomainEvent
    ) -> None:
        """Handle an event with a specific handler."""
        try:
            await handler.handle(event)
            self._logger.debug(
                f"Handler {handler.__class__.__name__} processed event {event.event_type}"
            )
        except Exception as e:
            self._logger.error(
                f"Handler {handler.__class__.__name__} failed to process event {event.event_type}: {e}"
            )
            # Don't re-raise to prevent one handler failure from affecting others

    def get_registered_handlers(self) -> Dict[str, List[str]]:
        """Get information about registered handlers."""
        return {
            event_type.__name__: [handler.__class__.__name__ for handler in handlers]
            for event_type, handlers in self._handlers.items()
        }


# Global event publisher instance
_domain_event_publisher: Optional[DomainEventPublisher] = None


def get_domain_event_publisher() -> DomainEventPublisher:
    """Get the global domain event publisher instance."""
    global _domain_event_publisher
    if _domain_event_publisher is None:
        _domain_event_publisher = DomainEventPublisher()
    return _domain_event_publisher


def publish_domain_event(event: DomainEvent) -> None:
    """Publish a domain event using the global publisher."""
    publisher = get_domain_event_publisher()
    asyncio.create_task(publisher.publish(event))
