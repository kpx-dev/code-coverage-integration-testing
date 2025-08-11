# Coverage Combiner Function Example

This example demonstrates combining multiple coverage files into consolidated reports with support for different trigger types.

## Features

- Multiple trigger support (scheduled, S3 events, manual)
- Date-based organization
- Flexible output naming
- Comprehensive error handling
- Event source detection

## Usage

### Scheduled Execution (CloudWatch Events)

```json
{
    "source": "aws.events",
    "detail-type": "Scheduled Event"
}
```

### S3 Event Trigger

```json
{
    "Records": [
        {
            "eventSource": "aws:s3",
            "s3": {
                "object": {
                    "key": "coverage/2024/01/15/function-123.coverage"
                }
            }
        }
    ]
}
```

### Manual Invocation

```json
{
    "prefix": "coverage/2024/01/15/",
    "output_key": "coverage/combined/custom-report.json",
    "date_filter": "2024/01/15"
}
```

## Environment Variables

- `COVERAGE_S3_BUCKET`: S3 bucket containing coverage files (required)
- `COVERAGE_S3_PREFIX`: Default prefix for coverage files (optional, default: "coverage/")
- `COVERAGE_COMBINED_PREFIX`: Prefix for combined reports (optional, default: "coverage/combined/")

## Trigger Types

### 1. Scheduled Execution
- Triggered by CloudWatch Events/EventBridge
- Creates daily reports with date-based organization
- Output: `coverage/combined/daily-report-YYYY/MM/DD.json`

### 2. S3 Event Trigger
- Triggered when new coverage files are uploaded
- Processes files from the same prefix as the trigger
- Output: `coverage/combined/triggered-report-{request-id}.json`

### 3. Manual Invocation
- Triggered by direct function invocation
- Supports custom parameters and date filtering
- Output: `coverage/combined/manual-report-{timestamp}.json`

## Response Format

```json
{
    "statusCode": 200,
    "body": {
        "message": "Coverage files combined successfully",
        "type": "scheduled|s3_trigger|manual",
        "result": {
            "files_processed": 5,
            "combined_coverage": 85.2,
            "output_location": "s3://bucket/coverage/combined/report.json"
        },
        "function_name": "coverage-combiner",
        "request_id": "abc-123"
    }
}
```

## CloudWatch Events Rule Example

```json
{
    "Rules": [
        {
            "Name": "DailyCoverageCombiner",
            "ScheduleExpression": "cron(0 2 * * ? *)",
            "State": "ENABLED",
            "Targets": [
                {
                    "Id": "1",
                    "Arn": "arn:aws:lambda:region:account:function:coverage-combiner"
                }
            ]
        }
    ]
}
```

## Testing Coverage

This example includes multiple execution paths:
- Different event source handling
- Date-based file organization
- Error handling and recovery
- Parameter validation and defaults