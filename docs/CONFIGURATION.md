# Configuration Reference

This document provides comprehensive configuration options for the Lambda Coverage Layer.

## Table of Contents

- [Environment Variables](#environment-variables)
- [Coverage Configuration](#coverage-configuration)
- [S3 Configuration](#s3-configuration)
- [IAM Permissions](#iam-permissions)
- [Performance Tuning](#performance-tuning)
- [Logging Configuration](#logging-configuration)
- [Advanced Configuration](#advanced-configuration)

## Environment Variables

### Required Variables

#### `COVERAGE_S3_BUCKET`
- **Type**: String
- **Required**: Yes
- **Description**: S3 bucket name for storing coverage files
- **Example**: `my-coverage-bucket`
- **Validation**: Must be a valid S3 bucket name

```bash
export COVERAGE_S3_BUCKET=my-coverage-bucket
```

### Optional Variables

#### `COVERAGE_S3_PREFIX`
- **Type**: String
- **Required**: No
- **Default**: `coverage/`
- **Description**: S3 key prefix for organizing coverage files
- **Example**: `coverage/production/`
- **Pattern**: Should end with `/` for directory-like organization

```bash
export COVERAGE_S3_PREFIX=coverage/production/
```

#### `COVERAGE_UPLOAD_TIMEOUT`
- **Type**: Integer
- **Required**: No
- **Default**: `30`
- **Description**: Timeout for S3 upload operations in seconds
- **Range**: 5-300 seconds
- **Example**: `60`

```bash
export COVERAGE_UPLOAD_TIMEOUT=60
```

#### `COVERAGE_INCLUDE_PATTERNS`
- **Type**: String (comma-separated)
- **Required**: No
- **Default**: All files included
- **Description**: Glob patterns for files to include in coverage
- **Example**: `src/*,lib/*,app/*`
- **Pattern**: Unix shell-style wildcards

```bash
export COVERAGE_INCLUDE_PATTERNS="src/*,lib/*,app/*"
```

#### `COVERAGE_EXCLUDE_PATTERNS`
- **Type**: String (comma-separated)
- **Required**: No
- **Default**: Common exclusions applied
- **Description**: Glob patterns for files to exclude from coverage
- **Example**: `tests/*,*/__pycache__/*,*/migrations/*`
- **Pattern**: Unix shell-style wildcards

```bash
export COVERAGE_EXCLUDE_PATTERNS="tests/*,*/__pycache__/*,*/migrations/*"
```

#### `COVERAGE_BRANCH_COVERAGE`
- **Type**: Boolean
- **Required**: No
- **Default**: `true`
- **Description**: Enable branch coverage tracking
- **Values**: `true`, `false`, `1`, `0`, `yes`, `no`

```bash
export COVERAGE_BRANCH_COVERAGE=true
```

#### `COVERAGE_DEBUG`
- **Type**: Boolean
- **Required**: No
- **Default**: `false`
- **Description**: Enable debug logging for coverage operations
- **Values**: `true`, `false`, `1`, `0`, `yes`, `no`

```bash
export COVERAGE_DEBUG=true
```

#### `COVERAGE_COMBINED_PREFIX`
- **Type**: String
- **Required**: No
- **Default**: `coverage/combined/`
- **Description**: S3 prefix for combined coverage reports
- **Example**: `reports/combined/`

```bash
export COVERAGE_COMBINED_PREFIX=reports/combined/
```

#### `AWS_REGION`
- **Type**: String
- **Required**: No
- **Default**: Auto-detected from Lambda environment
- **Description**: AWS region for S3 operations
- **Example**: `us-east-1`

```bash
export AWS_REGION=us-east-1
```

## Coverage Configuration

### Include/Exclude Patterns

#### Pattern Syntax
The layer uses Python's `fnmatch` module for pattern matching:

- `*` matches any number of characters
- `?` matches a single character
- `[seq]` matches any character in seq
- `[!seq]` matches any character not in seq

#### Common Patterns

**Include specific directories:**
```bash
COVERAGE_INCLUDE_PATTERNS="src/*,lib/*,app/*,handlers/*"
```

**Exclude test files:**
```bash
COVERAGE_EXCLUDE_PATTERNS="test_*,*_test.py,tests/*"
```

**Exclude generated files:**
```bash
COVERAGE_EXCLUDE_PATTERNS="*/__pycache__/*,*.pyc,*/migrations/*,*/.git/*"
```

**Complex exclusions:**
```bash
COVERAGE_EXCLUDE_PATTERNS="tests/*,*/__pycache__/*,*/node_modules/*,*.min.js,*/vendor/*"
```

### Branch Coverage

Branch coverage tracks whether each branch of conditional statements is executed:

```python
def example_function(x):
    if x > 0:        # Branch 1: True path
        return "positive"
    else:            # Branch 2: False path
        return "non-positive"
```

**Enable branch coverage:**
```bash
export COVERAGE_BRANCH_COVERAGE=true
```

**Disable branch coverage (line coverage only):**
```bash
export COVERAGE_BRANCH_COVERAGE=false
```

### Coverage Thresholds

While the layer doesn't enforce thresholds directly, you can configure them in your CI/CD pipeline:

```python
# In your test script
import coverage

cov = coverage.Coverage()
cov.load()
total_coverage = cov.report()

if total_coverage < 80:
    raise SystemExit("Coverage below threshold: {:.1f}%".format(total_coverage))
```

## S3 Configuration

### Bucket Setup

#### Bucket Creation
```bash
aws s3 mb s3://my-coverage-bucket --region us-east-1
```

#### Bucket Encryption
```bash
aws s3api put-bucket-encryption \
  --bucket my-coverage-bucket \
  --server-side-encryption-configuration '{
    "Rules": [
      {
        "ApplyServerSideEncryptionByDefault": {
          "SSEAlgorithm": "AES256"
        }
      }
    ]
  }'
```

#### Versioning (Optional)
```bash
aws s3api put-bucket-versioning \
  --bucket my-coverage-bucket \
  --versioning-configuration Status=Enabled
```

### Lifecycle Policies

#### Basic Lifecycle Policy
```json
{
  "Rules": [
    {
      "Id": "CoverageFileLifecycle",
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

#### Advanced Lifecycle Policy
```json
{
  "Rules": [
    {
      "Id": "IndividualCoverageFiles",
      "Status": "Enabled",
      "Filter": {
        "And": {
          "Prefix": "coverage/",
          "Tags": [
            {
              "Key": "Type",
              "Value": "Individual"
            }
          ]
        }
      },
      "Transitions": [
        {
          "Days": 7,
          "StorageClass": "STANDARD_IA"
        },
        {
          "Days": 30,
          "StorageClass": "GLACIER"
        }
      ],
      "Expiration": {
        "Days": 90
      }
    },
    {
      "Id": "CombinedReports",
      "Status": "Enabled",
      "Filter": {
        "Prefix": "coverage/combined/"
      },
      "Transitions": [
        {
          "Days": 90,
          "StorageClass": "GLACIER"
        }
      ],
      "Expiration": {
        "Days": 1095
      }
    }
  ]
}
```

### S3 Key Structure

The layer organizes files using a hierarchical structure:

```
coverage/
├── YYYY/MM/DD/                    # Date-based organization
│   ├── function-name-exec-id.coverage
│   ├── another-function-exec-id.coverage
│   └── ...
├── combined/                      # Combined reports
│   ├── daily-report-YYYY-MM-DD.json
│   ├── weekly-report-YYYY-WW.json
│   └── manual-report-timestamp.json
└── metadata/                      # Optional metadata files
    ├── function-inventory.json
    └── coverage-summary.json
```

**Customizing the structure:**
```bash
# Use environment-based prefixes
export COVERAGE_S3_PREFIX=coverage/production/
export COVERAGE_COMBINED_PREFIX=reports/production/combined/

# Results in:
# coverage/production/YYYY/MM/DD/function-name.coverage
# reports/production/combined/daily-report.json
```

## IAM Permissions

### Lambda Execution Role

#### Minimal Permissions
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::my-coverage-bucket/coverage/*"
    }
  ]
}
```

#### Recommended Permissions
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:PutObjectAcl",
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::my-coverage-bucket/coverage/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket"
      ],
      "Resource": "arn:aws:s3:::my-coverage-bucket",
      "Condition": {
        "StringLike": {
          "s3:prefix": "coverage/*"
        }
      }
    }
  ]
}
```

#### Full Permissions (for combiner functions)
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:PutObjectAcl",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::my-coverage-bucket/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket"
      ],
      "Resource": "arn:aws:s3:::my-coverage-bucket"
    }
  ]
}
```

### Cross-Account Access

If your coverage bucket is in a different AWS account:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:PutObjectAcl"
      ],
      "Resource": "arn:aws:s3:::cross-account-coverage-bucket/coverage/*"
    },
    {
      "Effect": "Allow",
      "Action": "sts:AssumeRole",
      "Resource": "arn:aws:iam::OTHER-ACCOUNT:role/CoverageUploadRole"
    }
  ]
}
```

## Performance Tuning

### Memory Configuration

#### Lambda Memory Settings
```bash
# For functions with coverage layer
aws lambda update-function-configuration \
  --function-name my-function \
  --memory-size 512  # Increase from default 128MB
