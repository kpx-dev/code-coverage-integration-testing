"""
S3 upload utilities for coverage files.

This module handles uploading coverage files to S3 with proper naming and error handling.
"""

import os
from datetime import datetime
from typing import Optional

from .models import CoverageConfig
from .logging_utils import get_logger, performance_timer
from .error_handling import GracefulErrorHandler, timeout_protection, S3UploadError

logger = get_logger(__name__)


@performance_timer("s3_config_parsing")
def get_s3_config() -> CoverageConfig:
    """
    Parse S3 settings from environment variables.
    
    Returns:
        CoverageConfig: Configuration object with S3 settings
        
    Raises:
        ValueError: If required environment variables are missing or invalid
    """
    try:
        config = CoverageConfig.from_environment()
        config.validate()
        logger.debug("S3 configuration parsed successfully", 
                    bucket=config.s3_bucket, prefix=config.s3_prefix)
        return config
    except ValueError as e:
        logger.error("Invalid S3 configuration", error=str(e), error_type=type(e).__name__)
        raise ValueError(f"Invalid S3 configuration: {e}") from e
    except Exception as e:
        logger.error("Error parsing S3 configuration", error=str(e), error_type=type(e).__name__)
        raise ValueError(f"Failed to parse S3 configuration: {e}") from e


@performance_timer("s3_key_generation")
def generate_s3_key(
    function_name: Optional[str] = None,
    execution_id: Optional[str] = None,
    prefix: str = "coverage/",
    timestamp: Optional[datetime] = None
) -> str:
    """
    Create unique S3 keys with timestamp and function name.
    
    Args:
        function_name: Lambda function name (defaults to AWS_LAMBDA_FUNCTION_NAME env var)
        execution_id: Lambda execution ID (defaults to AWS_LAMBDA_LOG_STREAM_NAME env var)
        prefix: S3 key prefix (defaults to "coverage/")
        timestamp: Timestamp for the key (defaults to current time)
        
    Returns:
        str: Unique S3 key in format: {prefix}{function_name}/{timestamp}_{execution_id}.coverage
        
    Raises:
        ValueError: If function_name cannot be determined
    """
    # Get function name from parameter or environment
    if function_name is None:
        function_name = os.environ.get('AWS_LAMBDA_FUNCTION_NAME')
    
    if not function_name:
        logger.error("Function name not available for S3 key generation")
        raise ValueError("Function name must be provided or AWS_LAMBDA_FUNCTION_NAME must be set")
    
    # Get execution ID from parameter or environment
    if execution_id is None:
        execution_id = os.environ.get('AWS_LAMBDA_LOG_STREAM_NAME', 'unknown')
    
    # Use current timestamp if not provided
    if timestamp is None:
        from datetime import timezone
        timestamp = datetime.now(timezone.utc)
    
    # Format timestamp as ISO string with milliseconds, safe for S3 keys
    timestamp_str = timestamp.strftime('%Y%m%d_%H%M%S_%f')[:-3]  # Remove last 3 digits for milliseconds
    
    # Ensure prefix ends with /
    if prefix and not prefix.endswith('/'):
        prefix += '/'
    
    # Clean function name and execution ID for S3 key safety
    clean_function_name = _sanitize_s3_key_component(function_name)
    clean_execution_id = _sanitize_s3_key_component(execution_id)
    
    # Generate the S3 key
    s3_key = f"{prefix}{clean_function_name}/{timestamp_str}_{clean_execution_id}.coverage"
    
    logger.debug("S3 key generated", 
                s3_key=s3_key,
                function_name=clean_function_name,
                execution_id=clean_execution_id,
                timestamp=timestamp_str)
    
    return s3_key


def _sanitize_s3_key_component(component: str) -> str:
    """
    Sanitize a string component for use in S3 keys.
    
    Args:
        component: String component to sanitize
        
    Returns:
        str: Sanitized component safe for S3 keys
    """
    # Replace problematic characters with underscores
    # S3 keys should avoid: spaces, special chars that might cause issues
    import re
    # Keep ASCII alphanumeric, hyphens, dots, and underscores; replace everything else with underscores
    sanitized = re.sub(r'[^a-zA-Z0-9\-._]', '_', component)
    
    # Remove leading/trailing underscores and ensure not empty
    sanitized = sanitized.strip('_')
    if not sanitized:
        sanitized = 'unknown'
    
    return sanitized


