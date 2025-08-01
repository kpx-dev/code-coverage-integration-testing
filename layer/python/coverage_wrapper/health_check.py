"""
Health check module for Lambda Coverage Layer.

This module provides health check endpoint functionality for Lambda functions
using the coverage layer. It includes functions to check coverage status,
layer information, and generate structured health responses.
"""

import os
from datetime import datetime
from typing import Dict, Any, Optional

from .models import HealthCheckResponse
from .wrapper import is_coverage_initialized, get_cached_config
from .logging_utils import get_logger, performance_timer

# Layer version - fallback if __version__ is not available
try:
    from . import __version__
except ImportError:
    __version__ = "unknown"

# Set up structured logging
logger = get_logger(__name__)


@performance_timer("coverage_status_check")
def get_coverage_status() -> Dict[str, Any]:
    """
    Check coverage initialization state and return status information.
    
    This function checks if coverage tracking is properly initialized and active,
    and returns detailed status information including any errors encountered.
    
    Returns:
        Dict[str, Any]: Dictionary containing coverage status information with keys:
            - enabled (bool): Whether coverage is currently enabled/initialized
            - active (bool): Whether coverage tracking is currently running
            - config_valid (bool): Whether the coverage configuration is valid
            - errors (List[str]): List of any errors encountered
    """
    status = {
        'enabled': False,
        'active': False,
        'config_valid': False,
        'errors': []
    }
    
    try:
        # Check if coverage is currently initialized and running
        status['active'] = is_coverage_initialized()
        logger.debug("Coverage active status checked", active=status['active'])
        
        # Try to get and validate configuration
        try:
            config = get_cached_config()
            config.validate()
            status['config_valid'] = True
            status['enabled'] = True
            logger.debug("Coverage configuration is valid", 
                        bucket=config.s3_bucket,
                        prefix=config.s3_prefix)
        except ValueError as e:
            error_msg = f"Configuration error: {str(e)}"
            status['errors'].append(error_msg)
            logger.warning("Coverage configuration invalid", 
                          error=str(e), error_type=type(e).__name__)
        except Exception as e:
            error_msg = f"Configuration check failed: {str(e)}"
            status['errors'].append(error_msg)
            logger.error("Error checking coverage configuration", 
                        error=str(e), error_type=type(e).__name__)
        
    except Exception as e:
        error_msg = f"Coverage status check failed: {str(e)}"
        status['errors'].append(error_msg)
        logger.error("Error checking coverage status", 
                    error=str(e), error_type=type(e).__name__)
    
    logger.debug("Coverage status check completed", 
                enabled=status['enabled'],
                active=status['active'],
                config_valid=status['config_valid'],
                error_count=len(status['errors']))
    
    return status


@performance_timer("layer_info_collection")
def get_layer_info() -> Dict[str, Any]:
    """
    Return layer version and configuration details.
    
    This function retrieves information about the coverage layer including
    version, configuration settings, and environment details.
    
    Returns:
        Dict[str, Any]: Dictionary containing layer information with keys:
            - version (str): Layer version
            - python_version (str): Python runtime version
            - function_name (str): Lambda function name (if available)
            - s3_config (Dict): S3 configuration details (sanitized)
            - environment_vars (Dict): Relevant environment variables (sanitized)
    """
    import sys
    
    layer_info = {
        'version': __version__,
        'python_version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        'function_name': os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'unknown'),
        's3_config': {},
        'environment_vars': {}
    }
    
    logger.debug("Collecting layer information", 
                version=__version__,
                python_version=layer_info['python_version'],
                function_name=layer_info['function_name'])
    
    try:
        # Get S3 configuration (sanitized for security)
        config = get_cached_config()
        layer_info['s3_config'] = {
            'bucket': config.s3_bucket,
            'prefix': config.s3_prefix,
            'upload_timeout': config.upload_timeout,
            'branch_coverage': config.branch_coverage,
            'has_include_patterns': config.include_patterns is not None,
            'has_exclude_patterns': config.exclude_patterns is not None
        }
        
        # Include pattern counts for debugging without exposing actual patterns
        if config.include_patterns:
            layer_info['s3_config']['include_pattern_count'] = len(config.include_patterns)
        if config.exclude_patterns:
            layer_info['s3_config']['exclude_pattern_count'] = len(config.exclude_patterns)
            
        logger.debug("Layer S3 configuration retrieved successfully", 
                    bucket=config.s3_bucket,
                    prefix=config.s3_prefix,
                    has_include_patterns=config.include_patterns is not None,
                    has_exclude_patterns=config.exclude_patterns is not None)
        
    except Exception as e:
        logger.warning("Could not retrieve S3 configuration", 
                      error=str(e), error_type=type(e).__name__)
        layer_info['s3_config'] = {'error': 'Configuration not available'}
    
    # Add relevant environment variables (sanitized)
    env_vars_to_check = [
        'AWS_LAMBDA_FUNCTION_NAME',
        'AWS_LAMBDA_FUNCTION_VERSION',
        'AWS_LAMBDA_LOG_GROUP_NAME',
        'AWS_LAMBDA_LOG_STREAM_NAME',
        'AWS_REGION',
        'COVERAGE_S3_BUCKET',
        'COVERAGE_S3_PREFIX',
        'COVERAGE_UPLOAD_TIMEOUT',
        'COVERAGE_BRANCH_COVERAGE'
    ]
    
    env_vars_found = 0
    for var in env_vars_to_check:
        value = os.environ.get(var)
        if value is not None:
            env_vars_found += 1
            # Sanitize sensitive information
            if 'BUCKET' in var:
                # Only show first and last 3 characters of bucket name for security
                if len(value) > 6:
                    layer_info['environment_vars'][var] = f"{value[:3]}...{value[-3:]}"
                else:
                    layer_info['environment_vars'][var] = "***"
            else:
                layer_info['environment_vars'][var] = value
    
    logger.debug("Environment variables collected", 
                env_vars_found=env_vars_found,
                total_checked=len(env_vars_to_check))
    
    return layer_info