```

#### Memory Usage by Component
| Component | Memory Usage | Recommendation |
|-----------|-------------|----------------|
| Coverage initialization | 10-20MB | Always allocated |
| Coverage data collection | 20-50MB | Scales with code size |
| S3 upload buffer | 10-20MB | Temporary allocation |
| **Total overhead** | **40-90MB** | **Add to base memory** |

### Timeout Configuration

#### Upload Timeout Tuning
```bash
# For large coverage files or slow networks
export COVERAGE_UPLOAD_TIMEOUT=120

# For fast networks and small files
export COVERAGE_UPLOAD_TIMEOUT=15
```

#### Lambda Timeout Considerations
```bash
# Ensure Lambda timeout accounts for coverage overhead
aws lambda update-function-configuration \
  --function-name my-function \
  --timeout 30  # Add 5-10 seconds for coverage operations
```

### Cold Start Optimization

#### Pattern Comparison
| Pattern | Cold Start Impact | Memory Impact | Use Case |
|---------|------------------|---------------|----------|
| `@coverage_handler` | +200-500ms | +40-90MB | Simple functions |
| `CoverageContext` | +50-100ms | +30-70MB | Performance-critical |
| Selective coverage | +20-50ms | +20-50MB | Batch processing |

#### Optimization Strategies

**1. Use Context Managers for Critical Paths:**
```python
def lambda_handler(event, context):
    # Fast initialization
    setup_resources()
    
    # Track only business logic
    with CoverageContext():
        result = process_request(event)
    
    # Fast cleanup
    cleanup_resources()
    return result
