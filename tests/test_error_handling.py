"""
Tests for the error handling utilities module.

This module tests the graceful error handling functionality including
error handlers, fallback mechanisms, and timeout protection.
"""

import os
import tempfile
import time
import unittest
from unittest.mock import patch, MagicMock, mock_open
from contextlib import contextmanager

from layer.python.coverage_wrapper.error_handling import (
    CoverageError,
    CoverageInitializationError,
    S3UploadError,
    TimeoutError,
    GracefulErrorHandler,
    graceful_operation,
    timeout_protection,
    FallbackStorage,
    get_remaining_lambda_time,
    ensure_lambda_completion_time,
    get_fallback_storage
)


class TestCustomExceptions(unittest.TestCase):
    """Test custom exception classes."""
    
    def test_coverage_error(self):
        """Test CoverageError exception."""
        error = CoverageError("Test error")
        self.assertIsInstance(error, Exception)
        self.assertEqual(str(error), "Test error")
    
    def test_coverage_initialization_error(self):
        """Test CoverageInitializationError exception."""
        error = CoverageInitializationError("Init error")
        self.assertIsInstance(error, CoverageError)
        self.assertEqual(str(error), "Init error")
    
    def test_s3_upload_error(self):
        """Test S3UploadError exception."""
        error = S3UploadError("Upload error")
        self.assertIsInstance(error, CoverageError)
        self.assertEqual(str(error), "Upload error")
    
    def test_timeout_error(self):
        """Test TimeoutError exception."""
        error = TimeoutError("Timeout error")
        self.assertIsInstance(error, CoverageError)
        self.assertEqual(str(error), "Timeout error")


class TestGracefulErrorHandler(unittest.TestCase):
    """Test the GracefulErrorHandler class."""
    
    def test_successful_operation(self):
        """Test graceful error handler with successful operation."""
        with GracefulErrorHandler("test_operation", critical=False) as handler:
            # Simulate successful operation
            pass
        
        self.assertFalse(handler.error_occurred)
        self.assertIsNone(handler.error_details)
    
    def test_non_critical_error_suppression(self):
        """Test that non-critical errors are suppressed."""
        with GracefulErrorHandler("test_operation", critical=False) as handler:
            raise ValueError("Test error")
        
        # Should not raise exception due to graceful handling
        self.assertTrue(handler.error_occurred)
        self.assertIsNotNone(handler.error_details)
        self.assertEqual(handler.error_details['type'], 'ValueError')
        self.assertEqual(handler.error_details['message'], 'Test error')
    
    def test_critical_error_propagation(self):
        """Test that critical errors are propagated."""
        with self.assertRaises(ValueError):
            with GracefulErrorHandler("test_operation", critical=True) as handler:
                raise ValueError("Critical error")
        
        # Error should still be recorded
        self.assertTrue(handler.error_occurred)
        self.assertIsNotNone(handler.error_details)


class TestGracefulOperationDecorator(unittest.TestCase):
    """Test the graceful_operation decorator."""
    
    def test_successful_function(self):
        """Test decorator with successful function."""
        @graceful_operation("test_op", critical=False)
        def test_function():
            return "success"
        
        result = test_function()
        self.assertEqual(result, "success")
    
    def test_non_critical_function_error(self):
        """Test decorator with non-critical function error."""
        @graceful_operation("test_op", critical=False)
        def test_function():
            raise ValueError("Test error")
        
        result = test_function()
        self.assertIsNone(result)  # Should return None due to graceful handling
    
    def test_critical_function_error(self):
        """Test decorator with critical function error."""
        @graceful_operation("test_op", critical=True)
        def test_function():
            raise ValueError("Critical error")
        
        with self.assertRaises(ValueError):
            test_function()


class TestTimeoutProtection(unittest.TestCase):
    """Test the timeout_protection context manager."""
    
    def test_operation_within_timeout(self):
        """Test operation that completes within timeout."""
        with timeout_protection(1.0, "test_operation"):
            time.sleep(0.1)  # Short operation
        
        # Should complete without raising exception
    
    def test_operation_exceeds_timeout(self):
        """Test operation that exceeds timeout."""
        with self.assertRaises(TimeoutError):
            with timeout_protection(0.1, "test_operation"):
                time.sleep(0.2)  # Long operation
    
    def test_operation_with_exception(self):
        """Test operation that raises exception within timeout."""
        with self.assertRaises(ValueError):
            with timeout_protection(1.0, "test_operation"):
                raise ValueError("Test error")


