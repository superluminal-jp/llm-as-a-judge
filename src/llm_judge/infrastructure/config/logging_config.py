"""Enhanced logging configuration with best practices."""

import logging
import logging.handlers
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import traceback
import uuid

from .config import LLMConfig


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record):
        """Format log record as structured JSON."""
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'thread': record.thread,
            'process': record.process
        }
        
        # Add correlation ID if present
        if hasattr(record, 'correlation_id'):
            log_entry['correlation_id'] = record.correlation_id
        
        # Add request context if present
        if hasattr(record, 'request_context'):
            log_entry['request_context'] = record.request_context
        
        # Add performance metrics if present
        if hasattr(record, 'duration'):
            log_entry['duration_ms'] = record.duration
        
        # Add error details for exceptions
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        # Add extra fields
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'exc_info', 'exc_text', 'stack_info',
                          'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                          'thread', 'threadName', 'processName', 'process', 'message',
                          'correlation_id', 'request_context', 'duration']:
                extra_fields[key] = value
        
        if extra_fields:
            log_entry['extra'] = extra_fields
        
        return json.dumps(log_entry, default=str)


class SensitiveDataFilter(logging.Filter):
    """Filter to remove sensitive data from logs."""
    
    SENSITIVE_KEYS = [
        'api_key', 'token', 'password', 'secret', 'key', 'auth', 'authorization',
        'bearer', 'credential', 'private_key', 'access_token', 'refresh_token'
    ]
    
    def filter(self, record):
        """Filter sensitive data from log records."""
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            message = record.msg
            for sensitive_key in self.SENSITIVE_KEYS:
                if sensitive_key in message.lower():
                    # Replace the actual values with [REDACTED]
                    import re
                    # Pattern to match key=value or "key": "value" patterns
                    patterns = [
                        rf'{sensitive_key}["\s]*[:=]["\s]*[^"\s,}}]+',
                        rf'"{sensitive_key}"["\s]*:["\s]*"[^"]*"',
                        rf"'{sensitive_key}'['\s]*:['\s]*'[^']*'",
                    ]
                    for pattern in patterns:
                        message = re.sub(pattern, f'{sensitive_key}=[REDACTED]', message, flags=re.IGNORECASE)
                    record.msg = message
        
        return True


class CorrelationIdFilter(logging.Filter):
    """Add correlation ID to log records for request tracing."""
    
    def __init__(self):
        super().__init__()
        self.correlation_id = None
    
    def set_correlation_id(self, correlation_id: str):
        """Set the correlation ID for this thread."""
        self.correlation_id = correlation_id
    
    def filter(self, record):
        """Add correlation ID to log record."""
        if self.correlation_id:
            record.correlation_id = self.correlation_id
        return True


class EnhancedLoggerAdapter(logging.LoggerAdapter):
    """Logger adapter with additional context and convenience methods."""
    
    def __init__(self, logger, extra=None):
        super().__init__(logger, extra or {})
        self.correlation_filter = CorrelationIdFilter()
        logger.addFilter(self.correlation_filter)
    
    def set_correlation_id(self, correlation_id: str = None):
        """Set correlation ID for request tracing."""
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())[:8]
        self.correlation_filter.set_correlation_id(correlation_id)
        return correlation_id
    
    def log_performance(self, operation: str, duration_ms: float, **kwargs):
        """Log performance metrics."""
        self.info(f"Performance: {operation} completed", 
                 extra={'duration': duration_ms, 'operation': operation, **kwargs})
    
    def log_api_call(self, provider: str, operation: str, duration_ms: float, success: bool, **kwargs):
        """Log API call metrics."""
        level = self.info if success else self.warning
        level(f"API Call: {provider}.{operation} {'succeeded' if success else 'failed'}",
              extra={
                  'provider': provider,
                  'operation': operation,
                  'duration': duration_ms,
                  'success': success,
                  **kwargs
              })
    
    def log_retry_attempt(self, attempt: int, max_attempts: int, error: str, delay: float, **kwargs):
        """Log retry attempts."""
        self.warning(f"Retry attempt {attempt}/{max_attempts} after error: {error}",
                    extra={
                        'retry_attempt': attempt,
                        'max_attempts': max_attempts,
                        'retry_delay': delay,
                        'error': error,
                        **kwargs
                    })
    
    def log_circuit_breaker(self, service: str, state: str, failure_count: int, **kwargs):
        """Log circuit breaker state changes."""
        self.warning(f"Circuit breaker for {service} is now {state}",
                    extra={
                        'service': service,
                        'circuit_breaker_state': state,
                        'failure_count': failure_count,
                        **kwargs
                    })
    
    def log_error_classification(self, classification_data: dict, **kwargs):
        """Log structured error classification data."""
        category = classification_data.get('error_classification', {}).get('category', 'unknown')
        severity = classification_data.get('error_classification', {}).get('severity', 'unknown')
        
        self.error(f"Classified error: {category} ({severity})",
                  extra={
                      'error_classification': classification_data,
                      **kwargs
                  })


