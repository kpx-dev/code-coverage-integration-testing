# API Reference

This document provides detailed API reference for the Lambda Coverage Layer.

## Table of Contents

- [Decorators](#decorators)
- [Context Managers](#context-managers)
- [Functions](#functions)
- [Classes](#classes)
- [Exceptions](#exceptions)
- [Configuration](#configuration)

## Decorators

### `@coverage_handler`

Automatically wraps your Lambda handler with coverage tracking.

**Module**: `coverage_wrapper`

**Signature**:
```python
def coverage_handler(func: Callable) -> Callable
```

**Parameters**:
- `func`: The Lambda handler function to wrap

**Returns**:
- Wrapped function with coverage tracking

**Example**:
```python
from coverage_wrapper import coverage_handler

@coverage_handler
def lambda_handler(event, context):
    return {"statusCode": 200, "body": "Hello World"}
```

**Behavior**:
1. Initializes coverage tracking before function execution
2. Executes the wrapped function
3. Stops coverage tracking and collects data
4. Uploads coverage file to S3 asynchronously
5. Returns the original function result

**Error Handling**:
- If coverage initialization fails, the function continues without coverage
- If S3 upload fails, errors are logged but don't affect function execution
- Original function exceptions are propagated unchanged

## Context Managers

### `CoverageContext`

Provides manual control over coverage tracking within a specific code block.

**Module**: `coverage_wrapper`

**Signature**:
```python
class CoverageContext:
    def __init__(self, config: Optional[CoverageConfig] = None)
    def __enter__(self) -> 'CoverageContext'
    def __exit__(self, exc_type, exc_val, exc_tb) -> None
```

**Parameters**:
- `config` (optional): Custom coverage configuration

**Example**:
```python
from coverage_wrapper import CoverageContext

def lambda_handler(event, context):
    # Initialization code (not tracked)
    setup_resources()
    
    # Business logic (tracked)
    with CoverageContext():
        result = process_request(event)
    
    # Cleanup code (not tracked)
    cleanup_resources()
    
    return result
```

**Methods**:

#### `__enter__()`
- Initializes coverage tracking
- Returns the context manager instance

#### `__exit__(exc_type, exc_val, exc_tb)`
- Stops coverage tracking
- Collects coverage data
- Uploads coverage file to S3
- Handles any exceptions gracefully

**Error Handling**:
- Exceptions in tracked code are propagated
- Coverage upload errors are logged but don't raise exceptions
- Context manager always completes successfully

## Functions

### Health Check Functions

#### `health_check_handler()`

Returns comprehensive health status including coverage information.

**Module**: `coverage_wrapper.health_check`

**Signature**:
```python
def health_check_handler() -> Dict[str, Any]
```

**Returns**:
Dictionary containing health status information:

```python
{
    "status": "healthy" | "unhealthy",
    "coverage_enabled": bool,
    "layer_version": str,
    "s3_config": {
        "bucket": str,
        "prefix": str
    },
    "timestamp": str,  # ISO format
    "errors": List[str]  # Only present if status is "unhealthy"
}
```

**Example**:
```python
from coverage_wrapper.health_check import health_check_handler

def lambda_handler(event, context):
    if event.get('path') == '/health':
        health_status = health_check_handler()
        return {
            'statusCode': 200,
            'body': json.dumps(health_status)
        }
```

#### `get_coverage_status()`

Returns the current coverage tracking status.

**Module**: `coverage_wrapper.health_check`

**Signature**:
```python
def get_coverage_status() -> Dict[str, Any]
```

**Returns**:
```python
{
    "initialized": bool,
    "active": bool,
    "config": Dict[str, Any]
}
```

#### `get_layer_info()`

Returns information about the coverage layer.

**Module**: `coverage_wrapper.health_check`

**Signature**:
```python
def get_layer_info() -> Dict[str, Any]
```

**Returns**:
```python
{
    "version": str,
    "python_version": str,
    "coverage_version": str,
    "dependencies": Dict[str, str]
}
```

### Coverage Combining Functions

#### `combine_coverage_files()`

Combines multiple coverage files from S3 into a single consolidated report.

**Module**: `coverage_wrapper.combiner`

**Signature**:
```python
def combine_coverage_files(
    bucket_name: str,
    prefix: str = "coverage/",
    output_key: Optional[str] = None
) -> Dict[str, Any]
```

**Parameters**:
- `bucket_name`: S3 bucket containing coverage files
- `prefix`: S3 key prefix to search for coverage files
- `output_key`: S3 key for the combined report (auto-generated if not provided)

**Returns**:
```python
{
    "files_processed": int,
    "files_skipped": int,
    "combined_coverage": float,  # Percentage
    "output_location": str,      # S3 URI
    "processing_time_ms": int,
    "errors": List[str]
}
```

**Example**:
```python
from coverage_wrapper.combiner import combine_coverage_files

result = combine_coverage_files(
    bucket_name="my-coverage-bucket",
    prefix="coverage/2024/01/15/",
    output_key="coverage/combined/daily-report.json"
)
```

#### `download_coverage_files()`

Downloads coverage files from S3 for processing.

**Module**: `coverage_wrapper.combiner`

**Signature**:
```python
def download_coverage_files(
    bucket_name: str,
    prefix: str
) -> List[str]
```

**Parameters**:
- `bucket_name`: S3 bucket name
- `prefix`: S3 key prefix

**Returns**:
List of local file paths for downloaded coverage files

#### `merge_coverage_data()`

Merges multiple coverage files using coverage.py combine functionality.

**Module**: `coverage_wrapper.combiner`

**Signature**:
```python
def merge_coverage_data(
    coverage_files: List[str]
) -> str
```

**Parameters**:
- `coverage_files`: List of local coverage file paths

**Returns**:
Path to the merged coverage file

### S3 Upload Functions

#### `upload_coverage_file()`

Uploads a coverage file to S3 with proper naming and metadata.

**Module**: `coverage_wrapper.s3_uploader`

**Signature**:
```python
def upload_coverage_file(
    coverage_data: bytes,
    function_name: str,
    execution_id: str,
    config: Optional[CoverageConfig] = None
) -> Dict[str, Any]
```

**Parameters**:
- `coverage_data`: Coverage file content as bytes
- `function_name`: Lambda function name
- `execution_id`: Unique execution identifier
- `config`: Coverage configuration (uses environment variables if not provided)

**Returns**:
```python
{
    "s3_key": str,
    "bucket": str,
    "file_size": int,
    "upload_time_ms": int,
    "success": bool
}
```

#### `generate_s3_key()`

Generates a unique S3 key for coverage files.

**Module**: `coverage_wrapper.s3_uploader`

**Signature**:
```python
def generate_s3_key(
    function_name: str,
    execution_id: str,
    prefix: str = "coverage/",
    timestamp: Optional[datetime] = None
) -> str
```

**Parameters**:
- `function_name`: Lambda function name
- `execution_id`: Unique execution identifier
- `prefix`: S3 key prefix
- `timestamp`: Timestamp for the key (current time if not provided)

**Returns**:
S3 key string in format: `{prefix}YYYY/MM/DD/{function_name}-{execution_id}.coverage`

#### `get_s3_config()`

Retrieves S3 configuration from environment variables.

**Module**: `coverage_wrapper.s3_uploader`

**Signature**:
```python
def get_s3_config() -> Dict[str, Any]
```

**Returns**:
```python
{
    "bucket": str,
    "prefix": str,
    "timeout": int,
    "region": str
}
```

**Raises**:
- `ValueError`: If required environment variables are missing

## Classes

### `CoverageConfig`

Configuration class for coverage tracking settings.

**Module**: `coverage_wrapper.models`

**Attributes**:
```python
@dataclass
class CoverageConfig:
    s3_bucket: str
    s3_prefix: str = "coverage/"
    upload_timeout: int = 30
    include_patterns: Optional[List[str]] = None
    exclude_patterns: Optional[List[str]] = None
    branch_coverage: bool = True
    debug: bool = False
```

**Class Methods**:

#### `from_environment()`

Creates a CoverageConfig instance from environment variables.

**Signature**:
```python
@classmethod
def from_environment(cls) -> 'CoverageConfig'
```

**Environment Variables**:
- `COVERAGE_S3_BUCKET` (required)
- `COVERAGE_S3_PREFIX` (optional, default: "coverage/")
- `COVERAGE_UPLOAD_TIMEOUT` (optional, default: 30)
- `COVERAGE_INCLUDE_PATTERNS` (optional, comma-separated)
- `COVERAGE_EXCLUDE_PATTERNS` (optional, comma-separated)
- `COVERAGE_BRANCH_COVERAGE` (optional, default: true)
- `COVERAGE_DEBUG` (optional, default: false)

### `CoverageReportMetadata`

Metadata for coverage reports.

**Module**: `coverage_wrapper.models`

**Attributes**:
```python
@dataclass
class CoverageReportMetadata:
    function_name: str
    execution_id: str
    timestamp: datetime
    s3_key: str
    file_size: int
    coverage_percentage: Optional[float] = None
    lines_covered: Optional[int] = None
    lines_total: Optional[int] = None
    branches_covered: Optional[int] = None
    branches_total: Optional[int] = None
```

### `HealthCheckResponse`

Response model for health check endpoints.

**Module**: `coverage_wrapper.models`

**Attributes**:
```python
@dataclass
class HealthCheckResponse:
    status: str  # "healthy" | "unhealthy" | "degraded"
    coverage_enabled: bool
    layer_version: str
    s3_config: Dict[str, Any]
    timestamp: datetime
    errors: Optional[List[str]] = None
    warnings: Optional[List[str]] = None
```

## Exceptions

### `CoverageError`

Base exception for coverage-related errors.

**Module**: `coverage_wrapper.error_handling`

**Signature**:
```python
class CoverageError(Exception):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None)
```

### `CoverageInitializationError`

Raised when coverage initialization fails.

**Module**: `coverage_wrapper.error_handling`

**Inherits**: `CoverageError`

### `S3UploadError`

Raised when S3 upload operations fail.

**Module**: `coverage_wrapper.error_handling`

**Inherits**: `CoverageError`

### `CoverageCombineError`

Raised when coverage file combining fails.

**Module**: `coverage_wrapper.error_handling`

**Inherits**: `CoverageError`

## Configuration

### Environment Variables

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `COVERAGE_S3_BUCKET` | string | Yes | - | S3 bucket for coverage uploads |
| `COVERAGE_S3_PREFIX` | string | No | `coverage/` | S3 key prefix |
| `COVERAGE_UPLOAD_TIMEOUT` | integer | No | `30` | Upload timeout in seconds |
| `COVERAGE_INCLUDE_PATTERNS` | string | No | - | Comma-separated include patterns |
| `COVERAGE_EXCLUDE_PATTERNS` | string | No | - | Comma-separated exclude patterns |
| `COVERAGE_BRANCH_COVERAGE` | boolean | No | `true` | Enable branch coverage |
| `COVERAGE_DEBUG` | boolean | No | `false` | Enable debug logging |
| `AWS_REGION` | string | No | - | AWS region (auto-detected if not set) |

### Coverage Patterns

#### Include Patterns
Specify which files to include in coverage tracking:
```bash
COVERAGE_INCLUDE_PATTERNS="src/*,lib/*,app/*"
```

#### Exclude Patterns
Specify which files to exclude from coverage tracking:
```bash
COVERAGE_EXCLUDE_PATTERNS="tests/*,*/__pycache__/*,*/migrations/*"
```

### S3 Configuration

#### Bucket Policy
Your S3 bucket should allow the Lambda execution role to perform these actions:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::ACCOUNT:role/lambda-execution-role"
            },
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::your-coverage-bucket",
                "arn:aws:s3:::your-coverage-bucket/*"
            ]
        }
    ]
}
```

#### Lifecycle Policy
Configure S3 lifecycle policy to manage coverage file retention:
```json
{
    "Rules": [
        {
            "Id": "CoverageFileRetention",
            "Status": "Enabled",
            "Filter": {
                "Prefix": "coverage/"
            },
            "Transitions": [
                {
                    "Days": 30,
                    "StorageClass": "STANDARD_IA"
                },
                {
                    "Days": 90,
                    "StorageClass": "GLACIER"
                }
            ],
            "Expiration": {
                "Days": 365
            }
        }
    ]
}
```

## Error Handling

### Error Logging

All errors are logged with structured JSON format:

```json
{
    "level": "ERROR",
    "timestamp": "2024-01-15T10:30:00Z",
    "error_type": "S3UploadError",
    "message": "Failed to upload coverage file",
    "details": {
        "s3_key": "coverage/2024/01/15/my-function-abc123.coverage",
        "error_code": "NoSuchBucket",
        "retry_count": 3
    },
    "function_name": "my-function",
    "request_id": "abc-123-def-456"
}
```

### Retry Logic

The layer implements exponential backoff retry logic for:
- S3 upload operations (max 3 retries)
- Coverage file downloads (max 3 retries)
- Health check operations (max 2 retries)

### Graceful Degradation

The layer is designed to fail gracefully:
- If coverage initialization fails, the Lambda function continues without coverage
- If S3 upload fails, errors are logged but don't affect function execution
- If health checks fail, a degraded status is returned instead of an error

## Performance Considerations

### Memory Usage

| Component | Memory Impact |
|-----------|---------------|
| Coverage initialization | ~10-20MB |
| Coverage data collection | ~20-50MB |
| S3 upload buffer | ~10-20MB |
| Total overhead | ~40-90MB |

### CPU Impact

| Operation | CPU Impact |
|-----------|------------|
| Coverage initialization | ~50-100ms |
| Coverage data collection | ~1-5% overhead |
| S3 upload | ~100-300ms |

### Optimization Tips

1. **Use selective patterns** to reduce coverage scope
2. **Use context managers** for performance-critical sections
3. **Monitor memory usage** and adjust Lambda memory allocation
4. **Use asynchronous uploads** to minimize execution time impact

## Version Compatibility

| Layer Version | Python Versions | Coverage.py Version | AWS Lambda Runtimes |
|---------------|-----------------|-------------------|-------------------|
| 1.0.x | 3.8, 3.9, 3.10, 3.11 | 7.x | python3.8, python3.9, python3.10, python3.11 |

## Migration Guide

### From Version 0.x to 1.x

1. Update environment variable names:
   - `COVERAGE_BUCKET` → `COVERAGE_S3_BUCKET`
   - `COVERAGE_PREFIX` → `COVERAGE_S3_PREFIX`

2. Update import statements:
   ```python
   # Old
   from coverage_layer import coverage_handler
   
   # New
   from coverage_wrapper import coverage_handler
   ```

3. Update health check usage:
   ```python
   # Old
   from coverage_layer.health import health_check
   
   # New
   from coverage_wrapper.health_check import health_check_handler
   ```