"""
Unit tests for data models.
"""

import os
import pytest
from datetime import datetime
from unittest.mock import patch

from layer.python.coverage_wrapper.models import (
    CoverageConfig,
    CoverageReportMetadata,
    HealthCheckResponse,
    CombinerResult
)


class TestCoverageConfig:
    """Test cases for CoverageConfig data model."""
    
    def test_default_values(self):
        """Test CoverageConfig with default values."""
        config = CoverageConfig(s3_bucket="test-bucket")
        
        assert config.s3_bucket == "test-bucket"
        assert config.s3_prefix == "coverage/"
        assert config.upload_timeout == 30
        assert config.include_patterns is None
        assert config.exclude_patterns is None
        assert config.branch_coverage is True
    
    def test_custom_values(self):
        """Test CoverageConfig with custom values."""
        config = CoverageConfig(
            s3_bucket="custom-bucket",
            s3_prefix="custom/prefix/",
            upload_timeout=60,
            include_patterns=["*.py"],
            exclude_patterns=["test_*.py"],
            branch_coverage=False
        )
        
        assert config.s3_bucket == "custom-bucket"
        assert config.s3_prefix == "custom/prefix/"
        assert config.upload_timeout == 60
        assert config.include_patterns == ["*.py"]
        assert config.exclude_patterns == ["test_*.py"]
        assert config.branch_coverage is False
    
    @patch.dict(os.environ, {
        'COVERAGE_S3_BUCKET': 'env-bucket',
        'COVERAGE_S3_PREFIX': 'env/prefix/',
        'COVERAGE_UPLOAD_TIMEOUT': '45',
        'COVERAGE_INCLUDE_PATTERNS': '*.py,*.pyx',
        'COVERAGE_EXCLUDE_PATTERNS': 'test_*.py,*_test.py',
        'COVERAGE_BRANCH_COVERAGE': 'false'
    })
    def test_from_environment(self):
        """Test creating config from environment variables."""
        config = CoverageConfig.from_environment()
        
        assert config.s3_bucket == "env-bucket"
        assert config.s3_prefix == "env/prefix/"
        assert config.upload_timeout == 45
        assert config.include_patterns == ["*.py", "*.pyx"]
        assert config.exclude_patterns == ["test_*.py", "*_test.py"]
        assert config.branch_coverage is False
    
    @patch.dict(os.environ, {}, clear=True)
    def test_from_environment_missing_bucket(self):
        """Test error when S3 bucket is not provided."""
        with pytest.raises(ValueError, match="COVERAGE_S3_BUCKET environment variable is required"):
            CoverageConfig.from_environment()
    
    @patch.dict(os.environ, {'COVERAGE_S3_BUCKET': 'test-bucket'})
    def test_from_environment_defaults(self):
        """Test environment config with default values."""
        config = CoverageConfig.from_environment()
        
        assert config.s3_bucket == "test-bucket"
        assert config.s3_prefix == "coverage/"
        assert config.upload_timeout == 30
        assert config.include_patterns is None
        assert config.exclude_patterns is None
        assert config.branch_coverage is True
    
    def test_validate_success(self):
        """Test successful validation."""
        config = CoverageConfig(s3_bucket="test-bucket")
        config.validate()  # Should not raise
    
    def test_validate_empty_bucket(self):
        """Test validation with empty bucket name."""
        config = CoverageConfig(s3_bucket="")
        with pytest.raises(ValueError, match="s3_bucket cannot be empty"):
            config.validate()
    
    def test_validate_negative_timeout(self):
        """Test validation with negative timeout."""
        config = CoverageConfig(s3_bucket="test-bucket", upload_timeout=-1)
        with pytest.raises(ValueError, match="upload_timeout must be positive"):
            config.validate()
    
    def test_validate_adds_trailing_slash(self):
        """Test validation adds trailing slash to prefix."""
        config = CoverageConfig(s3_bucket="test-bucket", s3_prefix="coverage")
        config.validate()
        assert config.s3_prefix == "coverage/"


