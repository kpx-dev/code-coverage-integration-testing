"""
Advanced Lambda function example demonstrating multiple coverage layer features
"""
import json
import os
import time
from typing import Dict, Any, Optional
from coverage_wrapper import coverage_handler, CoverageContext
from coverage_wrapper.health_check import health_check_handler, get_coverage_status


@coverage_handler
def lambda_handler(event, context):
    """
    Advanced Lambda handler demonstrating multiple coverage layer features:
    - Decorator usage for automatic coverage
    - Health check integration
    - Error handling with coverage
    - Performance monitoring
    """
    try:
        # Route based on event type
        if is_health_check_request(event):
            return handle_health_check_request(event, context)
        elif is_admin_request(event):
            return handle_admin_request(event, context)
        else:
            return handle_business_request(event, context)
            
    except Exception as e:
        # Error handling with coverage still active
        return handle_error(e, event, context)


def is_health_check_request(event: Dict[str, Any]) -> bool:
    """Check if this is a health check request"""
    return (
        event.get('path') == '/health' or
        event.get('action') == 'health_check' or
        event.get('httpMethod') == 'GET' and '/health' in event.get('path', '')
    )


def is_admin_request(event: Dict[str, Any]) -> bool:
    """Check if this is an admin request"""
    return (
        event.get('path', '').startswith('/admin') or
        event.get('admin', False) or
        'admin' in event.get('headers', {}).get('x-request-type', '')
    )


def handle_health_check_request(event: Dict[str, Any], context) -> Dict[str, Any]:
    """Handle health check requests with detailed status"""
    try:
        # Get basic health status
        health_status = health_check_handler()
        
        # Add additional application-specific health checks
        app_health = perform_application_health_checks()
        health_status.update(app_health)
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(health_status)
        }
        
    except Exception as e:
        return {
            'statusCode': 503,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': time.time()
            })
        }


def handle_admin_request(event: Dict[str, Any], context) -> Dict[str, Any]:
    """Handle admin requests with manual coverage control"""
    admin_action = event.get('admin_action', 'status')
    
    if admin_action == 'coverage_status':
        # Get coverage status without additional tracking
        coverage_status = get_coverage_status()
        return create_response(200, {'coverage_status': coverage_status})
    
    elif admin_action == 'performance_test':
        # Use manual coverage control for performance testing
        return handle_performance_test(event, context)
    
    elif admin_action == 'batch_process':
        # Process multiple items with selective coverage
        return handle_batch_processing(event, context)
    
    else:
        return create_response(400, {'error': f'Unknown admin action: {admin_action}'})


def handle_business_request(event: Dict[str, Any], context) -> Dict[str, Any]:
    """Handle regular business requests"""
    operation = event.get('operation', 'default')
    data = event.get('data', {})
    
    # Business logic with full coverage tracking
    if operation == 'process_data':
        result = process_business_data(data)
    elif operation == 'calculate':
        result = perform_calculations(data)
    elif operation == 'validate':
        result = validate_business_rules(data)
    else:
        result = {'message': 'Default operation executed', 'data': data}
    
    return create_response(200, {
        'operation': operation,
        'result': result,
        'metadata': {
            'function_name': context.function_name,
            'request_id': context.aws_request_id,
            'execution_time': time.time()
        }
    })


def handle_performance_test(event: Dict[str, Any], context) -> Dict[str, Any]:
    """Handle performance testing with selective coverage"""
    iterations = event.get('iterations', 100)
    test_type = event.get('test_type', 'cpu')
    
    # Measure performance without coverage overhead
    start_time = time.time()
    
    if test_type == 'cpu':
        # CPU-intensive task without coverage
        result = cpu_intensive_task(iterations)
    else:
        # Use coverage for the actual test logic
        with CoverageContext():
            result = memory_intensive_task(iterations)
    
    end_time = time.time()
    
    return create_response(200, {
        'test_type': test_type,
        'iterations': iterations,
        'execution_time': end_time - start_time,
        'result': result
    })


def handle_batch_processing(event: Dict[str, Any], context) -> Dict[str, Any]:
    """Handle batch processing with selective coverage"""
    items = event.get('items', [])
    track_coverage = event.get('track_coverage', True)
    
    results = []
    
    for i, item in enumerate(items):
        if track_coverage and i % 10 == 0:  # Track coverage for every 10th item
            with CoverageContext():
                result = process_single_item(item)
        else:
            # Process without coverage tracking for performance
            result = process_single_item(item)
        
        results.append(result)
    
    return create_response(200, {
        'processed_count': len(results),
        'results': results[:5],  # Return first 5 results
        'total_items': len(items)
    })


def perform_application_health_checks() -> Dict[str, Any]:
    """Perform application-specific health checks"""
    health_data = {
        'database_connection': check_database_connection(),
        'external_api': check_external_api(),
        'memory_usage': get_memory_usage(),
        'environment_variables': check_environment_variables()
    }
    
    # Overall health status
    all_healthy = all(
        check.get('status') == 'healthy' 
        for check in health_data.values() 
        if isinstance(check, dict)
    )
    
    health_data['overall_status'] = 'healthy' if all_healthy else 'degraded'
    return health_data