```

**2. Selective Coverage for Batch Processing:**
```python
def process_batch(items):
    for i, item in enumerate(items):
        if i % 10 == 0:  # Track every 10th item
            with CoverageContext():
                process_item(item)
        else:
            process_item(item)
```

**3. Conditional Coverage:**
```python
def lambda_handler(event, context):
    enable_coverage = event.get('enable_coverage', True)
    
    if enable_coverage:
        with CoverageContext():
            return business_logic(event)
    else:
        return business_logic(event)
```

## Logging Configuration

### Log Levels

#### Environment Variable
```bash
export COVERAGE_LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

#### Programmatic Configuration
```python
import logging
from coverage_wrapper.logging_utils import setup_logging

# Configure logging
setup_logging(level=logging.DEBUG)
```

### Log Format

#### Structured JSON Logging
```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "level": "INFO",
  "logger": "coverage_wrapper.s3_uploader",
  "message": "Coverage file uploaded successfully",
  "data": {
    "s3_key": "coverage/2024/01/15/my-function-abc123.coverage",
    "file_size": 2048,
    "upload_time_ms": 150,
    "function_name": "my-function",
    "request_id": "abc-123-def-456"
  }
}
```

#### Log Categories

**Coverage Operations:**
```json
{
  "level": "INFO",
  "category": "coverage",
  "operation": "initialize|collect|upload",
  "status": "success|failure",
  "duration_ms": 123
}
```

**S3 Operations:**
```json
{
  "level": "INFO",
  "category": "s3",
  "operation": "upload|download|list",
  "s3_key": "coverage/path/file.coverage",
  "status": "success|failure"
}
```

**Health Checks:**
```json
{
  "level": "INFO",
  "category": "health",
  "status": "healthy|unhealthy|degraded",
  "checks": ["coverage", "s3", "memory"]
}
```

### CloudWatch Integration

#### Log Group Configuration
```bash
aws logs create-log-group \
  --log-group-name /aws/lambda/my-function \
  --retention-in-days 30
```

