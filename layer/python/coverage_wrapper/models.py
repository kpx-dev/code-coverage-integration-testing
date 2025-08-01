"""
Data models for the Lambda Coverage Layer.

This module contains the core data classes used throughout the coverage wrapper system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
import os


@dataclass
class CoverageConfig:
    """Configuration for coverage tracking and S3 upload."""
    
    s3_bucket: str
    s3_prefix: str = "coverage/"
    upload_timeout: int = 30
    include_patterns: Optional[List[str]] = None
    exclude_patterns: Optional[List[str]] = None
    branch_coverage: bool = True
    
    @classmethod
    def from_environment(cls) -> 'CoverageConfig':
        """Create configuration from environment variables."""
        s3_bucket = os.environ.get('COVERAGE_S3_BUCKET')
        if not s3_bucket:
            raise ValueError("COVERAGE_S3_BUCKET environment variable is required")
        
        s3_prefix = os.environ.get('COVERAGE_S3_PREFIX', 'coverage/')
        upload_timeout = int(os.environ.get('COVERAGE_UPLOAD_TIMEOUT', '30'))
        
        # Parse include/exclude patterns from comma-separated strings
        include_patterns = None
        if os.environ.get('COVERAGE_INCLUDE_PATTERNS'):
            include_patterns = [p.strip() for p in os.environ['COVERAGE_INCLUDE_PATTERNS'].split(',')]
        
        exclude_patterns = None
        if os.environ.get('COVERAGE_EXCLUDE_PATTERNS'):
            exclude_patterns = [p.strip() for p in os.environ['COVERAGE_EXCLUDE_PATTERNS'].split(',')]
        
        branch_coverage = os.environ.get('COVERAGE_BRANCH_COVERAGE', 'true').lower() == 'true'
        
        return cls(
            s3_bucket=s3_bucket,
            s3_prefix=s3_prefix,
            upload_timeout=upload_timeout,
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
            branch_coverage=branch_coverage
        )
    
    def validate(self) -> None:
        """Validate configuration parameters."""
        if not self.s3_bucket:
            raise ValueError("s3_bucket cannot be empty")
        
        if self.upload_timeout <= 0:
            raise ValueError("upload_timeout must be positive")
        
        if not self.s3_prefix.endswith('/'):
            self.s3_prefix += '/'


@dataclass
class CoverageReportMetadata:
    """Metadata for a coverage report."""
    
    function_name: str
    execution_id: str
    timestamp: datetime
    s3_key: str
    file_size: int
    coverage_percentage: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'function_name': self.function_name,
            'execution_id': self.execution_id,
            'timestamp': self.timestamp.isoformat(),
            's3_key': self.s3_key,
            'file_size': self.file_size,
            'coverage_percentage': self.coverage_percentage
        }


@dataclass
class HealthCheckResponse:
    """Response model for health check endpoint."""
    
    status: str  # "healthy" | "unhealthy"
    coverage_enabled: bool
    layer_version: str
    s3_config: Dict[str, Any]
    timestamp: datetime
    errors: Optional[List[str]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'status': self.status,
            'coverage_enabled': self.coverage_enabled,
            'layer_version': self.layer_version,
            's3_config': self.s3_config,
            'timestamp': self.timestamp.isoformat(),
            'errors': self.errors or []
        }


@dataclass
class CombinerResult:
    """Result of coverage file combination operation."""
    
    success: bool
    combined_file_key: str
    files_processed: int
    files_skipped: int
    total_coverage_percentage: float
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'success': self.success,
            'combined_file_key': self.combined_file_key,
            'files_processed': self.files_processed,
            'files_skipped': self.files_skipped,
            'total_coverage_percentage': self.total_coverage_percentage,
            'errors': self.errors
        }