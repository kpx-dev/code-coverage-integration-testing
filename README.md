# Lambda Coverage Layer

A Python Lambda layer that provides automated code coverage tracking for AWS Lambda functions. This layer integrates the Python `coverage.py` package to collect coverage data during function execution, automatically uploads coverage reports to S3, and provides utilities for combining multiple coverage reports into consolidated reports.

## Features

- **Automatic Coverage Tracking**: Use decorators or context managers to track code coverage
- **S3 Integration**: Automatic upload of coverage files to S3 with configurable naming
- **Coverage Combining**: Utilities to merge multiple coverage files into consolidated reports

## How It Works

The Lambda Coverage Layer provides a seamless way to collect code coverage data from your Lambda functions without modifying your business logic. Here's how the solution works:

### High-Level Architecture

```mermaid
graph TB
    subgraph "Lambda Function Execution"
        A[Lambda Handler] --> B[Coverage Wrapper]
        B --> C[Coverage.py Library]
        B --> D[Your Business Logic]
        C --> E[Coverage Data Collection]
    end

    subgraph "Data Processing & Storage"
        E --> F[Coverage File Generation]
        F --> G[S3 Uploader]
        G --> H[S3 Bucket Storage]
    end

    subgraph "Reporting & Analysis"
        H --> I[Coverage Combiner Lambda]
        I --> J[Merged Coverage Reports]
        J --> K[Combined S3 Storage]

        L[Health Check Endpoint] --> M[Coverage Status API]
    end

    subgraph "Monitoring & Observability"
        N[CloudWatch Logs] --> O[Structured JSON Logs]
        P[Error Handling] --> Q[Graceful Degradation]
    end

    B --> N
    G --> P
    I --> N
```

### Solution Components

#### 1. **Lambda Layer**

- **Purpose**: Provides coverage tracking capabilities to any Lambda function
- **Contents**: Python coverage.py library + custom wrapper modules
- **Deployment**: Shared across multiple Lambda functions in your account

#### 2. **Coverage Wrapper**

- **Decorator Pattern**: `@coverage_handler` - Automatic coverage for entire function
- **Context Manager**: `CoverageContext()` - Selective coverage for specific code blocks
- **Initialization**: Configures coverage.py with environment-based settings

#### 3. **Data Collection & Upload**

- **Real-time Tracking**: Collects line and branch coverage during execution
- **Automatic Upload**: Sends coverage files to S3 after function completion
- **Retry Logic**: Handles network failures with exponential backoff
- **Fallback Storage**: Local storage when S3 upload fails

#### 4. **Coverage Combining**

- **Multi-Function Reports**: Combines coverage from multiple Lambda executions
- **Scheduled Processing**: Can be triggered by CloudWatch Events or S3 events
- **Data Validation**: Ensures coverage file integrity before merging

#### 5. **Health & Monitoring**

- **Health Endpoints**: Built-in health check API for coverage status
- **Structured Logging**: JSON logs for easy parsing and monitoring
- **Error Handling**: Graceful degradation ensures Lambda functions continue working

### Execution Flow

```mermaid
sequenceDiagram
    participant LF as Lambda Function
    participant CW as Coverage Wrapper
    participant CP as Coverage.py
    participant BL as Business Logic
    participant S3 as S3 Storage
    participant CL as CloudWatch Logs

    Note over LF,CL: Lambda Function Execution
    LF->>CW: Function invocation
    CW->>CP: Initialize coverage tracking
    CW->>BL: Execute business logic
    BL-->>CW: Return results
    CW->>CP: Stop coverage & generate report
    CP-->>CW: Coverage data file

    Note over CW,S3: Async Upload Process
    CW->>S3: Upload coverage file
    S3-->>CW: Upload confirmation
    CW->>CL: Log metrics & status
    CW-->>LF: Return business logic results

    Note over S3,CL: Optional Combining Process
    S3->>CW: Trigger combiner Lambda
    CW->>S3: Download multiple coverage files
    CW->>CP: Merge coverage data
    CW->>S3: Upload combined report
```

### Key Benefits