#### Custom Metrics from Logs
```bash
# Create metric filter for coverage upload failures
aws logs put-metric-filter \
  --log-group-name /aws/lambda/my-function \
  --filter-name CoverageUploadFailures \
  --filter-pattern '[timestamp, level="ERROR", category="s3", operation="upload"]' \
  --metric-transformations \
    metricName=CoverageUploadFailures,metricNamespace=Lambda/Coverage,metricValue=1
```

## Advanced Configuration

### Multi-Environment Setup

#### Environment-Specific Configuration
```bash
# Production
export COVERAGE_S3_BUCKET=prod-coverage-bucket
export COVERAGE_S3_PREFIX=coverage/production/
export COVERAGE_DEBUG=false

# Staging
export COVERAGE_S3_BUCKET=staging-coverage-bucket
export COVERAGE_S3_PREFIX=coverage/staging/
export COVERAGE_DEBUG=true

# Development
export COVERAGE_S3_BUCKET=dev-coverage-bucket
export COVERAGE_S3_PREFIX=coverage/development/
export COVERAGE_DEBUG=true
```

#### Configuration Management with AWS Systems Manager
```bash
# Store configuration in Parameter Store
aws ssm put-parameter \
  --name /lambda/coverage/s3-bucket \
  --value prod-coverage-bucket \
  --type String

aws ssm put-parameter \
  --name /lambda/coverage/s3-prefix \
  --value coverage/production/ \
  --type String
```

```python
# Load configuration from Parameter Store
import boto3

def get_parameter(name):
    ssm = boto3.client('ssm')
    response = ssm.get_parameter(Name=name)
    return response['Parameter']['Value']

# Use in Lambda function
os.environ['COVERAGE_S3_BUCKET'] = get_parameter('/lambda/coverage/s3-bucket')
os.environ['COVERAGE_S3_PREFIX'] = get_parameter('/lambda/coverage/s3-prefix')
```

### Custom Coverage Configuration

#### Programmatic Configuration
```python
from coverage_wrapper.models import CoverageConfig
from coverage_wrapper import CoverageContext

# Custom configuration
config = CoverageConfig(
    s3_bucket="my-custom-bucket",
    s3_prefix="custom/path/",
    include_patterns=["src/*", "lib/*"],
    exclude_patterns=["tests/*", "*.pyc"],
    branch_coverage=True,
    debug=True
)

# Use with context manager
with CoverageContext(config=config):
    result = business_logic()
```

#### Dynamic Configuration
```python
def get_coverage_config(event, context):
    """Get coverage configuration based on event or context"""
    
    # Environment-based configuration
    if context.function_name.endswith('-prod'):
        return CoverageConfig(
            s3_bucket="prod-coverage-bucket",
            s3_prefix="coverage/production/",
            debug=False
        )
    elif context.function_name.endswith('-staging'):
        return CoverageConfig(
            s3_bucket="staging-coverage-bucket",
            s3_prefix="coverage/staging/",
            debug=True
        )
    else:
        return CoverageConfig.from_environment()

def lambda_handler(event, context):
    config = get_coverage_config(event, context)
    
    with CoverageContext(config=config):
        return business_logic(event)
```

### Integration with CI/CD

#### GitHub Actions
```yaml
name: Deploy with Coverage
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Configure Coverage
        run: |
          echo "COVERAGE_S3_BUCKET=${{ secrets.COVERAGE_S3_BUCKET }}" >> $GITHUB_ENV
          echo "COVERAGE_S3_PREFIX=coverage/${{ github.ref_name }}/" >> $GITHUB_ENV
          echo "COVERAGE_DEBUG=false" >> $GITHUB_ENV
      
      - name: Deploy Lambda
        run: |
          aws lambda update-function-configuration \
            --function-name my-function \
            --environment Variables="{
              COVERAGE_S3_BUCKET=$COVERAGE_S3_BUCKET,
              COVERAGE_S3_PREFIX=$COVERAGE_S3_PREFIX,
              COVERAGE_DEBUG=$COVERAGE_DEBUG
            }"
```

#### AWS CodePipeline
```json
{
  "pipeline": {
    "stages": [
      {
        "name": "Deploy",
        "actions": [
          {
            "name": "UpdateLambdaConfig",
            "actionTypeId": {
              "category": "Invoke",
              "owner": "AWS",
              "provider": "Lambda",
              "version": "1"
            },
            "configuration": {
              "FunctionName": "update-lambda-coverage-config",
              "UserParameters": "{\"environment\": \"production\", \"debug\": false}"
            }
          }
        ]
      }
    ]
  }
}
```

