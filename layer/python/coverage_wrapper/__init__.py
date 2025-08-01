"""
Lambda Coverage Layer - Python Coverage Wrapper

This package provides automated code coverage tracking capabilities for AWS Lambda functions.
It integrates the Python coverage.py package to collect coverage data during function execution,
automatically uploads coverage reports to S3, and provides utilities for combining multiple
coverage reports into consolidated reports.
"""

__version__ = "1.0.0"

# Import models for external use
from .models import CoverageConfig, CoverageReportMetadata, HealthCheckResponse, CombinerResult

# Import main wrapper functions
from .wrapper import coverage_handler, CoverageContext

# Import health check functions
from .health_check import health_check_handler, get_coverage_status, get_layer_info, get_health_status

# Import combiner functions
from .combiner import (
    download_coverage_files, 
    merge_coverage_data, 
    combine_coverage_files, 
    coverage_combiner_handler,
    upload_combined_report
)

__all__ = [
    "CoverageConfig",
    "CoverageReportMetadata", 
    "HealthCheckResponse",
    "CombinerResult",
    "coverage_handler",
    "CoverageContext",
    "health_check_handler",
    "get_coverage_status",
    "get_layer_info",
    "get_health_status",
    "download_coverage_files",
    "merge_coverage_data",
    "combine_coverage_files",
    "coverage_combiner_handler",
    "upload_combined_report"
]