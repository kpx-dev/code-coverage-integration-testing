"""
Unit tests for the coverage wrapper module.

Tests configuration parsing, coverage initialization, and caching mechanisms.
"""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
import coverage

from layer.python.coverage_wrapper.wrapper import (
    get_cached_config,
    initialize_coverage,
    reset_coverage_cache,
    is_coverage_initialized,
    _cached_config,
    _coverage_instance
)
from layer.python.coverage_wrapper.models import CoverageConfig


class TestConfigurationParsing:
    """Test configuration parsing and caching."""
    
    def setup_method(self):
        """Reset cache before each test."""
        reset_coverage_cache()
    
    def teardown_method(self):
        """Clean up after each test."""
        reset_coverage_cache()
    
    def test_get_cached_config_creates_new_config(self):
        """Test that get_cached_config creates new configuration from environment."""
        env_vars = {
            'COVERAGE_S3_BUCKET': 'test-bucket',
            'COVERAGE_S3_PREFIX': 'test-prefix/',
            'COVERAGE_UPLOAD_TIMEOUT': '60',
            'COVERAGE_INCLUDE_PATTERNS': 'src/*,lib/*',
            'COVERAGE_EXCLUDE_PATTERNS': 'tests/*,*.pyc',
            'COVERAGE_BRANCH_COVERAGE': 'false'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = get_cached_config()
            
            assert config.s3_bucket == 'test-bucket'
            assert config.s3_prefix == 'test-prefix/'
            assert config.upload_timeout == 60
            assert config.include_patterns == ['src/*', 'lib/*']
            assert config.exclude_patterns == ['tests/*', '*.pyc']
            assert config.branch_coverage is False
    
    def test_get_cached_config_uses_defaults(self):
        """Test that get_cached_config uses default values when environment variables are not set."""
        env_vars = {
            'COVERAGE_S3_BUCKET': 'test-bucket'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = get_cached_config()
            
            assert config.s3_bucket == 'test-bucket'
            assert config.s3_prefix == 'coverage/'
            assert config.upload_timeout == 30
            assert config.include_patterns is None
            assert config.exclude_patterns is None
            assert config.branch_coverage is True
    
    def test_get_cached_config_caches_result(self):
        """Test that get_cached_config caches the configuration."""
        env_vars = {
            'COVERAGE_S3_BUCKET': 'test-bucket'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with patch.object(CoverageConfig, 'from_environment') as mock_from_env:
                mock_config = CoverageConfig(s3_bucket='test-bucket')
                mock_from_env.return_value = mock_config
                
                # First call should create config
                config1 = get_cached_config()
                assert mock_from_env.call_count == 1
                
                # Second call should use cached config
                config2 = get_cached_config()
                assert mock_from_env.call_count == 1
                assert config1 is config2
    
    def test_get_cached_config_missing_bucket_raises_error(self):
        """Test that missing S3 bucket raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="COVERAGE_S3_BUCKET environment variable is required"):
                get_cached_config()
    
    def test_get_cached_config_validates_configuration(self):
        """Test that configuration validation is called."""
        env_vars = {
            'COVERAGE_S3_BUCKET': 'test-bucket',
            'COVERAGE_UPLOAD_TIMEOUT': '-1'  # Invalid timeout
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(ValueError, match="upload_timeout must be positive"):
                get_cached_config()


class TestCoverageInitialization:
    """Test coverage initialization functionality."""
    
    def setup_method(self):
        """Reset cache before each test."""
        reset_coverage_cache()
    
    def teardown_method(self):
        """Clean up after each test."""
        reset_coverage_cache()
    
    @patch('layer.python.coverage_wrapper.wrapper.coverage.Coverage')
    def test_initialize_coverage_creates_instance(self, mock_coverage_class):
        """Test that initialize_coverage creates and starts coverage instance."""
        # Setup mocks
        mock_coverage_instance = Mock()
        mock_coverage_class.return_value = mock_coverage_instance
        
        env_vars = {
            'COVERAGE_S3_BUCKET': 'test-bucket'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            result = initialize_coverage()
            
            # Verify coverage instance was created with correct config
            mock_coverage_class.assert_called_once_with(
                config_file=False,
                branch=True,
                source=['.']
            )
            
            # Verify coverage was started
            mock_coverage_instance.start.assert_called_once()
            
            # Verify correct instance returned
            assert result is mock_coverage_instance
    
    @patch('layer.python.coverage_wrapper.wrapper.coverage.Coverage')
    def test_initialize_coverage_with_patterns(self, mock_coverage_class):
        """Test coverage initialization with include/exclude patterns."""
        mock_coverage_instance = Mock()
        mock_coverage_class.return_value = mock_coverage_instance
        
        env_vars = {
            'COVERAGE_S3_BUCKET': 'test-bucket',
            'COVERAGE_INCLUDE_PATTERNS': 'src/*,lib/*',
            'COVERAGE_EXCLUDE_PATTERNS': 'tests/*,*.pyc',
            'COVERAGE_BRANCH_COVERAGE': 'false'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            initialize_coverage()
            
            # Verify coverage instance was created with patterns
            mock_coverage_class.assert_called_once_with(
                config_file=False,
                branch=False,
                source=['.'],
                include=['src/*', 'lib/*'],
                omit=['tests/*', '*.pyc']
            )
    
    @patch('layer.python.coverage_wrapper.wrapper.coverage.Coverage')
    def test_initialize_coverage_caches_instance(self, mock_coverage_class):
        """Test that initialize_coverage caches the coverage instance."""
        mock_coverage_instance = Mock()
        mock_coverage_class.return_value = mock_coverage_instance
        
        env_vars = {
            'COVERAGE_S3_BUCKET': 'test-bucket'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            # First call should create instance
            result1 = initialize_coverage()
            assert mock_coverage_class.call_count == 1
            
            # Second call should return cached instance
            result2 = initialize_coverage()
            assert mock_coverage_class.call_count == 1
            assert result1 is result2
    
    @patch('layer.python.coverage_wrapper.wrapper.coverage.Coverage')
    def test_initialize_coverage_handles_failure(self, mock_coverage_class):
        """Test that initialize_coverage handles initialization failures."""
        mock_coverage_class.side_effect = Exception("Coverage init failed")
        
        env_vars = {
            'COVERAGE_S3_BUCKET': 'test-bucket'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(Exception, match="Coverage init failed"):
                initialize_coverage()
            
            # Verify cache is reset on failure
            assert not is_coverage_initialized()
    
    def test_initialize_coverage_config_error_propagates(self):
        """Test that configuration errors are propagated."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="COVERAGE_S3_BUCKET environment variable is required"):
                initialize_coverage()


class TestCoverageUtilities:
    """Test utility functions for coverage management."""
    
    def setup_method(self):
        """Reset cache before each test."""
        reset_coverage_cache()
    
    def teardown_method(self):
        """Clean up after each test."""
        reset_coverage_cache()
    
    def test_is_coverage_initialized_false_when_not_initialized(self):
        """Test is_coverage_initialized returns False when coverage not initialized."""
        assert not is_coverage_initialized()
    
    @patch('layer.python.coverage_wrapper.wrapper.coverage.Coverage')
    def test_is_coverage_initialized_true_when_initialized(self, mock_coverage_class):
        """Test is_coverage_initialized returns True when coverage is initialized."""
        mock_coverage_instance = Mock()
        mock_coverage_instance._started = True
        mock_coverage_class.return_value = mock_coverage_instance
        
        env_vars = {
            'COVERAGE_S3_BUCKET': 'test-bucket'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            initialize_coverage()
            assert is_coverage_initialized()
    
    @patch('layer.python.coverage_wrapper.wrapper.coverage.Coverage')
    def test_reset_coverage_cache_stops_coverage(self, mock_coverage_class):
        """Test that reset_coverage_cache stops active coverage."""
        mock_coverage_instance = Mock()
        mock_coverage_class.return_value = mock_coverage_instance
        
        env_vars = {
            'COVERAGE_S3_BUCKET': 'test-bucket'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            # Initialize coverage
            initialize_coverage()
            assert is_coverage_initialized()
            
            # Reset cache
            reset_coverage_cache()
            
            # Verify coverage was stopped
            mock_coverage_instance.stop.assert_called_once()
            assert not is_coverage_initialized()
    
    def test_reset_coverage_cache_handles_stop_error(self):
        """Test that reset_coverage_cache handles errors when stopping coverage."""
        # Manually set a mock coverage instance that raises error on stop
        import layer.python.coverage_wrapper.wrapper as wrapper_module
        mock_coverage = Mock()
        mock_coverage.stop.side_effect = Exception("Stop failed")
        wrapper_module._coverage_instance = mock_coverage
        
        # Should not raise exception
        reset_coverage_cache()
        
        # Cache should still be reset
        assert not is_coverage_initialized()


class TestIntegration:
    """Integration tests for coverage initialization."""
    
    def setup_method(self):
        """Reset cache before each test."""
        reset_coverage_cache()
    
    def teardown_method(self):
        """Clean up after each test."""
        reset_coverage_cache()
    
    def test_full_initialization_flow(self):
        """Test complete initialization flow with real coverage instance."""
        env_vars = {
            'COVERAGE_S3_BUCKET': 'test-bucket',
            'COVERAGE_S3_PREFIX': 'integration-test/',
            'COVERAGE_BRANCH_COVERAGE': 'true'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            # Initialize coverage
            cov = initialize_coverage()
            
            # Verify it's a real coverage instance
            assert isinstance(cov, coverage.Coverage)
            assert is_coverage_initialized()
            
            # Verify configuration was cached
            config = get_cached_config()
            assert config.s3_bucket == 'test-bucket'
            assert config.s3_prefix == 'integration-test/'
            assert config.branch_coverage is True
            
            # Verify second call returns same instance
            cov2 = initialize_coverage()
            assert cov is cov2


class TestCoverageFinalization:
    """Test coverage finalization functionality."""
    
    def setup_method(self):
        """Reset cache before each test."""
        reset_coverage_cache()
    
    def teardown_method(self):
        """Clean up after each test."""
        reset_coverage_cache()
    
    @patch('layer.python.coverage_wrapper.wrapper.coverage.Coverage')
    @patch('os.path.join')
    @patch('uuid.uuid4')
    def test_finalize_coverage_creates_file(self, mock_uuid, mock_path_join, mock_coverage_class):
        """Test that finalize_coverage creates coverage file."""
        # Setup mocks
        mock_coverage_instance = Mock()
        mock_coverage_class.return_value = mock_coverage_instance
        mock_uuid.return_value = Mock()
        mock_uuid.return_value.__str__ = Mock(return_value='12345678-1234-1234-1234-123456789012')
        mock_path_join.return_value = '/tmp/coverage-test-func-12345678.json'
        
        env_vars = {
            'COVERAGE_S3_BUCKET': 'test-bucket',
            'AWS_LAMBDA_FUNCTION_NAME': 'test-func'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            # Initialize coverage first
            initialize_coverage()
            
            # Finalize coverage
            from layer.python.coverage_wrapper.wrapper import finalize_coverage
            result = finalize_coverage()
            
            # Verify coverage was stopped
            mock_coverage_instance.stop.assert_called_once()
            
            # Verify JSON report was generated
            mock_coverage_instance.json_report.assert_called_once_with(
                outfile='/tmp/coverage-test-func-12345678.json'
            )
            
            # Verify correct file path returned
            assert result == '/tmp/coverage-test-func-12345678.json'
    
    def test_finalize_coverage_no_instance_returns_none(self):
        """Test that finalize_coverage returns None when no coverage instance exists."""
        from layer.python.coverage_wrapper.wrapper import finalize_coverage
        result = finalize_coverage()
        assert result is None
    
    @patch('layer.python.coverage_wrapper.wrapper.coverage.Coverage')
    def test_finalize_coverage_handles_error(self, mock_coverage_class):
        """Test that finalize_coverage handles errors during finalization."""
        mock_coverage_instance = Mock()
        mock_coverage_instance.stop.side_effect = Exception("Stop failed")
        mock_coverage_class.return_value = mock_coverage_instance
        
        env_vars = {
            'COVERAGE_S3_BUCKET': 'test-bucket'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            initialize_coverage()
            
            from layer.python.coverage_wrapper.wrapper import finalize_coverage
            with pytest.raises(Exception, match="Stop failed"):
                finalize_coverage()


class TestCoverageContext:
    """Test CoverageContext context manager."""
    
    def setup_method(self):
        """Reset cache before each test."""
        reset_coverage_cache()
    
    def teardown_method(self):
        """Clean up after each test."""
        reset_coverage_cache()
    
    @patch('layer.python.coverage_wrapper.wrapper.coverage.Coverage')
    @patch('layer.python.coverage_wrapper.s3_uploader.upload_coverage_file')
    @patch('os.remove')
    def test_coverage_context_normal_flow(self, mock_remove, mock_upload, mock_coverage_class):
        """Test CoverageContext normal execution flow."""
        # Setup mocks
        mock_coverage_instance = Mock()
        mock_coverage_instance._started = True
        mock_coverage_class.return_value = mock_coverage_instance
        
        env_vars = {
            'COVERAGE_S3_BUCKET': 'test-bucket',
            'AWS_LAMBDA_FUNCTION_NAME': 'test-func'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with patch('layer.python.coverage_wrapper.wrapper.finalize_coverage') as mock_finalize:
                mock_finalize.return_value = '/tmp/coverage-test.json'
                
                from layer.python.coverage_wrapper.wrapper import CoverageContext
                
                # Use context manager
                with CoverageContext() as ctx:
                    assert ctx is not None
                
                # Verify finalize was called
                mock_finalize.assert_called_once()
                
                # Verify upload was called
                mock_upload.assert_called_once_with('/tmp/coverage-test.json')
                
                # Verify cleanup was called
                mock_remove.assert_called_once_with('/tmp/coverage-test.json')
    
    @patch('layer.python.coverage_wrapper.wrapper.coverage.Coverage')
    def test_coverage_context_handles_init_error(self, mock_coverage_class):
        """Test CoverageContext handles initialization errors gracefully."""
        mock_coverage_class.side_effect = Exception("Init failed")
        
        env_vars = {
            'COVERAGE_S3_BUCKET': 'test-bucket'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            from layer.python.coverage_wrapper.wrapper import CoverageContext
            
            # Should not raise exception
            with CoverageContext() as ctx:
                assert ctx is not None
    
    @patch('layer.python.coverage_wrapper.wrapper.coverage.Coverage')
    @patch('layer.python.coverage_wrapper.s3_uploader.upload_coverage_file')
    def test_coverage_context_handles_upload_error(self, mock_upload, mock_coverage_class):
        """Test CoverageContext handles upload errors gracefully."""
        mock_coverage_instance = Mock()
        mock_coverage_class.return_value = mock_coverage_instance
        mock_upload.side_effect = Exception("Upload failed")
        
        env_vars = {
            'COVERAGE_S3_BUCKET': 'test-bucket'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with patch('layer.python.coverage_wrapper.wrapper.finalize_coverage') as mock_finalize:
                mock_finalize.return_value = '/tmp/coverage-test.json'
                
                from layer.python.coverage_wrapper.wrapper import CoverageContext
                
                # Should not raise exception
                with CoverageContext():
                    pass
    
    @patch('layer.python.coverage_wrapper.wrapper.coverage.Coverage')
    def test_coverage_context_with_exception_in_block(self, mock_coverage_class):
        """Test CoverageContext handles exceptions in the with block."""
        mock_coverage_instance = Mock()
        mock_coverage_class.return_value = mock_coverage_instance
        
        env_vars = {
            'COVERAGE_S3_BUCKET': 'test-bucket'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with patch('layer.python.coverage_wrapper.wrapper.finalize_coverage') as mock_finalize:
                mock_finalize.return_value = None
                
                from layer.python.coverage_wrapper.wrapper import CoverageContext
                
                # Exception in with block should be propagated
                with pytest.raises(ValueError, match="Test error"):
                    with CoverageContext():
                        raise ValueError("Test error")
                
                # Finalize should still be called
                mock_finalize.assert_called_once()


class TestCoverageHandlerDecorator:
    """Test coverage_handler decorator."""
    
    def setup_method(self):
        """Reset cache before each test."""
        reset_coverage_cache()
    
    def teardown_method(self):
        """Clean up after each test."""
        reset_coverage_cache()
    
    @patch('layer.python.coverage_wrapper.wrapper.coverage.Coverage')
    @patch('layer.python.coverage_wrapper.s3_uploader.upload_coverage_file')
    @patch('os.remove')
    def test_coverage_handler_normal_flow(self, mock_remove, mock_upload, mock_coverage_class):
        """Test coverage_handler decorator normal execution flow."""
        # Setup mocks
        mock_coverage_instance = Mock()
        mock_coverage_class.return_value = mock_coverage_instance
        
        env_vars = {
            'COVERAGE_S3_BUCKET': 'test-bucket',
            'AWS_LAMBDA_FUNCTION_NAME': 'test-func'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with patch('layer.python.coverage_wrapper.wrapper.finalize_coverage') as mock_finalize:
                mock_finalize.return_value = '/tmp/coverage-test.json'
                
                from layer.python.coverage_wrapper.wrapper import coverage_handler
                
                # Create test Lambda handler
                @coverage_handler
                def test_handler(event, context):
                    return {"statusCode": 200, "body": "success"}
                
                # Call the handler
                result = test_handler({"test": "event"}, {"test": "context"})
                
                # Verify result
                assert result == {"statusCode": 200, "body": "success"}
                
                # Verify coverage was initialized
                mock_coverage_class.assert_called_once()
                
                # Verify finalize was called
                mock_finalize.assert_called_once()
                
                # Verify upload was called
                mock_upload.assert_called_once_with('/tmp/coverage-test.json')
                
                # Verify cleanup was called
                mock_remove.assert_called_once_with('/tmp/coverage-test.json')
    
    @patch('layer.python.coverage_wrapper.wrapper.coverage.Coverage')
    def test_coverage_handler_preserves_function_metadata(self, mock_coverage_class):
        """Test that coverage_handler preserves original function metadata."""
        mock_coverage_instance = Mock()
        mock_coverage_class.return_value = mock_coverage_instance
        
        env_vars = {
            'COVERAGE_S3_BUCKET': 'test-bucket'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with patch('layer.python.coverage_wrapper.wrapper.finalize_coverage'):
                from layer.python.coverage_wrapper.wrapper import coverage_handler
                
                @coverage_handler
                def test_handler(event, context):
                    """Test handler docstring."""
                    return {"statusCode": 200}
                
                # Verify function metadata is preserved
                assert test_handler.__name__ == 'test_handler'
                assert test_handler.__doc__ == 'Test handler docstring.'
    
    @patch('layer.python.coverage_wrapper.wrapper.coverage.Coverage')
    def test_coverage_handler_propagates_exceptions(self, mock_coverage_class):
        """Test that coverage_handler propagates exceptions from handler."""
        mock_coverage_instance = Mock()
        mock_coverage_class.return_value = mock_coverage_instance
        
        env_vars = {
            'COVERAGE_S3_BUCKET': 'test-bucket'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with patch('layer.python.coverage_wrapper.wrapper.finalize_coverage') as mock_finalize:
                mock_finalize.return_value = None
                
                from layer.python.coverage_wrapper.wrapper import coverage_handler
                
                @coverage_handler
                def failing_handler(event, context):
                    raise ValueError("Handler failed")
                
                # Exception should be propagated
                with pytest.raises(ValueError, match="Handler failed"):
                    failing_handler({"test": "event"}, {"test": "context"})
                
                # Finalize should still be called in finally block
                mock_finalize.assert_called_once()
    
    @patch('layer.python.coverage_wrapper.wrapper.coverage.Coverage')
    @patch('layer.python.coverage_wrapper.s3_uploader.upload_coverage_file')
    def test_coverage_handler_handles_finalize_error(self, mock_upload, mock_coverage_class):
        """Test that coverage_handler handles finalization errors gracefully."""
        mock_coverage_instance = Mock()
        mock_coverage_class.return_value = mock_coverage_instance
        mock_upload.side_effect = Exception("Upload failed")
        
        env_vars = {
            'COVERAGE_S3_BUCKET': 'test-bucket'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with patch('layer.python.coverage_wrapper.wrapper.finalize_coverage') as mock_finalize:
                mock_finalize.return_value = '/tmp/coverage-test.json'
                
                from layer.python.coverage_wrapper.wrapper import coverage_handler
                
                @coverage_handler
                def test_handler(event, context):
                    return {"statusCode": 200}
                
                # Should not raise exception despite upload failure
                result = test_handler({"test": "event"}, {"test": "context"})
                assert result == {"statusCode": 200}
    
    @patch('layer.python.coverage_wrapper.wrapper.coverage.Coverage')
    def test_coverage_handler_handles_init_error(self, mock_coverage_class):
        """Test that coverage_handler handles initialization errors gracefully."""
        mock_coverage_class.side_effect = Exception("Init failed")
        
        env_vars = {
            'COVERAGE_S3_BUCKET': 'test-bucket'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            from layer.python.coverage_wrapper.wrapper import coverage_handler
            
            @coverage_handler
            def test_handler(event, context):
                return {"statusCode": 200}
            
            # Should propagate the initialization error
            with pytest.raises(Exception, match="Init failed"):
                test_handler({"test": "event"}, {"test": "context"})