### Monitoring and Alerting

#### CloudWatch Alarms
```bash
# High coverage upload failure rate
aws cloudwatch put-metric-alarm \
  --alarm-name "CoverageUploadFailureRate" \
  --alarm-description "Coverage upload failure rate is high" \
  --metric-name CoverageUploadFailures \
  --namespace Lambda/Coverage \
  --statistic Sum \
  --period 300 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2

# High memory usage
aws cloudwatch put-metric-alarm \
  --alarm-name "CoverageMemoryUsage" \
  --alarm-description "Coverage layer memory usage is high" \
  --metric-name MemoryUtilization \
  --namespace AWS/Lambda \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --dimensions Name=FunctionName,Value=my-function
```

#### Custom Dashboards
```json
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["Lambda/Coverage", "CoverageUploadSuccess"],
          [".", "CoverageUploadFailures"]
        ],
        "period": 300,
        "stat": "Sum",
        "region": "us-east-1",
        "title": "Coverage Upload Status"
      }
    },
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/Lambda", "Duration", "FunctionName", "my-function"],
          [".", "MemoryUtilization", ".", "."]
        ],
        "period": 300,
        "stat": "Average",
        "region": "us-east-1",
        "title": "Function Performance"
      }
    }
  ]
}
```

## Troubleshooting Configuration

### Validation Script

```python
#!/usr/bin/env python3
"""
Coverage Layer Configuration Validator
"""
import os
import boto3
from coverage_wrapper.models import CoverageConfig

def validate_configuration():
    """Validate coverage layer configuration"""
    errors = []
    warnings = []
    
    # Check required environment variables
    if not os.environ.get('COVERAGE_S3_BUCKET'):
        errors.append("COVERAGE_S3_BUCKET is required")
    
    # Validate S3 bucket access
    try:
        config = CoverageConfig.from_environment()
        s3 = boto3.client('s3')
        s3.head_bucket(Bucket=config.s3_bucket)
    except Exception as e:
        errors.append(f"Cannot access S3 bucket: {e}")
    
    # Check IAM permissions
    try:
        s3.put_object(
            Bucket=config.s3_bucket,
            Key=f"{config.s3_prefix}test-file.txt",
            Body=b"test"
        )
        s3.delete_object(
            Bucket=config.s3_bucket,
            Key=f"{config.s3_prefix}test-file.txt"
        )
    except Exception as e:
        errors.append(f"Insufficient S3 permissions: {e}")
    
    # Validate patterns
    if config.include_patterns:
        for pattern in config.include_patterns:
            if not pattern.strip():
                warnings.append(f"Empty include pattern: '{pattern}'")
    
    # Report results
    if errors:
        print("❌ Configuration errors:")
        for error in errors:
            print(f"  - {error}")
    
    if warnings:
        print("⚠️  Configuration warnings:")
        for warning in warnings:
            print(f"  - {warning}")
    
    if not errors and not warnings:
        print("✅ Configuration is valid")
    
    return len(errors) == 0

if __name__ == "__main__":
    import sys
    if not validate_configuration():
        sys.exit(1)
```

### Common Configuration Issues

#### Issue: Coverage files not uploaded
**Symptoms**: No files appear in S3 bucket
**Solutions**:
1. Check `COVERAGE_S3_BUCKET` environment variable
2. Verify IAM permissions for S3 access
3. Check CloudWatch logs for error messages
4. Validate S3 bucket exists and is accessible

#### Issue: High memory usage
**Symptoms**: Lambda function running out of memory
**Solutions**:
1. Increase Lambda memory allocation
2. Use selective coverage patterns
3. Use context managers instead of decorators
4. Monitor memory usage with CloudWatch

#### Issue: Slow cold starts
**Symptoms**: High function initialization time
**Solutions**:
1. Use `CoverageContext` instead of `@coverage_handler`
2. Optimize include/exclude patterns
3. Use provisioned concurrency
4. Consider selective coverage for performance-critical functions

#### Issue: Coverage files not combining
**Symptoms**: Combiner function fails or produces empty reports
**Solutions**:
1. Verify S3 prefix configuration
2. Check combiner function permissions
3. Ensure coverage files are in correct format
4. Check for file naming conflicts