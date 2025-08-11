# Lambda Coverage Layer Examples

This directory contains comprehensive examples demonstrating how to use the Lambda Coverage Layer in various scenarios.

## Quick Start

1. Deploy the coverage layer to your AWS account
2. Choose an example that matches your use case
3. Configure the required environment variables
4. Deploy the Lambda function with the coverage layer attached

## Examples Overview

### 1. [Simple Function](./simple_function/)
**Best for**: Getting started with basic coverage tracking

- Uses `@coverage_handler` decorator
- Automatic coverage initialization and upload
- Simple business logic with conditional paths
- JSON response formatting

```python
@coverage_handler
def lambda_handler(event, context):
    return {"message": "Hello World"}
```

### 2. [Context Manager Function](./context_manager_function/)
**Best for**: Fine-grained control over coverage tracking

- Uses `CoverageContext` context manager
- Selective coverage tracking
- Performance measurement outside coverage
- Multiple operation types

```python
def lambda_handler(event, context):
    with CoverageContext():
        return process_business_logic(event)
```

### 3. [Health Check Function](./health_check_function/)
**Best for**: API Gateway integration with health monitoring

- Health check endpoint implementation
- API Gateway event routing
- Coverage status reporting
- HTTP response formatting

```python
@coverage_handler
def lambda_handler(event, context):
    if event.get('path') == '/health':
        return health_check_handler()
    return business_logic(event)
```

### 4. [Coverage Combiner Function](./combiner_function/)
**Best for**: Consolidating coverage reports from multiple functions

- Combines multiple coverage files
- Supports scheduled execution
- S3 event triggers
- Date-based organization

```python
@coverage_handler
def lambda_handler(event, context):
    return combine_coverage_files(bucket, prefix, output_key)
```

### 5. [Advanced Usage](./advanced_usage/)
**Best for**: Complex applications with performance requirements

- Multiple coverage patterns
- Performance optimization
- Batch processing
- Comprehensive health checks
- Admin operations

```python
@coverage_handler
def lambda_handler(event, context):
    if is_performance_critical(event):
        return handle_without_coverage(event)
    
    with CoverageContext():
        return handle_with_coverage(event)
```

## Common Environment Variables

All examples require these environment variables:

```bash
# Required
COVERAGE_S3_BUCKET=your-coverage-bucket

# Optional
COVERAGE_S3_PREFIX=coverage/
COVERAGE_UPLOAD_TIMEOUT=30
AWS_REGION=us-east-1
```

## Deployment Options

### Option 1: AWS CDK (Recommended)

```python
from aws_cdk import aws_lambda as _lambda

function = _lambda.Function(
    self, "MyFunction",
    runtime=_lambda.Runtime.PYTHON_3_9,
    handler="lambda_function.lambda_handler",
    code=_lambda.Code.from_asset("examples/simple_function"),
    layers=[coverage_layer],
    environment={
        "COVERAGE_S3_BUCKET": coverage_bucket.bucket_name
    }
)
```

### Option 2: AWS SAM

```yaml
Resources:
  MyFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: examples/simple_function/
      Handler: simple_example.lambda_handler
      Runtime: python3.9
      Layers:
        - !Ref CoverageLayer
      Environment:
        Variables:
          COVERAGE_S3_BUCKET: !Ref CoverageBucket
```

### Option 3: Terraform

```hcl
resource "aws_lambda_function" "example" {
  filename         = "examples/simple_function.zip"
  function_name    = "coverage-example"
  role            = aws_iam_role.lambda_role.arn
  handler         = "simple_example.lambda_handler"
  runtime         = "python3.9"
  layers          = [aws_lambda_layer_version.coverage_layer.arn]

  environment {
    variables = {
      COVERAGE_S3_BUCKET = aws_s3_bucket.coverage.bucket
    }
  }
}
```

## Testing Your Implementation

### 1. Basic Functionality Test

```bash
# Invoke the function
aws lambda invoke \
  --function-name your-function-name \
  --payload '{"name": "test"}' \
  response.json

# Check S3 for coverage files
aws s3 ls s3://your-coverage-bucket/coverage/
```

### 2. Health Check Test

```bash
# Test health endpoint
aws lambda invoke \
  --function-name your-function-name \
  --payload '{"path": "/health", "httpMethod": "GET"}' \
  health-response.json
```

### 3. Coverage Combination Test

```bash
# Run coverage combiner
aws lambda invoke \
  --function-name your-combiner-function \
  --payload '{"prefix": "coverage/2024/01/15/"}' \
  combine-response.json
```

## Performance Considerations

### Cold Start Impact
- **Decorator**: ~200-500ms additional cold start time
- **Context Manager**: ~50-100ms additional cold start time
- **No Coverage**: No additional cold start time

### Memory Usage
- **Coverage Tracking**: ~20-50MB additional memory
- **File Upload**: ~10-20MB additional memory
- **Total Overhead**: ~30-70MB depending on code size

### Optimization Tips

1. **Use Context Manager for Performance-Critical Code**
   ```python
   # Fast initialization
   setup_resources()
   
   # Track only business logic
   with CoverageContext():
       result = process_request(event)
   
   # Fast cleanup
   cleanup_resources()
   ```

2. **Selective Batch Processing**
   ```python
   for i, item in enumerate(items):
       if i % 10 == 0:  # Track every 10th item
           with CoverageContext():
               process_item(item)
       else:
           process_item(item)
   ```

3. **Admin Endpoints Without Coverage**
   ```python
   if event.get('admin'):
       return handle_admin_request(event)  # No coverage
   
   @coverage_handler
   def handle_business_request(event):
       return process_business_logic(event)  # With coverage
   ```

## Troubleshooting

### Common Issues

1. **Coverage files not uploaded to S3**
   - Check IAM permissions for S3 access
   - Verify `COVERAGE_S3_BUCKET` environment variable
   - Check CloudWatch logs for error messages

2. **High cold start times**
   - Consider using context manager instead of decorator
   - Optimize imports and initialization code
   - Use provisioned concurrency for critical functions

3. **Memory issues**
   - Monitor memory usage in CloudWatch
   - Use selective coverage for large codebases
   - Consider increasing Lambda memory allocation

4. **Coverage files not combining**
   - Verify S3 prefix configuration
   - Check combiner function permissions
   - Ensure coverage files are in correct format

### Debug Mode

Enable debug logging:

```python
import os
os.environ['COVERAGE_DEBUG'] = 'true'
```

### Monitoring

Set up CloudWatch alarms for:
- Function duration
- Memory utilization
- Error rates
- S3 upload failures

## Next Steps

1. **Choose an Example**: Start with the simple function example
2. **Deploy and Test**: Deploy to your AWS account and run tests
3. **Customize**: Modify the example for your specific use case
4. **Monitor**: Set up monitoring and alerting
5. **Optimize**: Use performance optimization techniques as needed

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review CloudWatch logs
3. Verify IAM permissions
4. Test with minimal examples first