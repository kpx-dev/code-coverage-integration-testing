# Simple Function Example

This example demonstrates the basic usage of the coverage layer with the `@coverage_handler` decorator.

## Features

- Automatic coverage tracking using the decorator
- Simple business logic with conditional paths
- JSON response formatting
- Context information extraction

## Usage

```python
from coverage_wrapper import coverage_handler

@coverage_handler
def lambda_handler(event, context):
    # Your Lambda function code here
    return response
```

## Environment Variables

- `COVERAGE_S3_BUCKET`: S3 bucket for coverage uploads (required)
- `COVERAGE_S3_PREFIX`: S3 key prefix (optional, default: "coverage/")

## Example Event

```json
{
    "name": "John Doe",
    "uppercase": true
}
```

## Example Response

```json
{
    "statusCode": 200,
    "body": "{\"message\": \"HELLO, JOHN DOE!\", \"event_received\": {...}, \"function_name\": \"my-function\", \"request_id\": \"abc-123\"}"
}
```

## Testing Coverage

This example includes conditional logic that can be tested:
- Default name handling
- Uppercase transformation
- Event data processing