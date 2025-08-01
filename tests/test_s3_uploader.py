"""
Unit tests for S3 uploader utilities.
"""

import os
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from layer.python.coverage_wrapper.s3_uploader import (
    get_s3_config,
    generate_s3_key,
    _sanitize_s3_key_component
)
from layer.python.coverage_wrapper.models import CoverageConfig


class TestGetS3Config:
    """Test cases for get_s3_config function."""
    
    @patch.dict(os.environ, {
        'COVERAGE_S3_BUCKET': 'test-bucket',
        'COVERAGE_S3_PREFIX': 'test/prefix/',
        'COVERAGE_UPLOAD_TIMEOUT': '45'
    })
    def test_get_s3_config_success(self):
        """Test successful S3 configuration parsing."""
        config = get_s3_config()
        
        assert isinstance(config, CoverageConfig)
        assert config.s3_bucket == 'test-bucket'
        assert config.s3_prefix == 'test/prefix/'
        assert config.upload_timeout == 45
    
    @patch.dict(os.environ, {}, clear=True)
    def test_get_s3_config_missing_bucket(self):
        """Test error when required S3 bucket is missing."""
        with pytest.raises(ValueError, match="COVERAGE_S3_BUCKET environment variable is required"):
            get_s3_config()
    
    @patch.dict(os.environ, {
        'COVERAGE_S3_BUCKET': 'test-bucket',
        'COVERAGE_UPLOAD_TIMEOUT': 'invalid'
    })
    def test_get_s3_config_invalid_timeout(self):
        """Test error when timeout is invalid."""
        with pytest.raises(ValueError, match="Invalid S3 configuration"):
            get_s3_config()
    
    @patch.dict(os.environ, {
        'COVERAGE_S3_BUCKET': '',  # Empty bucket name
    })
    def test_get_s3_config_empty_bucket(self):
        """Test error when bucket name is empty."""
        with pytest.raises(ValueError, match="COVERAGE_S3_BUCKET environment variable is required"):
            get_s3_config()


