"""
Error handling utilities for the Lambda Coverage Layer.

This module provides comprehensive error handling capabilities including
graceful degradation, fallback mechanisms, and timeout handling.
"""

import os
import time
import tempfile
import threading
from contextlib import contextmanager
from typing import Any, Callable, Optional, Dict, Union, List
from functools import wraps

from .logging_utils import get_logger

logger = get_logger(__name__)


class CoverageError(Exception):
    """Base exception for coverage-related errors."""
    pass


class CoverageInitializationError(CoverageError):
    """Exception raised when coverage initialization fails."""
    pass


class S3UploadError(CoverageError):
    """Exception raised when S3 upload operations fail."""
    pass


class TimeoutError(CoverageError):
    """Exception raised when operations exceed timeout limits."""
    pass


class GracefulErrorHandler:
    """
    Context manager and utility class for graceful error handling.
    
    This class provides mechanisms for handling errors gracefully without
    failing the main Lambda function execution.
    """
    
    def __init__(self, operation_name: str, critical: bool = False):
        """
        Initialize the error handler.
        
        Args:
            operation_name: Name of the operation being protected
            critical: Whether errors in this operation should fail the Lambda
        """
        self.operation_name = operation_name
        self.critical = critical
        self.start_time = None
        self.error_occurred = False
        self.error_details = None
    
    def __enter__(self):
        """Enter the error handling context."""
        self.start_time = time.time()
        logger.debug("Starting protected operation", operation=self.operation_name)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit the error handling context.
        
        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred
            
        Returns:
            bool: True to suppress the exception, False to propagate it
        """
        duration = time.time() - self.start_time if self.start_time else 0
        
        if exc_type is not None:
            self.error_occurred = True
            self.error_details = {
                'type': exc_type.__name__,
                'message': str(exc_val),
                'operation': self.operation_name,
                'duration_ms': duration * 1000
            }
            
            if self.critical:
                logger.error("Critical operation failed", 
                           operation=self.operation_name,
                           error=str(exc_val),
                           error_type=exc_type.__name__,
                           duration_ms=duration * 1000)
                # Don't suppress critical errors
                return False
            else:
                logger.warning("Non-critical operation failed gracefully", 
                             operation=self.operation_name,
                             error=str(exc_val),
                             error_type=exc_type.__name__,
                             duration_ms=duration * 1000)
                # Suppress non-critical errors
                return True
        else:
            logger.debug("Protected operation completed successfully", 
                        operation=self.operation_name,
                        duration_ms=duration * 1000)
            return False


def graceful_operation(operation_name: str, critical: bool = False):
    """
    Decorator for graceful error handling of operations.
    
    Args:
        operation_name: Name of the operation being protected
        critical: Whether errors should fail the Lambda function
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            with GracefulErrorHandler(operation_name, critical) as handler:
                result = func(*args, **kwargs)
                return result
            
            # If we get here, a non-critical error was handled gracefully
            if handler.error_occurred:
                logger.info("Operation failed but was handled gracefully", 
                           operation=operation_name,
                           error_details=handler.error_details)
                return None
            
        return wrapper
    return decorator


@contextmanager
def timeout_protection(timeout_seconds: float, operation_name: str):
    """
    Context manager that provides timeout protection for operations.
    
    Args:
        timeout_seconds: Maximum time allowed for the operation
        operation_name: Name of the operation for logging
        
    Raises:
        TimeoutError: If the operation exceeds the timeout
    """
    start_time = time.time()
    timeout_occurred = False
    
    def timeout_handler():
        nonlocal timeout_occurred
        time.sleep(timeout_seconds)
        timeout_occurred = True
    
    # Start timeout thread
    timeout_thread = threading.Thread(target=timeout_handler, daemon=True)
    timeout_thread.start()
    
    try:
        logger.debug("Starting operation with timeout protection", 
                    operation=operation_name,
                    timeout_seconds=timeout_seconds)
        yield
        
        duration = time.time() - start_time
        if timeout_occurred:
            logger.error("Operation exceeded timeout", 
                        operation=operation_name,
                        timeout_seconds=timeout_seconds,
                        actual_duration=duration)
            raise TimeoutError(f"Operation '{operation_name}' exceeded timeout of {timeout_seconds}s")
        else:
            logger.debug("Operation completed within timeout", 
                        operation=operation_name,
                        duration_seconds=duration,
                        timeout_seconds=timeout_seconds)
    
    except Exception as e:
        duration = time.time() - start_time
        logger.error("Operation failed within timeout period", 
                    operation=operation_name,
                    duration_seconds=duration,
                    error=str(e),
                    error_type=type(e).__name__)
        raise


