"""
Unit tests for the coverage combiner module.

This module contains comprehensive tests for S3 coverage file discovery,
download utilities, file validation, and metadata extraction functionality.
"""

import os
import json
import tempfile
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path

from layer.python.coverage_wrapper.combiner import (
    download_coverage_files,
    cleanup_downloaded_files,
    get_coverage_file_stats,
    get_combiner_s3_config,
    _is_valid_coverage_file,
    _download_single_file,
    _extract_metadata_from_key,
    _validate_coverage_file
)
from layer.python.coverage_wrapper.models import CoverageConfig


class TestDownloadCoverageFiles:
    """Test cases for download_coverage_files function."""
    
    @patch('boto3.client')
    def test_download_coverage_files_success(self, mock_boto3_client):
        """Test successful download of coverage files from S3."""
        # Mock S3 client and responses
        mock_s3_client = MagicMock()
        mock_boto3_client.return_value = mock_s3_client
        
        # Mock list_objects_v2 response
        mock_s3_client.list_objects_v2.return_value = {
            'Contents': [
                {
                    'Key': 'coverage/coverage-test-function-abc123.json',
                    'Size': 1024,
                    'LastModified': datetime(2024, 1, 15, 10, 30, 0)
                },
                {
                    'Key': 'coverage/coverage-another-function-def456.json',
                    'Size': 2048,
                    'LastModified': datetime(2024, 1, 15, 11, 0, 0)
                }
            ],
            'IsTruncated': False
        }
        
        # Mock successful file downloads
        with patch('layer.python.coverage_wrapper.combiner._download_single_file') as mock_download:
            mock_download.side_effect = [
                {
                    's3_key': 'coverage/coverage-test-function-abc123.json',
                    'local_path': '/tmp/coverage_test1.json',
                    'file_size': 1024,
                    'last_modified': datetime(2024, 1, 15, 10, 30, 0),
                    'function_name': 'test-function',
                    'execution_id': 'abc123'
                },
                {
                    's3_key': 'coverage/coverage-another-function-def456.json',
                    'local_path': '/tmp/coverage_test2.json',
                    'file_size': 2048,
                    'last_modified': datetime(2024, 1, 15, 11, 0, 0),
                    'function_name': 'another-function',
                    'execution_id': 'def456'
                }
            ]
            
            # Call function
            result = download_coverage_files('test-bucket', 'coverage/')
            
            # Verify results
            assert len(result) == 2
            assert result[0]['function_name'] == 'test-function'
            assert result[1]['function_name'] == 'another-function'
            
            # Verify S3 client calls
            mock_s3_client.list_objects_v2.assert_called_once_with(
                Bucket='test-bucket',
                Prefix='coverage/',
                MaxKeys=1000
            )
    
    @patch('boto3.client')
    def test_download_coverage_files_empty_bucket(self, mock_boto3_client):
        """Test download when no coverage files exist in bucket."""
        mock_s3_client = MagicMock()
        mock_boto3_client.return_value = mock_s3_client
        
        # Mock empty response
        mock_s3_client.list_objects_v2.return_value = {}
        
        result = download_coverage_files('test-bucket', 'coverage/')
        
        assert result == []
    
    @patch('boto3.client')
    def test_download_coverage_files_with_max_files(self, mock_boto3_client):
        """Test download with maximum file limit."""
        mock_s3_client = MagicMock()
        mock_boto3_client.return_value = mock_s3_client
        
        # Mock response with multiple files
        mock_s3_client.list_objects_v2.return_value = {
            'Contents': [
                {
                    'Key': 'coverage/coverage-func1-id1.json',
                    'Size': 1024,
                    'LastModified': datetime(2024, 1, 15, 10, 30, 0)
                },
                {
                    'Key': 'coverage/coverage-func2-id2.json',
                    'Size': 1024,
                    'LastModified': datetime(2024, 1, 15, 10, 31, 0)
                },
                {
                    'Key': 'coverage/coverage-func3-id3.json',
                    'Size': 1024,
                    'LastModified': datetime(2024, 1, 15, 10, 32, 0)
                }
            ],
            'IsTruncated': False
        }
        
        with patch('layer.python.coverage_wrapper.combiner._download_single_file') as mock_download:
            mock_download.return_value = {
                's3_key': 'test-key',
                'local_path': '/tmp/test.json',
                'file_size': 1024,
                'last_modified': datetime.now(),
                'function_name': 'test',
                'execution_id': 'id'
            }
            
            # Call with max_files=2
            result = download_coverage_files('test-bucket', 'coverage/', max_files=2)
            
            # Should only download 2 files
            assert len(result) == 2
            assert mock_download.call_count == 2
    
    @patch('boto3.client')
    def test_download_coverage_files_pagination(self, mock_boto3_client):
        """Test download with S3 pagination."""
        mock_s3_client = MagicMock()
        mock_boto3_client.return_value = mock_s3_client
        
        # Mock paginated responses
        mock_s3_client.list_objects_v2.side_effect = [
            {
                'Contents': [
                    {
                        'Key': 'coverage/coverage-func1-id1.json',
                        'Size': 1024,
                        'LastModified': datetime(2024, 1, 15, 10, 30, 0)
                    }
                ],
                'IsTruncated': True,
                'NextContinuationToken': 'token123'
            },
            {
                'Contents': [
                    {
                        'Key': 'coverage/coverage-func2-id2.json',
                        'Size': 1024,
                        'LastModified': datetime(2024, 1, 15, 10, 31, 0)
                    }
                ],
                'IsTruncated': False
            }
        ]
        
        with patch('layer.python.coverage_wrapper.combiner._download_single_file') as mock_download:
            mock_download.return_value = {
                's3_key': 'test-key',
                'local_path': '/tmp/test.json',
                'file_size': 1024,
                'last_modified': datetime.now(),
                'function_name': 'test',
                'execution_id': 'id'
            }
            
            result = download_coverage_files('test-bucket', 'coverage/')
            
            # Should make two list_objects_v2 calls
            assert mock_s3_client.list_objects_v2.call_count == 2
            assert len(result) == 2
    
    def test_download_coverage_files_invalid_bucket(self):
        """Test download with invalid bucket name."""
        with pytest.raises(ValueError, match="bucket_name cannot be empty"):
            download_coverage_files('')
    
    @patch('boto3.client')
    def test_download_coverage_files_s3_error(self, mock_boto3_client):
        """Test download with S3 client errors."""
        from botocore.exceptions import ClientError
        
        mock_s3_client = MagicMock()
        mock_boto3_client.return_value = mock_s3_client
        
        # Mock S3 error
        mock_s3_client.list_objects_v2.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchBucket', 'Message': 'Bucket does not exist'}},
            'ListObjectsV2'
        )
        
        with pytest.raises(ClientError):
            download_coverage_files('nonexistent-bucket')


