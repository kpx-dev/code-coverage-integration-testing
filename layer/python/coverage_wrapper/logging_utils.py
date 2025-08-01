"""
Logging utilities for the Lambda Coverage Layer.

This module provides structured logging capabilities with consistent formatting,
configurable log levels, and security-conscious error handling.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, Optional, Union
from functools import wraps


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter that outputs structured JSON logs.
    
    This formatter creates consistent, machine-readable log entries that include
    contextual information like Lambda function name, execution ID, and timestamps.
    """
    
    def __init__(self):
        super().__init__()
        self.function_name = os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'unknown')
        self.function_version = os.environ.get('AWS_LAMBDA_FUNCTION_VERSION', 'unknown')
        self.request_id = os.environ.get('AWS_LAMBDA_LOG_GROUP_NAME', 'unknown')
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as structured JSON.
        
        Args:
            record: The log record to format
            
        Returns:
            str: JSON-formatted log entry
        """
        # Base log structure
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'function_name': self.function_name,
            'function_version': self.function_version,
        }
        
        # Add request ID if available from Lambda context
        if hasattr(record, 'request_id'):
            log_entry['request_id'] = record.request_id
        
        # Add execution metrics if available
        if hasattr(record, 'duration_ms'):
            log_entry['duration_ms'] = record.duration_ms
        
        if hasattr(record, 'memory_used_mb'):
            log_entry['memory_used_mb'] = record.memory_used_mb
        
        # Add custom fields from extra parameter
        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)
        
        # Add exception information if present
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'message': str(record.exc_info[1]) if record.exc_info[1] else None,
                'traceback': self.formatException(record.exc_info)
            }
        
        # Add stack trace for errors
        if record.levelno >= logging.ERROR and record.stack_info:
            log_entry['stack_trace'] = record.stack_info
        
        return json.dumps(log_entry, default=str, separators=(',', ':'))


class SecurityFilter(logging.Filter):
    """
    Filter that removes or masks sensitive information from log records.
    
    This filter helps prevent accidental exposure of sensitive data like
    AWS credentials, API keys, or personal information in log messages.
    """
    
    # Patterns to mask in log messages
    SENSITIVE_PATTERNS = [
        'aws_access_key_id',
        'aws_secret_access_key',
        'aws_session_token',
        'password',
        'secret',
        'token',
        'key',
        'credential',
    ]
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter and sanitize log record.
        
        Args:
            record: The log record to filter
            
        Returns:
            bool: True to allow the record, False to suppress it
        """
        # Sanitize the message
        record.msg = self._sanitize_message(str(record.msg))
        
        # Sanitize arguments if present
        if record.args:
            record.args = tuple(self._sanitize_message(str(arg)) for arg in record.args)
        
        return True
    
    def _sanitize_message(self, message: str) -> str:
        """
        Remove or mask sensitive information from a message.
        
        Args:
            message: The message to sanitize
            
        Returns:
            str: Sanitized message
        """
        message_lower = message.lower()
        
        for pattern in self.SENSITIVE_PATTERNS:
            if pattern in message_lower:
                # Replace sensitive values with masked placeholder
                # This is a simple approach - more sophisticated regex could be used
                return message.replace(message[message_lower.find(pattern):], f"{pattern}=***MASKED***")
        
        return message


