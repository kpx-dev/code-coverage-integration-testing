"""
Coverage wrapper module for Lambda functions.

This module provides decorators and context managers for automatic coverage tracking.
"""

import os
import time
from typing import Optional
import coverage
from .models import CoverageConfig
from .logging_utils import get_logger, performance_timer, log_lambda_context
from .error_handling import (
    GracefulErrorHandler, 
    graceful_operation, 
    timeout_protection,
    get_fallback_storage,
    ensure_lambda_completion_time,
    CoverageInitializationError
)

# Global variables for configuration caching
_cached_config: Optional[CoverageConfig] = None
_coverage_instance: Optional[coverage.Coverage] = None

# Set up structured logging
logger = get_logger(__name__)


@performance_timer("config_initialization")
def get_cached_config() -> CoverageConfig:
    """
    Get cached configuration or create new one from environment variables.
    
    Returns:
        CoverageConfig: The cached or newly created configuration
        
    Raises:
        ValueError: If required environment variables are missing or invalid
    """
    global _cached_config
    
    if _cached_config is None:
        logger.debug("Creating new coverage configuration from environment")
        _cached_config = CoverageConfig.from_environment()
        _cached_config.validate()
        logger.info("Coverage configuration created", 
                   bucket=_cached_config.s3_bucket, 
                   prefix=_cached_config.s3_prefix,
                   branch_coverage=_cached_config.branch_coverage)
    
    return _cached_config


@performance_timer("coverage_initialization")
@graceful_operation("coverage_initialization", critical=False)
def initialize_coverage() -> Optional[coverage.Coverage]:
    """
    Initialize coverage.py with proper configuration.
    
    This function sets up coverage tracking with the configuration from environment variables.
    It implements caching to optimize repeated calls within the same Lambda execution.
    Uses graceful error handling to ensure Lambda function continues even if coverage fails.
    
    Returns:
        Optional[coverage.Coverage]: The initialized coverage instance, or None if initialization failed
        
    Raises:
        CoverageInitializationError: Only if critical errors occur that should fail the Lambda
    """
    global _coverage_instance
    
    # Return cached instance if already initialized
    if _coverage_instance is not None:
        logger.debug("Returning cached coverage instance")
        return _coverage_instance
    
    try:
        # Get configuration with timeout protection
        with timeout_protection(5.0, "coverage_config_loading"):
            config = get_cached_config()
        
        logger.debug("Initializing coverage with configuration")
        
        # Create coverage configuration dictionary
        coverage_config = {
            'branch': config.branch_coverage,
            'source': ['.'],  # Track coverage for current directory
            'data_file': '/tmp/.coverage',  # Use writable /tmp directory for coverage data file
        }
        
        # Add include patterns if specified
        if config.include_patterns:
            coverage_config['include'] = config.include_patterns
            logger.debug("Coverage include patterns configured", patterns=config.include_patterns)
        
        # Add exclude patterns if specified
        if config.exclude_patterns:
            coverage_config['omit'] = config.exclude_patterns
            logger.debug("Coverage exclude patterns configured", patterns=config.exclude_patterns)
        
        # Initialize coverage instance with timeout protection
        with timeout_protection(10.0, "coverage_instance_creation"):
            _coverage_instance = coverage.Coverage(config_file=False, **coverage_config)
            _coverage_instance.start()
        
        logger.info("Coverage tracking initialized and started", 
                   branch_coverage=config.branch_coverage,
                   include_patterns_count=len(config.include_patterns or []),
                   exclude_patterns_count=len(config.exclude_patterns or []))
        
        return _coverage_instance
        
    except Exception as e:
        logger.error("Failed to initialize coverage", error=str(e), error_type=type(e).__name__)
        # Reset cached instance on failure
        _coverage_instance = None
        
        # For critical configuration errors, we might want to fail the Lambda
        if isinstance(e, ValueError) and "COVERAGE_S3_BUCKET" in str(e):
            logger.critical("Critical configuration error - S3 bucket not configured")
            raise CoverageInitializationError(f"Critical coverage configuration error: {e}") from e
        
        # For other errors, graceful degradation will handle it
        raise