class TestIsValidCoverageFile:
    """Test cases for _is_valid_coverage_file function."""
    
    def test_valid_coverage_files(self):
        """Test recognition of valid coverage file names."""
        valid_files = [
            'coverage/coverage-test-function-abc123.json',
            'coverage/coverage-my-lambda-def456.json',
            'coverage/combined-coverage-report.json',
            'coverage/coverage_alternative_naming.json'
        ]
        
        for file_key in valid_files:
            assert _is_valid_coverage_file(file_key), f"Should be valid: {file_key}"
    
    def test_invalid_coverage_files(self):
        """Test rejection of invalid file names."""
        invalid_files = [
            'coverage/not-a-coverage-file.json',
            'coverage/coverage-test.txt',  # Wrong extension
            'coverage/coverage-test.json.tmp',  # Temporary file
            'coverage/coverage-test.json.bak',  # Backup file
            'coverage/coverage-test~.json',  # Backup file
            'coverage/',  # Directory marker
            'logs/application.log',  # Different file type
            'coverage/coverage-test',  # No extension
        ]
        
        for file_key in invalid_files:
            assert not _is_valid_coverage_file(file_key), f"Should be invalid: {file_key}"
    
    def test_case_insensitive_validation(self):
        """Test that validation is case insensitive."""
        assert _is_valid_coverage_file('coverage/COVERAGE-TEST-ABC123.JSON')
        assert _is_valid_coverage_file('coverage/Coverage-Test-Def456.json')


class TestExtractMetadataFromKey:
    """Test cases for _extract_metadata_from_key function."""
    
    def test_extract_metadata_standard_format(self):
        """Test metadata extraction from standard format keys."""
        test_cases = [
            ('coverage/coverage-test-function-abc123.json', 'test-function', 'abc123'),
            ('coverage/coverage-my-lambda-def456.json', 'my-lambda', 'def456'),
            ('prefix/coverage-another-func-xyz789.json', 'another-func', 'xyz789'),
        ]
        
        for s3_key, expected_function, expected_id in test_cases:
            function_name, execution_id = _extract_metadata_from_key(s3_key)
            assert function_name == expected_function
            assert execution_id == expected_id
    
    def test_extract_metadata_no_execution_id(self):
        """Test metadata extraction when execution ID is missing."""
        function_name, execution_id = _extract_metadata_from_key('coverage/coverage-test-function.json')
        assert function_name == 'test-function'
        assert execution_id is None
    
    def test_extract_metadata_invalid_format(self):
        """Test metadata extraction from invalid format keys."""
        invalid_keys = [
            'coverage/not-coverage-file.json',
            'coverage/coverage-.json',
            'coverage/.json',
            'coverage/coverage.json'
        ]
        
        for key in invalid_keys:
            function_name, execution_id = _extract_metadata_from_key(key)
            # Should handle gracefully, may return None or partial data
            assert isinstance(function_name, (str, type(None)))
            assert isinstance(execution_id, (str, type(None)))