1. **Zero Code Changes**: Add coverage to existing Lambda functions without modifying business logic
2. **Performance Optimized**: Minimal cold start impact (~200-500ms) with async upload
3. **Fault Tolerant**: Functions continue working even if coverage collection fails
4. **Scalable**: Works across hundreds of Lambda functions with centralized storage
5. **Observable**: Rich logging and health check endpoints for monitoring

### Layer Structure

```
layer/
├── python/
│   └── coverage_wrapper/      # Custom wrapper modules
│       ├── __init__.py        # Public API exports
│       ├── wrapper.py         # Main coverage wrapper & decorators
│       ├── s3_uploader.py     # S3 upload with retry logic
│       ├── health_check.py    # Health check endpoints
│       ├── combiner.py        # Coverage file combining utilities
│       ├── models.py          # Data models & configuration
│       ├── logging_utils.py   # Structured logging
│       └── error_handling.py  # Graceful error handling
└── requirements.txt           # Layer dependencies (coverage.py, boto3)
```

### Data Flow Patterns

#### Pattern 1: Automatic Coverage (Decorator)

```python
@coverage_handler  # Wraps entire function
def lambda_handler(event, context):
    return process_request(event)  # All code tracked
```

#### Pattern 2: Selective Coverage (Context Manager)

```python
def lambda_handler(event, context):
    setup_resources()  # Not tracked

    with CoverageContext():  # Only this block tracked
        result = core_business_logic(event)

    cleanup_resources()  # Not tracked
    return result
```

#### Pattern 3: Health Check Integration

```python
@coverage_handler
def lambda_handler(event, context):
    if event.get('path') == '/health':
        return health_check_handler()  # Built-in health endpoint
    return handle_business_request(event)
```

## Quick Start

### 1. Build and Deploy Infrastructure

```bash
# Install dependencies and build the layer
make install-deps
make build

# Deploy the complete infrastructure (S3 bucket, layer, example functions)
make cdk-deploy

# Or deploy just the layer to AWS (us-east-1 only)
make deploy
```

This creates:

- **Lambda Layer**: Contains coverage.py and wrapper modules
- **S3 Bucket**: Stores individual and combined coverage reports
- **IAM Roles**: Proper permissions for Lambda functions to access S3
- **Example Functions**: Demonstrates different usage patterns

### 2. Add Layer to Your Lambda Function

#### Option A: Using AWS Console

1. Go to your Lambda function in AWS Console
2. Scroll to "Layers" section
3. Click "Add a layer"
4. Select "Custom layers" and choose "lambda-coverage-layer"

#### Option B: Using CDK/CloudFormation

```typescript
const myFunction = new lambda.Function(this, "MyFunction", {
  // ... other properties
  layers: [
    lambda.LayerVersion.fromLayerVersionArn(
      this,
      "CoverageLayer",
      "arn:aws:lambda:region:account:layer:lambda-coverage-layer:version"
    ),
  ],
});
```

#### Option C: Using AWS CLI

```bash
aws lambda update-function-configuration \
  --function-name my-function \
  --layers arn:aws:lambda:region:account:layer:lambda-coverage-layer:version
```

### 3. Update Your Lambda Function Code

```python
from coverage_wrapper import coverage_handler

@coverage_handler
def lambda_handler(event, context):
    # Your existing Lambda function code here
    return {"statusCode": 200, "body": "Hello World"}
```

### 4. Configure Environment Variables

Set these environment variables in your Lambda function:

```bash
COVERAGE_S3_BUCKET=your-coverage-bucket-name
COVERAGE_S3_PREFIX=coverage/
COVERAGE_LOG_LEVEL=INFO
```

### 5. Test and Monitor

```bash
# Invoke your function
aws lambda invoke --function-name my-function response.json

# Check S3 for coverage files
aws s3 ls s3://your-coverage-bucket/coverage/

# View logs in CloudWatch
aws logs tail /aws/lambda/my-function --follow
```

## Installation & Deployment Scenarios

### Prerequisites