def reset_coverage_cache() -> None:
    """
    Reset the cached configuration and coverage instance.
    
    This function is primarily used for testing purposes to ensure
    clean state between test runs.
    """
    global _cached_config, _coverage_instance
    
    if _coverage_instance is not None:
        try:
            _coverage_instance.stop()
        except Exception as e:
            logger.warning("Error stopping coverage during cache reset", 
                          error=str(e), error_type=type(e).__name__)
    
    _cached_config = None
    _coverage_instance = None
    logger.debug("Coverage cache reset")


def is_coverage_initialized() -> bool:
    """
    Check if coverage tracking is currently initialized and active.
    
    Returns:
        bool: True if coverage is initialized and running, False otherwise
    """
    return _coverage_instance is not None and _coverage_instance._started


@performance_timer("coverage_finalization")
@graceful_operation("coverage_finalization", critical=False)
def finalize_coverage() -> Optional[str]:
    """
    Stop coverage tracking and prepare data for upload.
    
    This function stops the coverage tracking, saves the coverage data to a temporary file,
    and returns the path to the coverage file for upload to S3.
    Uses graceful error handling to ensure Lambda function continues even if finalization fails.
    
    Returns:
        Optional[str]: Path to the coverage data file, or None if coverage wasn't initialized or failed
    """
    global _coverage_instance
    
    if _coverage_instance is None:
        logger.warning("Attempted to finalize coverage but no coverage instance exists")
        return None
    
    try:
        # Stop coverage tracking with timeout protection
        with timeout_protection(5.0, "coverage_stop"):
            _coverage_instance.stop()
        
        logger.debug("Coverage tracking stopped")
        
        # Save coverage data to temporary file
        import tempfile
        import uuid
        
        # Create unique filename for this execution
        execution_id = str(uuid.uuid4())[:8]
        function_name = os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'unknown')
        coverage_filename = f"coverage-{function_name}-{execution_id}.json"
        
        # Use Lambda's /tmp directory for temporary files
        coverage_file_path = os.path.join('/tmp', coverage_filename)
        
        # Save coverage data in JSON format with timeout protection
        with timeout_protection(10.0, "coverage_json_report"):
            _coverage_instance.json_report(outfile=coverage_file_path)
        
        # Verify file was created and get size
        if not os.path.exists(coverage_file_path):
            logger.error("Coverage file was not created", expected_path=coverage_file_path)
            return None
        
        file_size = os.path.getsize(coverage_file_path)
        
        # Basic validation - ensure file is not empty
        if file_size == 0:
            logger.error("Coverage file is empty", file_path=coverage_file_path)
            return None
        
        logger.info("Coverage data saved to temporary file", 
                   file_path=coverage_file_path,
                   file_size_bytes=file_size,
                   execution_id=execution_id,
                   function_name=function_name)
        
        return coverage_file_path
        
    except Exception as e:
        logger.error("Failed to finalize coverage", 
                    error=str(e), error_type=type(e).__name__)
        # Graceful degradation - don't fail the Lambda
        return None
    finally:
        # Reset the coverage instance since it's been stopped
        _coverage_instance = None