class TestValidateCoverageFile:
    """Test cases for _validate_coverage_file function."""
    
    def test_validate_valid_coverage_file(self):
        """Test validation of a valid coverage file."""
        valid_coverage_data = {
            'files': {
                '/path/to/file.py': {
                    'executed_lines': [1, 2, 3],
                    'missing_lines': [4, 5],
                    'summary': {'covered_lines': 3, 'num_statements': 5}
                }
            },
            'totals': {
                'covered_lines': 3,
                'num_statements': 5,
                'percent_covered': 60.0
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(valid_coverage_data, f)
            temp_path = f.name
        
        try:
            assert _validate_coverage_file(temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_validate_invalid_json(self):
        """Test validation of invalid JSON file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('invalid json content {')
            temp_path = f.name
        
        try:
            assert not _validate_coverage_file(temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_validate_missing_required_keys(self):
        """Test validation of JSON missing required keys."""
        invalid_data = {'files': {}}  # Missing 'totals'
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(invalid_data, f)
            temp_path = f.name
        
        try:
            assert not _validate_coverage_file(temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_validate_nonexistent_file(self):
        """Test validation of nonexistent file."""
        assert not _validate_coverage_file('/nonexistent/file.json')
    
    def test_validate_empty_file(self):
        """Test validation of empty file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            assert not _validate_coverage_file(temp_path)
        finally:
            os.unlink(temp_path)


class TestDownloadSingleFile:
    """Test cases for _download_single_file function."""
    
    @patch('tempfile.NamedTemporaryFile')
    @patch('layer.python.coverage_wrapper.combiner._validate_coverage_file')
    def test_download_single_file_success(self, mock_validate, mock_tempfile):
        """Test successful single file download."""
        # Mock temporary file
        mock_temp = MagicMock()
        mock_temp.name = '/tmp/coverage_test.json'
        mock_tempfile.return_value = mock_temp
        
        # Mock validation
        mock_validate.return_value = True
        
        # Mock S3 client
        mock_s3_client = MagicMock()
        
        # Mock object metadata
        obj_metadata = {
            'Size': 1024,
            'LastModified': datetime(2024, 1, 15, 10, 30, 0)
        }
        
        result = _download_single_file(
            mock_s3_client,
            'test-bucket',
            'coverage/coverage-test-func-abc123.json',
            obj_metadata
        )
        
        assert result is not None
        assert result['s3_key'] == 'coverage/coverage-test-func-abc123.json'
        assert result['local_path'] == '/tmp/coverage_test.json'
        assert result['file_size'] == 1024
        assert result['function_name'] == 'test-func'
        assert result['execution_id'] == 'abc123'
        
        # Verify S3 download was called
        mock_s3_client.download_fileobj.assert_called_once()
    
    @patch('tempfile.NamedTemporaryFile')
    @patch('layer.python.coverage_wrapper.combiner._validate_coverage_file')
    @patch('os.unlink')
    def test_download_single_file_validation_failure(self, mock_unlink, mock_validate, mock_tempfile):
        """Test single file download with validation failure."""
        # Mock temporary file
        mock_temp = MagicMock()
        mock_temp.name = '/tmp/coverage_test.json'
        mock_tempfile.return_value = mock_temp
        
        # Mock validation failure
        mock_validate.return_value = False
        
        # Mock S3 client
        mock_s3_client = MagicMock()
        
        obj_metadata = {
            'Size': 1024,
            'LastModified': datetime(2024, 1, 15, 10, 30, 0)
        }
        
        result = _download_single_file(
            mock_s3_client,
            'test-bucket',
            'coverage/invalid-file.json',
            obj_metadata
        )
        
        assert result is None
        mock_unlink.assert_called_once_with('/tmp/coverage_test.json')
    
    @patch('tempfile.NamedTemporaryFile')
    def test_download_single_file_s3_error(self, mock_tempfile):
        """Test single file download with S3 error."""
        from botocore.exceptions import ClientError
        
        # Mock temporary file
        mock_temp = MagicMock()
        mock_temp.name = '/tmp/coverage_test.json'
        mock_tempfile.return_value = mock_temp
        
        # Mock S3 client with error
        mock_s3_client = MagicMock()
        mock_s3_client.download_fileobj.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchKey', 'Message': 'Key does not exist'}},
            'GetObject'
        )
        
        obj_metadata = {
            'Size': 1024,
            'LastModified': datetime(2024, 1, 15, 10, 30, 0)
        }
        
        result = _download_single_file(
            mock_s3_client,
            'test-bucket',
            'coverage/nonexistent-file.json',
            obj_metadata
        )
        
        assert result is None


class TestCleanupDownloadedFiles:
    """Test cases for cleanup_downloaded_files function."""
    
    @patch('os.path.exists')
    @patch('os.unlink')
    def test_cleanup_downloaded_files_success(self, mock_unlink, mock_exists):
        """Test successful cleanup of downloaded files."""
        mock_exists.return_value = True
        
        file_list = [
            {'local_path': '/tmp/file1.json'},
            {'local_path': '/tmp/file2.json'},
            {'local_path': '/tmp/file3.json'}
        ]
        
        cleanup_downloaded_files(file_list)
        
        assert mock_unlink.call_count == 3
        mock_unlink.assert_any_call('/tmp/file1.json')
        mock_unlink.assert_any_call('/tmp/file2.json')
        mock_unlink.assert_any_call('/tmp/file3.json')
    
    @patch('os.path.exists')
    @patch('os.unlink')
    def test_cleanup_downloaded_files_missing_files(self, mock_unlink, mock_exists):
        """Test cleanup when some files don't exist."""
        mock_exists.side_effect = [True, False, True]
        
        file_list = [
            {'local_path': '/tmp/file1.json'},
            {'local_path': '/tmp/file2.json'},
            {'local_path': '/tmp/file3.json'}
        ]
        
        cleanup_downloaded_files(file_list)
        
        # Should only try to unlink existing files
        assert mock_unlink.call_count == 2
        mock_unlink.assert_any_call('/tmp/file1.json')
        mock_unlink.assert_any_call('/tmp/file3.json')
    
    @patch('os.path.exists')
    @patch('os.unlink')
    def test_cleanup_downloaded_files_with_errors(self, mock_unlink, mock_exists):
        """Test cleanup with OS errors."""
        mock_exists.return_value = True
        mock_unlink.side_effect = [None, OSError("Permission denied"), None]
        
        file_list = [
            {'local_path': '/tmp/file1.json'},
            {'local_path': '/tmp/file2.json'},
            {'local_path': '/tmp/file3.json'}
        ]
        
        # Should not raise exception
        cleanup_downloaded_files(file_list)
        
        assert mock_unlink.call_count == 3


class TestGetCoverageFileStats:
    """Test cases for get_coverage_file_stats function."""
    
    def test_get_coverage_file_stats_with_files(self):
        """Test statistics generation with multiple files."""
        file_list = [
            {
                'file_size': 1024,
                'function_name': 'func1',
                'last_modified': datetime(2024, 1, 15, 10, 0, 0)
            },
            {
                'file_size': 2048,
                'function_name': 'func2',
                'last_modified': datetime(2024, 1, 15, 11, 0, 0)
            },
            {
                'file_size': 512,
                'function_name': 'func1',  # Duplicate function
                'last_modified': datetime(2024, 1, 15, 12, 0, 0)
            }
        ]
        
        stats = get_coverage_file_stats(file_list)
        
        assert stats['file_count'] == 3
        assert stats['total_size_bytes'] == 3584
        assert stats['total_size_mb'] == 0.0  # Small files
        assert stats['function_count'] == 2
        assert set(stats['functions']) == {'func1', 'func2'}
        assert stats['date_range']['earliest'] == datetime(2024, 1, 15, 10, 0, 0)
        assert stats['date_range']['latest'] == datetime(2024, 1, 15, 12, 0, 0)
    
    def test_get_coverage_file_stats_empty_list(self):
        """Test statistics generation with empty file list."""
        stats = get_coverage_file_stats([])
        
        assert stats['file_count'] == 0
        assert stats['total_size_bytes'] == 0
        assert stats['functions'] == []
        assert stats['date_range'] is None
    
    def test_get_coverage_file_stats_with_none_function_names(self):
        """Test statistics generation with None function names."""
        file_list = [
            {
                'file_size': 1024,
                'function_name': None,
                'last_modified': datetime(2024, 1, 15, 10, 0, 0)
            },
            {
                'file_size': 2048,
                'function_name': 'func1',
                'last_modified': datetime(2024, 1, 15, 11, 0, 0)
            }
        ]
        
        stats = get_coverage_file_stats(file_list)
        
        assert stats['file_count'] == 2
        assert stats['function_count'] == 1
        assert stats['functions'] == ['func1']


class TestGetCombinerS3Config:
    """Test cases for get_combiner_s3_config function."""
    
    @patch('layer.python.coverage_wrapper.combiner.get_s3_config')
    def test_get_combiner_s3_config_success(self, mock_get_s3_config):
        """Test successful S3 configuration retrieval."""
        expected_config = CoverageConfig(s3_bucket='test-bucket')
        mock_get_s3_config.return_value = expected_config
        
        result = get_combiner_s3_config()
        
        assert result == expected_config
        mock_get_s3_config.assert_called_once()
    
    @patch('layer.python.coverage_wrapper.combiner.get_s3_config')
    def test_get_combiner_s3_config_error(self, mock_get_s3_config):
        """Test S3 configuration retrieval with error."""
        mock_get_s3_config.side_effect = ValueError("Missing S3 bucket")
        
        with pytest.raises(ValueError, match="Invalid S3 configuration"):
            get_combiner_s3_config()


class TestMergeCoverageData:
    """Test cases for merge_coverage_data function."""
    
    @patch('coverage.Coverage')
    @patch('tempfile.NamedTemporaryFile')
    @patch('tempfile.TemporaryDirectory')
    def test_merge_coverage_data_success(self, mock_temp_dir, mock_temp_file, mock_coverage_class):
        """Test successful coverage data merging."""
        # Mock temporary directory
        mock_temp_dir.return_value.__enter__.return_value = '/tmp/coverage_merge_test'
        
        # Mock temporary file
        mock_file = MagicMock()
        mock_file.name = '/tmp/combined_coverage_test.json'
        mock_temp_file.return_value = mock_file
        
        # Mock coverage instance
        mock_coverage = MagicMock()
        mock_coverage_class.return_value = mock_coverage
        
        # Mock combined coverage data
        combined_data = {
            'files': {
                '/path/to/file1.py': {'executed_lines': [1, 2, 3]},
                '/path/to/file2.py': {'executed_lines': [1, 2]}
            },
            'totals': {
                'covered_lines': 5,
                'num_statements': 10,
                'percent_covered': 50.0
            }
        }
        
        # Create test files
        test_files = [
            {
                'local_path': '/tmp/coverage1.json',
                's3_key': 'coverage/coverage-func1-id1.json',
                'function_name': 'func1',
                'execution_id': 'id1',
                'file_size': 1024,
                'last_modified': datetime(2024, 1, 15, 10, 0, 0)
            },
            {
                'local_path': '/tmp/coverage2.json',
                's3_key': 'coverage/coverage-func2-id2.json',
                'function_name': 'func2',
                'execution_id': 'id2',
                'file_size': 2048,
                'last_modified': datetime(2024, 1, 15, 11, 0, 0)
            }
        ]
        
        with patch('os.path.exists', return_value=True), \
             patch('layer.python.coverage_wrapper.combiner._validate_coverage_file', return_value=True), \
             patch('builtins.open', mock_open(read_data=json.dumps(combined_data))), \
             patch('os.path.getsize', return_value=5120):
            
            from layer.python.coverage_wrapper.combiner import merge_coverage_data
            
            combined_file_path, merge_stats = merge_coverage_data(test_files)
            
            assert combined_file_path == '/tmp/combined_coverage_test.json'
            assert merge_stats['files_processed'] == 2
            assert merge_stats['files_skipped'] == 0
            assert merge_stats['total_coverage_percentage'] == 50.0
            assert merge_stats['function_count'] == 2
            
            # Verify coverage.combine was called
            mock_coverage.combine.assert_called_once()
            mock_coverage.json_report.assert_called_once_with(outfile='/tmp/combined_coverage_test.json')
    
    def test_merge_coverage_data_empty_file_list(self):
        """Test merge with empty file list."""
        from layer.python.coverage_wrapper.combiner import merge_coverage_data
        
        with pytest.raises(ValueError, match="No coverage files provided for merging"):
            merge_coverage_data([])
    
    @patch('os.path.exists')
    def test_merge_coverage_data_no_valid_files(self, mock_exists):
        """Test merge when no valid files are found."""
        mock_exists.return_value = False
        
        test_files = [
            {'local_path': '/tmp/nonexistent.json', 's3_key': 'test.json'}
        ]
        
        from layer.python.coverage_wrapper.combiner import merge_coverage_data
        
        with pytest.raises(ValueError, match="No valid coverage files found for merging"):
            merge_coverage_data(test_files)
    
    @patch('coverage.Coverage')
    @patch('tempfile.NamedTemporaryFile')
    @patch('tempfile.TemporaryDirectory')
    def test_merge_coverage_data_with_invalid_files(self, mock_temp_dir, mock_temp_file, mock_coverage_class):
        """Test merge with some invalid files that should be skipped."""
        # Mock temporary directory and file
        mock_temp_dir.return_value.__enter__.return_value = '/tmp/coverage_merge_test'
        mock_file = MagicMock()
        mock_file.name = '/tmp/combined_coverage_test.json'
        mock_temp_file.return_value = mock_file
        
        # Mock coverage instance
        mock_coverage = MagicMock()
        mock_coverage_class.return_value = mock_coverage
        
        test_files = [
            {
                'local_path': '/tmp/valid_coverage.json',
                's3_key': 'coverage/valid.json',
                'function_name': 'func1',
                'file_size': 1024,
                'last_modified': datetime(2024, 1, 15, 10, 0, 0)
            },
            {
                'local_path': '/tmp/invalid_coverage.json',
                's3_key': 'coverage/invalid.json',
                'function_name': 'func2',
                'file_size': 512,
                'last_modified': datetime(2024, 1, 15, 11, 0, 0)
            }
        ]
        
        # Mock file existence and validation
        def mock_exists(path):
            return path == '/tmp/valid_coverage.json'
        
        def mock_validate(path):
            return path == '/tmp/valid_coverage.json'
        
        combined_data = {
            'files': {'/path/to/file.py': {'executed_lines': [1, 2]}},
            'totals': {'covered_lines': 2, 'num_statements': 5, 'percent_covered': 40.0}
        }
        
        with patch('os.path.exists', side_effect=mock_exists), \
             patch('layer.python.coverage_wrapper.combiner._validate_coverage_file', side_effect=mock_validate), \
             patch('builtins.open', mock_open(read_data=json.dumps(combined_data))), \
             patch('os.path.getsize', return_value=2048):
            
            from layer.python.coverage_wrapper.combiner import merge_coverage_data
            
            combined_file_path, merge_stats = merge_coverage_data(test_files)
            
            assert merge_stats['files_processed'] == 1
            assert merge_stats['files_skipped'] == 1
            assert merge_stats['total_coverage_percentage'] == 40.0


class TestValidateCoverageFilesIntegrity:
    """Test cases for validate_coverage_files_integrity function."""
    
    def test_validate_coverage_files_integrity_all_valid(self):
        """Test validation when all files are valid."""
        test_files = [
            {
                'local_path': '/tmp/coverage1.json',
                's3_key': 'coverage/coverage1.json'
            },
            {
                'local_path': '/tmp/coverage2.json',
                's3_key': 'coverage/coverage2.json'
            }
        ]
        
        with patch('os.path.exists', return_value=True), \
             patch('layer.python.coverage_wrapper.combiner._validate_coverage_file', return_value=True), \
             patch('layer.python.coverage_wrapper.combiner._perform_advanced_validation', return_value={'valid': True}):
            
            from layer.python.coverage_wrapper.combiner import validate_coverage_files_integrity
            
            valid_files, invalid_files = validate_coverage_files_integrity(test_files)
            
            assert len(valid_files) == 2
            assert len(invalid_files) == 0
            assert all(f['validation_status'] == 'valid' for f in valid_files)
    
    def test_validate_coverage_files_integrity_mixed_validity(self):
        """Test validation with mix of valid and invalid files."""
        test_files = [
            {
                'local_path': '/tmp/valid_coverage.json',
                's3_key': 'coverage/valid.json'
            },
            {
                'local_path': '/tmp/invalid_coverage.json',
                's3_key': 'coverage/invalid.json'
            },
            {
                'local_path': '/tmp/missing_coverage.json',
                's3_key': 'coverage/missing.json'
            }
        ]
        
        def mock_exists(path):
            return path != '/tmp/missing_coverage.json'
        
        def mock_validate(path):
            return path == '/tmp/valid_coverage.json'
        
        def mock_advanced_validate(path):
            if path == '/tmp/valid_coverage.json':
                return {'valid': True}
            else:
                return {'valid': False, 'error': 'Advanced validation failed'}
        
        with patch('os.path.exists', side_effect=mock_exists), \
             patch('layer.python.coverage_wrapper.combiner._validate_coverage_file', side_effect=mock_validate), \
             patch('layer.python.coverage_wrapper.combiner._perform_advanced_validation', side_effect=mock_advanced_validate):
            
            from layer.python.coverage_wrapper.combiner import validate_coverage_files_integrity
            
            valid_files, invalid_files = validate_coverage_files_integrity(test_files)
            
            assert len(valid_files) == 1
            assert len(invalid_files) == 2
            assert valid_files[0]['s3_key'] == 'coverage/valid.json'
            assert any(f['s3_key'] == 'coverage/invalid.json' for f in invalid_files)
            assert any(f['s3_key'] == 'coverage/missing.json' for f in invalid_files)


class TestPerformAdvancedValidation:
    """Test cases for _perform_advanced_validation function."""
    
    def test_perform_advanced_validation_valid_file(self):
        """Test advanced validation with valid coverage file."""
        valid_data = {
            'files': {
                '/path/to/file.py': {
                    'executed_lines': [1, 2, 3],
                    'missing_lines': [4, 5]
                }
            },
            'totals': {
                'covered_lines': 3,
                'num_statements': 5,
                'percent_covered': 60.0
            }
        }
        
        with patch('builtins.open', mock_open(read_data=json.dumps(valid_data))):
            from layer.python.coverage_wrapper.combiner import _perform_advanced_validation
            
            result = _perform_advanced_validation('/tmp/test.json')
            
            assert result['valid'] is True
    
    def test_perform_advanced_validation_missing_keys(self):
        """Test advanced validation with missing required keys."""
        invalid_data = {
            'files': {},
            'totals': {
                'covered_lines': 3
                # Missing 'num_statements'
            }
        }
        
        with patch('builtins.open', mock_open(read_data=json.dumps(invalid_data))):
            from layer.python.coverage_wrapper.combiner import _perform_advanced_validation
            
            result = _perform_advanced_validation('/tmp/test.json')
            
            assert result['valid'] is False
            assert 'num_statements' in result['error']
    
    def test_perform_advanced_validation_invalid_values(self):
        """Test advanced validation with invalid numeric values."""
        invalid_data = {
            'files': {},
            'totals': {
                'covered_lines': -1,  # Invalid negative value
                'num_statements': 5
            }
        }
        
        with patch('builtins.open', mock_open(read_data=json.dumps(invalid_data))):
            from layer.python.coverage_wrapper.combiner import _perform_advanced_validation
            
            result = _perform_advanced_validation('/tmp/test.json')
            
            assert result['valid'] is False
            assert 'covered_lines' in result['error']
    
    def test_perform_advanced_validation_json_error(self):
        """Test advanced validation with invalid JSON."""
        with patch('builtins.open', mock_open(read_data='invalid json {')):
            from layer.python.coverage_wrapper.combiner import _perform_advanced_validation
            
            result = _perform_advanced_validation('/tmp/test.json')
            
            assert result['valid'] is False
            assert 'JSON decode error' in result['error']


class TestCreateMergeReport:
    """Test cases for create_merge_report function."""
    
    def test_create_merge_report_complete(self):
        """Test creation of complete merge report."""
        merge_stats = {
            'total_coverage_percentage': 75.5,
            'functions_merged': ['func1', 'func2'],
            'function_count': 2,
            'total_size_bytes': 3072,
            'combined_file_size': 4096,
            'date_range': {
                'earliest': datetime(2024, 1, 15, 10, 0, 0),
                'latest': datetime(2024, 1, 15, 12, 0, 0)
            },
            'merge_timestamp': datetime(2024, 1, 15, 13, 0, 0)
        }
        
        valid_files = [
            {
                's3_key': 'coverage/func1.json',
                'function_name': 'func1',
                'execution_id': 'id1',
                'file_size': 1024,
                'last_modified': datetime(2024, 1, 15, 10, 0, 0)
            }
        ]
        
        invalid_files = [
            {
                's3_key': 'coverage/invalid.json',
                'validation_error': 'Invalid JSON format',
                'file_size': 512
            }
        ]
        
        from layer.python.coverage_wrapper.combiner import create_merge_report
        
        report = create_merge_report(merge_stats, valid_files, invalid_files)
        
        assert report['merge_summary']['total_files_processed'] == 2
        assert report['merge_summary']['files_successfully_merged'] == 1
        assert report['merge_summary']['files_skipped_or_failed'] == 1
        assert report['merge_summary']['overall_coverage_percentage'] == 75.5
        
        assert report['merged_functions']['function_count'] == 2
        assert 'func1' in report['merged_functions']['function_names']
        
        assert report['file_statistics']['total_size_bytes'] == 3072
        assert report['file_statistics']['combined_file_size_bytes'] == 4096
        
        assert len(report['processing_details']['valid_files']) == 1
        assert len(report['processing_details']['invalid_files']) == 1


# Integration test class
class TestCombinerIntegration:
    """Integration tests for combiner functionality."""
    
    @patch.dict(os.environ, {
        'COVERAGE_S3_BUCKET': 'test-bucket',
        'COVERAGE_S3_PREFIX': 'coverage/'
    })
    @patch('boto3.client')
    def test_download_coverage_files_integration(self, mock_boto3_client):
        """Integration test for the complete download workflow."""
        # Mock S3 client
        mock_s3_client = MagicMock()
        mock_boto3_client.return_value = mock_s3_client
        
        # Mock S3 response
        mock_s3_client.list_objects_v2.return_value = {
            'Contents': [
                {
                    'Key': 'coverage/coverage-test-function-abc123.json',
                    'Size': 1024,
                    'LastModified': datetime(2024, 1, 15, 10, 30, 0)
                }
            ],
            'IsTruncated': False
        }
        
        # Mock file download and validation
        with patch('tempfile.NamedTemporaryFile') as mock_tempfile, \
             patch('layer.python.coverage_wrapper.combiner._validate_coverage_file') as mock_validate:
            
            mock_temp = MagicMock()
            mock_temp.name = '/tmp/coverage_test.json'
            mock_tempfile.return_value = mock_temp
            mock_validate.return_value = True
            
            # Test the integration
            result = download_coverage_files('test-bucket')
            
            assert len(result) == 1
            assert result[0]['function_name'] == 'test-function'
            assert result[0]['execution_id'] == 'abc123'
    
    @patch('coverage.Coverage')
    @patch('tempfile.NamedTemporaryFile')
    @patch('tempfile.TemporaryDirectory')
    def test_complete_merge_workflow_integration(self, mock_temp_dir, mock_temp_file, mock_coverage_class):
        """Integration test for the complete merge workflow."""
        # Mock temporary directory and file
        mock_temp_dir.return_value.__enter__.return_value = '/tmp/coverage_merge_test'
        mock_file = MagicMock()
        mock_file.name = '/tmp/combined_coverage_test.json'
        mock_temp_file.return_value = mock_file
        
        # Mock coverage instance
        mock_coverage = MagicMock()
        mock_coverage_class.return_value = mock_coverage
        
        # Test files with realistic data
        test_files = [
            {
                'local_path': '/tmp/coverage1.json',
                's3_key': 'coverage/coverage-lambda1-abc123.json',
                'function_name': 'lambda1',
                'execution_id': 'abc123',
                'file_size': 1024,
                'last_modified': datetime(2024, 1, 15, 10, 0, 0)
            },
            {
                'local_path': '/tmp/coverage2.json',
                's3_key': 'coverage/coverage-lambda2-def456.json',
                'function_name': 'lambda2',
                'execution_id': 'def456',
                'file_size': 2048,
                'last_modified': datetime(2024, 1, 15, 11, 0, 0)
            }
        ]
        
        combined_data = {
            'files': {
                '/var/task/lambda1.py': {'executed_lines': [1, 2, 3, 5], 'missing_lines': [4]},
                '/var/task/lambda2.py': {'executed_lines': [1, 2], 'missing_lines': [3, 4, 5]}
            },
            'totals': {
                'covered_lines': 6,
                'num_statements': 10,
                'percent_covered': 60.0
            }
        }
        
        with patch('os.path.exists', return_value=True), \
             patch('layer.python.coverage_wrapper.combiner._validate_coverage_file', return_value=True), \
             patch('builtins.open', mock_open(read_data=json.dumps(combined_data))), \
             patch('os.path.getsize', return_value=3072):
            
            from layer.python.coverage_wrapper.combiner import (
                merge_coverage_data, 
                validate_coverage_files_integrity,
                create_merge_report
            )
            
            # Step 1: Validate files
            valid_files, invalid_files = validate_coverage_files_integrity(test_files)
            assert len(valid_files) == 2
            assert len(invalid_files) == 0
            
            # Step 2: Merge coverage data
            combined_file_path, merge_stats = merge_coverage_data(valid_files)
            assert combined_file_path == '/tmp/combined_coverage_test.json'
            assert merge_stats['files_processed'] == 2
            assert merge_stats['total_coverage_percentage'] == 60.0
            
            # Step 3: Create merge report
            report = create_merge_report(merge_stats, valid_files, invalid_files)
            assert report['merge_summary']['files_successfully_merged'] == 2
            assert report['merged_functions']['function_count'] == 2
            
            # Verify coverage operations were called
            mock_coverage.combine.assert_called_once()
            mock_coverage.json_report.assert_called_once()


class TestUploadCombinedReport:
    """Test cases for upload_combined_report function."""
    
    @patch('boto3.client')
    @patch('os.path.exists')
    @patch('os.path.getsize')
    @patch('builtins.open', new_callable=mock_open, read_data=b'{"test": "data"}')
    def test_upload_combined_report_success(self, mock_file, mock_getsize, mock_exists, mock_boto3_client):
        """Test successful upload of combined report."""
        # Mock file system
        mock_exists.return_value = True
        mock_getsize.return_value = 1024
        
        # Mock S3 client
        mock_s3_client = MagicMock()
        mock_boto3_client.return_value = mock_s3_client
        
        from layer.python.coverage_wrapper.combiner import upload_combined_report
        
        result = upload_combined_report(
            '/tmp/combined_coverage.json',
            'test-bucket',
            'coverage/combined-report.json',
            {'CustomKey': 'CustomValue'}
        )
        
        assert result['success'] is True
        assert result['bucket_name'] == 'test-bucket'
        assert result['output_key'] == 'coverage/combined-report.json'
        assert result['file_size'] == 1024
        
        # Verify S3 upload was called
        mock_s3_client.upload_fileobj.assert_called_once()
        call_args = mock_s3_client.upload_fileobj.call_args
        assert call_args[0][1] == 'test-bucket'
        assert call_args[0][2] == 'coverage/combined-report.json'
        assert 'CustomKey' in call_args[1]['ExtraArgs']['Metadata']
    
    def test_upload_combined_report_file_not_exists(self):
        """Test upload when file doesn't exist."""
        from layer.python.coverage_wrapper.combiner import upload_combined_report
        
        with patch('os.path.exists', return_value=False):
            with pytest.raises(ValueError, match="Combined coverage file does not exist"):
                upload_combined_report('/tmp/nonexistent.json', 'test-bucket', 'test-key')
    
    def test_upload_combined_report_invalid_parameters(self):
        """Test upload with invalid parameters."""
        from layer.python.coverage_wrapper.combiner import upload_combined_report
        
        with patch('os.path.exists', return_value=True):
            # Test empty bucket name
            with pytest.raises(ValueError, match="bucket_name cannot be empty"):
                upload_combined_report('/tmp/test.json', '', 'test-key')
            
            # Test empty output key
            with pytest.raises(ValueError, match="output_key cannot be empty"):
                upload_combined_report('/tmp/test.json', 'test-bucket', '')
    
    @patch('boto3.client')
    @patch('os.path.exists')
    def test_upload_combined_report_s3_error(self, mock_exists, mock_boto3_client):
        """Test upload with S3 error."""
        from botocore.exceptions import ClientError
        from layer.python.coverage_wrapper.combiner import upload_combined_report
        
        mock_exists.return_value = True
        
        # Mock S3 client with error
        mock_s3_client = MagicMock()
        mock_s3_client.upload_fileobj.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            'PutObject'
        )
        mock_boto3_client.return_value = mock_s3_client
        
        with patch('os.path.getsize', return_value=1024), \
             patch('builtins.open', mock_open(read_data=b'test')):
            
            with pytest.raises(ClientError):
                upload_combined_report('/tmp/test.json', 'test-bucket', 'test-key')


class TestCombineCoverageFiles:
    """Test cases for combine_coverage_files function."""
    
    @patch('layer.python.coverage_wrapper.combiner.download_coverage_files')
    @patch('layer.python.coverage_wrapper.combiner.validate_coverage_files_integrity')
    @patch('layer.python.coverage_wrapper.combiner.merge_coverage_data')
    @patch('layer.python.coverage_wrapper.combiner.upload_combined_report')
    @patch('layer.python.coverage_wrapper.combiner.cleanup_downloaded_files')
    def test_combine_coverage_files_success(self, mock_cleanup, mock_upload, mock_merge, 
                                          mock_validate, mock_download):
        """Test successful coverage file combination."""
        # Mock download
        downloaded_files = [
            {'local_path': '/tmp/file1.json', 's3_key': 'coverage/file1.json'},
            {'local_path': '/tmp/file2.json', 's3_key': 'coverage/file2.json'}
        ]
        mock_download.return_value = downloaded_files
        
        # Mock validation
        valid_files = downloaded_files
        invalid_files = []
        mock_validate.return_value = (valid_files, invalid_files)
        
        # Mock merge
        merge_stats = {
            'files_processed': 2,
            'files_skipped': 0,
            'total_coverage_percentage': 75.0,
            'function_count': 2
        }
        mock_merge.return_value = ('/tmp/combined.json', merge_stats)
        
        # Mock upload
        mock_upload.return_value = {'success': True}
        
        from layer.python.coverage_wrapper.combiner import combine_coverage_files
        
        result = combine_coverage_files('test-bucket', 'coverage/')
        
        assert result.success is True
        assert result.files_processed == 2
        assert result.files_skipped == 0
        assert result.total_coverage_percentage == 75.0
        assert len(result.errors) == 0
        
        # Verify all steps were called
        mock_download.assert_called_once_with('test-bucket', 'coverage/', None)
        mock_validate.assert_called_once_with(downloaded_files)
        mock_merge.assert_called_once_with(valid_files)
        mock_upload.assert_called_once()
        mock_cleanup.assert_called_once_with(downloaded_files)
    
    @patch('layer.python.coverage_wrapper.combiner.download_coverage_files')
    def test_combine_coverage_files_no_files_found(self, mock_download):
        """Test combination when no files are found."""
        mock_download.return_value = []
        
        from layer.python.coverage_wrapper.combiner import combine_coverage_files
        
        result = combine_coverage_files('test-bucket', 'coverage/')
        
        assert result.success is False
        assert result.files_processed == 0
        assert "No coverage files found" in result.errors[0]
    
    @patch('layer.python.coverage_wrapper.combiner.download_coverage_files')
    @patch('layer.python.coverage_wrapper.combiner.validate_coverage_files_integrity')
    def test_combine_coverage_files_no_valid_files(self, mock_validate, mock_download):
        """Test combination when no valid files are found after validation."""
        # Mock download with files
        downloaded_files = [
            {'local_path': '/tmp/invalid.json', 's3_key': 'coverage/invalid.json'}
        ]
        mock_download.return_value = downloaded_files
        
        # Mock validation with no valid files
        mock_validate.return_value = ([], downloaded_files)
        
        from layer.python.coverage_wrapper.combiner import combine_coverage_files
        
        result = combine_coverage_files('test-bucket', 'coverage/')
        
        assert result.success is False
        assert result.files_processed == 0
        assert result.files_skipped == 1
        assert "No valid coverage files found after validation" in result.errors[0]
    
    @patch('layer.python.coverage_wrapper.combiner.download_coverage_files')
    def test_combine_coverage_files_exception_handling(self, mock_download):
        """Test combination with exception during processing."""
        mock_download.side_effect = Exception("Download failed")
        
        from layer.python.coverage_wrapper.combiner import combine_coverage_files
        
        result = combine_coverage_files('test-bucket', 'coverage/')
        
        assert result.success is False
        assert "Combination failed: Download failed" in result.errors[0]


class TestCoverageCombinerHandler:
    """Test cases for coverage_combiner_handler function."""
    
    @patch('layer.python.coverage_wrapper.combiner.combine_coverage_files')
    def test_coverage_combiner_handler_success(self, mock_combine):
        """Test successful Lambda handler execution."""
        # Mock combine result
        from layer.python.coverage_wrapper.models import CombinerResult
        mock_result = CombinerResult(
            success=True,
            combined_file_key='coverage/combined-report.json',
            files_processed=3,
            files_skipped=1,
            total_coverage_percentage=80.0,
            errors=[]
        )
        mock_combine.return_value = mock_result
        
        # Mock Lambda context
        mock_context = MagicMock()
        mock_context.aws_request_id = 'test-request-id'
        mock_context.function_name = 'test-combiner-function'
        
        event = {
            'bucket_name': 'test-bucket',
            'prefix': 'coverage/',
            'max_files': 100
        }
        
        from layer.python.coverage_wrapper.combiner import coverage_combiner_handler
        
        response = coverage_combiner_handler(event, mock_context)
        
        assert response['success'] is True
        assert response['combined_file_key'] == 'coverage/combined-report.json'
        assert response['files_processed'] == 3
        assert response['files_skipped'] == 1
        assert response['total_coverage_percentage'] == 80.0
        assert response['lambda_request_id'] == 'test-request-id'
        assert response['lambda_function_name'] == 'test-combiner-function'
        
        # Verify combine was called with correct parameters
        mock_combine.assert_called_once_with(
            bucket_name='test-bucket',
            prefix='coverage/',
            output_key=None,
            max_files=100
        )
    
    def test_coverage_combiner_handler_missing_bucket(self):
        """Test handler with missing bucket_name."""
        event = {'prefix': 'coverage/'}
        mock_context = MagicMock()
        mock_context.aws_request_id = 'test-request-id'
        mock_context.function_name = 'test-function'
        
        from layer.python.coverage_wrapper.combiner import coverage_combiner_handler
        
        response = coverage_combiner_handler(event, mock_context)
        
        assert response['success'] is False
        assert "bucket_name is required" in response['errors'][0]
    
    def test_coverage_combiner_handler_invalid_max_files(self):
        """Test handler with invalid max_files parameter."""
        event = {
            'bucket_name': 'test-bucket',
            'max_files': -1  # Invalid negative value
        }
        mock_context = MagicMock()
        
        from layer.python.coverage_wrapper.combiner import coverage_combiner_handler
        
        response = coverage_combiner_handler(event, mock_context)
        
        assert response['success'] is False
        assert "max_files must be a positive integer" in response['errors'][0]
    
    @patch('layer.python.coverage_wrapper.combiner.combine_coverage_files')
    def test_coverage_combiner_handler_with_defaults(self, mock_combine):
        """Test handler with default parameters."""
        from layer.python.coverage_wrapper.models import CombinerResult
        mock_result = CombinerResult(
            success=True,
            combined_file_key='coverage/combined-report.json',
            files_processed=1,
            files_skipped=0,
            total_coverage_percentage=90.0,
            errors=[]
        )
        mock_combine.return_value = mock_result
        
        event = {'bucket_name': 'test-bucket'}  # Only required parameter
        mock_context = MagicMock()
        
        from layer.python.coverage_wrapper.combiner import coverage_combiner_handler
        
        response = coverage_combiner_handler(event, mock_context)
        
        assert response['success'] is True
        
        # Verify combine was called with defaults
        mock_combine.assert_called_once_with(
            bucket_name='test-bucket',
            prefix='coverage/',  # Default
            output_key=None,     # Default
            max_files=None       # Default
        )
    
    @patch('layer.python.coverage_wrapper.combiner.combine_coverage_files')
    def test_coverage_combiner_handler_exception(self, mock_combine):
        """Test handler with exception during combination."""
        mock_combine.side_effect = Exception("Unexpected error")
        
        event = {'bucket_name': 'test-bucket'}
        mock_context = MagicMock()
        mock_context.aws_request_id = 'test-request-id'
        mock_context.function_name = 'test-function'
        
        from layer.python.coverage_wrapper.combiner import coverage_combiner_handler
        
        response = coverage_combiner_handler(event, mock_context)
        
        assert response['success'] is False
        assert "Handler error: Unexpected error" in response['errors'][0]
        assert response['lambda_request_id'] == 'test-request-id'


# Additional integration tests
class TestCombinerFullIntegration:
    """Full integration tests for the complete combiner workflow."""
    
    @patch('boto3.client')
    @patch('coverage.Coverage')
    @patch('tempfile.NamedTemporaryFile')
    @patch('tempfile.TemporaryDirectory')
    def test_full_combiner_workflow(self, mock_temp_dir, mock_temp_file, mock_coverage_class, mock_boto3_client):
        """Test the complete end-to-end combiner workflow."""
        # Mock S3 client
        mock_s3_client = MagicMock()
        mock_boto3_client.return_value = mock_s3_client
        
        # Mock S3 list response
        mock_s3_client.list_objects_v2.return_value = {
            'Contents': [
                {
                    'Key': 'coverage/coverage-func1-id1.json',
                    'Size': 1024,
                    'LastModified': datetime(2024, 1, 15, 10, 0, 0)
                },
                {
                    'Key': 'coverage/coverage-func2-id2.json',
                    'Size': 2048,
                    'LastModified': datetime(2024, 1, 15, 11, 0, 0)
                }
            ],
            'IsTruncated': False
        }
        
        # Mock temporary directory and files
        mock_temp_dir.return_value.__enter__.return_value = '/tmp/coverage_merge_test'
        
        # Mock downloaded files
        mock_temp_download1 = MagicMock()
        mock_temp_download1.name = '/tmp/coverage_download1.json'
        mock_temp_download2 = MagicMock()
        mock_temp_download2.name = '/tmp/coverage_download2.json'
        
        # Mock combined file
        mock_temp_combined = MagicMock()
        mock_temp_combined.name = '/tmp/combined_coverage.json'
        mock_temp_file.side_effect = [mock_temp_download1, mock_temp_download2, mock_temp_combined]
        
        # Mock coverage instance
        mock_coverage = MagicMock()
        mock_coverage_class.return_value = mock_coverage
        
        # Mock coverage data
        combined_data = {
            'files': {
                '/var/task/func1.py': {'executed_lines': [1, 2, 3], 'missing_lines': [4]},
                '/var/task/func2.py': {'executed_lines': [1, 2], 'missing_lines': [3, 4]}
            },
            'totals': {
                'covered_lines': 5,
                'num_statements': 8,
                'percent_covered': 62.5
            }
        }
        
        with patch('os.path.exists', return_value=True), \
             patch('layer.python.coverage_wrapper.combiner._validate_coverage_file', return_value=True), \
             patch('layer.python.coverage_wrapper.combiner._perform_advanced_validation', return_value={'valid': True}), \
             patch('builtins.open', mock_open(read_data=json.dumps(combined_data))), \
             patch('os.path.getsize', return_value=3072), \
             patch('os.unlink'):
            
            from layer.python.coverage_wrapper.combiner import combine_coverage_files
            
            # Execute the full workflow
            result = combine_coverage_files(
                bucket_name='test-bucket',
                prefix='coverage/',
                output_key='coverage/combined-report-test.json'
            )
            
            # Verify successful completion
            assert result.success is True
            assert result.files_processed == 2
            assert result.files_skipped == 0
            assert result.total_coverage_percentage == 62.5
            assert result.combined_file_key == 'coverage/combined-report-test.json'
            assert len(result.errors) == 0
            
            # Verify S3 operations
            mock_s3_client.list_objects_v2.assert_called_once()
            mock_s3_client.download_fileobj.assert_called()  # Called for each file
            mock_s3_client.upload_fileobj.assert_called_once()  # Called for combined report
            
            # Verify coverage operations
            mock_coverage.combine.assert_called_once()
            mock_coverage.json_report.assert_called_once()