def setup_enhanced_logging(config: LLMConfig) -> EnhancedLoggerAdapter:
    """Setup enhanced logging with multiple handlers and formatters."""
    
    # Create logs directory
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Create subdirectories
    for subdir in ['app', 'error', 'debug', 'performance', 'audit']:
        (logs_dir / subdir).mkdir(exist_ok=True)
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture all levels, handlers will filter
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Create formatters
    console_formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    structured_formatter = StructuredFormatter()
    
    # Console handler for development
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, config.log_level))
    console_handler.setFormatter(console_formatter)
    console_handler.addFilter(SensitiveDataFilter())
    
    # Main application log (rotating)
    app_handler = logging.handlers.RotatingFileHandler(
        logs_dir / 'app' / 'application.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    app_handler.setLevel(logging.INFO)
    app_handler.setFormatter(structured_formatter)
    app_handler.addFilter(SensitiveDataFilter())
    
    # Error log (rotating)
    error_handler = logging.handlers.RotatingFileHandler(
        logs_dir / 'error' / 'errors.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=10
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(structured_formatter)
    error_handler.addFilter(SensitiveDataFilter())
    
    # Debug log (time-based rotation)
    debug_handler = logging.handlers.TimedRotatingFileHandler(
        logs_dir / 'debug' / 'debug.log',
        when='midnight',
        interval=1,
        backupCount=7  # Keep 7 days
    )
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(structured_formatter)
    debug_handler.addFilter(SensitiveDataFilter())
    
    # Performance log
    performance_handler = logging.handlers.RotatingFileHandler(
        logs_dir / 'performance' / 'performance.log',
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3
    )
    performance_handler.setLevel(logging.INFO)
    performance_handler.setFormatter(structured_formatter)
    
    # Add performance filter
    class PerformanceFilter(logging.Filter):
        def filter(self, record):
            return hasattr(record, 'duration') or hasattr(record, 'operation')
    
    performance_handler.addFilter(PerformanceFilter())
    
    # Audit log (for security and compliance)
    audit_handler = logging.handlers.RotatingFileHandler(
        logs_dir / 'audit' / 'audit.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=50  # Keep more audit logs
    )
    audit_handler.setLevel(logging.INFO)
    audit_handler.setFormatter(structured_formatter)
    
    # Add audit filter
    class AuditFilter(logging.Filter):
        def filter(self, record):
            return (hasattr(record, 'audit') or 
                   'api_call' in record.getMessage().lower() or
                   'auth' in record.getMessage().lower() or
                   'circuit_breaker' in record.getMessage().lower())
    
    audit_handler.addFilter(AuditFilter())
    
    # Add all handlers
    root_logger.addHandler(console_handler)
    root_logger.addHandler(app_handler)
    root_logger.addHandler(error_handler)
    root_logger.addHandler(debug_handler)
    root_logger.addHandler(performance_handler)
    root_logger.addHandler(audit_handler)
    
    # Create enhanced logger adapter
    app_logger = logging.getLogger('llm_judge')
    enhanced_logger = EnhancedLoggerAdapter(app_logger)
    
    # Log initialization
    enhanced_logger.info("Enhanced logging system initialized", 
                        extra={'log_level': config.log_level, 'logs_directory': str(logs_dir)})
    
    return enhanced_logger


def get_logger(name: str) -> EnhancedLoggerAdapter:
    """Get an enhanced logger for a specific module."""
    logger = logging.getLogger(name)
    return EnhancedLoggerAdapter(logger)


# Performance monitoring decorator
def log_performance(operation_name: str = None):
    """Decorator to automatically log function performance."""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            import time
            start_time = time.time()
            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            
            try:
                result = await func(*args, **kwargs)
                duration = (time.time() - start_time) * 1000
                
                # Get logger from first arg if it has one
                logger = None
                if args and hasattr(args[0], 'logger'):
                    logger = args[0].logger
                elif args and hasattr(args[0], '_logger'):
                    logger = args[0]._logger
                else:
                    logger = get_logger(func.__module__)
                
                if hasattr(logger, 'log_performance'):
                    logger.log_performance(op_name, duration, success=True)
                else:
                    logger.info(f"Performance: {op_name} completed in {duration:.2f}ms")
                
                return result
            except Exception as e:
                duration = (time.time() - start_time) * 1000
                
                # Get logger from first arg if it has one
                logger = None
                if args and hasattr(args[0], 'logger'):
                    logger = args[0].logger
                elif args and hasattr(args[0], '_logger'):
                    logger = args[0]._logger
                else:
                    logger = get_logger(func.__module__)
                
                if hasattr(logger, 'log_performance'):
                    logger.log_performance(op_name, duration, success=False, error=str(e))
                else:
                    logger.error(f"Performance: {op_name} failed after {duration:.2f}ms: {e}")
                
                raise
        
        def sync_wrapper(*args, **kwargs):
            import time
            start_time = time.time()
            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            
            try:
                result = func(*args, **kwargs)
                duration = (time.time() - start_time) * 1000
                
                # Get logger from first arg if it has one
                logger = None
                if args and hasattr(args[0], 'logger'):
                    logger = args[0].logger
                elif args and hasattr(args[0], '_logger'):
                    logger = args[0]._logger
                else:
                    logger = get_logger(func.__module__)
                
                if hasattr(logger, 'log_performance'):
                    logger.log_performance(op_name, duration, success=True)
                else:
                    logger.info(f"Performance: {op_name} completed in {duration:.2f}ms")
                
                return result
            except Exception as e:
                duration = (time.time() - start_time) * 1000
                
                # Get logger from first arg if it has one
                logger = None
                if args and hasattr(args[0], 'logger'):
                    logger = args[0].logger
                elif args and hasattr(args[0], '_logger'):
                    logger = args[0]._logger
                else:
                    logger = get_logger(func.__module__)
                
                if hasattr(logger, 'log_performance'):
                    logger.log_performance(op_name, duration, success=False, error=str(e))
                else:
                    logger.error(f"Performance: {op_name} failed after {duration:.2f}ms: {e}")
                
                raise
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator