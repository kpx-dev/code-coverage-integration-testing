# Usage Guide

This comprehensive guide covers all aspects of using the Lambda Coverage Layer, from basic setup to advanced optimization techniques.

## Table of Contents

- [Quick Start](#quick-start)
- [Basic Usage](#basic-usage)
- [Advanced Usage](#advanced-usage)
- [Configuration](#configuration)
- [Best Practices](#best-practices)
- [Performance Optimization](#performance-optimization)
- [Monitoring and Debugging](#monitoring-and-debugging)
- [Integration Patterns](#integration-patterns)

## Quick Start

### 1. Deploy the Layer

```bash
# Clone the repository
git clone <repository-url>
cd lambda-coverage-layer

# Build and deploy
make build-layer
cdk deploy
```

### 2. Attach Layer to Your Function

**Using AWS CLI:**
```bash
aws lambda update-function-configuration \
  --function-name your-function-name \
  --layers arn:aws:lambda:us-east-1:123456789012:layer:coverage-layer:1
```

**Using CDK:**
```python
from aws_cdk import aws_lambda as _lambda

function = _lambda.Function(
    self, "MyFunction",
    runtime=_lambda.Runtime.PYTHON_3_9,
    handler="lambda_function.lambda_handler",
    code=_lambda.Code.from_asset("src/"),
    layers=[coverage_layer]
)
```

### 3. Configure Environment Variables

```bash
aws lambda update-function-configuration \
  --function-name your-function-name \
  --environment Variables='{
    "COVERAGE_S3_BUCKET": "your-coverage-bucket",
    "COVERAGE_S3_PREFIX": "coverage/"
  }'
```

### 4. Update Your Lambda Function

```python
from coverage_wrapper import coverage_handler

@coverage_handler
def lambda_handler(event, context):
    # Your existing code here
    return {"statusCode": 200, "body": "Hello World"}
```

## Basic Usage

### Using the Decorator

The simplest way to add coverage tracking:

```python
from coverage_wrapper import coverage_handler

@coverage_handler
def lambda_handler(event, context):
    # All code in this function is automatically tracked
    name = event.get('name', 'World')
    
    if event.get('uppercase', False):
        name = name.upper()
    
    return {
        'statusCode': 200,
        'body': f'Hello, {name}!'
    }
```

**Pros:**
- Zero configuration required
- Automatic initialization and cleanup
- Complete coverage of function code

**Cons:**
- Higher cold start impact
- Cannot exclude specific code sections
- Fixed configuration

### Using the Context Manager

For more control over what code is tracked:

```python
from coverage_wrapper import CoverageContext

def lambda_handler(event, context):
    # Initialization code (not tracked)
    request_id = context.aws_request_id
    start_time = time.time()
    
    # Business logic (tracked)
    with CoverageContext():
        result = process_business_logic(event)
        
        if event.get('include_metadata', True):
            result['metadata'] = generate_metadata(context)
    
    # Cleanup code (not tracked)
    execution_time = time.time() - start_time
    log_execution_metrics(request_id, execution_time)
    
    return result

def process_business_logic(event):
    # This code will be tracked for coverage
    operation = event.get('operation', 'default')
    
    if operation == 'create':
        return create_resource(event.get('data', {}))
    elif operation == 'update':
        return update_resource(event.get('id'), event.get('data', {}))
    elif operation == 'delete':
        return delete_resource(event.get('id'))
    else:
        return {'message': 'Unknown operation'}
```

**Pros:**
- Lower cold start impact
- Selective coverage tracking
- Better performance for large functions

**Cons:**
- Requires manual placement
- More complex code structure
- Potential to miss important code paths

## Advanced Usage

### Conditional Coverage

Enable coverage based on runtime conditions:

```python
from coverage_wrapper import CoverageContext
import os

def lambda_handler(event, context):
    # Enable coverage based on environment or event
    enable_coverage = (
        os.environ.get('STAGE') in ['staging', 'production'] or
        event.get('enable_coverage', False) or
        context.function_name.endswith('-test')
    )
    
    if enable_coverage:
        with CoverageContext():
            return business_logic(event, context)
    else:
        return business_logic(event, context)
```

### Selective Coverage for Performance

Track coverage for only critical code paths:

```python
from coverage_wrapper import CoverageContext

def lambda_handler(event, context):
    operation = event.get('operation')
    
    # Track coverage only for business operations
    if operation in ['create', 'update', 'delete']:
        with CoverageContext():
            return handle_business_operation(event, context)
    
    # Don't track coverage for utility operations
    elif operation in ['health_check', 'metrics', 'status']:
        return handle_utility_operation(event, context)
    
    # Default handling with coverage
    else:
        with CoverageContext():
            return handle_default_operation(event, context)
```

### Batch Processing Optimization

For functions that process multiple items:

```python
from coverage_wrapper import CoverageContext

def lambda_handler(event, context):
    items = event.get('items', [])
    results = []
    
    for i, item in enumerate(items):
        # Track coverage for every 10th item
        if i % 10 == 0:
            with CoverageContext():
                result = process_item(item)
        else:
            result = process_item(item)
        
        results.append(result)
    
    return {
        'statusCode': 200,
        'processed_count': len(results),
        'results': results
    }

def process_item(item):
    # Business logic for processing individual items
    if item.get('type') == 'A':
        return process_type_a(item)
    elif item.get('type') == 'B':
        return process_type_b(item)
    else:
        return process_default_type(item)
```

### Custom Configuration

Use custom coverage configuration:

```python
from coverage_wrapper import CoverageContext
from coverage_wrapper.models import CoverageConfig

def lambda_handler(event, context):
    # Create custom configuration
    config = CoverageConfig(
        s3_bucket=os.environ['COVERAGE_S3_BUCKET'],
        s3_prefix=f"coverage/{context.function_name}/",
        include_patterns=['src/*', 'lib/*'],
        exclude_patterns=['tests/*', 'utils/*'],
        branch_coverage=True,
        debug=event.get('debug', False)
    )
    
    with CoverageContext(config=config):
        return business_logic(event, context)
```

### Multi-Stage Processing

For functions with multiple processing stages:

```python
from coverage_wrapper import CoverageContext

def lambda_handler(event, context):
    # Stage 1: Input validation (always track)
    with CoverageContext():
        validated_data = validate_input(event)
    
    # Stage 2: Data processing (track based on data size)
    if len(validated_data) < 1000:
        with CoverageContext():
            processed_data = process_data(validated_data)
    else:
        # Skip coverage for large datasets to improve performance
        processed_data = process_data(validated_data)
    
    # Stage 3: Output formatting (always track)
    with CoverageContext():
        formatted_output = format_output(processed_data)
    
    return formatted_output
```

## Configuration

### Environment Variables

#### Required Configuration
```bash
# S3 bucket for coverage files
export COVERAGE_S3_BUCKET=your-coverage-bucket
```

#### Optional Configuration
```bash
# S3 key prefix (default: coverage/)
export COVERAGE_S3_PREFIX=coverage/production/

# Upload timeout in seconds (default: 30)
export COVERAGE_UPLOAD_TIMEOUT=60

# Include patterns (comma-separated)
export COVERAGE_INCLUDE_PATTERNS="src/*,lib/*,handlers/*"

# Exclude patterns (comma-separated)
export COVERAGE_EXCLUDE_PATTERNS="tests/*,*/__pycache__/*,*/migrations/*"

# Enable branch coverage (default: true)
export COVERAGE_BRANCH_COVERAGE=true

# Enable debug logging (default: false)
export COVERAGE_DEBUG=true
```

### Dynamic Configuration

Load configuration from AWS Systems Manager:

```python
import boto3
from coverage_wrapper import CoverageContext
from coverage_wrapper.models import CoverageConfig

def get_coverage_config():
    ssm = boto3.client('ssm')
    
    try:
        # Load configuration from Parameter Store
        bucket = ssm.get_parameter(Name='/lambda/coverage/s3-bucket')['Parameter']['Value']
        prefix = ssm.get_parameter(Name='/lambda/coverage/s3-prefix')['Parameter']['Value']
        debug = ssm.get_parameter(Name='/lambda/coverage/debug')['Parameter']['Value'] == 'true'
        
        return CoverageConfig(
            s3_bucket=bucket,
            s3_prefix=prefix,
            debug=debug
        )
    except Exception:
        # Fallback to environment variables
        return CoverageConfig.from_environment()

def lambda_handler(event, context):
    config = get_coverage_config()
    
    with CoverageContext(config=config):
        return business_logic(event, context)
```

### Environment-Specific Configuration

```python
import os
from coverage_wrapper import CoverageContext
from coverage_wrapper.models import CoverageConfig

def get_environment_config():
    stage = os.environ.get('STAGE', 'development')
    
    if stage == 'production':
        return CoverageConfig(
            s3_bucket='prod-coverage-bucket',
            s3_prefix='coverage/production/',
            debug=False,
            exclude_patterns=['tests/*', 'debug/*']
        )
    elif stage == 'staging':
        return CoverageConfig(
            s3_bucket='staging-coverage-bucket',
            s3_prefix='coverage/staging/',
            debug=True,
            include_patterns=['src/*', 'lib/*']
        )
    else:
        return CoverageConfig(
            s3_bucket='dev-coverage-bucket',
            s3_prefix='coverage/development/',
            debug=True
        )

def lambda_handler(event, context):
    config = get_environment_config()
    
    with CoverageContext(config=config):
        return business_logic(event, context)
```

## Best Practices

### 1. Choose the Right Pattern

**Use `@coverage_handler` when:**
- Function is simple and small
- Complete coverage is needed
- Performance is not critical
- Minimal code changes are preferred

**Use `CoverageContext` when:**
- Function has initialization/cleanup code
- Performance is critical
- Selective coverage is needed
- Fine-grained control is required

### 2. Optimize Coverage Scope

**Include only relevant code:**
```bash
export COVERAGE_INCLUDE_PATTERNS="src/core/*,src/handlers/*,src/models/*"
```

**Exclude unnecessary files:**
```bash
export COVERAGE_EXCLUDE_PATTERNS="tests/*,*/__pycache__/*,*/migrations/*,*/vendor/*"
```

### 3. Handle Errors Gracefully

```python
from coverage_wrapper import CoverageContext
from coverage_wrapper.error_handling import CoverageError

def lambda_handler(event, context):
    try:
        with CoverageContext():
            return business_logic(event, context)
    except CoverageError as e:
        # Log coverage error but continue function execution
        print(f"Coverage error: {e}")
        return business_logic(event, context)
    except Exception as e:
        # Handle business logic errors
        return {
            'statusCode': 500,
            'body': f'Error: {str(e)}'
        }
```

### 4. Monitor Performance Impact

```python
import time
from coverage_wrapper import CoverageContext

def lambda_handler(event, context):
    start_time = time.time()
    
    with CoverageContext():
        result = business_logic(event, context)
    
    execution_time = time.time() - start_time
    
    # Log performance metrics
    print(f"Execution time: {execution_time:.3f}s")
    
    # Add execution time to response for monitoring
    if isinstance(result, dict):
        result['execution_time_ms'] = round(execution_time * 1000, 2)
    
    return result
```

### 5. Use Health Checks

```python
from coverage_wrapper import coverage_handler
from coverage_wrapper.health_check import health_check_handler

@coverage_handler
def lambda_handler(event, context):
    # Handle health check requests
    if event.get('path') == '/health' or event.get('action') == 'health_check':
        return {
            'statusCode': 200,
            'body': json.dumps(health_check_handler())
        }
    
    # Regular business logic
    return business_logic(event, context)
```

## Performance Optimization

### 1. Memory Optimization

**Monitor memory usage:**
```python
import psutil
from coverage_wrapper import CoverageContext

def lambda_handler(event, context):
    process = psutil.Process()
    memory_before = process.memory_info().rss / 1024 / 1024
    
    with CoverageContext():
        result = business_logic(event, context)
    
    memory_after = process.memory_info().rss / 1024 / 1024
    memory_delta = memory_after - memory_before
    
    print(f"Memory usage: {memory_before:.1f}MB -> {memory_after:.1f}MB (Δ{memory_delta:.1f}MB)")
    
    return result
```

**Optimize for large codebases:**
```bash
# Reduce coverage scope
export COVERAGE_INCLUDE_PATTERNS="src/core/*"
export COVERAGE_EXCLUDE_PATTERNS="src/utils/*,src/tests/*,src/migrations/*"

# Disable branch coverage if not needed
export COVERAGE_BRANCH_COVERAGE=false
```

### 2. Cold Start Optimization

**Use lazy loading:**
```python
from coverage_wrapper import CoverageContext

# Global variables for caching
_cached_resources = None

def get_resources():
    global _cached_resources
    if _cached_resources is None:
        _cached_resources = initialize_resources()
    return _cached_resources

def lambda_handler(event, context):
    # Fast resource access
    resources = get_resources()
    
    # Track only business logic
    with CoverageContext():
        return process_with_resources(event, resources)
```

**Conditional coverage for cold starts:**
```python
import os
from coverage_wrapper import CoverageContext

# Track coverage only after warm-up
_is_warm = False

def lambda_handler(event, context):
    global _is_warm
    
    # Skip coverage on cold start
    if not _is_warm:
        _is_warm = True
        return business_logic(event, context)
    
    # Use coverage on warm invocations
    with CoverageContext():
        return business_logic(event, context)
```

### 3. Batch Processing Optimization

**Adaptive coverage frequency:**
```python
from coverage_wrapper import CoverageContext

def lambda_handler(event, context):
    items = event.get('items', [])
    batch_size = len(items)
    
    # Adjust coverage frequency based on batch size
    if batch_size < 10:
        coverage_frequency = 1  # Track every item
    elif batch_size < 100:
        coverage_frequency = 5  # Track every 5th item
    else:
        coverage_frequency = 20  # Track every 20th item
    
    results = []
    for i, item in enumerate(items):
        if i % coverage_frequency == 0:
            with CoverageContext():
                result = process_item(item)
        else:
            result = process_item(item)
        
        results.append(result)
    
    return {'results': results}
```

## Monitoring and Debugging

### 1. Enable Debug Logging

```bash
export COVERAGE_DEBUG=true
```

### 2. Custom Logging

```python
from coverage_wrapper.logging_utils import get_logger
from coverage_wrapper import CoverageContext

logger = get_logger(__name__)

def lambda_handler(event, context):
    logger.info("Function started", extra={
        "request_id": context.aws_request_id,
        "function_name": context.function_name,
        "event_keys": list(event.keys())
    })
    
    try:
        with CoverageContext():
            result = business_logic(event, context)
        
        logger.info("Function completed successfully", extra={
            "result_keys": list(result.keys()) if isinstance(result, dict) else None
        })
        
        return result
    
    except Exception as e:
        logger.error("Function failed", extra={
            "error": str(e),
            "error_type": type(e).__name__
        })
        raise
```

### 3. Performance Monitoring

```python
import time
import boto3
from coverage_wrapper import CoverageContext

cloudwatch = boto3.client('cloudwatch')

def put_metric(name, value, unit='Count'):
    cloudwatch.put_metric_data(
        Namespace='Lambda/Coverage',
        MetricData=[{
            'MetricName': name,
            'Value': value,
            'Unit': unit,
            'Dimensions': [{
                'Name': 'FunctionName',
                'Value': os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'unknown')
            }]
        }]
    )

def lambda_handler(event, context):
    start_time = time.time()
    
    try:
        with CoverageContext():
            result = business_logic(event, context)
        
        execution_time = time.time() - start_time
        put_metric('ExecutionTime', execution_time * 1000, 'Milliseconds')
        put_metric('Success', 1)
        
        return result
    
    except Exception as e:
        put_metric('Error', 1)
        raise
```

## Integration Patterns

### 1. API Gateway Integration

```python
from coverage_wrapper import coverage_handler
from coverage_wrapper.health_check import health_check_handler
import json

@coverage_handler
def lambda_handler(event, context):
    # Handle different HTTP methods and paths
    method = event.get('httpMethod')
    path = event.get('path')
    
    if method == 'GET' and path == '/health':
        return create_response(200, health_check_handler())
    
    elif method == 'POST' and path == '/api/users':
        return handle_create_user(event, context)
    
    elif method == 'GET' and path.startswith('/api/users/'):
        user_id = path.split('/')[-1]
        return handle_get_user(user_id, event, context)
    
    else:
        return create_response(404, {'error': 'Not Found'})

def create_response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(body)
    }
```

### 2. EventBridge Integration

```python
from coverage_wrapper import coverage_handler
import json

@coverage_handler
def lambda_handler(event, context):
    # Handle EventBridge events
    if 'source' in event and event['source'] == 'myapp.orders':
        return handle_order_event(event, context)
    
    elif 'source' in event and event['source'] == 'myapp.users':
        return handle_user_event(event, context)
    
    else:
        print(f"Unknown event source: {event.get('source', 'unknown')}")
        return {'status': 'ignored'}

def handle_order_event(event, context):
    detail_type = event.get('detail-type')
    detail = event.get('detail', {})
    
    if detail_type == 'Order Created':
        return process_order_created(detail)
    elif detail_type == 'Order Updated':
        return process_order_updated(detail)
    else:
        return {'status': 'unknown_event_type'}
```

### 3. S3 Event Integration

```python
from coverage_wrapper import coverage_handler
import urllib.parse

@coverage_handler
def lambda_handler(event, context):
    results = []
    
    for record in event.get('Records', []):
        if record.get('eventSource') == 'aws:s3':
            bucket = record['s3']['bucket']['name']
            key = urllib.parse.unquote_plus(record['s3']['object']['key'])
            event_name = record['eventName']
            
            result = process_s3_event(bucket, key, event_name)
            results.append(result)
    
    return {'processed': len(results), 'results': results}

def process_s3_event(bucket, key, event_name):
    if event_name.startswith('ObjectCreated'):
        return handle_object_created(bucket, key)
    elif event_name.startswith('ObjectRemoved'):
        return handle_object_removed(bucket, key)
    else:
        return {'status': 'ignored', 'event': event_name}
```

### 4. SQS Integration

```python
from coverage_wrapper import coverage_handler
import json

@coverage_handler
def lambda_handler(event, context):
    results = []
    
    for record in event.get('Records', []):
        if record.get('eventSource') == 'aws:sqs':
            message_body = json.loads(record['body'])
            receipt_handle = record['receiptHandle']
            
            result = process_sqs_message(message_body, receipt_handle)
            results.append(result)
    
    return {
        'batchItemFailures': [
            {'itemIdentifier': r['receipt_handle']} 
            for r in results if not r['success']
        ]
    }

def process_sqs_message(message, receipt_handle):
    try:
        # Process the message
        result = handle_message(message)
        return {
            'success': True,
            'receipt_handle': receipt_handle,
            'result': result
        }
    except Exception as e:
        return {
            'success': False,
            'receipt_handle': receipt_handle,
            'error': str(e)
        }
```

### 5. Step Functions Integration

```python
from coverage_wrapper import coverage_handler

@coverage_handler
def lambda_handler(event, context):
    # Step Functions pass state between steps
    step_name = event.get('step_name', 'unknown')
    input_data = event.get('input', {})
    
    if step_name == 'validate':
        return validate_step(input_data)
    elif step_name == 'process':
        return process_step(input_data)
    elif step_name == 'finalize':
        return finalize_step(input_data)
    else:
        raise ValueError(f"Unknown step: {step_name}")

def validate_step(data):
    # Validation logic
    errors = []
    if not data.get('id'):
        errors.append('Missing required field: id')
    
    return {
        'step_name': 'validate',
        'valid': len(errors) == 0,
        'errors': errors,
        'data': data
    }

def process_step(data):
    # Processing logic
    processed_data = {
        'id': data['id'],
        'processed_at': time.time(),
        'result': perform_processing(data)
    }
    
    return {
        'step_name': 'process',
        'data': processed_data
    }
```

This comprehensive usage guide covers all major aspects of using the Lambda Coverage Layer effectively. Choose the patterns that best fit your use case and performance requirements.