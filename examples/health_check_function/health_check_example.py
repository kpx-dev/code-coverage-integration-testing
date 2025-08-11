"""
Lambda function example with health check endpoint using coverage layer
"""
import json
from coverage_wrapper import coverage_handler
from coverage_wrapper.health_check import health_check_handler


@coverage_handler
def lambda_handler(event, context):
    """
    Lambda handler with health check endpoint and coverage tracking
    Demonstrates proper routing for API Gateway events
    """
    # Handle API Gateway events
    if 'httpMethod' in event and 'path' in event:
        return handle_api_gateway_event(event, context)
    
    # Handle direct invocation events
    if event.get('action') == 'health_check':
        return handle_health_check(event, context)
    
    # Regular business logic
    return handle_business_logic(event, context)


def handle_api_gateway_event(event, context):
    """Handle API Gateway events with proper routing"""
    method = event['httpMethod']
    path = event['path']
    
    # Health check endpoint
    if path == '/health' and method == 'GET':
        return handle_health_check(event, context)
    
    # Business logic endpoints
    if path == '/api/process' and method == 'POST':
        return handle_business_logic(event, context)
    
    # Default 404 response
    return {
        'statusCode': 404,
        'headers': {
            'Content-Type': 'application/json'
        },
        'body': json.dumps({
            'error': 'Not Found',
            'message': f'Path {path} with method {method} not found'
        })
    }


def handle_health_check(event, context):
    """Handle health check requests"""
    try:
        health_status = health_check_handler()
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps(health_status)
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'status': 'unhealthy',
                'error': str(e)
            })
        }


def handle_business_logic(event, context):
    """Handle regular business logic"""
    # Sample business logic with multiple code paths
    operation = event.get('operation', 'default')
    
    if operation == 'add':
        result = add_numbers(event.get('a', 0), event.get('b', 0))
    elif operation == 'multiply':
        result = multiply_numbers(event.get('a', 1), event.get('b', 1))
    else:
        result = {'message': 'Default operation executed'}
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'operation': operation,
            'result': result,
            'function_name': context.function_name,
            'request_id': context.aws_request_id
        })
    }


def add_numbers(a, b):
    """Add two numbers"""
    return {'sum': a + b}


def multiply_numbers(a, b):
    """Multiply two numbers"""
    return {'product': a * b}