- Python 3.8+
- AWS CLI configured with appropriate permissions
- AWS CDK v2 (for infrastructure deployment)
- Make (for build automation)

### Scenario 1: Complete Infrastructure Setup (Recommended)

For new projects or when you want the full solution including S3 bucket and example functions:

```bash
# Clone and setup
git clone <repository-url>
cd lambda-coverage-layer
make dev-setup

# Deploy everything: S3 bucket, layer, IAM roles, example functions
make cdk-deploy
```

**What this creates:**

- Lambda layer with coverage capabilities
- S3 bucket with lifecycle policies for coverage storage
- IAM execution role with proper S3 permissions
- Example Lambda functions demonstrating usage patterns
- CloudWatch log groups for monitoring

### Scenario 2: Layer-Only Deployment

When you have existing infrastructure and only need the layer:

```bash
# Build and deploy just the layer
make build
make deploy
```

**What this creates:**

- Lambda layer deployed to us-east-1 region
- Layer versions for different Python runtimes

### Scenario 3: Development/Testing Setup

For local development and testing:

```bash
# Setup development environment
make dev-setup

# Run tests
make test

# Build and validate locally
make dev-build
```

### Scenario 4: CI/CD Pipeline Integration

For automated deployments in CI/CD:

```bash
# In your CI/CD pipeline
make install-deps
make build
make validate

# Deploy to different environments
make deploy  # Deploys to us-east-1
make cdk-deploy --context environment=staging
```

### Multi-Region Deployment

For global applications requiring the layer in multiple regions, you'll need to deploy manually to each region or use CDK:

```bash
# Deploy layer to us-east-1 (default)
make deploy

# For other regions, use AWS CLI directly
aws lambda publish-layer-version \
  --layer-name lambda-coverage-layer \
  --zip-file fileb://dist/lambda-coverage-layer-latest.zip \
  --compatible-runtimes python3.8 python3.9 python3.10 python3.11 python3.12 \
  --region us-west-2

# Or use CDK for multi-region infrastructure
cdk deploy --context regions="us-east-1,eu-west-1"
```

## Usage Patterns & Use Cases

### When to Use This Solution

#### ✅ **Ideal Use Cases**

- **Microservices Architecture**: Track coverage across multiple Lambda functions
- **CI/CD Quality Gates**: Ensure code coverage thresholds in deployment pipelines
- **Production Monitoring**: Monitor which code paths are actually used in production
- **Testing Gap Analysis**: Identify untested code in serverless applications
- **Compliance Requirements**: Meet code coverage requirements for regulated industries
- **Performance Optimization**: Identify unused code for optimization

#### ❌ **Not Recommended For**

- **High-frequency functions** (>1000 invocations/minute) - consider sampling
- **Memory-constrained functions** (<256MB) - coverage adds ~30-70MB overhead
- **Ultra-low latency requirements** (<100ms) - adds 50-500ms cold start time
- **Functions with sensitive data** - ensure proper S3 bucket security

### Usage Patterns

### Basic Usage with Decorator

The simplest way to add coverage tracking to your Lambda function:

```python
from coverage_wrapper import coverage_handler

@coverage_handler
def lambda_handler(event, context):
    # All your code is automatically tracked
    name = event.get('name', 'World')
    return {
        'statusCode': 200,
        'body': f'Hello, {name}!'
    }
```

### Manual Control with Context Manager

For fine-grained control over what code is tracked:

```python
from coverage_wrapper import CoverageContext

def lambda_handler(event, context):
    # Initialization code (not tracked)
    setup_resources()

    # Business logic (tracked)
    with CoverageContext():
        result = process_business_logic(event)

    # Cleanup code (not tracked)
    cleanup_resources()

    return result
```

### Health Check Integration

Add health check endpoints to your Lambda functions:

```python
from coverage_wrapper import coverage_handler
from coverage_wrapper.health_check import health_check_handler

@coverage_handler
def lambda_handler(event, context):
    if event.get('path') == '/health':
        return {
            'statusCode': 200,
            'body': json.dumps(health_check_handler())
        }

    # Regular business logic
    return handle_request(event, context)
```

