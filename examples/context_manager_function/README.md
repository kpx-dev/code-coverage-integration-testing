# Context Manager Function Example

This example demonstrates manual coverage control using the `CoverageContext` context manager.

## Features

- Manual coverage control with context manager
- Selective coverage tracking
- Multiple operation types
- Execution time measurement outside coverage

## Usage

```python
from coverage_wrapper import CoverageContext

def lambda_handler(event, context):
    # Code outside coverage tracking
    with CoverageContext():
        # Code with coverage tracking
        result = process_request(event, context)
    # More code outside coverage tracking
    return response
```

## When to Use Context Manager

Use the context manager when you need:
- Fine-grained control over what code is tracked
- To exclude initialization or cleanup code from coverage
- To measure performance impact of coverage tracking
- To selectively track only business logic

## Environment Variables

- `COVERAGE_S3_BUCKET`: S3 bucket for coverage uploads (required)
- `COVERAGE_S3_PREFIX`: S3 key prefix (optional, default: "coverage/")

## Example Events

### Echo Operation
```json
{
    "operation": "echo",
    "data": {"key": "value"},
    "include_metadata": true
}
```

### Transform Operation
```json
{
    "operation": "transform",
    "data": {"name": "john", "age": 30}
}
```

### Validate Operation
```json
{
    "operation": "validate",
    "data": {"id": "123", "name": "John Doe"}
}
```

## Testing Coverage

This example includes multiple code paths for testing:
- Different operation types (echo, transform, validate)
- Data type handling (dict, list, string)
- Validation rules and error conditions
- Metadata generation