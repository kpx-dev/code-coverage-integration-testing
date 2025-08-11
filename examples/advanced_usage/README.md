# Advanced Usage Example

This example demonstrates advanced patterns and features of the coverage layer, including selective coverage tracking, performance optimization, and comprehensive health checks.

## Features

- Multiple coverage patterns (decorator + context manager)
- Advanced request routing
- Performance testing with selective coverage
- Comprehensive health checks
- Batch processing optimization
- Error handling and monitoring
- Memory usage tracking

## Usage Patterns

### 1. Automatic Coverage with Decorator
```python
@coverage_handler
def lambda_handler(event, context):
    # All code automatically tracked
    return handle_request(event, context)
```

### 2. Selective Coverage with Context Manager
```python
def performance_test():
    # Measure without coverage overhead
    start_time = time.time()
    
    # Track only specific operations
    with CoverageContext():
        result = critical_business_logic()
    
    end_time = time.time()
    return result, end_time - start_time
```

### 3. Batch Processing Optimization
```python
def process_batch(items):
    for i, item in enumerate(items):
        if i % 10 == 0:  # Track every 10th item
            with CoverageContext():
                process_item(item)
        else:
            process_item(item)  # No coverage overhead
```

## Request Types

### Health Check Request
```json
{
    "path": "/health",
    "httpMethod": "GET"
}
```

### Admin Request
```json
{
    "admin": true,
    "admin_action": "coverage_status"
}
```

### Performance Test Request
```json
{
    "admin": true,
    "admin_action": "performance_test",
    "iterations": 1000,
    "test_type": "cpu"
}
```

### Batch Processing Request
```json
{
    "admin": true,
    "admin_action": "batch_process",
    "items": [1, 2, 3, 4, 5],
    "track_coverage": true
}
```

### Business Request
```json
{
    "operation": "process_data",
    "data": {
        "transform": {"name": "john"},
        "validate": {"id": "123", "name": "John"},
        "aggregate": [1, 2, 3, 4, 5]
    }
}
```

## Environment Variables

- `COVERAGE_S3_BUCKET`: S3 bucket for coverage uploads (required)
- `COVERAGE_S3_PREFIX`: S3 key prefix (optional, default: "coverage/")
- `AWS_REGION`: AWS region (required for health checks)

## Health Check Response

```json
{
    "status": "healthy",
    "coverage_enabled": true,
    "layer_version": "1.0.0",
    "database_connection": {
        "status": "healthy",
        "response_time_ms": 45
    },
    "external_api": {
        "status": "healthy",
        "response_time_ms": 120
    },
    "memory_usage": {
        "rss_mb": 128.5,
        "percent": 15.2
    },
    "environment_variables": {
        "status": "healthy",
        "missing_variables": []
    },
    "overall_status": "healthy"
}
```

## Performance Optimization Strategies

### 1. Selective Coverage
- Use context managers for critical paths only
- Skip coverage for initialization/cleanup code
- Track coverage for business logic, skip for utilities

### 2. Batch Processing
- Track coverage for sample items, not all items
- Use coverage for validation logic, skip for data processing
- Balance coverage completeness with performance

### 3. Admin Operations
- Provide coverage-free admin endpoints for performance testing
- Allow toggling coverage for debugging
- Monitor coverage overhead with performance metrics

## Testing Coverage

This example provides extensive code paths for testing:

### Request Routing
- Health check vs admin vs business requests
- Different admin actions
- Error handling for unknown operations

### Business Logic
- Data transformation (string, list, dict)
- Validation rules and error conditions
- Mathematical calculations
- Aggregation operations

### Performance Testing
- CPU-intensive operations
- Memory-intensive operations
- Batch processing patterns

### Health Checks
- Database connection simulation
- External API checks
- Memory usage monitoring
- Environment variable validation

### Error Handling
- Exception catching and logging
- Graceful degradation
- Error response formatting

## Monitoring and Observability

The example includes structured logging and metrics:

```python
# Error logging
print(f"ERROR: {json.dumps(error_details)}")

# Performance metrics
execution_time = end_time - start_time

# Memory monitoring
memory_info = process.memory_info()
```

## Best Practices Demonstrated

1. **Separation of Concerns**: Different handlers for different request types
2. **Performance Optimization**: Selective coverage tracking
3. **Error Handling**: Comprehensive error catching and logging
4. **Health Monitoring**: Multi-layer health checks
5. **Resource Management**: Memory usage tracking
6. **Flexibility**: Support for multiple invocation patterns
7. **Observability**: Structured logging and metrics