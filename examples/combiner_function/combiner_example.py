"""
Lambda function example for combining coverage files using the coverage layer
"""
import json
import os
from datetime import datetime
from coverage_wrapper import coverage_handler
from coverage_wrapper.combiner import combine_coverage_files


@coverage_handler
def lambda_handler(event, context):
    """
    Lambda handler for combining multiple coverage files into a consolidated report
    Supports both scheduled execution and manual invocation
    """
    try:
        # Get configuration from environment variables and event
        bucket_name = os.environ.get('COVERAGE_S3_BUCKET')
        if not bucket_name:
            raise ValueError("COVERAGE_S3_BUCKET environment variable is required")
        
        # Handle different event sources
        if 'source' in event and event['source'] == 'aws.events':
            # CloudWatch Events/EventBridge scheduled execution
            return handle_scheduled_combine(event, context, bucket_name)
        elif 'Records' in event:
            # S3 event trigger
            return handle_s3_trigger(event, context, bucket_name)
        else:
            # Manual invocation
            return handle_manual_combine(event, context, bucket_name)
        
    except Exception as e:
        error_response = {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'function_name': context.function_name,
                'request_id': context.aws_request_id,
                'timestamp': datetime.utcnow().isoformat()
            })
        }
        
        # Log error for monitoring
        print(f"ERROR: Coverage combination failed: {str(e)}")
        return error_response


def handle_scheduled_combine(event, context, bucket_name):
    """Handle scheduled coverage combination (e.g., daily reports)"""
    # Use date-based prefix for scheduled runs
    date_str = datetime.utcnow().strftime('%Y/%m/%d')
    prefix = f"coverage/{date_str}/"
    output_key = f"coverage/combined/daily-report-{date_str}.json"
    
    result = combine_coverage_files(
        bucket_name=bucket_name,
        prefix=prefix,
        output_key=output_key
    )
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Scheduled coverage combination completed',
            'type': 'scheduled',
            'date': date_str,
            'result': result,
            'function_name': context.function_name,
            'request_id': context.aws_request_id
        })
    }


def handle_s3_trigger(event, context, bucket_name):
    """Handle S3 event-triggered coverage combination"""
    results = []
    
    for record in event['Records']:
        if record['eventSource'] == 'aws:s3':
            # Extract S3 object information
            s3_key = record['s3']['object']['key']
            
            # Determine prefix from the uploaded file
            prefix = '/'.join(s3_key.split('/')[:-1]) + '/'
            output_key = f"coverage/combined/triggered-report-{context.aws_request_id}.json"
            
            result = combine_coverage_files(
                bucket_name=bucket_name,
                prefix=prefix,
                output_key=output_key
            )
            
            results.append({
                'trigger_key': s3_key,
                'prefix': prefix,
                'result': result
            })
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'S3-triggered coverage combination completed',
            'type': 's3_trigger',
            'results': results,
            'function_name': context.function_name,
            'request_id': context.aws_request_id
        })
    }


def handle_manual_combine(event, context, bucket_name):
    """Handle manual coverage combination with custom parameters"""
    # Get parameters from event or use defaults
    prefix = event.get('prefix', os.environ.get('COVERAGE_S3_PREFIX', 'coverage/'))
    combined_prefix = event.get('combined_prefix', os.environ.get('COVERAGE_COMBINED_PREFIX', 'coverage/combined/'))
    
    # Generate output key with timestamp
    timestamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
    output_key = event.get('output_key', f"{combined_prefix}manual-report-{timestamp}.json")
    
    # Optional: filter by date range
    date_filter = event.get('date_filter')
    if date_filter:
        prefix = f"{prefix}{date_filter}/"
    
    result = combine_coverage_files(
        bucket_name=bucket_name,
        prefix=prefix,
        output_key=output_key
    )
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Manual coverage combination completed',
            'type': 'manual',
            'parameters': {
                'prefix': prefix,
                'output_key': output_key,
                'date_filter': date_filter
            },
            'result': result,
            'function_name': context.function_name,
            'request_id': context.aws_request_id
        })
    }