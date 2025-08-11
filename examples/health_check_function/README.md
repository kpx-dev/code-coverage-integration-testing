# Health Check Function Example

This example demonstrates implementing health check endpoints with proper routing and coverage tracking.

## Features

- Health check endpoint integration
- API Gateway event routing
- Direct invocation support
- Business logic with multiple operations
- Proper HTTP response formatting

## Usage

### API Gateway Integration

Deploy this function behind API Gateway with the following routes:
- `GET /health` - Health check endpoint
- `POST /api/process` - Business logic endpoint

### Direct Invocation

```json
{
    "action": "health_check"
}
```

## Environment Variables

- `COVERAGE_S3_BUCKET`: S3 bucket for coverage uploads (required)
- `COVERAGE_S3_PREFIX`: S3 key prefix (optional, default: "coverage/")

## Health Check Response

```json
{
    "status": "healthy",
    "coverage_enabled": true,
    "layer_version": "1.0.0",
    "s3_config": {
        "bucket": "my-coverage-bucket",
        "prefix": "coverage/"
    },
    "timestamp": "2024-01-15T10:30:00Z"
}
```

## Business Logic Examples

### Addition Operation
```json
{
    "httpMethod": "POST",
    "path": "/api/process",
    "body": "{\"operation\": \"add\", \"a\": 5, \"b\": 3}"
}
```

### Multiplication Operation
```json
{
    "httpMethod": "POST",
    "path": "/api/process",
    "body": "{\"operation\": \"multiply\", \"a\": 4, \"b\": 7}"
}
```

## Testing Coverage

This example provides multiple code paths:
- Health check vs business logic routing
- Different mathematical operations
- Error handling for unknown paths
- API Gateway vs direct invocation handling