class FallbackStorage:
    """
    Fallback storage mechanism for coverage files when S3 upload fails.
    
    This class provides local storage capabilities as a fallback when
    S3 uploads are not possible.
    """
    
    def __init__(self, base_path: str = "/tmp/coverage_fallback"):
        """
        Initialize fallback storage.
        
        Args:
            base_path: Base directory for fallback storage
        """
        self.base_path = base_path
        self.ensure_directory_exists()
    
    def ensure_directory_exists(self):
        """Ensure the fallback directory exists."""
        try:
            os.makedirs(self.base_path, exist_ok=True)
            logger.debug("Fallback storage directory ensured", path=self.base_path)
        except OSError as e:
            logger.error("Failed to create fallback storage directory", 
                        path=self.base_path,
                        error=str(e),
                        error_type=type(e).__name__)
            raise
    
    def store_coverage_file(self, source_path: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Store a coverage file in fallback storage.
        
        Args:
            source_path: Path to the source coverage file
            metadata: Optional metadata to store with the file
            
        Returns:
            str: Path to the stored file in fallback storage
            
        Raises:
            OSError: If file operations fail
        """
        import shutil
        import uuid
        
        # Generate unique filename
        file_id = str(uuid.uuid4())[:8]
        function_name = os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'unknown')
        fallback_filename = f"coverage-{function_name}-{file_id}.json"
        fallback_path = os.path.join(self.base_path, fallback_filename)
        
        try:
            # Copy the coverage file
            shutil.copy2(source_path, fallback_path)
            
            # Store metadata if provided
            if metadata:
                metadata_path = fallback_path + '.metadata'
                with open(metadata_path, 'w') as f:
                    import json
                    json.dump(metadata, f, indent=2, default=str)
            
            logger.info("Coverage file stored in fallback storage", 
                       source_path=source_path,
                       fallback_path=fallback_path,
                       has_metadata=metadata is not None)
            
            return fallback_path
            
        except Exception as e:
            logger.error("Failed to store coverage file in fallback storage", 
                        source_path=source_path,
                        fallback_path=fallback_path,
                        error=str(e),
                        error_type=type(e).__name__)
            raise
    
    def list_stored_files(self) -> List[Dict[str, Any]]:
        """
        List all files in fallback storage.
        
        Returns:
            List[Dict[str, Any]]: List of file information dictionaries
        """
        import json
        from datetime import datetime
        
        files = []
        
        try:
            if not os.path.exists(self.base_path):
                return files
            
            for filename in os.listdir(self.base_path):
                if filename.endswith('.json') and not filename.endswith('.metadata'):
                    file_path = os.path.join(self.base_path, filename)
                    metadata_path = file_path + '.metadata'
                    
                    file_info = {
                        'filename': filename,
                        'path': file_path,
                        'size': os.path.getsize(file_path),
                        'modified': datetime.fromtimestamp(os.path.getmtime(file_path)),
                        'metadata': None
                    }
                    
                    # Load metadata if available
                    if os.path.exists(metadata_path):
                        try:
                            with open(metadata_path, 'r') as f:
                                file_info['metadata'] = json.load(f)
                        except Exception as e:
                            logger.warning("Failed to load metadata for fallback file", 
                                         filename=filename,
                                         error=str(e))
                    
                    files.append(file_info)
            
            logger.debug("Listed fallback storage files", 
                        file_count=len(files),
                        base_path=self.base_path)
            
        except Exception as e:
            logger.error("Failed to list fallback storage files", 
                        base_path=self.base_path,
                        error=str(e),
                        error_type=type(e).__name__)
        
        return files
    
    def cleanup_old_files(self, max_age_hours: int = 24):
        """
        Clean up old files from fallback storage.
        
        Args:
            max_age_hours: Maximum age of files to keep in hours
        """
        import time
        
        cutoff_time = time.time() - (max_age_hours * 3600)
        removed_count = 0
        
        try:
            if not os.path.exists(self.base_path):
                return
            
            for filename in os.listdir(self.base_path):
                file_path = os.path.join(self.base_path, filename)
                
                if os.path.getmtime(file_path) < cutoff_time:
                    try:
                        os.remove(file_path)
                        removed_count += 1
                        
                        # Also remove metadata file if it exists
                        metadata_path = file_path + '.metadata'
                        if os.path.exists(metadata_path):
                            os.remove(metadata_path)
                        
                    except OSError as e:
                        logger.warning("Failed to remove old fallback file", 
                                     filename=filename,
                                     error=str(e))
            
            logger.info("Cleaned up old fallback files", 
                       removed_count=removed_count,
                       max_age_hours=max_age_hours)
            
        except Exception as e:
            logger.error("Failed to cleanup fallback storage", 
                        base_path=self.base_path,
                        error=str(e),
                        error_type=type(e).__name__)


def get_remaining_lambda_time(context) -> float:
    """
    Get remaining execution time for Lambda function.
    
    Args:
        context: Lambda context object
        
    Returns:
        float: Remaining time in seconds, or 0 if context is not available
    """
    try:
        if hasattr(context, 'get_remaining_time_in_millis'):
            remaining_ms = context.get_remaining_time_in_millis()
            return remaining_ms / 1000.0
        else:
            logger.warning("Lambda context does not have get_remaining_time_in_millis method")
            return 0.0
    except Exception as e:
        logger.warning("Failed to get remaining Lambda time", 
                      error=str(e),
                      error_type=type(e).__name__)
        return 0.0


def ensure_lambda_completion_time(context, min_buffer_seconds: float = 5.0) -> bool:
    """
    Check if there's enough time remaining for Lambda completion.
    
    Args:
        context: Lambda context object
        min_buffer_seconds: Minimum buffer time required for completion
        
    Returns:
        bool: True if there's enough time remaining, False otherwise
    """
    remaining_time = get_remaining_lambda_time(context)
    
    if remaining_time <= min_buffer_seconds:
        logger.warning("Insufficient time remaining for Lambda completion", 
                      remaining_seconds=remaining_time,
                      min_buffer_seconds=min_buffer_seconds)
        return False
    
    logger.debug("Sufficient time remaining for Lambda completion", 
                remaining_seconds=remaining_time,
                min_buffer_seconds=min_buffer_seconds)
    return True


# Global fallback storage instance
_fallback_storage = None


def get_fallback_storage() -> FallbackStorage:
    """
    Get the global fallback storage instance.
    
    Returns:
        FallbackStorage: Global fallback storage instance
    """
    global _fallback_storage
    
    if _fallback_storage is None:
        _fallback_storage = FallbackStorage()
    
    return _fallback_storage