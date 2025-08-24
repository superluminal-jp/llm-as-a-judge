"""Timeout management system with request cancellation capabilities."""

import asyncio
import logging
import time
from typing import Any, Callable, Optional, Dict
from dataclasses import dataclass
from enum import Enum

try:
    from ..config.logging_config import get_logger
except ImportError:
    def get_logger(name: str) -> logging.Logger:
        return logging.getLogger(name)


class TimeoutType(Enum):
    """Types of timeouts that can occur."""
    REQUEST = "request"
    CONNECT = "connect"
    READ = "read"


@dataclass
class TimeoutConfig:
    """Configuration for timeout management."""
    request_timeout: float
    connect_timeout: float
    read_timeout: Optional[float] = None
    cancellation_grace_period: float = 2.0  # Time to wait for graceful cancellation


@dataclass
class TimeoutResult:
    """Result of a timeout-managed operation."""
    success: bool
    result: Any = None
    error: Optional[Exception] = None
    timeout_type: Optional[TimeoutType] = None
    duration: float = 0.0
    was_cancelled: bool = False


class TimeoutManager:
    """Manages timeouts and request cancellation for API operations."""
    
    def __init__(self, provider_name: str):
        self.provider_name = provider_name
        self.logger = get_logger(f"timeout_manager.{provider_name}")
        self._active_operations: Dict[str, asyncio.Task] = {}
        self._operation_counter = 0
    
    async def execute_with_timeout(
        self,
        operation: Callable,
        config: TimeoutConfig,
        operation_name: str = "unknown",
        **operation_kwargs
    ) -> TimeoutResult:
        """Execute an operation with comprehensive timeout management."""
        self._operation_counter += 1
        operation_id = f"{operation_name}_{self._operation_counter}"
        
        start_time = time.time()
        
        try:
            # Create the operation task
            operation_task = asyncio.create_task(
                self._wrap_operation(operation, **operation_kwargs),
                name=f"{self.provider_name}_{operation_id}"
            )
            
            # Store the task for potential cancellation
            self._active_operations[operation_id] = operation_task
            
            self.logger.debug(f"Starting operation {operation_id} with timeout {config.request_timeout}s")
            
            # Execute with timeout
            try:
                result = await asyncio.wait_for(
                    operation_task,
                    timeout=config.request_timeout
                )
                
                duration = time.time() - start_time
                self.logger.debug(f"Operation {operation_id} completed successfully in {duration:.2f}s")
                
                return TimeoutResult(
                    success=True,
                    result=result,
                    duration=duration
                )
                
            except asyncio.TimeoutError:
                duration = time.time() - start_time
                self.logger.warning(f"Operation {operation_id} timed out after {duration:.2f}s")
                
                # Attempt graceful cancellation
                cancelled = await self._cancel_operation(operation_task, config.cancellation_grace_period)
                
                return TimeoutResult(
                    success=False,
                    error=TimeoutError(f"Operation {operation_name} timed out after {duration:.2f}s"),
                    timeout_type=TimeoutType.REQUEST,
                    duration=duration,
                    was_cancelled=cancelled
                )
                
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"Operation {operation_id} failed: {e}")
            
            return TimeoutResult(
                success=False,
                error=e,
                duration=duration
            )
            
        finally:
            # Clean up the operation tracking
            self._active_operations.pop(operation_id, None)
    
    async def _wrap_operation(self, operation: Callable, **kwargs) -> Any:
        """Wrap the operation to handle cancellation gracefully."""
        try:
            if asyncio.iscoroutinefunction(operation):
                return await operation(**kwargs)
            else:
                # Run synchronous operation in thread pool
                return await asyncio.get_event_loop().run_in_executor(
                    None, lambda: operation(**kwargs)
                )
        except asyncio.CancelledError:
            self.logger.debug("Operation was cancelled gracefully")
            raise
        except Exception as e:
            self.logger.error(f"Operation failed: {e}")
            raise
    
    async def _cancel_operation(self, task: asyncio.Task, grace_period: float) -> bool:
        """Cancel an operation with a grace period for cleanup."""
        if task.done():
            return True
        
        self.logger.debug(f"Cancelling operation with {grace_period}s grace period")
        
        # Request cancellation
        task.cancel()
        
        try:
            # Wait for graceful shutdown
            await asyncio.wait_for(task, timeout=grace_period)
            self.logger.debug("Operation cancelled gracefully")
            return True
        except (asyncio.TimeoutError, asyncio.CancelledError):
            self.logger.warning("Operation did not cancel gracefully within grace period")
            # Force cancellation if needed
            if not task.done():
                task.cancel()
            return False
        except Exception as e:
            self.logger.warning(f"Error during cancellation: {e}")
            return False
    
    async def cancel_all_operations(self) -> Dict[str, bool]:
        """Cancel all active operations."""
        if not self._active_operations:
            return {}
        
        self.logger.info(f"Cancelling {len(self._active_operations)} active operations")
        
        # Cancel all operations concurrently
        cancellation_tasks = []
        operation_ids = list(self._active_operations.keys())
        
        for operation_id in operation_ids:
            task = self._active_operations.get(operation_id)
            if task and not task.done():
                cancellation_tasks.append(
                    self._cancel_operation(task, 2.0)
                )
        
        if cancellation_tasks:
            results = await asyncio.gather(*cancellation_tasks, return_exceptions=True)
            return {
                operation_id: isinstance(result, bool) and result
                for operation_id, result in zip(operation_ids, results)
            }
        
        return {}
    
    def get_active_operations(self) -> Dict[str, Dict[str, Any]]:
        """Get information about currently active operations."""
        active_ops = {}
        for operation_id, task in self._active_operations.items():
            active_ops[operation_id] = {
                "name": task.get_name() if hasattr(task, 'get_name') else "unknown",
                "done": task.done(),
                "cancelled": task.cancelled() if hasattr(task, 'cancelled') else False,
                "created_at": getattr(task, '_created_at', None)
            }
        return active_ops
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform a health check on the timeout manager."""
        return {
            "provider": self.provider_name,
            "active_operations": len(self._active_operations),
            "operation_counter": self._operation_counter,
            "status": "healthy"
        }


class ProviderTimeoutManager:
    """Provider-specific timeout manager that handles partial responses and provider-specific timeouts."""
    
    def __init__(self, provider_name: str, config):
        self.provider_name = provider_name
        self.config = config
        self.logger = get_logger(f"provider_timeout.{provider_name}")
        self._timeout_manager = TimeoutManager(provider_name)
        
        # Set provider-specific timeout configuration
        if provider_name.lower() == "openai":
            self.timeout_config = TimeoutConfig(
                request_timeout=config.openai_request_timeout,
                connect_timeout=config.openai_connect_timeout
            )
        elif provider_name.lower() == "anthropic":
            self.timeout_config = TimeoutConfig(
                request_timeout=config.anthropic_request_timeout,
                connect_timeout=config.anthropic_connect_timeout
            )
        else:
            # Fallback to general timeout configuration
            self.timeout_config = TimeoutConfig(
                request_timeout=config.request_timeout,
                connect_timeout=10.0
            )
        
        self.logger.info(f"Initialized {provider_name} timeout manager: "
                        f"request={self.timeout_config.request_timeout}s, "
                        f"connect={self.timeout_config.connect_timeout}s")
    
    async def execute_api_call(
        self,
        api_operation: Callable,
        operation_name: str,
        **operation_kwargs
    ) -> TimeoutResult:
        """Execute an API call with provider-specific timeout management."""
        self.logger.debug(f"Executing {operation_name} with timeout management")
        
        result = await self._timeout_manager.execute_with_timeout(
            api_operation,
            self.timeout_config,
            operation_name,
            **operation_kwargs
        )
        
        # Log timeout events
        if not result.success:
            if result.timeout_type == TimeoutType.REQUEST:
                self.logger.error(f"{self.provider_name} {operation_name} timed out after {result.duration:.2f}s")
            else:
                self.logger.error(f"{self.provider_name} {operation_name} failed: {result.error}")
        else:
            if hasattr(self.logger, 'log_performance'):
                self.logger.log_performance(
                    f"{self.provider_name}_{operation_name}",
                    result.duration * 1000  # Convert to milliseconds
                )
        
        return result
    
    async def handle_partial_response(
        self,
        result: TimeoutResult,
        operation_name: str
    ) -> Any:
        """Handle partial responses that may occur during timeouts."""
        if result.success:
            return result.result
        
        if result.timeout_type == TimeoutType.REQUEST:
            # Check if we have any partial data
            if hasattr(result.error, 'partial_response'):
                partial_data = result.error.partial_response
                self.logger.warning(f"Using partial response from {operation_name}: "
                                  f"{len(str(partial_data))} characters")
                return {
                    "content": str(partial_data),
                    "partial": True,
                    "timeout_duration": result.duration
                }
        
        # Re-raise the original error if no partial response handling is possible
        if result.error:
            raise result.error
        else:
            raise TimeoutError(f"{operation_name} failed without specific error")
    
    async def close(self):
        """Clean up the timeout manager."""
        cancelled_ops = await self._timeout_manager.cancel_all_operations()
        if cancelled_ops:
            self.logger.info(f"Cancelled {len(cancelled_ops)} operations during cleanup")
    
    def get_timeout_stats(self) -> Dict[str, Any]:
        """Get timeout statistics for monitoring."""
        return {
            "provider": self.provider_name,
            "timeout_config": {
                "request_timeout": self.timeout_config.request_timeout,
                "connect_timeout": self.timeout_config.connect_timeout,
                "cancellation_grace_period": self.timeout_config.cancellation_grace_period
            },
            "active_operations": self._timeout_manager.get_active_operations()
        }