class TestFallbackStorage(unittest.TestCase):
    """Test the FallbackStorage class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.fallback_storage = FallbackStorage(self.temp_dir)
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_directory_creation(self):
        """Test that fallback directory is created."""
        self.assertTrue(os.path.exists(self.temp_dir))
        self.assertTrue(os.path.isdir(self.temp_dir))
    
    def test_store_coverage_file(self):
        """Test storing a coverage file."""
        # Create a temporary source file
        source_file = os.path.join(self.temp_dir, "source.json")
        with open(source_file, 'w') as f:
            f.write('{"test": "data"}')
        
        # Store the file
        metadata = {"function": "test_function", "timestamp": time.time()}
        stored_path = self.fallback_storage.store_coverage_file(source_file, metadata)
        
        # Verify file was stored
        self.assertTrue(os.path.exists(stored_path))
        self.assertIn("coverage-", os.path.basename(stored_path))
        
        # Verify metadata file was created
        metadata_path = stored_path + '.metadata'
        self.assertTrue(os.path.exists(metadata_path))
    
    def test_list_stored_files(self):
        """Test listing stored files."""
        # Store a test file
        source_file = os.path.join(self.temp_dir, "source.json")
        with open(source_file, 'w') as f:
            f.write('{"test": "data"}')
        
        stored_path = self.fallback_storage.store_coverage_file(source_file)
        
        # List files
        files = self.fallback_storage.list_stored_files()
        
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]['path'], stored_path)
        self.assertGreater(files[0]['size'], 0)
    
    def test_cleanup_old_files(self):
        """Test cleanup of old files."""
        # Create an old file by modifying its timestamp
        source_file = os.path.join(self.temp_dir, "source.json")
        with open(source_file, 'w') as f:
            f.write('{"test": "data"}')
        
        stored_path = self.fallback_storage.store_coverage_file(source_file)
        
        # Make the file appear old
        old_time = time.time() - (25 * 3600)  # 25 hours ago
        os.utime(stored_path, (old_time, old_time))
        
        # Cleanup files older than 24 hours
        self.fallback_storage.cleanup_old_files(max_age_hours=24)
        
        # File should be removed
        self.assertFalse(os.path.exists(stored_path))


class TestLambdaTimeUtilities(unittest.TestCase):
    """Test Lambda time-related utility functions."""
    
    def test_get_remaining_lambda_time_with_context(self):
        """Test getting remaining time with valid context."""
        mock_context = MagicMock()
        mock_context.get_remaining_time_in_millis.return_value = 30000
        
        remaining_time = get_remaining_lambda_time(mock_context)
        
        self.assertEqual(remaining_time, 30.0)
    
    def test_get_remaining_lambda_time_without_method(self):
        """Test getting remaining time with context missing method."""
        mock_context = MagicMock()
        del mock_context.get_remaining_time_in_millis
        
        remaining_time = get_remaining_lambda_time(mock_context)
        
        self.assertEqual(remaining_time, 0.0)
    
    def test_get_remaining_lambda_time_with_exception(self):
        """Test getting remaining time when method raises exception."""
        mock_context = MagicMock()
        mock_context.get_remaining_time_in_millis.side_effect = Exception("Test error")
        
        remaining_time = get_remaining_lambda_time(mock_context)
        
        self.assertEqual(remaining_time, 0.0)
    
    def test_ensure_lambda_completion_time_sufficient(self):
        """Test ensuring completion time when sufficient time remains."""
        mock_context = MagicMock()
        mock_context.get_remaining_time_in_millis.return_value = 10000  # 10 seconds
        
        result = ensure_lambda_completion_time(mock_context, min_buffer_seconds=5.0)
        
        self.assertTrue(result)
    
    def test_ensure_lambda_completion_time_insufficient(self):
        """Test ensuring completion time when insufficient time remains."""
        mock_context = MagicMock()
        mock_context.get_remaining_time_in_millis.return_value = 3000  # 3 seconds
        
        result = ensure_lambda_completion_time(mock_context, min_buffer_seconds=5.0)
        
        self.assertFalse(result)


class TestGlobalFallbackStorage(unittest.TestCase):
    """Test the global fallback storage functionality."""
    
    def test_get_fallback_storage_singleton(self):
        """Test that get_fallback_storage returns a singleton."""
        storage1 = get_fallback_storage()
        storage2 = get_fallback_storage()
        
        self.assertIs(storage1, storage2)
        self.assertIsInstance(storage1, FallbackStorage)


if __name__ == '__main__':
    unittest.main()