class TestGenerateS3Key:
    """Test cases for generate_s3_key function."""
    
    def test_generate_s3_key_with_all_params(self):
        """Test S3 key generation with all parameters provided."""
        timestamp = datetime(2024, 1, 15, 10, 30, 45, 123000)
        
        key = generate_s3_key(
            function_name="test-function",
            execution_id="exec-123",
            prefix="custom/prefix/",
            timestamp=timestamp
        )
        
        expected = "custom/prefix/test-function/20240115_103045_123_exec-123.coverage"
        assert key == expected
    
    def test_generate_s3_key_with_defaults(self):
        """Test S3 key generation with default parameters."""
        with patch.dict(os.environ, {
            'AWS_LAMBDA_FUNCTION_NAME': 'env-function',
            'AWS_LAMBDA_LOG_STREAM_NAME': 'env-stream'
        }):
            key = generate_s3_key()
            
            # Should contain function name and stream name
            assert 'env-function' in key
            assert 'env-stream' in key
            assert key.startswith('coverage/')
            assert key.endswith('.coverage')
    
    def test_generate_s3_key_no_function_name(self):
        """Test error when function name cannot be determined."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Function name must be provided or AWS_LAMBDA_FUNCTION_NAME must be set"):
                generate_s3_key()
    
    def test_generate_s3_key_missing_execution_id(self):
        """Test S3 key generation when execution ID is missing."""
        key = generate_s3_key(
            function_name="test-function",
            execution_id=None
        )
        
        # Should use 'unknown' as execution ID
        assert 'unknown' in key
        assert 'test-function' in key
    
    def test_generate_s3_key_prefix_normalization(self):
        """Test that prefix is normalized with trailing slash."""
        key = generate_s3_key(
            function_name="test-function",
            execution_id="exec-123",
            prefix="no-slash"
        )
        
        assert key.startswith("no-slash/")
    
    def test_generate_s3_key_empty_prefix(self):
        """Test S3 key generation with empty prefix."""
        key = generate_s3_key(
            function_name="test-function",
            execution_id="exec-123",
            prefix=""
        )
        
        # Should start directly with function name
        assert key.startswith("test-function/")
    
    def test_generate_s3_key_special_characters(self):
        """Test S3 key generation with special characters in names."""
        key = generate_s3_key(
            function_name="test function!@#",
            execution_id="exec/stream:123",
            prefix="coverage/"
        )
        
        # Special characters should be sanitized
        assert "test_function" in key
        assert "exec_stream_123" in key
        assert key.startswith("coverage/")
        assert key.endswith(".coverage")
    
    def test_generate_s3_key_timestamp_format(self):
        """Test that timestamp is formatted correctly."""
        timestamp = datetime(2024, 12, 31, 23, 59, 59, 999000)
        
        key = generate_s3_key(
            function_name="test-function",
            execution_id="exec-123",
            timestamp=timestamp
        )
        
        # Should contain formatted timestamp
        assert "20241231_235959_999" in key


class TestSanitizeS3KeyComponent:
    """Test cases for _sanitize_s3_key_component function."""
    
    def test_sanitize_normal_string(self):
        """Test sanitizing normal alphanumeric string."""
        result = _sanitize_s3_key_component("test-function_123")
        assert result == "test-function_123"
    
    def test_sanitize_special_characters(self):
        """Test sanitizing string with special characters."""
        result = _sanitize_s3_key_component("test function!@#$%")
        assert result == "test_function"
    
    def test_sanitize_with_dots_and_hyphens(self):
        """Test that dots and hyphens are preserved."""
        result = _sanitize_s3_key_component("test-function.v1")
        assert result == "test-function.v1"
    
    def test_sanitize_empty_string(self):
        """Test sanitizing empty string."""
        result = _sanitize_s3_key_component("")
        assert result == "unknown"
    
    def test_sanitize_only_special_chars(self):
        """Test sanitizing string with only special characters."""
        result = _sanitize_s3_key_component("!@#$%")
        assert result == "unknown"
    
    def test_sanitize_leading_trailing_underscores(self):
        """Test that leading/trailing underscores are removed."""
        result = _sanitize_s3_key_component("___test___")
        assert result == "test"
    
    def test_sanitize_unicode_characters(self):
        """Test sanitizing string with unicode characters."""
        result = _sanitize_s3_key_component("test-función-λ")
        assert result == "test-funci_n-"


class TestUploadCoverageFile:
    """Test cases for upload_coverage_file function."""
    
    @patch('boto3.client')
    @patch('layer.python.coverage_wrapper.s3_uploader.get_s3_config')
    @patch('layer.python.coverage_wrapper.s3_uploader.generate_s3_key')
    @patch('os.path.exists')
    def test_upload_coverage_file_success(self, mock_exists, mock_generate_key, mock_get_config, mock_boto3_client):
        """Test successful coverage file upload."""
        from layer.python.coverage_wrapper.s3_uploader import upload_coverage_file
        from layer.python.coverage_wrapper.models import CoverageConfig
        
        # Setup mocks
        mock_exists.return_value = True
        mock_generate_key.return_value = "coverage/test-function/20240115_103045_123_exec-123.coverage"
        mock_config = CoverageConfig(s3_bucket="test-bucket", s3_prefix="coverage/")
        mock_get_config.return_value = mock_config
        
        mock_s3_client = mock_boto3_client.return_value
        mock_s3_client.upload_file.return_value = None
        
        # Execute
        result = upload_coverage_file("/path/to/coverage.json")
        
        # Verify
        assert result == "coverage/test-function/20240115_103045_123_exec-123.coverage"
        mock_exists.assert_called_once_with("/path/to/coverage.json")
        mock_s3_client.upload_file.assert_called_once_with(
            "/path/to/coverage.json",
            "test-bucket",
            "coverage/test-function/20240115_103045_123_exec-123.coverage",
            ExtraArgs={
                'ServerSideEncryption': 'AES256',
                'ContentType': 'application/octet-stream'
            }
        )
    
    @patch('os.path.exists')
    def test_upload_coverage_file_missing_file(self, mock_exists):
        """Test error when coverage file doesn't exist."""
        from layer.python.coverage_wrapper.s3_uploader import upload_coverage_file
        
        mock_exists.return_value = False
        
        with pytest.raises(ValueError, match="Coverage file not found"):
            upload_coverage_file("/path/to/missing.json")
    
    @patch('boto3.client')
    @patch('layer.python.coverage_wrapper.s3_uploader.get_s3_config')
    @patch('layer.python.coverage_wrapper.s3_uploader.generate_s3_key')
    @patch('os.path.exists')
    def test_upload_coverage_file_with_custom_params(self, mock_exists, mock_generate_key, mock_get_config, mock_boto3_client):
        """Test upload with custom S3 key and config."""
        from layer.python.coverage_wrapper.s3_uploader import upload_coverage_file
        from layer.python.coverage_wrapper.models import CoverageConfig
        
        # Setup mocks
        mock_exists.return_value = True
        custom_config = CoverageConfig(s3_bucket="custom-bucket", s3_prefix="custom/")
        
        mock_s3_client = mock_boto3_client.return_value
        mock_s3_client.upload_file.return_value = None
        
        # Execute with custom parameters
        result = upload_coverage_file(
            "/path/to/coverage.json",
            s3_key="custom/key.coverage",
            config=custom_config
        )
        
        # Verify
        assert result == "custom/key.coverage"
        mock_generate_key.assert_not_called()  # Should not generate key when provided
        mock_get_config.assert_not_called()  # Should not load config when provided
        mock_s3_client.upload_file.assert_called_once_with(
            "/path/to/coverage.json",
            "custom-bucket",
            "custom/key.coverage",
            ExtraArgs={
                'ServerSideEncryption': 'AES256',
                'ContentType': 'application/octet-stream'
            }
        )
    
    @patch('boto3.client')
    @patch('layer.python.coverage_wrapper.s3_uploader.get_s3_config')
    @patch('layer.python.coverage_wrapper.s3_uploader.generate_s3_key')
    @patch('os.path.exists')
    def test_upload_coverage_file_no_credentials(self, mock_exists, mock_generate_key, mock_get_config, mock_boto3_client):
        """Test error when AWS credentials are not available."""
        from layer.python.coverage_wrapper.s3_uploader import upload_coverage_file
        from layer.python.coverage_wrapper.models import CoverageConfig
        from botocore.exceptions import NoCredentialsError
        
        # Setup mocks
        mock_exists.return_value = True
        mock_generate_key.return_value = "coverage/test.coverage"
        mock_config = CoverageConfig(s3_bucket="test-bucket")
        mock_get_config.return_value = mock_config
        mock_boto3_client.side_effect = NoCredentialsError()
        
        with pytest.raises(Exception, match="AWS credentials not available"):
            upload_coverage_file("/path/to/coverage.json")
    
    @patch('boto3.client')
    @patch('layer.python.coverage_wrapper.s3_uploader.get_s3_config')
    @patch('layer.python.coverage_wrapper.s3_uploader.generate_s3_key')
    @patch('time.sleep')
    @patch('os.path.exists')
    def test_upload_coverage_file_retry_success(self, mock_exists, mock_sleep, mock_generate_key, mock_get_config, mock_boto3_client):
        """Test successful upload after retry."""
        from layer.python.coverage_wrapper.s3_uploader import upload_coverage_file
        from layer.python.coverage_wrapper.models import CoverageConfig
        from botocore.exceptions import ClientError
        
        # Setup mocks
        mock_exists.return_value = True
        mock_generate_key.return_value = "coverage/test.coverage"
        mock_config = CoverageConfig(s3_bucket="test-bucket")
        mock_get_config.return_value = mock_config
        
        mock_s3_client = mock_boto3_client.return_value
        # First call fails, second succeeds
        mock_s3_client.upload_file.side_effect = [
            ClientError({'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service unavailable'}}, 'upload_file'),
            None
        ]
        
        # Execute
        result = upload_coverage_file("/path/to/coverage.json")
        
        # Verify
        assert result == "coverage/test.coverage"
        assert mock_s3_client.upload_file.call_count == 2
        mock_sleep.assert_called_once_with(1.0)  # First retry delay
    
    @patch('boto3.client')
    @patch('layer.python.coverage_wrapper.s3_uploader.get_s3_config')
    @patch('layer.python.coverage_wrapper.s3_uploader.generate_s3_key')
    @patch('time.sleep')
    @patch('os.path.exists')
    def test_upload_coverage_file_non_retryable_error(self, mock_exists, mock_sleep, mock_generate_key, mock_get_config, mock_boto3_client):
        """Test non-retryable error (e.g., AccessDenied)."""
        from layer.python.coverage_wrapper.s3_uploader import upload_coverage_file
        from layer.python.coverage_wrapper.models import CoverageConfig
        from botocore.exceptions import ClientError
        
        # Setup mocks
        mock_exists.return_value = True
        mock_generate_key.return_value = "coverage/test.coverage"
        mock_config = CoverageConfig(s3_bucket="test-bucket")
        mock_get_config.return_value = mock_config
        
        mock_s3_client = mock_boto3_client.return_value
        mock_s3_client.upload_file.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}}, 'upload_file'
        )
        
        # Execute and verify
        with pytest.raises(Exception, match="S3 upload failed: AccessDenied"):
            upload_coverage_file("/path/to/coverage.json")
        
        # Should not retry for AccessDenied
        assert mock_s3_client.upload_file.call_count == 1
        mock_sleep.assert_not_called()
    
    @patch('boto3.client')
    @patch('layer.python.coverage_wrapper.s3_uploader.get_s3_config')
    @patch('layer.python.coverage_wrapper.s3_uploader.generate_s3_key')
    @patch('time.sleep')
    @patch('os.path.exists')
    def test_upload_coverage_file_max_retries_exceeded(self, mock_exists, mock_sleep, mock_generate_key, mock_get_config, mock_boto3_client):
        """Test failure after maximum retries."""
        from layer.python.coverage_wrapper.s3_uploader import upload_coverage_file
        from layer.python.coverage_wrapper.models import CoverageConfig
        from botocore.exceptions import ClientError
        
        # Setup mocks
        mock_exists.return_value = True
        mock_generate_key.return_value = "coverage/test.coverage"
        mock_config = CoverageConfig(s3_bucket="test-bucket")
        mock_get_config.return_value = mock_config
        
        mock_s3_client = mock_boto3_client.return_value
        mock_s3_client.upload_file.side_effect = ClientError(
            {'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service unavailable'}}, 'upload_file'
        )
        
        # Execute and verify
        with pytest.raises(Exception, match="S3 upload failed after 3 attempts"):
            upload_coverage_file("/path/to/coverage.json")
        
        # Should retry 3 times total
        assert mock_s3_client.upload_file.call_count == 3
        # Should sleep twice (between retries)
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1.0)  # First retry delay
        mock_sleep.assert_any_call(2.0)  # Second retry delay (exponential backoff)


class TestUploadCoverageFileAsync:
    """Test cases for upload_coverage_file_async function."""
    
    @patch('threading.Thread')
    def test_upload_coverage_file_async(self, mock_thread):
        """Test asynchronous upload starts thread."""
        from layer.python.coverage_wrapper.s3_uploader import upload_coverage_file_async
        
        mock_thread_instance = mock_thread.return_value
        
        # Execute
        upload_coverage_file_async("/path/to/coverage.json")
        
        # Verify thread was created and started
        mock_thread.assert_called_once()
        mock_thread_instance.start.assert_called_once()
        
        # Verify thread was created as daemon
        args, kwargs = mock_thread.call_args
        assert kwargs.get('daemon') is True