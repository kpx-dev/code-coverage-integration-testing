"""
Coverage file combining module for Lambda Coverage Layer.

This module provides utilities for discovering, downloading, and combining
multiple coverage files from S3 into consolidated reports. It includes
functions for S3 file discovery, download management, and coverage data merging.
"""

import os
import json
import tempfile
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import coverage

from .models import CoverageConfig, CombinerResult
from .s3_uploader import get_s3_config
from .logging_utils import get_logger, performance_timer

# Set up structured logging
logger = get_logger(__name__)


@performance_timer("coverage_files_download")
def download_coverage_files(bucket_name: str, 
                          prefix: str = "coverage/",
                          max_files: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Download coverage files from S3 prefix and return file information.
    
    This function lists all coverage files in the specified S3 bucket and prefix,
    downloads them to temporary local storage, and returns metadata about each file.
    It includes filtering logic to identify valid coverage files and handles
    download errors gracefully.
    
    Args:
        bucket_name (str): S3 bucket name containing coverage files
        prefix (str): S3 key prefix to search for coverage files (default: "coverage/")
        max_files (Optional[int]): Maximum number of files to download (None for unlimited)
        
    Returns:
        List[Dict[str, Any]]: List of dictionaries containing file information:
            - s3_key (str): Original S3 key
            - local_path (str): Path to downloaded file
            - file_size (int): Size of the file in bytes
            - last_modified (datetime): Last modified timestamp from S3
            - function_name (str): Extracted Lambda function name (if available)
            - execution_id (str): Extracted execution ID (if available)
            
    Raises:
        ClientError: If S3 operations fail due to permissions or service issues
        NoCredentialsError: If AWS credentials are not available
        ValueError: If bucket_name is empty or invalid
    """
    if not bucket_name:
        raise ValueError("bucket_name cannot be empty")
    
    if not prefix.endswith('/'):
        prefix += '/'
    
    logger.info("Starting coverage file discovery", 
               bucket=bucket_name, prefix=prefix, max_files=max_files)
    
    try:
        # Initialize S3 client
        s3_client = boto3.client('s3')
        
        # List all objects in the prefix
        downloaded_files = []
        continuation_token = None
        files_processed = 0
        
        while True:
            # Prepare list_objects_v2 parameters
            list_params = {
                'Bucket': bucket_name,
                'Prefix': prefix,
                'MaxKeys': 1000  # Process in batches
            }
            
            if continuation_token:
                list_params['ContinuationToken'] = continuation_token
            
            # List objects
            response = s3_client.list_objects_v2(**list_params)
            
            if 'Contents' not in response:
                logger.info("No coverage files found", bucket=bucket_name, prefix=prefix)
                break
            
            # Process each object
            for obj in response['Contents']:
                s3_key = obj['Key']
                
                # Check if we've reached the maximum file limit
                if max_files and files_processed >= max_files:
                    logger.info("Reached maximum file limit, stopping download", 
                               max_files=max_files, files_processed=files_processed)
                    break
                
                # Filter valid coverage files
                if not _is_valid_coverage_file(s3_key):
                    logger.debug("Skipping non-coverage file", s3_key=s3_key)
                    continue
                
                try:
                    # Download the file
                    file_info = _download_single_file(s3_client, bucket_name, s3_key, obj)
                    if file_info:
                        downloaded_files.append(file_info)
                        files_processed += 1
                        logger.debug("Downloaded coverage file", s3_key=s3_key, 
                                   file_size=file_info.get('file_size', 0))
                    
                except Exception as e:
                    logger.warning("Failed to download coverage file", 
                                  s3_key=s3_key, error=str(e), error_type=type(e).__name__)
                    continue
            
            # Check if there are more objects to process
            if not response.get('IsTruncated', False):
                break
            
            continuation_token = response.get('NextContinuationToken')
            
            # Break if we've reached the file limit
            if max_files and files_processed >= max_files:
                break
        
        logger.info("Successfully downloaded coverage files", 
                   files_downloaded=len(downloaded_files),
                   bucket=bucket_name, prefix=prefix)
        return downloaded_files
        
    except NoCredentialsError:
        logger.error("AWS credentials not available for S3 operations")
        raise
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        if error_code == 'NoSuchBucket':
            logger.error("S3 bucket does not exist", bucket=bucket_name, error_code=error_code)
        elif error_code == 'AccessDenied':
            logger.error("Access denied to S3 bucket", bucket=bucket_name, error_code=error_code)
        else:
            logger.error("S3 client error", bucket=bucket_name, 
                        error_code=error_code, error_message=error_message)
        raise
    except Exception as e:
        logger.error("Unexpected error during coverage file download", 
                    bucket=bucket_name, prefix=prefix,
                    error=str(e), error_type=type(e).__name__)
        raise


def _is_valid_coverage_file(s3_key: str) -> bool:
    """
    Check if an S3 key represents a valid coverage file.
    
    This function implements filtering logic to identify coverage files
    based on naming patterns and file extensions.
    
    Args:
        s3_key (str): S3 object key to validate
        
    Returns:
        bool: True if the key represents a valid coverage file
    """
    # Convert to Path for easier manipulation
    key_path = Path(s3_key)
    
    # Check file extension - coverage files should be .json
    if key_path.suffix.lower() != '.json':
        return False
    
    # Check if filename contains coverage-related patterns
    filename = key_path.name.lower()
    
    # Valid patterns for coverage files
    coverage_patterns = [
        'coverage-',  # Standard coverage files: coverage-function-id.json
        'combined-coverage',  # Combined coverage reports
        'coverage_',  # Alternative naming pattern
    ]
    
    # Check if filename starts with any valid pattern
    if not any(filename.startswith(pattern) for pattern in coverage_patterns):
        return False
    
    # Exclude temporary or backup files
    exclude_patterns = [
        '.tmp',
        '.bak',
        '.backup',
        '~',
    ]
    
    if any(pattern in filename for pattern in exclude_patterns):
        return False
    
    # Additional validation: check if it's not a directory marker
    if s3_key.endswith('/'):
        return False
    
    return True


def _download_single_file(s3_client, bucket_name: str, s3_key: str, obj_metadata: Dict) -> Optional[Dict[str, Any]]:
    """
    Download a single coverage file from S3 to local temporary storage.
    
    Args:
        s3_client: Boto3 S3 client instance
        bucket_name (str): S3 bucket name
        s3_key (str): S3 object key
        obj_metadata (Dict): S3 object metadata from list_objects_v2
        
    Returns:
        Optional[Dict[str, Any]]: File information dictionary or None if download failed
    """
    try:
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(
            mode='wb',
            suffix='.json',
            prefix='coverage_',
            delete=False  # Keep file for processing
        )
        
        # Download file from S3
        s3_client.download_fileobj(bucket_name, s3_key, temp_file)
        temp_file.close()
        
        # Extract metadata from S3 key
        function_name, execution_id = _extract_metadata_from_key(s3_key)
        
        # Validate downloaded file
        if not _validate_coverage_file(temp_file.name):
            logger.warning(f"Downloaded file {s3_key} failed validation, skipping")
            os.unlink(temp_file.name)  # Clean up invalid file
            return None
        
        # Return file information
        return {
            's3_key': s3_key,
            'local_path': temp_file.name,
            'file_size': obj_metadata['Size'],
            'last_modified': obj_metadata['LastModified'],
            'function_name': function_name,
            'execution_id': execution_id
        }
        
    except Exception as e:
        logger.error(f"Error downloading {s3_key}: {str(e)}")
        # Clean up temporary file if it was created
        if 'temp_file' in locals() and hasattr(temp_file, 'name'):
            try:
                os.unlink(temp_file.name)
            except OSError:
                pass
        return None


def _extract_metadata_from_key(s3_key: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract function name and execution ID from S3 key.
    
    Expected key format: coverage/coverage-{function_name}-{execution_id}.json
    
    Args:
        s3_key (str): S3 object key
        
    Returns:
        Tuple[Optional[str], Optional[str]]: (function_name, execution_id)
    """
    try:
        # Get filename without path and extension
        filename = Path(s3_key).stem
        
        # Remove 'coverage-' prefix if present
        if filename.startswith('coverage-'):
            filename = filename[9:]  # Remove 'coverage-' prefix
        
        # For files without execution ID, the entire remaining string is the function name
        # For files with execution ID, split by last hyphen
        if '-' in filename:
            # Try to split by last hyphen - this assumes execution IDs don't contain hyphens
            # but function names might
            parts = filename.rsplit('-', 1)
            if len(parts) == 2:
                function_name, potential_execution_id = parts
                # Check if the last part looks like an execution ID
                # Execution IDs are typically short alphanumeric strings (UUIDs, timestamps, etc.)
                # They usually don't contain common words like "function", "lambda", "handler"
                common_function_words = ['function', 'lambda', 'handler', 'service', 'api', 'worker']
                
                if (potential_execution_id and 
                    len(potential_execution_id) <= 20 and 
                    potential_execution_id.lower() not in common_function_words and
                    # Check if it's mostly alphanumeric (allowing some special chars)
                    len([c for c in potential_execution_id if c.isalnum()]) / len(potential_execution_id) > 0.7):
                    return function_name, potential_execution_id
                else:
                    # Last part doesn't look like execution ID, treat whole thing as function name
                    return filename, None
            else:
                return filename, None
        else:
            # No hyphens, entire string is function name
            return filename, None
            
    except Exception as e:
        logger.debug(f"Could not extract metadata from key {s3_key}: {str(e)}")
        return None, None


def _validate_coverage_file(file_path: str) -> bool:
    """
    Validate that a downloaded file is a valid coverage file.
    
    This function checks the file format and basic structure to ensure
    it's a valid coverage.py JSON report.
    
    Args:
        file_path (str): Path to the downloaded file
        
    Returns:
        bool: True if the file is valid, False otherwise
    """
    try:
        # Check if file exists and is not empty
        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            return False
        
        # Try to parse as JSON
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Check for required coverage.py JSON structure
        required_keys = ['files', 'totals']
        if not all(key in data for key in required_keys):
            logger.debug(f"Coverage file {file_path} missing required keys: {required_keys}")
            return False
        
        # Check that 'files' is a dictionary
        if not isinstance(data['files'], dict):
            logger.debug(f"Coverage file {file_path} has invalid 'files' structure")
            return False
        
        # Check that 'totals' has expected structure
        if not isinstance(data['totals'], dict):
            logger.debug(f"Coverage file {file_path} has invalid 'totals' structure")
            return False
        
        # Basic validation passed
        return True
        
    except json.JSONDecodeError as e:
        logger.debug(f"Coverage file {file_path} is not valid JSON: {str(e)}")
        return False
    except Exception as e:
        logger.debug(f"Error validating coverage file {file_path}: {str(e)}")
        return False


def cleanup_downloaded_files(file_list: List[Dict[str, Any]]) -> None:
    """
    Clean up temporary files downloaded from S3.
    
    This function removes all temporary files created during the download process
    to free up disk space.
    
    Args:
        file_list (List[Dict[str, Any]]): List of file information dictionaries
                                         containing 'local_path' keys
    """
    logger.debug(f"Cleaning up {len(file_list)} temporary coverage files")
    
    for file_info in file_list:
        local_path = file_info.get('local_path')
        if local_path and os.path.exists(local_path):
            try:
                os.unlink(local_path)
                logger.debug(f"Removed temporary file: {local_path}")
            except OSError as e:
                logger.warning(f"Failed to remove temporary file {local_path}: {str(e)}")


def get_coverage_file_stats(file_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate statistics about downloaded coverage files.
    
    Args:
        file_list (List[Dict[str, Any]]): List of downloaded file information
        
    Returns:
        Dict[str, Any]: Statistics including file count, total size, date range, etc.
    """
    if not file_list:
        return {
            'file_count': 0,
            'total_size_bytes': 0,
            'functions': [],
            'date_range': None
        }
    
    # Calculate statistics
    total_size = sum(f['file_size'] for f in file_list)
    functions = list(set(f['function_name'] for f in file_list if f['function_name']))
    
    # Find date range
    dates = [f['last_modified'] for f in file_list]
    date_range = {
        'earliest': min(dates),
        'latest': max(dates)
    } if dates else None
    
    return {
        'file_count': len(file_list),
        'total_size_bytes': total_size,
        'total_size_mb': round(total_size / (1024 * 1024), 2),
        'functions': sorted(functions),
        'function_count': len(functions),
        'date_range': date_range
    }


def merge_coverage_data(file_list: List[Dict[str, Any]]) -> Tuple[str, Dict[str, Any]]:
    """
    Merge multiple coverage files into a single coverage report.
    
    This function uses coverage.py's combine functionality to merge multiple
    coverage data files into a single consolidated report. It handles duplicate
    and overlapping coverage data appropriately and validates file integrity.
    
    Args:
        file_list (List[Dict[str, Any]]): List of downloaded file information
                                         containing 'local_path' keys
        
    Returns:
        Tuple[str, Dict[str, Any]]: (combined_file_path, merge_statistics)
            - combined_file_path: Path to the merged coverage file
            - merge_statistics: Dictionary with merge statistics and metadata
            
    Raises:
        ValueError: If no valid coverage files are provided
        Exception: If coverage merging fails
    """
    if not file_list:
        raise ValueError("No coverage files provided for merging")
    
    logger.info(f"Starting coverage data merge for {len(file_list)} files")
    
    # Filter out files that don't exist or are invalid
    valid_files = []
    skipped_files = []
    
    for file_info in file_list:
        local_path = file_info.get('local_path')
        if not local_path or not os.path.exists(local_path):
            logger.warning(f"Skipping missing file: {file_info.get('s3_key', 'unknown')}")
            skipped_files.append(file_info)
            continue
        
        # Re-validate file to ensure it's still valid
        if not _validate_coverage_file(local_path):
            logger.warning(f"Skipping invalid coverage file: {file_info.get('s3_key', 'unknown')}")
            skipped_files.append(file_info)
            continue
        
        valid_files.append(file_info)
    
    if not valid_files:
        raise ValueError("No valid coverage files found for merging")
    
    logger.info(f"Merging {len(valid_files)} valid files, skipped {len(skipped_files)} invalid files")
    
    try:
        # Create temporary directory for coverage operations
        with tempfile.TemporaryDirectory(prefix='coverage_merge_') as temp_dir:
            # Create coverage instance for combining
            combined_coverage = coverage.Coverage(
                data_file=os.path.join(temp_dir, '.coverage_combined'),
                config_file=False
            )
            
            # Combine all coverage files
            data_files = [f['local_path'] for f in valid_files]
            combined_coverage.combine(data_files, strict=False, keep=False)
            
            # Generate JSON report
            combined_file = tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.json',
                prefix='combined_coverage_',
                delete=False
            )
            combined_file.close()
            
            # Export combined data as JSON
            combined_coverage.json_report(outfile=combined_file.name)
            
            # Calculate merge statistics
            merge_stats = _calculate_merge_statistics(valid_files, skipped_files, combined_file.name)
            
            logger.info(f"Successfully merged coverage data into {combined_file.name}")
            logger.info(f"Combined coverage: {merge_stats['total_coverage_percentage']:.2f}%")
            
            return combined_file.name, merge_stats
            
    except Exception as e:
        logger.error(f"Failed to merge coverage data: {str(e)}")
        raise


def _calculate_merge_statistics(valid_files: List[Dict[str, Any]], 
                               skipped_files: List[Dict[str, Any]], 
                               combined_file_path: str) -> Dict[str, Any]:
    """
    Calculate statistics about the coverage merge operation.
    
    Args:
        valid_files (List[Dict[str, Any]]): List of successfully merged files
        skipped_files (List[Dict[str, Any]]): List of skipped files
        combined_file_path (str): Path to the combined coverage file
        
    Returns:
        Dict[str, Any]: Merge statistics including coverage percentage and file counts
    """
    try:
        # Read combined coverage data to get total coverage
        with open(combined_file_path, 'r', encoding='utf-8') as f:
            combined_data = json.load(f)
        
        # Extract coverage percentage from totals
        totals = combined_data.get('totals', {})
        total_coverage_percentage = totals.get('percent_covered', 0.0)
        
        # Calculate file statistics
        functions_merged = list(set(f.get('function_name') for f in valid_files if f.get('function_name')))
        total_size_merged = sum(f.get('file_size', 0) for f in valid_files)
        
        # Get date range
        dates = [f.get('last_modified') for f in valid_files if f.get('last_modified')]
        date_range = {
            'earliest': min(dates),
            'latest': max(dates)
        } if dates else None
        
        return {
            'files_processed': len(valid_files),
            'files_skipped': len(skipped_files),
            'total_coverage_percentage': total_coverage_percentage,
            'functions_merged': sorted(functions_merged),
            'function_count': len(functions_merged),
            'total_size_bytes': total_size_merged,
            'date_range': date_range,
            'combined_file_size': os.path.getsize(combined_file_path),
            'merge_timestamp': datetime.utcnow()
        }
        
    except Exception as e:
        logger.warning(f"Failed to calculate merge statistics: {str(e)}")
        return {
            'files_processed': len(valid_files),
            'files_skipped': len(skipped_files),
            'total_coverage_percentage': 0.0,
            'functions_merged': [],
            'function_count': 0,
            'total_size_bytes': 0,
            'date_range': None,
            'combined_file_size': 0,
            'merge_timestamp': datetime.utcnow(),
            'error': str(e)
        }


def validate_coverage_files_integrity(file_list: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Validate the integrity of coverage files before merging.
    
    This function performs comprehensive validation of coverage files to ensure
    they can be safely merged. It checks file format, data structure, and
    detects potential corruption issues.
    
    Args:
        file_list (List[Dict[str, Any]]): List of downloaded file information
        
    Returns:
        Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]: (valid_files, invalid_files)
    """
    logger.info(f"Validating integrity of {len(file_list)} coverage files")
    
    valid_files = []
    invalid_files = []
    
    for file_info in file_list:
        local_path = file_info.get('local_path')
        s3_key = file_info.get('s3_key', 'unknown')
        
        if not local_path or not os.path.exists(local_path):
            logger.warning(f"File does not exist: {s3_key}")
            invalid_files.append({**file_info, 'validation_error': 'File not found'})
            continue
        
        try:
            # Basic file validation
            if not _validate_coverage_file(local_path):
                logger.warning(f"Basic validation failed: {s3_key}")
                invalid_files.append({**file_info, 'validation_error': 'Basic validation failed'})
                continue
            
            # Advanced integrity checks
            validation_result = _perform_advanced_validation(local_path)
            if not validation_result['valid']:
                logger.warning(f"Advanced validation failed for {s3_key}: {validation_result['error']}")
                invalid_files.append({**file_info, 'validation_error': validation_result['error']})
                continue
            
            # File passed all validations
            valid_files.append({**file_info, 'validation_status': 'valid'})
            logger.debug(f"File validated successfully: {s3_key}")
            
        except Exception as e:
            logger.error(f"Validation error for {s3_key}: {str(e)}")
            invalid_files.append({**file_info, 'validation_error': f"Validation exception: {str(e)}"})
    
    logger.info(f"Validation complete: {len(valid_files)} valid, {len(invalid_files)} invalid")
    return valid_files, invalid_files


def _perform_advanced_validation(file_path: str) -> Dict[str, Any]:
    """
    Perform advanced validation checks on a coverage file.
    
    Args:
        file_path (str): Path to the coverage file
        
    Returns:
        Dict[str, Any]: Validation result with 'valid' boolean and optional 'error' message
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Check for reasonable data structure
        files_data = data.get('files', {})
        totals_data = data.get('totals', {})
        
        # Validate files section
        if not isinstance(files_data, dict):
            return {'valid': False, 'error': 'Invalid files section structure'}
        
        # Check if files section has reasonable content
        if len(files_data) == 0:
            logger.debug(f"Coverage file {file_path} has no file coverage data")
        
        # Validate totals section
        required_total_keys = ['covered_lines', 'num_statements']
        for key in required_total_keys:
            if key not in totals_data:
                return {'valid': False, 'error': f'Missing required total key: {key}'}
        
        # Check for reasonable numeric values
        covered_lines = totals_data.get('covered_lines', 0)
        num_statements = totals_data.get('num_statements', 0)
        
        if not isinstance(covered_lines, (int, float)) or covered_lines < 0:
            return {'valid': False, 'error': 'Invalid covered_lines value'}
        
        if not isinstance(num_statements, (int, float)) or num_statements < 0:
            return {'valid': False, 'error': 'Invalid num_statements value'}
        
        # Check coverage percentage consistency
        if num_statements > 0:
            calculated_percentage = (covered_lines / num_statements) * 100
            reported_percentage = totals_data.get('percent_covered', calculated_percentage)
            
            # Allow for small floating point differences
            if abs(calculated_percentage - reported_percentage) > 0.1:
                logger.warning(f"Coverage percentage mismatch in {file_path}: "
                             f"calculated={calculated_percentage:.2f}, reported={reported_percentage:.2f}")
        
        return {'valid': True}
        
    except json.JSONDecodeError as e:
        return {'valid': False, 'error': f'JSON decode error: {str(e)}'}
    except Exception as e:
        return {'valid': False, 'error': f'Validation error: {str(e)}'}


def create_merge_report(merge_stats: Dict[str, Any], 
                       valid_files: List[Dict[str, Any]], 
                       invalid_files: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Create a comprehensive report about the coverage merge operation.
    
    Args:
        merge_stats (Dict[str, Any]): Statistics from the merge operation
        valid_files (List[Dict[str, Any]]): List of successfully merged files
        invalid_files (List[Dict[str, Any]]): List of files that couldn't be merged
        
    Returns:
        Dict[str, Any]: Comprehensive merge report
    """
    report = {
        'merge_summary': {
            'total_files_processed': len(valid_files) + len(invalid_files),
            'files_successfully_merged': len(valid_files),
            'files_skipped_or_failed': len(invalid_files),
            'overall_coverage_percentage': merge_stats.get('total_coverage_percentage', 0.0),
            'merge_timestamp': merge_stats.get('merge_timestamp', datetime.utcnow()).isoformat()
        },
        'merged_functions': {
            'function_names': merge_stats.get('functions_merged', []),
            'function_count': merge_stats.get('function_count', 0)
        },
        'file_statistics': {
            'total_size_bytes': merge_stats.get('total_size_bytes', 0),
            'combined_file_size_bytes': merge_stats.get('combined_file_size', 0),
            'date_range': merge_stats.get('date_range')
        },
        'processing_details': {
            'valid_files': [
                {
                    's3_key': f.get('s3_key'),
                    'function_name': f.get('function_name'),
                    'execution_id': f.get('execution_id'),
                    'file_size': f.get('file_size'),
                    'last_modified': f.get('last_modified').isoformat() if f.get('last_modified') else None
                }
                for f in valid_files
            ],
            'invalid_files': [
                {
                    's3_key': f.get('s3_key'),
                    'error': f.get('validation_error', 'Unknown error'),
                    'file_size': f.get('file_size')
                }
                for f in invalid_files
            ]
        }
    }
    
    return report


def upload_combined_report(combined_file_path: str, 
                          bucket_name: str,
                          output_key: str,
                          metadata: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Upload combined coverage report to S3.
    
    This function uploads the merged coverage report back to S3 with appropriate
    metadata and handles upload errors gracefully.
    
    Args:
        combined_file_path (str): Path to the combined coverage file
        bucket_name (str): S3 bucket name for upload
        output_key (str): S3 key for the combined report
        metadata (Optional[Dict[str, str]]): Additional metadata to attach to the S3 object
        
    Returns:
        Dict[str, Any]: Upload result with success status and metadata
        
    Raises:
        ValueError: If file doesn't exist or parameters are invalid
        ClientError: If S3 upload fails
    """
    if not os.path.exists(combined_file_path):
        raise ValueError(f"Combined coverage file does not exist: {combined_file_path}")
    
    if not bucket_name:
        raise ValueError("bucket_name cannot be empty")
    
    if not output_key:
        raise ValueError("output_key cannot be empty")
    
    logger.info(f"Uploading combined coverage report to s3://{bucket_name}/{output_key}")
    
    try:
        # Initialize S3 client
        s3_client = boto3.client('s3')
        
        # Prepare metadata
        upload_metadata = {
            'Content-Type': 'application/json',
            'Content-Encoding': 'utf-8',
            'CoverageType': 'combined-report',
            'UploadTimestamp': datetime.utcnow().isoformat(),
            'GeneratedBy': 'lambda-coverage-layer'
        }
        
        # Add custom metadata if provided
        if metadata:
            upload_metadata.update(metadata)
        
        # Get file size
        file_size = os.path.getsize(combined_file_path)
        
        # Upload file to S3
        with open(combined_file_path, 'rb') as f:
            s3_client.upload_fileobj(
                f,
                bucket_name,
                output_key,
                ExtraArgs={
                    'Metadata': upload_metadata,
                    'ContentType': 'application/json'
                }
            )
        
        logger.info(f"Successfully uploaded combined report: {file_size} bytes to s3://{bucket_name}/{output_key}")
        
        return {
            'success': True,
            'bucket_name': bucket_name,
            'output_key': output_key,
            'file_size': file_size,
            'upload_timestamp': datetime.utcnow(),
            'metadata': upload_metadata
        }
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        logger.error(f"S3 upload failed: {error_code} - {error_message}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during upload: {str(e)}")
        raise


def combine_coverage_files(bucket_name: str,
                          prefix: str = "coverage/",
                          output_key: Optional[str] = None,
                          max_files: Optional[int] = None) -> CombinerResult:
    """
    Main function that orchestrates the entire coverage combining process.
    
    This function downloads coverage files from S3, validates them, merges them
    into a single report, and uploads the combined report back to S3. It provides
    comprehensive error handling and detailed reporting.
    
    Args:
        bucket_name (str): S3 bucket containing coverage files
        prefix (str): S3 prefix to search for coverage files (default: "coverage/")
        output_key (Optional[str]): S3 key for combined report (auto-generated if None)
        max_files (Optional[int]): Maximum number of files to process (None for unlimited)
        
    Returns:
        CombinerResult: Comprehensive result object with success status and details
    """
    logger.info(f"Starting coverage file combination for s3://{bucket_name}/{prefix}")
    
    # Initialize result tracking
    start_time = datetime.utcnow()
    errors = []
    downloaded_files = []
    combined_file_path = None
    
    try:
        # Step 1: Download coverage files from S3
        logger.info("Step 1: Downloading coverage files from S3")
        downloaded_files = download_coverage_files(bucket_name, prefix, max_files)
        
        if not downloaded_files:
            logger.warning("No coverage files found to combine")
            return CombinerResult(
                success=False,
                combined_file_key="",
                files_processed=0,
                files_skipped=0,
                total_coverage_percentage=0.0,
                errors=["No coverage files found in the specified S3 location"]
            )
        
        logger.info(f"Downloaded {len(downloaded_files)} coverage files")
        
        # Step 2: Validate file integrity
        logger.info("Step 2: Validating coverage file integrity")
        valid_files, invalid_files = validate_coverage_files_integrity(downloaded_files)
        
        if not valid_files:
            logger.error("No valid coverage files found after validation")
            return CombinerResult(
                success=False,
                combined_file_key="",
                files_processed=0,
                files_skipped=len(invalid_files),
                total_coverage_percentage=0.0,
                errors=["No valid coverage files found after validation"] + 
                       [f"Invalid file {f.get('s3_key', 'unknown')}: {f.get('validation_error', 'Unknown error')}" 
                        for f in invalid_files[:5]]  # Limit error details
            )
        
        logger.info(f"Validated files: {len(valid_files)} valid, {len(invalid_files)} invalid")
        
        # Step 3: Merge coverage data
        logger.info("Step 3: Merging coverage data")
        combined_file_path, merge_stats = merge_coverage_data(valid_files)
        
        logger.info(f"Successfully merged coverage data: {merge_stats['total_coverage_percentage']:.2f}% coverage")
        
        # Step 4: Generate output key if not provided
        if not output_key:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            output_key = f"{prefix}combined-coverage-{timestamp}.json"
        
        # Step 5: Upload combined report to S3
        logger.info("Step 4: Uploading combined report to S3")
        upload_metadata = {
            'FilesProcessed': str(merge_stats['files_processed']),
            'FilesSkipped': str(merge_stats['files_skipped']),
            'CoveragePercentage': str(merge_stats['total_coverage_percentage']),
            'FunctionCount': str(merge_stats['function_count'])
        }
        
        upload_result = upload_combined_report(
            combined_file_path,
            bucket_name,
            output_key,
            upload_metadata
        )
        
        logger.info(f"Successfully uploaded combined report to s3://{bucket_name}/{output_key}")
        
        # Create comprehensive result
        end_time = datetime.utcnow()
        processing_time = (end_time - start_time).total_seconds()
        
        return CombinerResult(
            success=True,
            combined_file_key=output_key,
            files_processed=merge_stats['files_processed'],
            files_skipped=merge_stats['files_skipped'],
            total_coverage_percentage=merge_stats['total_coverage_percentage'],
            errors=errors
        )
        
    except Exception as e:
        logger.error(f"Coverage combination failed: {str(e)}")
        errors.append(f"Combination failed: {str(e)}")
        
        return CombinerResult(
            success=False,
            combined_file_key=output_key or "",
            files_processed=0,
            files_skipped=len(downloaded_files),
            total_coverage_percentage=0.0,
            errors=errors
        )
        
    finally:
        # Clean up temporary files
        try:
            if downloaded_files:
                cleanup_downloaded_files(downloaded_files)
                logger.debug(f"Cleaned up {len(downloaded_files)} temporary files")
            
            if combined_file_path and os.path.exists(combined_file_path):
                os.unlink(combined_file_path)
                logger.debug(f"Cleaned up combined file: {combined_file_path}")
                
        except Exception as cleanup_error:
            logger.warning(f"Error during cleanup: {str(cleanup_error)}")


def coverage_combiner_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler function for the coverage combiner.
    
    This function serves as the entry point for a Lambda function that combines
    coverage files. It parses the event parameters and orchestrates the combination
    process.
    
    Expected event format:
    {
        "bucket_name": "my-coverage-bucket",
        "prefix": "coverage/",  # optional, defaults to "coverage/"
        "output_key": "coverage/combined-report.json",  # optional, auto-generated if not provided
        "max_files": 100  # optional, no limit if not provided
    }
    
    Args:
        event (Dict[str, Any]): Lambda event containing combination parameters
        context (Any): Lambda context object
        
    Returns:
        Dict[str, Any]: Combination result with success status and details
    """
    logger.info("Coverage combiner Lambda handler invoked")
    logger.debug(f"Event: {json.dumps(event, default=str)}")
    
    try:
        # Extract parameters from event
        bucket_name = event.get('bucket_name')
        if not bucket_name:
            raise ValueError("bucket_name is required in event")
        
        prefix = event.get('prefix', 'coverage/')
        output_key = event.get('output_key')
        max_files = event.get('max_files')
        
        # Validate parameters
        if max_files is not None and (not isinstance(max_files, int) or max_files <= 0):
            raise ValueError("max_files must be a positive integer")
        
        logger.info(f"Starting coverage combination: bucket={bucket_name}, prefix={prefix}, max_files={max_files}")
        
        # Execute combination process
        result = combine_coverage_files(
            bucket_name=bucket_name,
            prefix=prefix,
            output_key=output_key,
            max_files=max_files
        )
        
        # Convert result to dictionary for Lambda response
        response = result.to_dict()
        
        # Add Lambda-specific metadata
        response['lambda_request_id'] = getattr(context, 'aws_request_id', 'unknown')
        response['lambda_function_name'] = getattr(context, 'function_name', 'unknown')
        response['processing_timestamp'] = datetime.utcnow().isoformat()
        
        if result.success:
            logger.info(f"Coverage combination completed successfully: {result.combined_file_key}")
        else:
            logger.error(f"Coverage combination failed: {result.errors}")
        
        return response
        
    except Exception as e:
        logger.error(f"Coverage combiner handler failed: {str(e)}")
        
        # Return error response
        error_result = CombinerResult(
            success=False,
            combined_file_key="",
            files_processed=0,
            files_skipped=0,
            total_coverage_percentage=0.0,
            errors=[f"Handler error: {str(e)}"]
        )
        
        response = error_result.to_dict()
        response['lambda_request_id'] = getattr(context, 'aws_request_id', 'unknown')
        response['lambda_function_name'] = getattr(context, 'function_name', 'unknown')
        response['processing_timestamp'] = datetime.utcnow().isoformat()
        
        return response


# Convenience function for getting S3 configuration
def get_combiner_s3_config() -> CoverageConfig:
    """
    Get S3 configuration for the coverage combiner.
    
    This is a convenience wrapper around get_s3_config() that provides
    configuration specifically for the combiner functionality.
    
    Returns:
        CoverageConfig: Configuration object with S3 settings
        
    Raises:
        ValueError: If required configuration is missing
    """
    try:
        return get_s3_config()
    except Exception as e:
        logger.error(f"Failed to get S3 configuration for combiner: {str(e)}")
        raise ValueError(f"Invalid S3 configuration: {str(e)}")