### Coverage Combining

Combine multiple coverage files into consolidated reports:

```python
from coverage_wrapper import coverage_handler
from coverage_wrapper.combiner import combine_coverage_files

@coverage_handler
def coverage_combiner_handler(event, context):
    result = combine_coverage_files(
        bucket_name=os.environ['COVERAGE_S3_BUCKET'],
        prefix='coverage/',
        output_key='coverage/combined/daily-report.json'
    )
    return {'statusCode': 200, 'body': json.dumps(result)}
```

### Real-World Implementation Examples

#### E-commerce Microservices

```python
# Order processing service
@coverage_handler
def process_order_handler(event, context):
    order = validate_order(event['order'])
    payment = process_payment(order)
    inventory = update_inventory(order)
    return create_order_response(order, payment, inventory)

# Inventory service with selective coverage
def inventory_handler(event, context):
    # Skip coverage for initialization
    setup_database_connection()

    # Track only business logic
    with CoverageContext():
        if event['action'] == 'check':
            return check_inventory(event['items'])
        elif event['action'] == 'update':
            return update_inventory(event['items'])
```

#### API Gateway with Health Checks

```python
@coverage_handler
def api_gateway_handler(event, context):
    # Built-in health check endpoint
    if event.get('path') == '/health':
        return {
            'statusCode': 200,
            'body': json.dumps(health_check_handler())
        }

    # Route to business logic
    if event['httpMethod'] == 'GET':
        return handle_get_request(event)
    elif event['httpMethod'] == 'POST':
        return handle_post_request(event)
```

#### Scheduled Coverage Reports

```python
# CloudWatch Events trigger this daily
@coverage_handler
def daily_coverage_report(event, context):
    """Combines yesterday's coverage files into daily report"""
    from datetime import datetime, timedelta

    yesterday = datetime.now() - timedelta(days=1)
    prefix = f"coverage/{yesterday.strftime('%Y/%m/%d')}/"

    result = combine_coverage_files(
        bucket_name=os.environ['COVERAGE_S3_BUCKET'],
        prefix=prefix,
        output_key=f"coverage/daily/{yesterday.strftime('%Y-%m-%d')}.json"
    )

    # Send to monitoring system
    send_coverage_metrics(result)
    return result
```

## Configuration

### Environment Variables

| Variable                    | Required | Default     | Description                             |
| --------------------------- | -------- | ----------- | --------------------------------------- |
| `COVERAGE_S3_BUCKET`        | Yes      | -           | S3 bucket for coverage file uploads     |
| `COVERAGE_S3_PREFIX`        | No       | `coverage/` | S3 key prefix for coverage files        |
| `COVERAGE_UPLOAD_TIMEOUT`   | No       | `30`        | Upload timeout in seconds               |
| `COVERAGE_INCLUDE_PATTERNS` | No       | -           | Comma-separated patterns to include     |
| `COVERAGE_EXCLUDE_PATTERNS` | No       | -           | Comma-separated patterns to exclude     |
| `COVERAGE_BRANCH_COVERAGE`  | No       | `true`      | Enable branch coverage tracking         |
| `COVERAGE_LOG_LEVEL`        | No       | `INFO`      | Log level (DEBUG, INFO, WARNING, ERROR) |

### IAM Permissions