class CoverageContext:
    """
    Context manager for manual coverage control.
    
    This context manager allows developers to manually control when coverage
    tracking starts and stops within their Lambda function.
    
    Example:
        def lambda_handler(event, context):
            with CoverageContext():
                # Your code here will be tracked for coverage
                return {"statusCode": 200}
    """
    
    def __init__(self):
        """Initialize the coverage context manager."""
        self.coverage_file_path: Optional[str] = None
        self.upload_task: Optional[object] = None  # Will hold asyncio task if implemented
        self.coverage_initialized: bool = False
    
    def __enter__(self):
        """
        Enter the coverage context and start tracking.
        
        Returns:
            CoverageContext: Self for chaining
        """
        with GracefulErrorHandler("coverage_context_enter", critical=False) as handler:
            coverage_instance = initialize_coverage()
            self.coverage_initialized = coverage_instance is not None
            
            if self.coverage_initialized:
                logger.debug("Coverage context entered - tracking started")
            else:
                logger.warning("Coverage context entered but tracking not available")
        
        if handler.error_occurred:
            logger.warning("Coverage context initialization failed gracefully", 
                          error_details=handler.error_details)
            self.coverage_initialized = False
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit the coverage context and finalize tracking.
        
        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred  
            exc_tb: Exception traceback if an exception occurred
        """
        # Only proceed if coverage was successfully initialized
        if not self.coverage_initialized:
            logger.debug("Coverage context exit - no coverage to finalize")
            return False
        
        upload_success = False
        fallback_used = False
        
        # Finalize coverage with graceful error handling
        with GracefulErrorHandler("coverage_context_finalize", critical=False) as finalize_handler:
            self.coverage_file_path = finalize_coverage()
        
        if finalize_handler.error_occurred or not self.coverage_file_path:
            logger.warning("Coverage finalization failed in context manager", 
                          error_details=finalize_handler.error_details if finalize_handler.error_occurred else None)
            return False
        
        # Attempt S3 upload with fallback
        with GracefulErrorHandler("coverage_context_s3_upload", critical=False) as upload_handler:
            from .s3_uploader import upload_coverage_file
            
            s3_key = upload_coverage_file(self.coverage_file_path)
            if s3_key:
                logger.debug("Coverage data uploaded to S3", s3_key=s3_key)
                upload_success = True
        
        # Use fallback storage if S3 upload failed
        if not upload_success:
            with GracefulErrorHandler("coverage_context_fallback", critical=False) as fallback_handler:
                import time
                fallback_storage = get_fallback_storage()
                
                metadata = {
                    'context_manager': True,
                    'timestamp': time.time(),
                    'file_size': os.path.getsize(self.coverage_file_path),
                    'upload_failed': True,
                    'had_exception': exc_type is not None
                }
                
                fallback_path = fallback_storage.store_coverage_file(self.coverage_file_path, metadata)
                logger.info("Coverage data stored in fallback storage", 
                           fallback_path=fallback_path)
                fallback_used = True
            
            if fallback_handler.error_occurred:
                logger.error("Both S3 upload and fallback storage failed in context manager", 
                            s3_error=upload_handler.error_details if upload_handler.error_occurred else None,
                            fallback_error=fallback_handler.error_details)
        
        # Clean up temporary file
        with GracefulErrorHandler("coverage_context_cleanup", critical=False):
            if self.coverage_file_path and os.path.exists(self.coverage_file_path):
                os.remove(self.coverage_file_path)
                logger.debug("Temporary coverage file removed", 
                           file_path=self.coverage_file_path)
        
        logger.debug("Coverage context exit completed", 
                    upload_success=upload_success,
                    fallback_used=fallback_used,
                    had_exception=exc_type is not None)
        
        # Return False to propagate any exceptions from the with block
        return False


def coverage_handler(func):
    """
    Decorator that wraps Lambda handlers with coverage tracking.
    
    This decorator automatically initializes coverage tracking when the Lambda
    function starts and finalizes/uploads coverage data when it completes.
    Includes comprehensive error handling and fallback mechanisms.
    
    Args:
        func: The Lambda handler function to wrap
        
    Returns:
        function: The wrapped Lambda handler function
        
    Example:
        @coverage_handler
        def lambda_handler(event, context):
            # Your Lambda code here
            return {"statusCode": 200}
    """
    import functools
    import time
    
    @functools.wraps(func)
    def wrapper(event, context):
        """
        Wrapper function that handles coverage tracking with graceful error handling.
        
        Args:
            event: Lambda event object
            context: Lambda context object
            
        Returns:
            Any: The result from the original Lambda handler
        """
        start_time = time.time()
        coverage_file_path = None
        coverage_initialized = False
        
        # Log Lambda context information
        with GracefulErrorHandler("lambda_context_logging", critical=False):
            log_lambda_context(context)
            
            # Set request ID for this execution
            if hasattr(context, 'aws_request_id'):
                logger.set_request_id(context.aws_request_id)
        
        # Initialize coverage tracking with graceful error handling
        with GracefulErrorHandler("coverage_initialization", critical=False):
            coverage_instance = initialize_coverage()
            coverage_initialized = coverage_instance is not None
            
            if coverage_initialized:
                logger.debug("Coverage tracking started for Lambda handler", 
                            function_name=func.__name__)
            else:
                logger.warning("Coverage tracking not available for this execution", 
                              function_name=func.__name__)
        
        try:
            # Execute the original Lambda handler
            result = func(event, context)
            
            execution_time = (time.time() - start_time) * 1000
            logger.info("Lambda handler execution completed", 
                       function_name=func.__name__,
                       execution_time_ms=execution_time,
                       coverage_enabled=coverage_initialized)
            
            return result
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error("Error in Lambda handler execution", 
                        function_name=func.__name__,
                        execution_time_ms=execution_time,
                        coverage_enabled=coverage_initialized,
                        error=str(e), error_type=type(e).__name__)
            # Re-raise the exception to maintain normal Lambda error handling
            raise
            
        finally:
            # Always try to finalize and upload coverage, even if handler failed
            # Only proceed if coverage was successfully initialized
            if coverage_initialized:
                _handle_coverage_finalization(func.__name__, context, start_time)
    
    return wrapper


def _handle_coverage_finalization(function_name: str, context, start_time: float):
    """
    Handle coverage finalization with comprehensive error handling and fallback mechanisms.
    
    Args:
        function_name: Name of the Lambda function
        context: Lambda context object
        start_time: Start time of the Lambda execution
    """
    coverage_file_path = None
    fallback_used = False
    
    # Check if we have enough time remaining for coverage operations
    if not ensure_lambda_completion_time(context, min_buffer_seconds=3.0):
        logger.warning("Insufficient time remaining for coverage finalization", 
                      function_name=function_name)
        return
    
    # Finalize coverage with graceful error handling
    with GracefulErrorHandler("coverage_finalization", critical=False) as finalize_handler:
        coverage_file_path = finalize_coverage()
    
    if finalize_handler.error_occurred:
        logger.warning("Coverage finalization failed, skipping upload", 
                      function_name=function_name,
                      error_details=finalize_handler.error_details)
        return
    
    if not coverage_file_path:
        logger.warning("No coverage file generated", function_name=function_name)
        return
    
    # Attempt S3 upload with fallback to local storage
    upload_success = False
    
    # Check remaining time before upload
    if ensure_lambda_completion_time(context, min_buffer_seconds=2.0):
        with GracefulErrorHandler("s3_upload", critical=False) as upload_handler:
            from .s3_uploader import upload_coverage_file
            
            upload_start = time.time()
            s3_key = upload_coverage_file(coverage_file_path)
            upload_time = (time.time() - upload_start) * 1000
            
            if s3_key:
                file_size = os.path.getsize(coverage_file_path)
                logger.info("Coverage data uploaded successfully to S3", 
                           function_name=function_name,
                           s3_key=s3_key,
                           file_size_bytes=file_size,
                           upload_time_ms=upload_time)
                upload_success = True
        
        if upload_handler.error_occurred:
            logger.warning("S3 upload failed, attempting fallback storage", 
                          function_name=function_name,
                          error_details=upload_handler.error_details)
    else:
        logger.warning("Insufficient time for S3 upload, using fallback storage", 
                      function_name=function_name)
    
    # Use fallback storage if S3 upload failed or time is insufficient
    if not upload_success:
        with GracefulErrorHandler("fallback_storage", critical=False) as fallback_handler:
            fallback_storage = get_fallback_storage()
            
            # Prepare metadata for fallback storage
            metadata = {
                'function_name': function_name,
                'timestamp': time.time(),
                'execution_time_ms': (time.time() - start_time) * 1000,
                'file_size': os.path.getsize(coverage_file_path),
                'upload_failed': True,
                'lambda_request_id': getattr(context, 'aws_request_id', 'unknown')
            }
            
            fallback_path = fallback_storage.store_coverage_file(coverage_file_path, metadata)
            logger.info("Coverage data stored in fallback storage", 
                       function_name=function_name,
                       fallback_path=fallback_path,
                       file_size_bytes=metadata['file_size'])
            fallback_used = True
        
        if fallback_handler.error_occurred:
            logger.error("Both S3 upload and fallback storage failed", 
                        function_name=function_name,
                        s3_error=upload_handler.error_details if 'upload_handler' in locals() else None,
                        fallback_error=fallback_handler.error_details)
    
    # Clean up temporary file
    with GracefulErrorHandler("temp_file_cleanup", critical=False):
        if os.path.exists(coverage_file_path):
            os.remove(coverage_file_path)
            logger.debug("Temporary coverage file removed", 
                        file_path=coverage_file_path)
    
    # Log final status
    logger.info("Coverage processing completed", 
               function_name=function_name,
               s3_upload_success=upload_success,
               fallback_used=fallback_used,
               total_time_ms=(time.time() - start_time) * 1000)