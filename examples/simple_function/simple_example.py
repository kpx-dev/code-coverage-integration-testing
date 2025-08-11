"""
Simple Lambda function example using the coverage layer with decorator
"""
import json
from coverage_wrapper import coverage_handler


@coverage_handler
def lambda_handler(event, context):
    """
    Simple Lambda handler demonstrating coverage tracking with decorator
    """
    # Sample business logic
    name = event.get('name', 'World')
    message = f"Hello, {name}!"
    
    # Some conditional logic to generate coverage data
    if event.get('uppercase', False):
        message = message.upper()
    
    # Return response
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': message,
            'event_received': event,
            'function_name': context.function_name,
            'request_id': context.aws_request_id
        })
    }