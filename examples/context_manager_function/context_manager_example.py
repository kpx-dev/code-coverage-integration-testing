"""
Lambda function example using CoverageContext context manager for manual coverage control
"""
import json
import time
from coverage_wrapper import CoverageContext


def lambda_handler(event, context):
    """
    Lambda handler demonstrating manual coverage control using CoverageContext
    """
    # Some initialization logic outside of coverage tracking
    start_time = time.time()
    request_id = context.aws_request_id
    
    # Use CoverageContext for manual coverage control
    with CoverageContext():
        # Business logic that should be tracked for coverage
        result = process_request(event, context)
        
        # Additional processing with coverage tracking
        if event.get('include_metadata', True):
            result['metadata'] = generate_metadata(event, context)
    
    # Post-processing outside of coverage tracking
    execution_time = time.time() - start_time
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'result': result,
            'execution_time_ms': round(execution_time * 1000, 2),
            'request_id': request_id
        })
    }


def process_request(event, context):
    """
    Main business logic that should be covered by tests
    """
    operation = event.get('operation', 'echo')
    data = event.get('data', {})
    
    if operation == 'echo':
        return echo_data(data)
    elif operation == 'transform':
        return transform_data(data)
    elif operation == 'validate':
        return validate_data(data)
    else:
        raise ValueError(f"Unknown operation: {operation}")


def echo_data(data):
    """Echo the input data back"""
    return {
        'operation': 'echo',
        'input': data,
        'output': data
    }


def transform_data(data):
    """Transform the input data"""
    if isinstance(data, dict):
        # Transform dictionary keys to uppercase
        transformed = {k.upper(): v for k, v in data.items()}
    elif isinstance(data, list):
        # Transform list items to strings
        transformed = [str(item) for item in data]
    elif isinstance(data, str):
        # Transform string to title case
        transformed = data.title()
    else:
        # Default transformation
        transformed = str(data).upper()
    
    return {
        'operation': 'transform',
        'input': data,
        'output': transformed
    }


def validate_data(data):
    """Validate the input data"""
    validation_results = {
        'operation': 'validate',
        'input': data,
        'is_valid': True,
        'errors': []
    }
    
    # Basic validation rules
    if not data:
        validation_results['is_valid'] = False
        validation_results['errors'].append('Data cannot be empty')
    
    if isinstance(data, dict):
        # Validate required fields
        required_fields = ['id', 'name']
        for field in required_fields:
            if field not in data:
                validation_results['is_valid'] = False
                validation_results['errors'].append(f'Missing required field: {field}')
    
    return validation_results


def generate_metadata(event, context):
    """Generate metadata for the response"""
    return {
        'function_name': context.function_name,
        'function_version': context.function_version,
        'memory_limit': context.memory_limit_in_mb,
        'remaining_time': context.get_remaining_time_in_millis(),
        'event_source': event.get('source', 'unknown'),
        'timestamp': time.time()
    }