class TestCoverageReportMetadata:
    """Test cases for CoverageReportMetadata data model."""
    
    def test_creation(self):
        """Test creating CoverageReportMetadata."""
        timestamp = datetime.now()
        metadata = CoverageReportMetadata(
            function_name="test-function",
            execution_id="exec-123",
            timestamp=timestamp,
            s3_key="coverage/test-function/exec-123.json",
            file_size=1024,
            coverage_percentage=85.5
        )
        
        assert metadata.function_name == "test-function"
        assert metadata.execution_id == "exec-123"
        assert metadata.timestamp == timestamp
        assert metadata.s3_key == "coverage/test-function/exec-123.json"
        assert metadata.file_size == 1024
        assert metadata.coverage_percentage == 85.5
    
    def test_to_dict(self):
        """Test converting metadata to dictionary."""
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        metadata = CoverageReportMetadata(
            function_name="test-function",
            execution_id="exec-123",
            timestamp=timestamp,
            s3_key="coverage/test-function/exec-123.json",
            file_size=1024,
            coverage_percentage=85.5
        )
        
        result = metadata.to_dict()
        expected = {
            'function_name': 'test-function',
            'execution_id': 'exec-123',
            'timestamp': '2024-01-15T10:30:00',
            's3_key': 'coverage/test-function/exec-123.json',
            'file_size': 1024,
            'coverage_percentage': 85.5
        }
        
        assert result == expected


class TestHealthCheckResponse:
    """Test cases for HealthCheckResponse data model."""
    
    def test_creation_healthy(self):
        """Test creating healthy health check response."""
        timestamp = datetime.now()
        response = HealthCheckResponse(
            status="healthy",
            coverage_enabled=True,
            layer_version="1.0.0",
            s3_config={"bucket": "test-bucket", "prefix": "coverage/"},
            timestamp=timestamp
        )
        
        assert response.status == "healthy"
        assert response.coverage_enabled is True
        assert response.layer_version == "1.0.0"
        assert response.s3_config == {"bucket": "test-bucket", "prefix": "coverage/"}
        assert response.timestamp == timestamp
        assert response.errors == []
    
    def test_creation_with_errors(self):
        """Test creating health check response with errors."""
        timestamp = datetime.now()
        errors = ["S3 permission denied", "Coverage initialization failed"]
        response = HealthCheckResponse(
            status="unhealthy",
            coverage_enabled=False,
            layer_version="1.0.0",
            s3_config={},
            timestamp=timestamp,
            errors=errors
        )
        
        assert response.status == "unhealthy"
        assert response.coverage_enabled is False
        assert response.errors == errors
    
    def test_to_dict(self):
        """Test converting health check response to dictionary."""
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        response = HealthCheckResponse(
            status="healthy",
            coverage_enabled=True,
            layer_version="1.0.0",
            s3_config={"bucket": "test-bucket", "prefix": "coverage/"},
            timestamp=timestamp,
            errors=["warning message"]
        )
        
        result = response.to_dict()
        expected = {
            'status': 'healthy',
            'coverage_enabled': True,
            'layer_version': '1.0.0',
            's3_config': {'bucket': 'test-bucket', 'prefix': 'coverage/'},
            'timestamp': '2024-01-15T10:30:00',
            'errors': ['warning message']
        }
        
        assert result == expected


class TestCombinerResult:
    """Test cases for CombinerResult data model."""
    
    def test_creation_success(self):
        """Test creating successful combiner result."""
        result = CombinerResult(
            success=True,
            combined_file_key="coverage/combined-report.json",
            files_processed=5,
            files_skipped=1,
            total_coverage_percentage=78.5
        )
        
        assert result.success is True
        assert result.combined_file_key == "coverage/combined-report.json"
        assert result.files_processed == 5
        assert result.files_skipped == 1
        assert result.total_coverage_percentage == 78.5
        assert result.errors == []
    
    def test_creation_with_errors(self):
        """Test creating combiner result with errors."""
        errors = ["File corruption detected", "S3 upload failed"]
        result = CombinerResult(
            success=False,
            combined_file_key="",
            files_processed=3,
            files_skipped=2,
            total_coverage_percentage=0.0,
            errors=errors
        )
        
        assert result.success is False
        assert result.errors == errors
    
    def test_to_dict(self):
        """Test converting combiner result to dictionary."""
        result = CombinerResult(
            success=True,
            combined_file_key="coverage/combined-report.json",
            files_processed=5,
            files_skipped=1,
            total_coverage_percentage=78.5,
            errors=["warning message"]
        )
        
        dict_result = result.to_dict()
        expected = {
            'success': True,
            'combined_file_key': 'coverage/combined-report.json',
            'files_processed': 5,
            'files_skipped': 1,
            'total_coverage_percentage': 78.5,
            'errors': ['warning message']
        }
        
        assert dict_result == expected