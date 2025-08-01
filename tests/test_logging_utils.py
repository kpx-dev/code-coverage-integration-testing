"""
Tests for the logging utilities module.

This module tests the structured logging functionality including
formatters, filters, and performance tracking.
"""

import json
import logging
import os
import sys
import tempfile
import unittest
from datetime import datetime
from io import StringIO
from unittest.mock import patch, MagicMock

from layer.python.coverage_wrapper.logging_utils import (
    StructuredFormatter,
    SecurityFilter,
    CoverageLogger,
    get_logger,
    performance_timer,
    log_lambda_context
)


class TestStructuredFormatter(unittest.TestCase):
    """Test the StructuredFormatter class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.formatter = StructuredFormatter()
    
    def test_format_basic_log(self):
        """Test basic log formatting."""
        record = logging.LogRecord(
            name='test_logger',
            level=logging.INFO,
            pathname='test.py',
            lineno=10,
            msg='Test message',
            args=(),
            exc_info=None
        )
        
        formatted = self.formatter.format(record)
        log_data = json.loads(formatted)
        
        self.assertEqual(log_data['level'], 'INFO')
        self.assertEqual(log_data['logger'], 'test_logger')
        self.assertEqual(log_data['message'], 'Test message')
        self.assertIn('timestamp', log_data)
        self.assertIn('function_name', log_data)
    
    def test_format_with_exception(self):
        """Test log formatting with exception information."""
        try:
            raise ValueError("Test exception")
        except ValueError:
            exc_info = sys.exc_info()
        
        record = logging.LogRecord(
            name='test_logger',
            level=logging.ERROR,
            pathname='test.py',
            lineno=10,
            msg='Error occurred',
            args=(),
            exc_info=exc_info
        )
        
        formatted = self.formatter.format(record)
        log_data = json.loads(formatted)
        
        self.assertEqual(log_data['level'], 'ERROR')
        self.assertIn('exception', log_data)
        self.assertEqual(log_data['exception']['type'], 'ValueError')
        self.assertEqual(log_data['exception']['message'], 'Test exception')
    
    def test_format_with_extra_fields(self):
        """Test log formatting with extra fields."""
        record = logging.LogRecord(
            name='test_logger',
            level=logging.INFO,
            pathname='test.py',
            lineno=10,
            msg='Test message',
            args=(),
            exc_info=None
        )
        record.extra_fields = {'custom_field': 'custom_value', 'count': 42}
        
        formatted = self.formatter.format(record)
        log_data = json.loads(formatted)
        
        self.assertEqual(log_data['custom_field'], 'custom_value')
        self.assertEqual(log_data['count'], 42)


class TestSecurityFilter(unittest.TestCase):
    """Test the SecurityFilter class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.filter = SecurityFilter()
    
    def test_filter_sensitive_data(self):
        """Test filtering of sensitive information."""
        record = logging.LogRecord(
            name='test_logger',
            level=logging.INFO,
            pathname='test.py',
            lineno=10,
            msg='aws_access_key_id=AKIAIOSFODNN7EXAMPLE',
            args=(),
            exc_info=None
        )
        
        result = self.filter.filter(record)
        
        self.assertTrue(result)
        self.assertIn('***MASKED***', record.msg)
        self.assertNotIn('AKIAIOSFODNN7EXAMPLE', record.msg)
    
    def test_filter_normal_data(self):
        """Test that normal data passes through unchanged."""
        original_msg = 'Normal log message without sensitive data'
        record = logging.LogRecord(
            name='test_logger',
            level=logging.INFO,
            pathname='test.py',
            lineno=10,
            msg=original_msg,
            args=(),
            exc_info=None
        )
        
        result = self.filter.filter(record)
        
        self.assertTrue(result)
        self.assertEqual(record.msg, original_msg)


