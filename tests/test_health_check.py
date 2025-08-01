"""
Unit tests for the health check module.

This module contains comprehensive tests for health check response generation,
coverage status checking, layer information retrieval, and error conditions.
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from layer.python.coverage_wrapper.health_check import (
    get_coverage_status,
    get_layer_info,
    health_check_handler,
    get_health_status
)
from layer.python.coverage_wrapper.models import HealthCheckResponse, CoverageConfig


class TestGetCoverageStatus:
    """Test cases for get_coverage_status function."""
    
    def test_coverage_status_when_active_and_configured(self):
        """Test coverage status when coverage is active and properly configured."""
        with patch('layer.python.coverage_wrapper.health_check.is_coverage_initialized', return_value=True), \
             patch('layer.python.coverage_wrapper.health_check.get_cached_config') as mock_config:
            
            # Mock valid configuration
            mock_config.return_value = CoverageConfig(s3_bucket='test-bucket')
            
            status = get_coverage_status()
            
            assert status['enabled'] is True
            assert status['active'] is True
            assert status['config_valid'] is True
            assert status['errors'] == []
    
    def test_coverage_status_when_inactive_but_configured(self):
        """Test coverage status when coverage is not active but configuration is valid."""
        with patch('layer.python.coverage_wrapper.health_check.is_coverage_initialized', return_value=False), \
             patch('layer.python.coverage_wrapper.health_check.get_cached_config') as mock_config:
            
            # Mock valid configuration
            mock_config.return_value = CoverageConfig(s3_bucket='test-bucket')
            
            status = get_coverage_status()
            
            assert status['enabled'] is True
            assert status['active'] is False
            assert status['config_valid'] is True
            assert status['errors'] == []
    
    def test_coverage_status_with_configuration_error(self):
        """Test coverage status when configuration is invalid."""
        with patch('layer.python.coverage_wrapper.health_check.is_coverage_initialized', return_value=False), \
             patch('layer.python.coverage_wrapper.health_check.get_cached_config') as mock_config:
            
            # Mock configuration error
            mock_config.side_effect = ValueError("COVERAGE_S3_BUCKET environment variable is required")
            
            status = get_coverage_status()
            
            assert status['enabled'] is False
            assert status['active'] is False
            assert status['config_valid'] is False
            assert len(status['errors']) == 1
            assert "Configuration error" in status['errors'][0]
    
    def test_coverage_status_with_validation_error(self):
        """Test coverage status when configuration validation fails."""
        with patch('layer.python.coverage_wrapper.health_check.is_coverage_initialized', return_value=False), \
             patch('layer.python.coverage_wrapper.health_check.get_cached_config') as mock_config:
            
            # Mock configuration that fails validation
            config = CoverageConfig(s3_bucket='')  # Invalid empty bucket
            mock_config.return_value = config
            
            status = get_coverage_status()
            
            assert status['enabled'] is False
            assert status['active'] is False
            assert status['config_valid'] is False
            assert len(status['errors']) == 1
            assert "Configuration error" in status['errors'][0]
    
    def test_coverage_status_with_unexpected_error(self):
        """Test coverage status when an unexpected error occurs."""
        with patch('layer.python.coverage_wrapper.health_check.is_coverage_initialized') as mock_init:
            
            # Mock unexpected error
            mock_init.side_effect = Exception("Unexpected error")
            
            status = get_coverage_status()
            
            assert status['enabled'] is False
            assert status['active'] is False
            assert status['config_valid'] is False
            assert len(status['errors']) == 1
            assert "Coverage status check failed" in status['errors'][0]


class TestGetLayerInfo:
    """Test cases for get_layer_info function."""
    
    @patch.dict(os.environ, {
        'AWS_LAMBDA_FUNCTION_NAME': 'test-function',
        'AWS_LAMBDA_FUNCTION_VERSION': '1',
        'AWS_REGION': 'us-east-1',
        'COVERAGE_S3_BUCKET': 'test-bucket',
        'COVERAGE_S3_PREFIX': 'coverage/',
        'COVERAGE_UPLOAD_TIMEOUT': '30'
    })
    def test_layer_info_with_valid_config(self):
        """Test layer info retrieval with valid configuration."""
        with patch('layer.python.coverage_wrapper.health_check.get_cached_config') as mock_config:
            
            # Mock valid configuration
            config = CoverageConfig(
                s3_bucket='test-bucket',
                s3_prefix='coverage/',
                upload_timeout=30,
                branch_coverage=True,
                include_patterns=['*.py'],
                exclude_patterns=['test_*.py']
            )
            mock_config.return_value = config
            
            layer_info = get_layer_info()
            
            assert layer_info['version'] == '1.0.0'
            assert 'python_version' in layer_info
            assert layer_info['function_name'] == 'test-function'
            assert layer_info['s3_config']['bucket'] == 'test-bucket'
            assert layer_info['s3_config']['prefix'] == 'coverage/'
            assert layer_info['s3_config']['upload_timeout'] == 30
            assert layer_info['s3_config']['branch_coverage'] is True
            assert layer_info['s3_config']['has_include_patterns'] is True
            assert layer_info['s3_config']['has_exclude_patterns'] is True
            assert layer_info['s3_config']['include_pattern_count'] == 1
            assert layer_info['s3_config']['exclude_pattern_count'] == 1
            
            # Check environment variables
            assert layer_info['environment_vars']['AWS_LAMBDA_FUNCTION_NAME'] == 'test-function'
            assert layer_info['environment_vars']['AWS_REGION'] == 'us-east-1'
            assert 'tes...ket' in layer_info['environment_vars']['COVERAGE_S3_BUCKET']  # Sanitized
    
    def test_layer_info_with_config_error(self):
        """Test layer info retrieval when configuration fails."""
        with patch('layer.python.coverage_wrapper.health_check.get_cached_config') as mock_config:
            
            # Mock configuration error
            mock_config.side_effect = ValueError("Configuration error")
            
            layer_info = get_layer_info()
            
            assert layer_info['version'] == '1.0.0'
            assert 'python_version' in layer_info
            assert layer_info['s3_config'] == {'error': 'Configuration not available'}
    
    @patch.dict(os.environ, {'COVERAGE_S3_BUCKET': 'short'})
    def test_layer_info_bucket_name_sanitization_short(self):
        """Test bucket name sanitization for short bucket names."""
        with patch('layer.python.coverage_wrapper.health_check.get_cached_config') as mock_config:
            
            config = CoverageConfig(s3_bucket='short')
            mock_config.return_value = config
            
            layer_info = get_layer_info()
            
            # Short bucket names should be completely masked
            assert layer_info['environment_vars']['COVERAGE_S3_BUCKET'] == '***'
    
    @patch.dict(os.environ, {'COVERAGE_S3_BUCKET': 'very-long-bucket-name'})
    def test_layer_info_bucket_name_sanitization_long(self):
        """Test bucket name sanitization for long bucket names."""
        with patch('layer.python.coverage_wrapper.health_check.get_cached_config') as mock_config:
            
            config = CoverageConfig(s3_bucket='very-long-bucket-name')
            mock_config.return_value = config
            
            layer_info = get_layer_info()
            
            # Long bucket names should show first and last 3 characters
            assert layer_info['environment_vars']['COVERAGE_S3_BUCKET'] == 'ver...ame'


class TestHealthCheckHandler:
    """Test cases for health_check_handler function."""
    
    def test_health_check_handler_healthy_status(self):
        """Test health check handler when system is healthy."""
        with patch('layer.python.coverage_wrapper.health_check.get_coverage_status') as mock_status, \
             patch('layer.python.coverage_wrapper.health_check.get_layer_info') as mock_info:
            
            # Mock healthy status
            mock_status.return_value = {
                'enabled': True,
                'active': True,
                'config_valid': True,
                'errors': []
            }
            
            mock_info.return_value = {
                'version': '1.0.0',
                'python_version': '3.9.0',
                'function_name': 'test-function',
                's3_config': {
                    'bucket': 'test-bucket',
                    'prefix': 'coverage/'
                },
                'environment_vars': {}
            }
            
            response = health_check_handler()
            
            assert response['status'] == 'healthy'
            assert response['coverage_enabled'] is True
            assert response['layer_version'] == '1.0.0'
            assert response['errors'] == []
            assert 'timestamp' in response
            assert 'details' in response
            assert response['details']['coverage_active'] is True
    
    def test_health_check_handler_unhealthy_status(self):
        """Test health check handler when system is unhealthy."""
        with patch('layer.python.coverage_wrapper.health_check.get_coverage_status') as mock_status, \
             patch('layer.python.coverage_wrapper.health_check.get_layer_info') as mock_info:
            
            # Mock unhealthy status
            mock_status.return_value = {
                'enabled': False,
                'active': False,
                'config_valid': False,
                'errors': ['Configuration error: Missing S3 bucket']
            }
            
            mock_info.return_value = {
                'version': '1.0.0',
                'python_version': '3.9.0',
                'function_name': 'test-function',
                's3_config': {'error': 'Configuration not available'},
                'environment_vars': {}
            }
            
            response = health_check_handler()
            
            assert response['status'] == 'unhealthy'
            assert response['coverage_enabled'] is False
            assert response['layer_version'] == '1.0.0'
            assert len(response['errors']) == 2
            assert 'Configuration error' in response['errors'][0]
            assert 'Configuration not available' in response['errors'][1]
    
    def test_health_check_handler_with_exception(self):
        """Test health check handler when an exception occurs."""
        with patch('layer.python.coverage_wrapper.health_check.get_coverage_status') as mock_status:
            
            # Mock exception
            mock_status.side_effect = Exception("Unexpected error")
            
            response = health_check_handler()
            
            assert response['status'] == 'unhealthy'
            assert response['coverage_enabled'] is False
            assert response['layer_version'] == '1.0.0'
            assert len(response['errors']) == 1
            assert 'Health check handler error' in response['errors'][0]
    
    def test_health_check_handler_ignores_event_and_context(self):
        """Test that health check handler ignores event and context parameters."""
        with patch('layer.python.coverage_wrapper.health_check.get_coverage_status') as mock_status, \
             patch('layer.python.coverage_wrapper.health_check.get_layer_info') as mock_info:
            
            # Mock healthy status
            mock_status.return_value = {
                'enabled': True,
                'active': True,
                'config_valid': True,
                'errors': []
            }
            
            mock_info.return_value = {
                'version': '1.0.0',
                'python_version': '3.9.0',
                'function_name': 'test-function',
                's3_config': {'bucket': 'test-bucket'},
                'environment_vars': {}
            }
            
            # Call with event and context
            event = {'test': 'data'}
            context = MagicMock()
            
            response = health_check_handler(event, context)
            
            assert response['status'] == 'healthy'
            # Verify that the function works regardless of event/context content


class TestGetHealthStatus:
    """Test cases for get_health_status function."""
    
    def test_get_health_status_returns_object(self):
        """Test that get_health_status returns a HealthCheckResponse object."""
        with patch('layer.python.coverage_wrapper.health_check.health_check_handler') as mock_handler:
            
            # Mock handler response
            mock_handler.return_value = {
                'status': 'healthy',
                'coverage_enabled': True,
                'layer_version': '1.0.0',
                's3_config': {'bucket': 'test-bucket'},
                'timestamp': '2024-01-15T10:30:00',
                'errors': None
            }
            
            health_status = get_health_status()
            
            assert isinstance(health_status, HealthCheckResponse)
            assert health_status.status == 'healthy'
            assert health_status.coverage_enabled is True
            assert health_status.layer_version == '1.0.0'
            assert health_status.errors is None
    
    def test_get_health_status_with_exception(self):
        """Test get_health_status when an exception occurs."""
        with patch('layer.python.coverage_wrapper.health_check.health_check_handler') as mock_handler:
            
            # Mock exception
            mock_handler.side_effect = Exception("Handler error")
            
            health_status = get_health_status()
            
            assert isinstance(health_status, HealthCheckResponse)
            assert health_status.status == 'unhealthy'
            assert health_status.coverage_enabled is False
            assert health_status.layer_version == '1.0.0'
            assert len(health_status.errors) == 1
            assert 'Status check error' in health_status.errors[0]


class TestHealthCheckIntegration:
    """Integration tests for health check functionality."""
    
    @patch.dict(os.environ, {
        'COVERAGE_S3_BUCKET': 'test-bucket',
        'AWS_LAMBDA_FUNCTION_NAME': 'test-function'
    })
    def test_health_check_integration_with_real_config(self):
        """Test health check with real configuration parsing."""
        # This test uses real configuration parsing but mocks coverage initialization
        with patch('layer.python.coverage_wrapper.health_check.is_coverage_initialized', return_value=False):
            
            response = health_check_handler()
            
            # Should be healthy since configuration is valid
            assert response['status'] == 'healthy'
            assert response['coverage_enabled'] is True
            assert response['details']['function_name'] == 'test-function'
            assert response['s3_config']['bucket'] == 'test-bucket'
    
    @patch.dict(os.environ, {}, clear=True)
    def test_health_check_integration_missing_config(self):
        """Test health check with missing configuration."""
        # Clear any cached configuration from previous tests
        from layer.python.coverage_wrapper.wrapper import reset_coverage_cache
        reset_coverage_cache()
        
        response = health_check_handler()
        
        # Should be unhealthy due to missing configuration
        assert response['status'] == 'unhealthy'
        assert response['coverage_enabled'] is False
        assert len(response['errors']) > 0
        assert any('COVERAGE_S3_BUCKET' in error for error in response['errors'])


# Test fixtures and utilities
@pytest.fixture
def mock_datetime():
    """Fixture to mock datetime for consistent testing."""
    with patch('layer.python.coverage_wrapper.health_check.datetime') as mock_dt:
        mock_dt.utcnow.return_value = datetime(2024, 1, 15, 10, 30, 0)
        mock_dt.fromisoformat = datetime.fromisoformat
        yield mock_dt


@pytest.fixture
def sample_coverage_config():
    """Fixture providing a sample coverage configuration."""
    return CoverageConfig(
        s3_bucket='test-bucket',
        s3_prefix='coverage/',
        upload_timeout=30,
        branch_coverage=True
    )


# Error condition tests
class TestHealthCheckErrorConditions:
    """Test cases for various error conditions in health check functionality."""
    
    def test_coverage_status_with_multiple_errors(self):
        """Test coverage status when multiple errors occur."""
        with patch('layer.python.coverage_wrapper.health_check.is_coverage_initialized') as mock_init, \
             patch('layer.python.coverage_wrapper.health_check.get_cached_config') as mock_config:
            
            # Mock multiple errors
            mock_init.side_effect = Exception("Init error")
            mock_config.side_effect = ValueError("Config error")
            
            status = get_coverage_status()
            
            assert status['enabled'] is False
            assert status['active'] is False
            assert status['config_valid'] is False
            assert len(status['errors']) == 1  # Only the first error is caught
    
    def test_layer_info_with_missing_environment_vars(self):
        """Test layer info when environment variables are missing."""
        with patch.dict(os.environ, {}, clear=True), \
             patch('layer.python.coverage_wrapper.health_check.get_cached_config') as mock_config:
            
            config = CoverageConfig(s3_bucket='test-bucket')
            mock_config.return_value = config
            
            layer_info = get_layer_info()
            
            assert layer_info['function_name'] == 'unknown'
            assert len(layer_info['environment_vars']) == 0
    
    def test_health_check_response_serialization(self):
        """Test that health check responses can be properly serialized."""
        response = health_check_handler()
        
        # Verify that the response can be JSON serialized
        import json
        json_str = json.dumps(response)
        
        # Verify that it can be deserialized
        deserialized = json.loads(json_str)
        assert deserialized['status'] in ['healthy', 'unhealthy']
        assert 'timestamp' in deserialized