class CoverageLogger:
    """
    Main logger class for the coverage wrapper system.
    
    This class provides a centralized logging interface with structured output,
    performance tracking, and security filtering.
    """
    
    def __init__(self, name: str):
        """
        Initialize the coverage logger.
        
        Args:
            name: Logger name (typically __name__ from calling module)
        """
        self.logger = logging.getLogger(name)
        self._setup_logger()
        self._request_id: Optional[str] = None
    
    def _setup_logger(self) -> None:
        """Set up logger with structured formatter and security filter."""
        # Don't add handlers if they already exist (avoid duplicate logs)
        if self.logger.handlers:
            return
        
        # Set log level from environment variable
        log_level = os.environ.get('COVERAGE_LOG_LEVEL', 'INFO').upper()
        self.logger.setLevel(getattr(logging, log_level, logging.INFO))
        
        # Create console handler
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredFormatter())
        handler.addFilter(SecurityFilter())
        
        self.logger.addHandler(handler)
        
        # Prevent propagation to avoid duplicate logs
        self.logger.propagate = False
    
    def set_request_id(self, request_id: str) -> None:
        """
        Set the request ID for this logger instance.
        
        Args:
            request_id: Lambda request ID from context
        """
        self._request_id = request_id
    
    def _log_with_context(self, level: int, message: str, extra_fields: Optional[Dict[str, Any]] = None) -> None:
        """
        Log message with additional context.
        
        Args:
            level: Log level
            message: Log message
            extra_fields: Additional fields to include in log entry
        """
        extra = {}
        
        if self._request_id:
            extra['request_id'] = self._request_id
        
        if extra_fields:
            extra['extra_fields'] = extra_fields
        
        self.logger.log(level, message, extra=extra)
    
    def debug(self, message: str, **kwargs) -> None:
        """Log debug message."""
        self._log_with_context(logging.DEBUG, message, kwargs)
    
    def info(self, message: str, **kwargs) -> None:
        """Log info message."""
        self._log_with_context(logging.INFO, message, kwargs)
    
    def warning(self, message: str, **kwargs) -> None:
        """Log warning message."""
        self._log_with_context(logging.WARNING, message, kwargs)
    
    def error(self, message: str, **kwargs) -> None:
        """Log error message."""
        self._log_with_context(logging.ERROR, message, kwargs)
    
    def critical(self, message: str, **kwargs) -> None:
        """Log critical message."""
        self._log_with_context(logging.CRITICAL, message, kwargs)
    
    def log_performance(self, operation: str, duration_ms: float, **kwargs) -> None:
        """
        Log performance metrics for an operation.
        
        Args:
            operation: Name of the operation
            duration_ms: Duration in milliseconds
            **kwargs: Additional metrics to log
        """
        metrics = {
            'operation': operation,
            'duration_ms': duration_ms,
            **kwargs
        }
        self.info(f"Performance: {operation} completed", **metrics)
    
    def log_coverage_metrics(self, function_name: str, coverage_percentage: float, 
                           file_size: int, upload_duration_ms: float) -> None:
        """
        Log coverage-specific metrics.
        
        Args:
            function_name: Name of the Lambda function
            coverage_percentage: Coverage percentage achieved
            file_size: Size of coverage file in bytes
            upload_duration_ms: Time taken to upload to S3
        """
        metrics = {
            'coverage_function': function_name,
            'coverage_percentage': coverage_percentage,
            'coverage_file_size_bytes': file_size,
            'upload_duration_ms': upload_duration_ms
        }
        self.info("Coverage metrics collected", **metrics)


def get_logger(name: str) -> CoverageLogger:
    """
    Get a configured logger instance.
    
    Args:
        name: Logger name (typically __name__ from calling module)
        
    Returns:
        CoverageLogger: Configured logger instance
    """
    return CoverageLogger(name)


def performance_timer(operation_name: str):
    """
    Decorator to automatically log performance metrics for functions.
    
    Args:
        operation_name: Name of the operation being timed
        
    Returns:
        Decorator function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                logger.log_performance(operation_name, duration_ms, success=True)
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.log_performance(operation_name, duration_ms, success=False, error=str(e))
                raise
        
        return wrapper
    return decorator


def log_lambda_context(context) -> None:
    """
    Log Lambda context information at the start of execution.
    
    Args:
        context: Lambda context object
    """
    logger = get_logger(__name__)
    
    # Set request ID for this execution
    if hasattr(context, 'aws_request_id'):
        logger.set_request_id(context.aws_request_id)
    
    # Log context information
    context_info = {
        'request_id': getattr(context, 'aws_request_id', 'unknown'),
        'function_name': getattr(context, 'function_name', 'unknown'),
        'function_version': getattr(context, 'function_version', 'unknown'),
        'memory_limit_mb': getattr(context, 'memory_limit_in_mb', 'unknown'),
        'remaining_time_ms': getattr(context, 'get_remaining_time_in_millis', lambda: 'unknown')(),
    }
    
    logger.info("Lambda execution started", **context_info)


# Module-level logger for this module
logger = get_logger(__name__)