class TestCoverageLogger(unittest.TestCase):
    """Test the CoverageLogger class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Capture log output
        self.log_stream = StringIO()
        self.handler = logging.StreamHandler(self.log_stream)
        
        # Create logger with test handler
        self.logger = CoverageLogger('test_logger')
        self.logger.logger.handlers.clear()
        self.logger.logger.addHandler(self.handler)
        self.logger.logger.setLevel(logging.DEBUG)
    
    def test_structured_logging(self):
        """Test that structured logging works correctly."""
        self.logger.info('Test message', custom_field='test_value')
        
        log_output = self.log_stream.getvalue()
        self.assertIn('Test message', log_output)
        # Should be JSON formatted
        self.assertIn('{', log_output)
        self.assertIn('}', log_output)
    
    def test_log_levels(self):
        """Test different log levels."""
        self.logger.debug('Debug message')
        self.logger.info('Info message')
        self.logger.warning('Warning message')
        self.logger.error('Error message')
        self.logger.critical('Critical message')
        
        log_output = self.log_stream.getvalue()
        self.assertIn('Debug message', log_output)
        self.assertIn('Info message', log_output)
        self.assertIn('Warning message', log_output)
        self.assertIn('Error message', log_output)
        self.assertIn('Critical message', log_output)
    
    def test_performance_logging(self):
        """Test performance metrics logging."""
        self.logger.log_performance('test_operation', 123.45, success=True)
        
        log_output = self.log_stream.getvalue()
        self.assertIn('test_operation', log_output)
        self.assertIn('123.45', log_output)
    
    def test_coverage_metrics_logging(self):
        """Test coverage-specific metrics logging."""
        self.logger.log_coverage_metrics('test_function', 85.5, 1024, 250.0)
        
        log_output = self.log_stream.getvalue()
        self.assertIn('test_function', log_output)
        self.assertIn('85.5', log_output)
        self.assertIn('1024', log_output)
        self.assertIn('250.0', log_output)


class TestPerformanceTimer(unittest.TestCase):
    """Test the performance_timer decorator."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.log_stream = StringIO()
        self.handler = logging.StreamHandler(self.log_stream)
        
        # Mock the logger to capture performance logs
        self.mock_logger = MagicMock()
        
    @patch('layer.python.coverage_wrapper.logging_utils.get_logger')
    def test_performance_timer_success(self, mock_get_logger):
        """Test performance timer with successful function execution."""
        mock_get_logger.return_value = self.mock_logger
        
        @performance_timer('test_operation')
        def test_function():
            return 'success'
        
        result = test_function()
        
        self.assertEqual(result, 'success')
        self.mock_logger.log_performance.assert_called_once()
        
        # Check that the call includes success=True
        call_args = self.mock_logger.log_performance.call_args
        self.assertEqual(call_args[0][0], 'test_operation')  # operation name
        self.assertIsInstance(call_args[0][1], float)  # duration
        self.assertTrue(call_args[1]['success'])  # success flag
    
    @patch('layer.python.coverage_wrapper.logging_utils.get_logger')
    def test_performance_timer_exception(self, mock_get_logger):
        """Test performance timer with function that raises exception."""
        mock_get_logger.return_value = self.mock_logger
        
        @performance_timer('test_operation')
        def test_function():
            raise ValueError('Test error')
        
        with self.assertRaises(ValueError):
            test_function()
        
        self.mock_logger.log_performance.assert_called_once()
        
        # Check that the call includes success=False and error info
        call_args = self.mock_logger.log_performance.call_args
        self.assertEqual(call_args[0][0], 'test_operation')  # operation name
        self.assertIsInstance(call_args[0][1], float)  # duration
        self.assertFalse(call_args[1]['success'])  # success flag
        self.assertIn('error', call_args[1])  # error message


class TestLogLambdaContext(unittest.TestCase):
    """Test the log_lambda_context function."""
    
    @patch('layer.python.coverage_wrapper.logging_utils.get_logger')
    def test_log_lambda_context(self, mock_get_logger):
        """Test logging Lambda context information."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        # Mock Lambda context
        mock_context = MagicMock()
        mock_context.aws_request_id = 'test-request-id'
        mock_context.function_name = 'test-function'
        mock_context.function_version = '1'
        mock_context.memory_limit_in_mb = 128
        mock_context.get_remaining_time_in_millis.return_value = 30000
        
        log_lambda_context(mock_context)
        
        # Verify logger methods were called
        mock_logger.set_request_id.assert_called_once_with('test-request-id')
        mock_logger.info.assert_called_once()
        
        # Check the info call arguments
        call_args = mock_logger.info.call_args
        self.assertIn('Lambda execution started', call_args[0][0])


class TestGetLogger(unittest.TestCase):
    """Test the get_logger function."""
    
    def test_get_logger_returns_coverage_logger(self):
        """Test that get_logger returns a CoverageLogger instance."""
        logger = get_logger('test_module')
        
        self.assertIsInstance(logger, CoverageLogger)
        self.assertEqual(logger.logger.name, 'test_module')
    
    @patch.dict(os.environ, {'COVERAGE_LOG_LEVEL': 'DEBUG'})
    def test_get_logger_respects_log_level(self):
        """Test that get_logger respects the COVERAGE_LOG_LEVEL environment variable."""
        logger = get_logger('test_module')
        
        self.assertEqual(logger.logger.level, logging.DEBUG)
    
    @patch.dict(os.environ, {'COVERAGE_LOG_LEVEL': 'ERROR'})
    def test_get_logger_handles_different_log_levels(self):
        """Test that get_logger handles different log levels."""
        logger = get_logger('test_module')
        
        self.assertEqual(logger.logger.level, logging.ERROR)


if __name__ == '__main__':
    unittest.main()