@performance_timer("s3_upload")
def upload_coverage_file(
    coverage_file_path: str,
    s3_key: Optional[str] = None,
    config: Optional[CoverageConfig] = None,
    timeout_seconds: float = 30.0
) -> Optional[str]:
    """
    Upload coverage file to S3 with error handling and retry logic.
    
    Args:
        coverage_file_path: Path to the coverage file to upload
        s3_key: S3 key for the file (auto-generated if not provided)
        config: S3 configuration (loaded from environment if not provided)
        timeout_seconds: Maximum time allowed for the upload operation
        
    Returns:
        Optional[str]: S3 key of the uploaded file, or None if upload failed
        
    Raises:
        ValueError: If configuration is invalid or file doesn't exist
        S3UploadError: If upload fails after all retry attempts (only for critical errors)
    """
    import boto3
    import time
    from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError
    
    # Use graceful error handling for the entire upload process
    with GracefulErrorHandler("s3_upload_operation", critical=False) as upload_handler:
        # Validate input file exists
        if not os.path.exists(coverage_file_path):
            logger.error("Coverage file not found", file_path=coverage_file_path)
            raise ValueError(f"Coverage file not found: {coverage_file_path}")
        
        # Get file size for metrics
        file_size = os.path.getsize(coverage_file_path)
        
        # Basic file validation
        if file_size == 0:
            logger.error("Coverage file is empty", file_path=coverage_file_path)
            raise ValueError(f"Coverage file is empty: {coverage_file_path}")
        
        # Get configuration with timeout protection
        with timeout_protection(5.0, "s3_config_loading"):
            if config is None:
                config = get_s3_config()
        
        # Generate S3 key if not provided
        with timeout_protection(2.0, "s3_key_generation"):
            if s3_key is None:
                s3_key = generate_s3_key(prefix=config.s3_prefix)
        
        logger.debug("Starting S3 upload", 
                    file_path=coverage_file_path,
                    file_size_bytes=file_size,
                    s3_bucket=config.s3_bucket,
                    s3_key=s3_key,
                    timeout_seconds=timeout_seconds)
        
        # Create S3 client with timeout protection
        with timeout_protection(5.0, "s3_client_creation"):
            try:
                s3_client = boto3.client('s3')
            except (NoCredentialsError, PartialCredentialsError) as e:
                logger.error("AWS credentials not available for S3 upload", 
                            error=str(e), error_type=type(e).__name__)
                raise S3UploadError(f"AWS credentials not available: {e}") from e
    
        # Upload with retry logic and timeout protection
        max_retries = 3
        base_delay = 1.0  # Base delay in seconds
        
        with timeout_protection(timeout_seconds, "s3_upload_with_retries"):
            for attempt in range(max_retries):
                try:
                    logger.info("Attempting S3 upload", 
                               bucket=config.s3_bucket,
                               key=s3_key,
                               attempt=attempt + 1,
                               max_attempts=max_retries,
                               file_size_bytes=file_size)
                    
                    # Upload file
                    s3_client.upload_file(
                        coverage_file_path,
                        config.s3_bucket,
                        s3_key,
                        ExtraArgs={
                            'ServerSideEncryption': 'AES256',
                            'ContentType': 'application/octet-stream'
                        }
                    )
                    
                    logger.info("S3 upload completed successfully", 
                               bucket=config.s3_bucket,
                               key=s3_key,
                               file_size_bytes=file_size,
                               attempts_used=attempt + 1)
                    return s3_key
                
                except ClientError as e:
                    error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                    error_message = e.response.get('Error', {}).get('Message', str(e))
                    
                    logger.warning("S3 upload attempt failed with ClientError", 
                                  attempt=attempt + 1,
                                  max_attempts=max_retries,
                                  error_code=error_code,
                                  error_message=error_message,
                                  bucket=config.s3_bucket,
                                  key=s3_key)
                    
                    # Don't retry for certain error types
                    if error_code in ['NoSuchBucket', 'AccessDenied', 'InvalidBucketName']:
                        logger.error("Non-retryable S3 error encountered", 
                                   error_code=error_code,
                                   error_message=error_message,
                                   bucket=config.s3_bucket)
                        raise S3UploadError(f"S3 upload failed: {error_code} - {error_message}") from e
                    
                    # Retry for other errors
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)  # Exponential backoff
                        logger.info("Retrying S3 upload after delay", 
                                   delay_seconds=delay,
                                   next_attempt=attempt + 2)
                        time.sleep(delay)
                    else:
                        logger.error("S3 upload failed after all retry attempts", 
                                   max_attempts=max_retries,
                                   error_code=error_code,
                                   error_message=error_message)
                        raise S3UploadError(f"S3 upload failed after {max_retries} attempts: {error_code} - {error_message}") from e
                        
                except Exception as e:
                    logger.warning("S3 upload attempt failed with unexpected error", 
                                  attempt=attempt + 1,
                                  max_attempts=max_retries,
                                  error=str(e),
                                  error_type=type(e).__name__)
                    
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)  # Exponential backoff
                        logger.info("Retrying S3 upload after delay", 
                                   delay_seconds=delay,
                                   next_attempt=attempt + 2)
                        time.sleep(delay)
                    else:
                        logger.error("S3 upload failed after all retry attempts", 
                                   max_attempts=max_retries,
                                   error=str(e),
                                   error_type=type(e).__name__)
                        raise S3UploadError(f"S3 upload failed after {max_retries} attempts: {e}") from e
    
    # If we get here, the graceful error handler caught an error
    if upload_handler.error_occurred:
        logger.warning("S3 upload failed gracefully", 
                      error_details=upload_handler.error_details)
        return None
    
    # This shouldn't happen, but just in case
    logger.error("S3 upload completed without returning a result")
    return None


def upload_coverage_file_async(
    coverage_file_path: str,
    s3_key: Optional[str] = None,
    config: Optional[CoverageConfig] = None
) -> None:
    """
    Upload coverage file to S3 asynchronously to minimize Lambda execution time impact.
    
    This function starts the upload in a separate thread and returns immediately.
    The upload will continue in the background.
    
    Args:
        coverage_file_path: Path to the coverage file to upload
        s3_key: S3 key for the file (auto-generated if not provided)
        config: S3 configuration (loaded from environment if not provided)
    """
    import threading
    
    def _upload_worker():
        try:
            result_key = upload_coverage_file(coverage_file_path, s3_key, config)
            logger.debug("Async S3 upload completed successfully", 
                        file_path=coverage_file_path,
                        s3_key=result_key)
        except Exception as e:
            logger.error("Async S3 upload failed", 
                        file_path=coverage_file_path,
                        error=str(e),
                        error_type=type(e).__name__)
    
    # Start upload in background thread
    upload_thread = threading.Thread(target=_upload_worker, daemon=True)
    upload_thread.start()
    
    logger.info("Started async upload of coverage file", 
               file_path=coverage_file_path,
               thread_name=upload_thread.name)