Your Lambda execution role needs the following permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::your-coverage-bucket/*",
        "arn:aws:s3:::your-coverage-bucket"
      ]
    }
  ]
}
```

## Examples

See the [examples](./examples/) directory for comprehensive usage examples:

- **[Simple Function](./examples/simple_function/)**: Basic decorator usage
- **[Context Manager](./examples/context_manager_function/)**: Manual coverage control
- **[Health Check](./examples/health_check_function/)**: API Gateway integration
- **[Coverage Combiner](./examples/combiner_function/)**: Consolidating reports
- **[Advanced Usage](./examples/advanced_usage/)**: Performance optimization patterns

## API Reference

### Decorators

#### `@coverage_handler`

Automatically wraps your Lambda handler with coverage tracking.

```python
@coverage_handler
def lambda_handler(event, context):
    return response
```

### Context Managers

#### `CoverageContext`

Provides manual control over coverage tracking.

```python
with CoverageContext():
    # Code tracked for coverage
    result = business_logic()
```

### Functions

#### `health_check_handler()`

Returns health status including coverage information.

```python
from coverage_wrapper.health_check import health_check_handler

status = health_check_handler()
# Returns: {"status": "healthy", "coverage_enabled": true, ...}
```

#### `combine_coverage_files(bucket_name, prefix, output_key)`

Combines multiple coverage files into a single report.

```python
from coverage_wrapper.combiner import combine_coverage_files

result = combine_coverage_files(
    bucket_name="my-bucket",
    prefix="coverage/2024/01/15/",
    output_key="coverage/combined/report.json"
)
```

## Performance

### Cold Start Impact

| Usage Pattern       | Additional Cold Start Time |
| ------------------- | -------------------------- |
| `@coverage_handler` | ~200-500ms                 |
| `CoverageContext`   | ~50-100ms                  |
| No coverage         | 0ms                        |

### Memory Overhead

| Component         | Memory Usage |
| ----------------- | ------------ |
| Coverage tracking | ~20-50MB     |
| File upload       | ~10-20MB     |
| Total overhead    | ~30-70MB     |

### Optimization Tips

1. **Use context managers for performance-critical functions**
2. **Exclude initialization/cleanup code from coverage**
3. **Use selective coverage for batch processing**
4. **Monitor memory usage and adjust Lambda memory allocation**

## Troubleshooting

### Common Implementation Issues

#### Coverage files not uploaded to S3

**Symptoms**: Function executes successfully but no coverage files appear in S3

**Solutions**:

1. **Check IAM permissions**:

   ```bash
   # Verify your Lambda execution role has S3 permissions
   aws iam get-role-policy --role-name your-lambda-role --policy-name S3Access
   ```

2. **Verify environment variables**:

   ```bash
   # Check Lambda configuration
   aws lambda get-function-configuration --function-name your-function
   ```

3. **Check CloudWatch logs**:
   ```bash
   # Look for S3 upload errors
   aws logs filter-log-events --log-group-name /aws/lambda/your-function \
     --filter-pattern "S3 upload"
   ```

#### High cold start times

**Symptoms**: Lambda functions taking 500ms+ longer to start

**Solutions**:

1. **Use selective coverage for performance-critical functions**:

   ```python
   def lambda_handler(event, context):
       # Fast initialization (not tracked)
       setup_connections()

       # Only track critical business logic
       with CoverageContext():
           return process_request(event)
   ```

2. **Optimize imports**:

   ```python
   # Import coverage_wrapper only when needed
   if os.environ.get('COVERAGE_ENABLED', 'false') == 'true':
       from coverage_wrapper import coverage_handler
   else:
       coverage_handler = lambda f: f  # No-op decorator
   ```

3. **Use provisioned concurrency for critical functions**:
   ```bash
   aws lambda put-provisioned-concurrency-config \
     --function-name your-function \
     --provisioned-concurrency-config AllocatedProvisionedConcurrencyUnits=10
   ```

#### Memory issues

**Symptoms**: Lambda functions running out of memory or increased memory usage

**Solutions**:

1. **Monitor memory usage patterns**:

   ```python
   # Add memory monitoring to your function
   import psutil

   @coverage_handler
   def lambda_handler(event, context):
       initial_memory = psutil.virtual_memory().used
       result = your_business_logic(event)
       final_memory = psutil.virtual_memory().used
       print(f"Memory used: {final_memory - initial_memory} bytes")
       return result
   ```

2. **Use selective coverage for large codebases**:

   ```python
   # Only track specific modules
   os.environ['COVERAGE_INCLUDE_PATTERNS'] = 'src/core/*,src/business/*'
   os.environ['COVERAGE_EXCLUDE_PATTERNS'] = 'src/vendor/*,tests/*'
   ```

3. **Increase Lambda memory allocation**:
   ```bash
   aws lambda update-function-configuration \
     --function-name your-function \
     --memory-size 512  # Increase from 256MB
   ```

### Performance Optimization

#### Sampling for High-Volume Functions

```python
import random

def lambda_handler(event, context):
    # Only collect coverage for 1% of invocations
    if random.random() < 0.01:
        with CoverageContext():
            return process_request(event)
    else:
        return process_request(event)
```

#### Environment-Based Coverage

```python
import os

# Only enable coverage in development/staging
ENABLE_COVERAGE = os.environ.get('STAGE') in ['dev', 'staging']

if ENABLE_COVERAGE:
    from coverage_wrapper import coverage_handler
else:
    coverage_handler = lambda f: f  # No-op decorator

@coverage_handler
def lambda_handler(event, context):
    return process_request(event)
```

### Debug Mode

Enable debug logging by setting the log level:

```python
import os
os.environ['COVERAGE_LOG_LEVEL'] = 'DEBUG'
```

Or set it as an environment variable in your Lambda configuration:

```bash
COVERAGE_LOG_LEVEL=DEBUG
```

### Log Analysis

Coverage operations are logged with structured JSON:

```json
{
  "level": "INFO",
  "message": "Coverage file uploaded successfully",
  "s3_key": "coverage/2024/01/15/my-function-abc123.coverage",
  "file_size": 1024,
  "upload_time_ms": 150
}
```

## Development

### Available Make Commands

```bash
# Setup and building
make help           # Show all available commands
make dev-setup      # Install dependencies and setup development environment
make build          # Build the Lambda layer package
make validate       # Validate the built layer package
make clean          # Clean build artifacts

# Testing
make test           # Run tests with coverage report
make dev-test       # Run tests and validation

# Deployment
make deploy         # Deploy layer to AWS (us-east-1 only)
make cdk-synth      # Synthesize CDK stack
make cdk-deploy     # Deploy CDK infrastructure
make cdk-destroy    # Destroy CDK infrastructure

# Version management
make version        # Show current version
make bump-patch     # Bump patch version
make bump-minor     # Bump minor version
make bump-major     # Bump major version

# Development workflows
make dev-build      # Clean, build, and validate
make release-patch  # Bump patch version, build, and validate
```

### Building the Layer

```bash
# Install development dependencies
make install-deps

# Build the layer package
make build

# Validate the layer
make validate
```

### Running Tests

#### Unit Tests
```bash
# Run unit tests with coverage report
make test

# Clean build artifacts
make clean

# Full development workflow
make dev-build
```

#### Integration Testing with CDK

The project includes comprehensive CDK-based testing infrastructure:

```bash
# 1. Build and deploy the layer
make build
make deploy

# 2. Deploy testing infrastructure (replace with your layer ARN)
make test-deploy LAYER_ARN=arn:aws:lambda:us-east-1:ACCOUNT:layer:lambda-coverage-layer:VERSION

# 3. Run load tests
make load-test        # Standard load test (2 iterations)
make load-test-quick  # Quick test (1 iteration)
make load-test-full   # Comprehensive test (5 iterations)

# 4. Check deployment status
make test-status

# 5. Complete workflow (build + deploy + test)
make test-all LAYER_ARN=arn:aws:lambda:us-east-1:ACCOUNT:layer:lambda-coverage-layer:VERSION

# 6. Cleanup testing infrastructure
make test-destroy
```

The testing infrastructure deploys:
- **Main Test Function**: Comprehensive Lambda with multiple operations (add, multiply, divide, random, health, complex, async)
- **Simple Test Function**: Basic Lambda for simple coverage testing
- **Error Test Function**: Lambda for testing error handling and edge cases
- **S3 Bucket**: For storing coverage reports with lifecycle policies
- **IAM Roles**: Proper permissions for S3 access and Lambda execution

Load tests exercise different code paths and generate coverage reports that are uploaded to S3.

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For issues and questions:

1. Check the [troubleshooting section](#troubleshooting)
2. Review the [examples](./examples/)
3. Check CloudWatch logs
4. Open an issue on GitHub

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and changes.