def check_database_connection() -> Dict[str, Any]:
    """Simulate database connection check"""
    # In real implementation, this would check actual database
    return {
        'status': 'healthy',
        'response_time_ms': 45,
        'connection_pool': 'available'
    }


def check_external_api() -> Dict[str, Any]:
    """Simulate external API check"""
    # In real implementation, this would check actual external service
    return {
        'status': 'healthy',
        'response_time_ms': 120,
        'last_check': time.time()
    }


def get_memory_usage() -> Dict[str, Any]:
    """Get current memory usage information"""
    import psutil
    process = psutil.Process()
    memory_info = process.memory_info()
    
    return {
        'rss_mb': round(memory_info.rss / 1024 / 1024, 2),
        'vms_mb': round(memory_info.vms / 1024 / 1024, 2),
        'percent': process.memory_percent()
    }


def check_environment_variables() -> Dict[str, Any]:
    """Check required environment variables"""
    required_vars = ['COVERAGE_S3_BUCKET', 'AWS_REGION']
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    return {
        'status': 'healthy' if not missing_vars else 'unhealthy',
        'missing_variables': missing_vars,
        'total_env_vars': len(os.environ)
    }


def process_business_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Process business data with multiple code paths"""
    if not data:
        return {'error': 'No data provided'}
    
    processed_data = {}
    
    # Data transformation
    if 'transform' in data:
        processed_data['transformed'] = transform_data(data['transform'])
    
    # Data validation
    if 'validate' in data:
        processed_data['validation'] = validate_data(data['validate'])
    
    # Data aggregation
    if 'aggregate' in data:
        processed_data['aggregated'] = aggregate_data(data['aggregate'])
    
    return processed_data


def perform_calculations(data: Dict[str, Any]) -> Dict[str, Any]:
    """Perform various calculations"""
    calc_type = data.get('type', 'sum')
    numbers = data.get('numbers', [])
    
    if calc_type == 'sum':
        result = sum(numbers)
    elif calc_type == 'average':
        result = sum(numbers) / len(numbers) if numbers else 0
    elif calc_type == 'max':
        result = max(numbers) if numbers else None
    elif calc_type == 'min':
        result = min(numbers) if numbers else None
    else:
        result = None
    
    return {
        'type': calc_type,
        'input': numbers,
        'result': result
    }


def validate_business_rules(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate data against business rules"""
    errors = []
    warnings = []
    
    # Rule 1: Required fields
    required_fields = ['id', 'name', 'type']
    for field in required_fields:
        if field not in data:
            errors.append(f'Missing required field: {field}')
    
    # Rule 2: Data types
    if 'id' in data and not isinstance(data['id'], (int, str)):
        errors.append('ID must be a string or integer')
    
    # Rule 3: Value ranges
    if 'age' in data and (data['age'] < 0 or data['age'] > 150):
        warnings.append('Age value seems unusual')
    
    return {
        'is_valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings,
        'data': data
    }


def cpu_intensive_task(iterations: int) -> Dict[str, Any]:
    """CPU-intensive task for performance testing"""
    result = 0
    for i in range(iterations):
        result += i ** 2
    
    return {'result': result, 'iterations': iterations}


def memory_intensive_task(iterations: int) -> Dict[str, Any]:
    """Memory-intensive task for performance testing"""
    data = []
    for i in range(iterations):
        data.append({'id': i, 'data': f'item_{i}' * 100})
    
    return {'items_created': len(data), 'memory_used': len(str(data))}


def process_single_item(item: Any) -> Dict[str, Any]:
    """Process a single item in batch processing"""
    return {
        'item': item,
        'processed': True,
        'timestamp': time.time()
    }


def transform_data(data: Any) -> Any:
    """Transform data based on type"""
    if isinstance(data, str):
        return data.upper()
    elif isinstance(data, list):
        return [str(item) for item in data]
    elif isinstance(data, dict):
        return {k.upper(): v for k, v in data.items()}
    else:
        return str(data)


def validate_data(data: Any) -> Dict[str, Any]:
    """Validate data structure"""
    return {
        'type': type(data).__name__,
        'is_empty': not bool(data),
        'size': len(str(data))
    }


def aggregate_data(data: list) -> Dict[str, Any]:
    """Aggregate list data"""
    if not isinstance(data, list):
        return {'error': 'Data must be a list'}
    
    return {
        'count': len(data),
        'sum': sum(x for x in data if isinstance(x, (int, float))),
        'types': list(set(type(x).__name__ for x in data))
    }


def handle_error(error: Exception, event: Dict[str, Any], context) -> Dict[str, Any]:
    """Handle errors with proper logging and response"""
    error_details = {
        'error_type': type(error).__name__,
        'error_message': str(error),
        'function_name': context.function_name,
        'request_id': context.aws_request_id,
        'event_summary': {
            'keys': list(event.keys()),
            'size': len(str(event))
        }
    }
    
    # Log error for monitoring
    print(f"ERROR: {json.dumps(error_details)}")
    
    return create_response(500, error_details)


def create_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Create standardized HTTP response"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'X-Coverage-Layer': 'enabled'
        },
        'body': json.dumps(body, default=str)
    }