"""
CDK Stack for Lambda Coverage Layer Infrastructure
"""
from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_lambda as _lambda,
    aws_s3 as s3,
    aws_iam as iam,
    aws_logs as logs,
)
from constructs import Construct
import os


class LambdaCoverageLayerStack(Stack):
    """CDK Stack for deploying Lambda Coverage Layer infrastructure"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create S3 bucket for coverage storage
        self.coverage_bucket = self._create_coverage_bucket()
        
        # Create the Lambda layer
        self.coverage_layer = self._create_coverage_layer()
        
        # Create IAM role for Lambda functions using the layer
        self.lambda_execution_role = self._create_lambda_execution_role()
        
        # Create example Lambda functions
        self._create_example_functions()
        
        # Create testing infrastructure (optional, controlled by context)
        if self.node.try_get_context("include_testing"):
            self._create_testing_infrastructure()
        
        # Always output the bucket name for easy access
        from aws_cdk import CfnOutput
        CfnOutput(
            self, "CoverageBucketName",
            value=self.coverage_bucket.bucket_name,
            description="S3 bucket for coverage reports"
        )

    def _create_coverage_bucket(self) -> s3.Bucket:
        """Create S3 bucket with proper encryption and lifecycle policies"""
        bucket = s3.Bucket(
            self,
            "CoverageBucket",
            bucket_name=None,  # Let CDK generate unique name
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,  # For development - change for production
            auto_delete_objects=True,  # For development - change for production
        )

        # Add lifecycle policy to clean up old coverage files
        bucket.add_lifecycle_rule(
            id="CoverageFileCleanup",
            prefix="coverage/",
            expiration=Duration.days(30),  # Delete coverage files after 30 days
            noncurrent_version_expiration=Duration.days(7),  # Delete old versions after 7 days
        )

        # Add lifecycle policy for combined reports (keep longer)
        bucket.add_lifecycle_rule(
            id="CombinedReportCleanup", 
            prefix="coverage/combined/",
            expiration=Duration.days(90),  # Keep combined reports for 90 days
        )

        return bucket

    def _create_coverage_layer(self) -> _lambda.LayerVersion:
        """Create Lambda layer with coverage wrapper functionality"""
        layer = _lambda.LayerVersion(
            self,
            "CoverageLayer",
            code=_lambda.Code.from_asset("layer"),  # Points to the layer/ directory
            compatible_runtimes=[
                _lambda.Runtime.PYTHON_3_8,
                _lambda.Runtime.PYTHON_3_9,
                _lambda.Runtime.PYTHON_3_10,
                _lambda.Runtime.PYTHON_3_11,
                _lambda.Runtime.PYTHON_3_12,
            ],
            description="Lambda layer for automated code coverage tracking",
            layer_version_name="lambda-coverage-layer",
        )

        return layer

    def _create_lambda_execution_role(self) -> iam.Role:
        """Create IAM role with necessary permissions for Lambda functions using the coverage layer"""
        role = iam.Role(
            self,
            "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Execution role for Lambda functions using coverage layer",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
        )

        # Add S3 permissions for coverage uploads
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:PutObject",
                    "s3:GetObject", 
                    "s3:ListBucket",
                    "s3:DeleteObject",
                ],
                resources=[
                    self.coverage_bucket.bucket_arn,
                    f"{self.coverage_bucket.bucket_arn}/*",
                ],
            )
        )

        return role

    def _create_example_functions(self) -> None:
        """Create example Lambda functions demonstrating layer usage"""
        
        # Example 1: Simple function with coverage decorator
        simple_function = _lambda.Function(
            self,
            "SimpleCoverageExample",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="simple_example.lambda_handler",
            code=_lambda.Code.from_asset("examples/simple_function"),
            layers=[self.coverage_layer],
            role=self.lambda_execution_role,
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "COVERAGE_S3_BUCKET": self.coverage_bucket.bucket_name,
                "COVERAGE_S3_PREFIX": "coverage/simple/",
            },
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

        # Example 2: Function with health check endpoint
        health_check_function = _lambda.Function(
            self,
            "HealthCheckExample", 
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="health_check_example.lambda_handler",
            code=_lambda.Code.from_asset("examples/health_check_function"),
            layers=[self.coverage_layer],
            role=self.lambda_execution_role,
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "COVERAGE_S3_BUCKET": self.coverage_bucket.bucket_name,
                "COVERAGE_S3_PREFIX": "coverage/health/",
            },
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

        # Example 3: Coverage combiner function
        combiner_function = _lambda.Function(
            self,
            "CoverageCombiner",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="combiner_example.lambda_handler", 
            code=_lambda.Code.from_asset("examples/combiner_function"),
            layers=[self.coverage_layer],
            role=self.lambda_execution_role,
            timeout=Duration.minutes(5),  # Longer timeout for combining operations
            memory_size=512,  # More memory for processing multiple files
            environment={
                "COVERAGE_S3_BUCKET": self.coverage_bucket.bucket_name,
                "COVERAGE_S3_PREFIX": "coverage/",
                "COVERAGE_COMBINED_PREFIX": "coverage/combined/",
            },
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

    def _create_testing_infrastructure(self) -> None:
        """Create comprehensive testing infrastructure for the coverage layer"""
        from aws_cdk import CfnOutput
        
        # Create the main test Lambda function
        self.test_function = self._create_test_function()

        # Create additional test functions for different scenarios
        self.simple_test_function = self._create_simple_test_function()
        self.error_test_function = self._create_error_test_function()

        # Create outputs for testing
        CfnOutput(
            self, "TestFunctionName",
            value=self.test_function.function_name,
            description="Main test Lambda function name"
        )

        CfnOutput(
            self, "SimpleTestFunctionName", 
            value=self.simple_test_function.function_name,
            description="Simple test Lambda function name"
        )

        CfnOutput(
            self, "ErrorTestFunctionName",
            value=self.error_test_function.function_name,
            description="Error test Lambda function name"
        )

        CfnOutput(
            self, "LoadTestCommand",
            value=f"python load_test.py --bucket {self.coverage_bucket.bucket_name} --functions {self.test_function.function_name},{self.simple_test_function.function_name},{self.error_test_function.function_name}",
            description="Command to run load tests"
        )

    def _create_test_function(self) -> _lambda.Function:
        """Create the main comprehensive test Lambda function"""
        
        function_code = '''
"""
Comprehensive Lambda function for testing coverage layer functionality.
Tests multiple code paths, operations, and error conditions.
"""
import json
import random
import time
from coverage_wrapper import coverage_handler


@coverage_handler
def lambda_handler(event, context):
    """Main Lambda handler with multiple code paths for coverage testing."""
    
    # Get the operation type from the event
    operation = event.get('operation', 'default')
    
    # Different code paths for coverage testing
    if operation == 'add':
        return handle_add_operation(event, context)
    elif operation == 'multiply':
        return handle_multiply_operation(event, context)
    elif operation == 'divide':
        return handle_divide_operation(event, context)
    elif operation == 'random':
        return handle_random_operation(event, context)
    elif operation == 'health':
        return handle_health_check(event, context)
    elif operation == 'complex':
        return handle_complex_operation(event, context)
    elif operation == 'async':
        return handle_async_operation(event, context)
    else:
        return handle_default_operation(event, context)


def handle_add_operation(event, context):
    """Handle addition operation with multiple branches."""
    a = event.get('a', 0)
    b = event.get('b', 0)
    result = a + b
    
    # Multiple conditional branches for coverage
    if result > 100:
        message = "Large result"
        category = "high"
    elif result > 50:
        message = "Medium-large result"
        category = "medium-high"
    elif result > 10:
        message = "Medium result"
        category = "medium"
    elif result > 0:
        message = "Small positive result"
        category = "low"
    elif result == 0:
        message = "Zero result"
        category = "zero"
    else:
        message = "Negative result"
        category = "negative"
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'operation': 'add',
            'inputs': {'a': a, 'b': b},
            'result': result,
            'message': message,
            'category': category,
            'timestamp': context.aws_request_id
        })
    }


def handle_multiply_operation(event, context):
    """Handle multiplication with edge cases."""
    a = event.get('a', 1)
    b = event.get('b', 1)
    result = a * b
    
    # Edge case handling
    if a == 0 or b == 0:
        message = "Zero multiplication"
        special = True
    elif a == 1:
        message = "Identity multiplication (a=1)"
        special = True
    elif b == 1:
        message = "Identity multiplication (b=1)"
        special = True
    elif a == b:
        message = "Square operation"
        special = True
    elif (a < 0) != (b < 0):  # XOR for different signs
        message = "Negative result"
        special = False
    else:
        message = "Standard multiplication"
        special = False
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'operation': 'multiply',
            'inputs': {'a': a, 'b': b},
            'result': result,
            'message': message,
            'special_case': special
        })
    }


def handle_divide_operation(event, context):
    """Handle division with comprehensive error handling."""
    a = event.get('a', 10)
    b = event.get('b', 1)
    
    try:
        if b == 0:
            raise ValueError("Division by zero")
        
        result = a / b
        
        # Check result type and properties
        if result == int(result):
            result = int(result)
            result_type = "integer"
        else:
            result_type = "decimal"
        
        if abs(result) > 1000:
            magnitude = "very_large"
        elif abs(result) > 100:
            magnitude = "large"
        elif abs(result) > 1:
            magnitude = "normal"
        elif abs(result) == 1:
            magnitude = "unity"
        elif abs(result) > 0.1:
            magnitude = "small"
        else:
            magnitude = "very_small"
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'operation': 'divide',
                'inputs': {'a': a, 'b': b},
                'result': result,
                'result_type': result_type,
                'magnitude': magnitude
            })
        }
    
    except ValueError as e:
        return {
            'statusCode': 400,
            'body': json.dumps({
                'operation': 'divide',
                'error': str(e),
                'error_type': 'ValueError',
                'inputs': {'a': a, 'b': b}
            })
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'operation': 'divide',
                'error': str(e),
                'error_type': type(e).__name__,
                'inputs': {'a': a, 'b': b}
            })
        }


def handle_random_operation(event, context):
    """Handle random number generation with statistics."""
    min_val = event.get('min', 1)
    max_val = event.get('max', 100)
    count = event.get('count', 1)
    
    if count < 1:
        count = 1
    elif count > 10:
        count = 10  # Limit for performance
    
    results = []
    for i in range(count):
        num = random.randint(min_val, max_val)
        results.append(num)
    
    # Calculate statistics
    if results:
        avg = sum(results) / len(results)
        min_result = min(results)
        max_result = max(results)
        
        # Categorize average
        range_size = max_val - min_val
        if range_size > 0:
            avg_percentile = (avg - min_val) / range_size
            if avg_percentile < 0.25:
                avg_category = "low_quartile"
            elif avg_percentile < 0.5:
                avg_category = "second_quartile"
            elif avg_percentile < 0.75:
                avg_category = "third_quartile"
            else:
                avg_category = "high_quartile"
        else:
            avg_category = "single_value"
    else:
        avg = min_result = max_result = 0
        avg_category = "no_data"
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'operation': 'random',
            'inputs': {'min': min_val, 'max': max_val, 'count': count},
            'results': results,
            'statistics': {
                'average': avg,
                'min': min_result,
                'max': max_result,
                'avg_category': avg_category
            }
        })
    }


def handle_health_check(event, context):
    """Handle health check with coverage layer status."""
    from coverage_wrapper.health_check import health_check_handler
    
    # Get detailed health status
    health_status = health_check_handler()
    
    # Add additional system info
    additional_info = {
        'event_size': len(json.dumps(event)),
        'context_info': {
            'function_name': context.function_name,
            'function_version': context.function_version,
            'memory_limit': context.memory_limit_in_mb,
            'remaining_time': context.get_remaining_time_in_millis()
        }
    }
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'operation': 'health',
            'health_status': health_status,
            'additional_info': additional_info,
            'message': 'Health check completed'
        })
    }


def handle_complex_operation(event, context):
    """Handle complex operation with nested logic."""
    data = event.get('data', [])
    operation_type = event.get('type', 'sum')
    
    if not isinstance(data, list):
        data = [data] if data is not None else []
    
    # Convert to numbers
    numbers = []
    for item in data:
        try:
            if isinstance(item, (int, float)):
                numbers.append(item)
            else:
                numbers.append(float(item))
        except (ValueError, TypeError):
            continue  # Skip invalid items
    
    if not numbers:
        return {
            'statusCode': 400,
            'body': json.dumps({
                'operation': 'complex',
                'error': 'No valid numbers provided',
                'input_data': data
            })
        }
    
    # Perform operation based on type
    if operation_type == 'sum':
        result = sum(numbers)
        description = "Sum of all numbers"
    elif operation_type == 'product':
        result = 1
        for num in numbers:
            result *= num
        description = "Product of all numbers"
    elif operation_type == 'average':
        result = sum(numbers) / len(numbers)
        description = "Average of all numbers"
    elif operation_type == 'max':
        result = max(numbers)
        description = "Maximum value"
    elif operation_type == 'min':
        result = min(numbers)
        description = "Minimum value"
    else:
        result = len(numbers)
        description = "Count of valid numbers"
    
    # Additional analysis
    analysis = {
        'count': len(numbers),
        'positive_count': len([n for n in numbers if n > 0]),
        'negative_count': len([n for n in numbers if n < 0]),
        'zero_count': len([n for n in numbers if n == 0]),
        'has_decimals': any(n != int(n) for n in numbers if isinstance(n, float))
    }
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'operation': 'complex',
            'type': operation_type,
            'result': result,
            'description': description,
            'analysis': analysis,
            'processed_numbers': numbers
        })
    }


def handle_async_operation(event, context):
    """Simulate async operation with delays."""
    delay = event.get('delay', 0.1)
    steps = event.get('steps', 3)
    
    # Limit parameters for safety
    delay = max(0, min(delay, 2.0))  # 0-2 seconds
    steps = max(1, min(steps, 5))    # 1-5 steps
    
    results = []
    for step in range(steps):
        # Simulate work
        time.sleep(delay)
        
        # Different logic per step
        if step == 0:
            step_result = "initialization"
        elif step == 1:
            step_result = "processing"
        elif step == 2:
            step_result = "validation"
        elif step == 3:
            step_result = "optimization"
        else:
            step_result = "finalization"
        
        results.append({
            'step': step + 1,
            'result': step_result,
            'timestamp': time.time()
        })
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'operation': 'async',
            'total_steps': steps,
            'delay_per_step': delay,
            'results': results,
            'total_time': steps * delay
        })
    }


def handle_default_operation(event, context):
    """Handle default/unknown operations."""
    event_analysis = {
        'keys': list(event.keys()),
        'key_count': len(event.keys()),
        'has_operation': 'operation' in event,
        'event_size': len(json.dumps(event))
    }
    
    # Analyze event structure
    if event_analysis['key_count'] == 0:
        category = "empty_event"
    elif event_analysis['key_count'] == 1:
        category = "single_key"
    elif event_analysis['key_count'] <= 5:
        category = "simple_event"
    else:
        category = "complex_event"
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'operation': 'default',
            'message': 'Default handler - unknown operation',
            'event_analysis': event_analysis,
            'category': category,
            'suggestion': 'Use operation: add, multiply, divide, random, health, complex, or async'
        })
    }


# Utility functions that may or may not be called (for coverage testing)
def utility_function_1(x):
    """Utility function that might be unused."""
    return x * 2 + 1


def utility_function_2(a, b):
    """Another utility function for coverage testing."""
    if a > b:
        return a - b
    elif a < b:
        return b - a
    else:
        return 0


def rarely_used_function(condition):
    """Function called only under specific conditions."""
    if condition == "special":
        return utility_function_1(42)
    elif condition == "rare":
        return utility_function_2(10, 5)
    else:
        return "normal"


def never_called_function():
    """This function should appear as uncovered."""
    return "This should never be called in normal testing"
'''

        return _lambda.Function(
            self, "TestFunction",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=_lambda.Code.from_inline(function_code),
            layers=[self.coverage_layer],
            role=self.lambda_execution_role,
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "COVERAGE_S3_BUCKET": self.coverage_bucket.bucket_name,
                "COVERAGE_DEBUG": "true"
            },
            log_retention=logs.RetentionDays.ONE_WEEK
        )

    def _create_simple_test_function(self) -> _lambda.Function:
        """Create a simple test Lambda function"""
        
        simple_code = '''
"""
Simple Lambda function for basic coverage testing.
"""
import json
from coverage_wrapper import coverage_handler


@coverage_handler
def lambda_handler(event, context):
    """Simple handler with basic operations."""
    
    name = event.get('name', 'World')
    count = event.get('count', 1)
    
    # Simple branching logic
    if count <= 0:
        message = f"Hello {name}! (Invalid count corrected)"
        count = 1
    elif count == 1:
        message = f"Hello {name}!"
    else:
        message = f"Hello {name}! (repeated {count} times)"
    
    # Generate response
    response = {
        'message': message,
        'count': count,
        'name': name
    }
    
    return {
        'statusCode': 200,
        'body': json.dumps(response)
    }


def helper_function(text):
    """Helper function for coverage testing."""
    return text.upper() if text else "EMPTY"
'''

        return _lambda.Function(
            self, "SimpleTestFunction",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=_lambda.Code.from_inline(simple_code),
            layers=[self.coverage_layer],
            role=self.lambda_execution_role,
            timeout=Duration.seconds(10),
            memory_size=128,
            environment={
                "COVERAGE_S3_BUCKET": self.coverage_bucket.bucket_name,
                "COVERAGE_DEBUG": "true"
            },
            log_retention=logs.RetentionDays.ONE_WEEK
        )

    def _create_error_test_function(self) -> _lambda.Function:
        """Create a function that tests error handling"""
        
        error_code = '''
"""
Lambda function for testing error handling and edge cases.
"""
import json
from coverage_wrapper import coverage_handler


@coverage_handler
def lambda_handler(event, context):
    """Handler that can generate various types of errors."""
    
    error_type = event.get('error_type', 'none')
    
    if error_type == 'none':
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'No error requested',
                'available_errors': ['value_error', 'type_error', 'key_error', 'runtime_error']
            })
        }
    elif error_type == 'value_error':
        raise ValueError("This is a test ValueError")
    elif error_type == 'type_error':
        # Intentionally cause a TypeError
        result = "string" + 123
    elif error_type == 'key_error':
        # Intentionally cause a KeyError
        data = {'a': 1}
        return data['nonexistent_key']
    elif error_type == 'runtime_error':
        raise RuntimeError("This is a test RuntimeError")
    elif error_type == 'custom_error':
        raise CustomTestError("This is a custom error")
    else:
        return {
            'statusCode': 400,
            'body': json.dumps({
                'error': f'Unknown error type: {error_type}',
                'available_errors': ['value_error', 'type_error', 'key_error', 'runtime_error', 'custom_error']
            })
        }


class CustomTestError(Exception):
    """Custom exception for testing."""
    pass


def error_prone_function(value):
    """Function that might cause errors."""
    if value is None:
        raise ValueError("Value cannot be None")
    
    if isinstance(value, str):
        return int(value)  # Might raise ValueError
    elif isinstance(value, (int, float)):
        return value / 0 if value == 0 else value  # Might raise ZeroDivisionError
    else:
        raise TypeError(f"Unsupported type: {type(value)}")
'''

        return _lambda.Function(
            self, "ErrorTestFunction",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=_lambda.Code.from_inline(error_code),
            layers=[self.coverage_layer],
            role=self.lambda_execution_role,
            timeout=Duration.seconds(15),
            memory_size=128,
            environment={
                "COVERAGE_S3_BUCKET": self.coverage_bucket.bucket_name,
                "COVERAGE_DEBUG": "true"
            },
            log_retention=logs.RetentionDays.ONE_WEEK
        )