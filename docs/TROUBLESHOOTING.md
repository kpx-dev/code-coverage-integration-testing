# Troubleshooting Guide

This guide helps you diagnose and resolve common issues with the Lambda Coverage Layer.

## Table of Contents

- [Quick Diagnostics](#quick-diagnostics)
- [Common Issues](#common-issues)
- [Error Messages](#error-messages)
- [Performance Issues](#performance-issues)
- [Configuration Problems](#configuration-problems)
- [S3 Integration Issues](#s3-integration-issues)
- [Debug Mode](#debug-mode)
- [Monitoring and Logging](#monitoring-and-logging)

## Quick Diagnostics

### Health Check Test

First, test if the coverage layer is working correctly:

```python
from coverage_wrapper.health_check import health_check_handler

def lambda_handler(event, context):
    if event.get('action') == 'health_check':
        return health_check_handler()
    
    # Your regular code here
    return {"statusCode": 200, "body": "OK"}
```

Invoke with:
```bash
aws lambda invoke \
  --function-name your-function-name \
  --payload '{"action": "health_check"}' \
  response.json

cat response.json
```

Expected healthy response:
```json
{
  "status": "healthy",
  "coverage_enabled": true,
  "layer_version": "1.0.0",
  "s3_config": {
    "bucket": "your-coverage-bucket",
    "prefix": "coverage/"
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Basic Functionality Test

Test basic coverage collection:

```python
from coverage_wrapper import coverage_handler

@coverage_handler
def lambda_handler(event, context):
    name = event.get('name', 'World')
    return {"message": f"Hello, {name}!"}
```

Invoke and check S3:
```bash
# Invoke function
aws lambda invoke \
  --function-name your-function-name \
  --payload '{"name": "test"}' \
  response.json

# Check for coverage files in S3
aws s3 ls s3://your-coverage-bucket/coverage/ --recursive
```

## Common Issues

### 1. Coverage Files Not Uploaded to S3

#### Symptoms
- No coverage files appear in S3 bucket
- Function executes successfully but no coverage data

#### Diagnosis
```bash
# Check CloudWatch logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/your-function-name \
  --filter-pattern "ERROR"

# Check S3 bucket exists
aws s3 ls s3://your-coverage-bucket/

# Test S3 permissions
aws s3 cp test.txt s3://your-coverage-bucket/coverage/test.txt
```

#### Solutions

**Check Environment Variables:**
```bash
aws lambda get-function-configuration \
  --function-name your-function-name \
  --query 'Environment.Variables'
```

**Verify IAM Permissions:**
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
      "Resource": "arn:aws:s3:::your-coverage-bucket/coverage/*"
    }
  ]
}
```

**Check S3 Bucket Policy:**
```bash
aws s3api get-bucket-policy --bucket your-coverage-bucket
```

### 2. High Cold Start Times

#### Symptoms
- Lambda function takes longer to initialize
- Timeout errors on first invocation
- Performance degradation

#### Diagnosis
```bash
# Check function duration metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=your-function-name \
  --start-time 2024-01-15T00:00:00Z \
  --end-time 2024-01-15T23:59:59Z \
  --period 3600 \
  --statistics Average,Maximum
```

#### Solutions

**Use Context Manager Instead of Decorator:**
```python
# Instead of this (slower)
@coverage_handler
def lambda_handler(event, context):
    return process_request(event)

# Use this (faster)
def lambda_handler(event, context):
    with CoverageContext():
        return process_request(event)
```

**Selective Coverage:**
```python
def lambda_handler(event, context):
    # Fast initialization
    setup_resources()
    
    # Track only business logic
    with CoverageContext():
        result = business_logic(event)
    
    # Fast cleanup
    cleanup_resources()
    return result
```

**Optimize Include/Exclude Patterns:**
```bash
# Exclude unnecessary files
export COVERAGE_EXCLUDE_PATTERNS="tests/*,*/__pycache__/*,*/node_modules/*"

# Include only relevant directories
export COVERAGE_INCLUDE_PATTERNS="src/*,lib/*,handlers/*"
```

### 3. Memory Issues

#### Symptoms
- Lambda function runs out of memory
- "Runtime exited with error: signal: killed" errors
- High memory utilization in CloudWatch

#### Diagnosis
```bash
# Check memory utilization
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name MemoryUtilization \
  --dimensions Name=FunctionName,Value=your-function-name \
  --start-time 2024-01-15T00:00:00Z \
  --end-time 2024-01-15T23:59:59Z \
  --period 3600 \
  --statistics Average,Maximum
```

#### Solutions

**Increase Lambda Memory:**
```bash
aws lambda update-function-configuration \
  --function-name your-function-name \
  --memory-size 512  # Increase from 128MB
```

**Use Selective Coverage:**
```python
# For batch processing
def process_batch(items):
    for i, item in enumerate(items):
        if i % 10 == 0:  # Track every 10th item
            with CoverageContext():
                process_item(item)
        else:
            process_item(item)  # No coverage overhead
```

**Optimize Coverage Patterns:**
```bash
# Reduce coverage scope
export COVERAGE_INCLUDE_PATTERNS="src/core/*,src/handlers/*"
export COVERAGE_EXCLUDE_PATTERNS="src/utils/*,src/tests/*"
```

### 4. Coverage Files Not Combining

#### Symptoms
- Combiner function fails
- Empty combined reports
- Missing coverage data in consolidated reports

#### Diagnosis
```bash
# Check combiner function logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/your-combiner-function \
  --filter-pattern "ERROR"

# List coverage files
aws s3 ls s3://your-coverage-bucket/coverage/ --recursive

# Check file formats
aws s3 cp s3://your-coverage-bucket/coverage/sample-file.coverage ./
file sample-file.coverage
```

#### Solutions

**Verify S3 Prefix Configuration:**
```python
# In combiner function
result = combine_coverage_files(
    bucket_name=os.environ['COVERAGE_S3_BUCKET'],
    prefix='coverage/',  # Make sure this matches upload prefix
    output_key='coverage/combined/report.json'
)
```

**Check File Permissions:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket",
        "s3:PutObject"
      ],
      "Resource": [
        "arn:aws:s3:::your-coverage-bucket",
        "arn:aws:s3:::your-coverage-bucket/*"
      ]
    }
  ]
}
```

**Validate Coverage File Format:**
```python
import coverage

# Test if coverage file is valid
cov = coverage.Coverage()
try:
    cov.load()
    print("Coverage file is valid")
except Exception as e:
    print(f"Invalid coverage file: {e}")
```

## Error Messages

### `CoverageInitializationError`

**Error Message:**
```
CoverageInitializationError: Failed to initialize coverage tracking
```

**Causes:**
- Missing coverage.py dependency
- Insufficient memory
- File system permissions

**Solutions:**
1. Verify layer is attached to function
2. Increase Lambda memory allocation
3. Check CloudWatch logs for detailed error

### `S3UploadError`

**Error Message:**
```
S3UploadError: Failed to upload coverage file to S3
```

**Causes:**
- Missing S3 permissions
- Invalid bucket name
- Network connectivity issues

**Solutions:**
1. Check IAM permissions
2. Verify `COVERAGE_S3_BUCKET` environment variable
3. Test S3 connectivity manually

### `NoSuchBucket`

**Error Message:**
```
botocore.exceptions.ClientError: An error occurred (NoSuchBucket) when calling the PutObject operation
```

**Causes:**
- S3 bucket doesn't exist
- Bucket name typo
- Wrong AWS region

**Solutions:**
```bash
# Create bucket if it doesn't exist
aws s3 mb s3://your-coverage-bucket --region us-east-1

# Check bucket exists
aws s3 ls s3://your-coverage-bucket/

# Verify region
aws s3api get-bucket-location --bucket your-coverage-bucket
```

### `AccessDenied`

**Error Message:**
```
botocore.exceptions.ClientError: An error occurred (AccessDenied) when calling the PutObject operation
```

**Causes:**
- Insufficient IAM permissions
- Bucket policy restrictions
- Cross-account access issues

**Solutions:**
1. Add S3 permissions to Lambda execution role
2. Check bucket policy allows Lambda role
3. Verify cross-account trust relationships

### `RequestTimeout`

**Error Message:**
```
botocore.exceptions.ConnectTimeoutError: Connect timeout on endpoint URL
```

**Causes:**
- Network connectivity issues
- S3 service unavailability
- Timeout configuration too low

**Solutions:**
```bash
# Increase upload timeout
export COVERAGE_UPLOAD_TIMEOUT=120

# Check VPC configuration if applicable
aws lambda get-function-configuration \
  --function-name your-function-name \
  --query 'VpcConfig'
```

## Performance Issues

### Slow Upload Times

#### Symptoms
- Long function execution times
- Timeout errors
- High S3 upload duration

#### Diagnosis
```python
# Add timing to your function
import time

def lambda_handler(event, context):
    start_time = time.time()
    
    with CoverageContext():
        result = business_logic(event)
    
    end_time = time.time()
    print(f"Execution time: {end_time - start_time:.2f}s")
    
    return result
```

#### Solutions

**Optimize File Size:**
```bash
# Reduce coverage scope
export COVERAGE_INCLUDE_PATTERNS="src/core/*"
export COVERAGE_EXCLUDE_PATTERNS="tests/*,*/__pycache__/*,*/vendor/*"
```

**Increase Timeout:**
```bash
export COVERAGE_UPLOAD_TIMEOUT=60
```

**Use Asynchronous Upload:**
```python
# The layer already uses async upload, but you can verify:
from coverage_wrapper.s3_uploader import upload_coverage_file

# This is non-blocking
upload_coverage_file(coverage_data, function_name, execution_id)
```

### High Memory Usage

#### Symptoms
- Memory utilization > 80%
- Out of memory errors
- Function killed by runtime

#### Solutions

**Monitor Memory Usage:**
```python
import psutil

def lambda_handler(event, context):
    process = psutil.Process()
    memory_before = process.memory_info().rss / 1024 / 1024
    
    with CoverageContext():
        result = business_logic(event)
    
    memory_after = process.memory_info().rss / 1024 / 1024
    print(f"Memory usage: {memory_before:.1f}MB -> {memory_after:.1f}MB")
    
    return result
```

**Optimize Memory Usage:**
```python
# Use selective coverage for large codebases
def lambda_handler(event, context):
    if event.get('enable_coverage', True) and should_track_coverage(event):
        with CoverageContext():
            return business_logic(event)
    else:
        return business_logic(event)

def should_track_coverage(event):
    # Only track coverage for certain operations
    return event.get('operation') in ['create', 'update', 'delete']
```

## Configuration Problems

### Environment Variables Not Set

#### Symptoms
- `ValueError: COVERAGE_S3_BUCKET is required`
- Coverage layer not initializing

#### Solutions
```bash
# Check current environment variables
aws lambda get-function-configuration \
  --function-name your-function-name \
  --query 'Environment.Variables'

# Update environment variables
aws lambda update-function-configuration \
  --function-name your-function-name \
  --environment Variables='{
    "COVERAGE_S3_BUCKET": "your-coverage-bucket",
    "COVERAGE_S3_PREFIX": "coverage/",
    "COVERAGE_DEBUG": "true"
  }'
```

### Invalid Configuration Values

#### Symptoms
- Configuration validation errors
- Unexpected behavior

#### Solutions

**Validate Configuration:**
```python
from coverage_wrapper.models import CoverageConfig

try:
    config = CoverageConfig.from_environment()
    print("Configuration is valid")
    print(f"S3 Bucket: {config.s3_bucket}")
    print(f"S3 Prefix: {config.s3_prefix}")
except Exception as e:
    print(f"Configuration error: {e}")
```

**Use Configuration Validator:**
```python
#!/usr/bin/env python3
import os
import boto3
from coverage_wrapper.models import CoverageConfig

def validate_config():
    # Check required variables
    required_vars = ['COVERAGE_S3_BUCKET']
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        print(f"Missing required variables: {missing_vars}")
        return False
    
    # Test S3 access
    try:
        config = CoverageConfig.from_environment()
        s3 = boto3.client('s3')
        s3.head_bucket(Bucket=config.s3_bucket)
        print("✅ Configuration is valid")
        return True
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False

if __name__ == "__main__":
    validate_config()
```

## S3 Integration Issues

### Bucket Access Problems

#### Symptoms
- `NoSuchBucket` errors
- `AccessDenied` errors
- Files not appearing in S3

#### Solutions

**Test S3 Access:**
```bash
# Test bucket access
aws s3 ls s3://your-coverage-bucket/

# Test write permissions
echo "test" | aws s3 cp - s3://your-coverage-bucket/coverage/test.txt

# Test read permissions
aws s3 cp s3://your-coverage-bucket/coverage/test.txt -

# Clean up
aws s3 rm s3://your-coverage-bucket/coverage/test.txt
```

**Check Bucket Policy:**
```bash
aws s3api get-bucket-policy --bucket your-coverage-bucket
```

**Verify Cross-Region Access:**
```bash
# Check bucket region
aws s3api get-bucket-location --bucket your-coverage-bucket

# Ensure Lambda and bucket are in same region or configure cross-region access
```

### File Naming Issues

#### Symptoms
- Files overwriting each other
- Inconsistent file names
- Missing files

#### Solutions

**Check File Naming Pattern:**
```python
from coverage_wrapper.s3_uploader import generate_s3_key
from datetime import datetime

# Test key generation
key = generate_s3_key(
    function_name="my-function",
    execution_id="abc-123",
    prefix="coverage/",
    timestamp=datetime.now()
)
print(f"Generated key: {key}")
# Expected: coverage/2024/01/15/my-function-abc-123.coverage
```

**Verify Unique Keys:**
```bash
# List recent files to check for conflicts
aws s3 ls s3://your-coverage-bucket/coverage/ --recursive | tail -20
```

## Debug Mode

### Enabling Debug Mode

```bash
# Enable debug logging
export COVERAGE_DEBUG=true

# Or set in Lambda configuration
aws lambda update-function-configuration \
  --function-name your-function-name \
  --environment Variables='{"COVERAGE_DEBUG": "true"}'
```

### Debug Output

With debug mode enabled, you'll see detailed logs:

```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "level": "DEBUG",
  "logger": "coverage_wrapper.wrapper",
  "message": "Initializing coverage tracking",
  "data": {
    "config": {
      "s3_bucket": "my-coverage-bucket",
      "s3_prefix": "coverage/",
      "include_patterns": ["src/*"],
      "exclude_patterns": ["tests/*"]
    },
    "function_name": "my-function",
    "request_id": "abc-123-def-456"
  }
}
```

### Debug Utilities

```python
from coverage_wrapper.logging_utils import get_logger

logger = get_logger(__name__)

def lambda_handler(event, context):
    logger.debug("Function started", extra={
        "event_keys": list(event.keys()),
        "context_info": {
            "function_name": context.function_name,
            "memory_limit": context.memory_limit_in_mb,
            "remaining_time": context.get_remaining_time_in_millis()
        }
    })
    
    # Your code here
    
    logger.debug("Function completed")
    return result
```

## Monitoring and Logging

### CloudWatch Logs Analysis

**Search for Errors:**
```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/your-function-name \
  --filter-pattern "ERROR" \
  --start-time $(date -d "1 hour ago" +%s)000
```

**Search for Coverage Operations:**
```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/your-function-name \
  --filter-pattern "coverage" \
  --start-time $(date -d "1 hour ago" +%s)000
```

**Search for S3 Operations:**
```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/your-function-name \
  --filter-pattern "s3" \
  --start-time $(date -d "1 hour ago" +%s)000
```

### Custom Metrics

**Create Custom Metrics:**
```python
import boto3

cloudwatch = boto3.client('cloudwatch')

def put_coverage_metric(metric_name, value, unit='Count'):
    cloudwatch.put_metric_data(
        Namespace='Lambda/Coverage',
        MetricData=[
            {
                'MetricName': metric_name,
                'Value': value,
                'Unit': unit,
                'Dimensions': [
                    {
                        'Name': 'FunctionName',
                        'Value': os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'unknown')
                    }
                ]
            }
        ]
    )

# Usage in your function
def lambda_handler(event, context):
    try:
        with CoverageContext():
            result = business_logic(event)
        
        put_coverage_metric('CoverageSuccess', 1)
        return result
    
    except Exception as e:
        put_coverage_metric('CoverageFailure', 1)
        raise
```

### Alerting

**Set up CloudWatch Alarms:**
```bash
# Alert on high error rate
aws cloudwatch put-metric-alarm \
  --alarm-name "CoverageHighErrorRate" \
  --alarm-description "Coverage layer error rate is high" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --dimensions Name=FunctionName,Value=your-function-name

# Alert on high duration
aws cloudwatch put-metric-alarm \
  --alarm-name "CoverageHighDuration" \
  --alarm-description "Coverage layer causing high duration" \
  --metric-name Duration \
  --namespace AWS/Lambda \
  --statistic Average \
  --period 300 \
  --threshold 10000 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --dimensions Name=FunctionName,Value=your-function-name
```

## Getting Help

### Information to Collect

When reporting issues, please collect:

1. **Function Configuration:**
```bash
aws lambda get-function-configuration --function-name your-function-name
```

2. **Recent Logs:**
```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/your-function-name \
  --start-time $(date -d "1 hour ago" +%s)000
```

3. **S3 Bucket Status:**
```bash
aws s3 ls s3://your-coverage-bucket/coverage/ --recursive | head -10
```

4. **Layer Information:**
```bash
aws lambda list-layers --query 'Layers[?contains(LayerName, `coverage`)]'
```

### Support Checklist

Before seeking help:

- [ ] Verified environment variables are set correctly
- [ ] Checked IAM permissions for S3 access
- [ ] Reviewed CloudWatch logs for error messages
- [ ] Tested basic S3 connectivity
- [ ] Confirmed layer is attached to function
- [ ] Tried with debug mode enabled
- [ ] Checked function memory and timeout settings

### Common Solutions Summary

| Issue | Quick Fix |
|-------|-----------|
| No coverage files | Check `COVERAGE_S3_BUCKET` and IAM permissions |
| High cold start | Use `CoverageContext` instead of `@coverage_handler` |
| Memory issues | Increase Lambda memory or use selective coverage |
| Upload failures | Verify S3 permissions and bucket exists |
| Files not combining | Check S3 prefix configuration and file formats |
| Configuration errors | Use configuration validator script |
| Performance issues | Optimize include/exclude patterns |