@performance_timer("health_check_handler")
def health_check_handler(event: Optional[Dict[str, Any]] = None, 
                        context: Optional[Any] = None) -> Dict[str, Any]:
    """
    Lambda handler function that returns structured health status.
    
    This function can be used as a Lambda handler to provide health check
    functionality. It combines coverage status and layer information into
    a comprehensive health response.
    
    Args:
        event (Optional[Dict[str, Any]]): Lambda event object (unused)
        context (Optional[Any]): Lambda context object (unused)
        
    Returns:
        Dict[str, Any]: Health check response dictionary containing:
            - status (str): Overall health status ("healthy" or "unhealthy")
            - coverage_enabled (bool): Whether coverage is enabled
            - layer_version (str): Version of the coverage layer
            - s3_config (Dict): S3 configuration details
            - timestamp (str): ISO timestamp of the health check
            - errors (List[str]): Any errors encountered
            - details (Dict): Additional diagnostic information
    """
    # Suppress unused parameter warnings - these are required for Lambda handler signature
    _ = event
    _ = context
    
    logger.info("Health check handler invoked")
    
    try:
        # Get coverage status
        coverage_status = get_coverage_status()
        
        # Get layer information
        layer_info = get_layer_info()
        
        # Determine overall health status
        is_healthy = (
            coverage_status['config_valid'] and 
            len(coverage_status['errors']) == 0 and
            'error' not in layer_info['s3_config']
        )
        
        # Collect all errors
        all_errors = coverage_status['errors'].copy()
        if 'error' in layer_info['s3_config']:
            all_errors.append(layer_info['s3_config']['error'])
        
        # Create health check response
        health_response = HealthCheckResponse(
            status="healthy" if is_healthy else "unhealthy",
            coverage_enabled=coverage_status['enabled'],
            layer_version=layer_info['version'],
            s3_config=layer_info['s3_config'],
            timestamp=datetime.utcnow(),
            errors=all_errors if all_errors else None
        )
        
        # Convert to dictionary and add additional details
        response_dict = health_response.to_dict()
        response_dict['details'] = {
            'coverage_active': coverage_status['active'],
            'python_version': layer_info['python_version'],
            'function_name': layer_info['function_name'],
            'environment_vars': layer_info['environment_vars']
        }
        
        # Log the health check result
        if is_healthy:
            logger.info("Health check completed successfully - system healthy",
                       coverage_enabled=coverage_status['enabled'],
                       coverage_active=coverage_status['active'])
        else:
            logger.warning("Health check completed - system unhealthy", 
                          error_count=len(all_errors),
                          errors=all_errors,
                          coverage_enabled=coverage_status['enabled'])
        
        return response_dict
        
    except Exception as e:
        logger.error("Health check handler failed", 
                    error=str(e), error_type=type(e).__name__)
        
        # Return error response
        error_response = HealthCheckResponse(
            status="unhealthy",
            coverage_enabled=False,
            layer_version=__version__,
            s3_config={'error': 'Health check failed'},
            timestamp=datetime.utcnow(),
            errors=[f"Health check handler error: {str(e)}"]
        )
        
        return error_response.to_dict()


@performance_timer("health_status_object_creation")
def get_health_status() -> HealthCheckResponse:
    """
    Get health status as a HealthCheckResponse object.
    
    This is a convenience function that returns the health status as a
    structured HealthCheckResponse object instead of a dictionary.
    
    Returns:
        HealthCheckResponse: Structured health check response object
    """
    try:
        response_dict = health_check_handler()
        
        # Convert back to HealthCheckResponse object
        return HealthCheckResponse(
            status=response_dict['status'],
            coverage_enabled=response_dict['coverage_enabled'],
            layer_version=response_dict['layer_version'],
            s3_config=response_dict['s3_config'],
            timestamp=datetime.fromisoformat(response_dict['timestamp'].replace('Z', '+00:00')),
            errors=response_dict.get('errors')
        )
        
    except Exception as e:
        logger.error("Error getting health status", 
                    error=str(e), error_type=type(e).__name__)
        return HealthCheckResponse(
            status="unhealthy",
            coverage_enabled=False,
            layer_version=__version__,
            s3_config={'error': 'Status check failed'},
            timestamp=datetime.utcnow(),
            errors=[f"Status check error: {str(e)}"]
        )