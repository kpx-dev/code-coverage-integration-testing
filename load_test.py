#!/usr/bin/env python3
"""
Comprehensive Load Test Script for Lambda Coverage Layer
Tests multiple Lambda functions and verifies S3 coverage output
Designed to work with CDK-deployed infrastructure
"""

import json
import time
import boto3
import concurrent.futures
from datetime import datetime
import argparse
from typing import List, Dict, Any

class LambdaCoverageLoadTest:
    def __init__(self, function_names: List[str], s3_bucket: str, region='us-east-1'):
        self.function_names = function_names
        self.s3_bucket = s3_bucket
        self.region = region
        self.lambda_client = boto3.client('lambda', region_name=region)
        self.s3_client = boto3.client('s3', region_name=region)
        
    def invoke_lambda(self, function_name: str, payload: Dict[str, Any]):
        """Invoke Lambda function with given payload"""
        try:
            response = self.lambda_client.invoke(
                FunctionName=function_name,
                Payload=json.dumps(payload)
            )
            
            result = json.loads(response['Payload'].read())
            return {
                'success': True,
                'function_name': function_name,
                'payload': payload,
                'response': result,
                'status_code': response['StatusCode']
            }
        except Exception as e:
            return {
                'success': False,
                'function_name': function_name,
                'payload': payload,
                'error': str(e)
            }
    
    def generate_test_payloads(self):
        """Generate comprehensive test payloads for all function types"""
        
        # Main test function payloads
        main_payloads = [
            # Health checks
            {'operation': 'health'},
            
            # Add operations - comprehensive coverage
            {'operation': 'add', 'a': 5, 'b': 3},        # Small result
            {'operation': 'add', 'a': 15, 'b': 20},      # Medium result  
            {'operation': 'add', 'a': 150, 'b': 200},    # Large result
            {'operation': 'add', 'a': -5, 'b': -3},      # Negative result
            {'operation': 'add', 'a': 0, 'b': 0},        # Zero result
            
            # Multiply operations - edge cases
            {'operation': 'multiply', 'a': 0, 'b': 5},   # Zero result
            {'operation': 'multiply', 'a': 1, 'b': 42},  # Identity (a=1)
            {'operation': 'multiply', 'a': 42, 'b': 1},  # Identity (b=1)
            {'operation': 'multiply', 'a': 7, 'b': 7},   # Square
            {'operation': 'multiply', 'a': -3, 'b': 4},  # Negative result
            {'operation': 'multiply', 'a': 7, 'b': 8},   # Positive result
            
            # Divide operations - including errors
            {'operation': 'divide', 'a': 10, 'b': 2},    # Integer result
            {'operation': 'divide', 'a': 10, 'b': 3},    # Decimal result
            {'operation': 'divide', 'a': 10, 'b': 0},    # Division by zero
            {'operation': 'divide', 'a': 1000, 'b': 1},  # Large result
            {'operation': 'divide', 'a': 1, 'b': 10},    # Small result
            
            # Random operations - different configurations
            {'operation': 'random', 'min': 1, 'max': 20, 'count': 1},     # Single low
            {'operation': 'random', 'min': 30, 'max': 60, 'count': 3},    # Multiple medium
            {'operation': 'random', 'min': 80, 'max': 100, 'count': 5},   # Multiple high
            {'operation': 'random', 'min': 50, 'max': 50, 'count': 2},    # Same min/max
            
            # Complex operations
            {'operation': 'complex', 'data': [1, 2, 3, 4, 5], 'type': 'sum'},
            {'operation': 'complex', 'data': [2, 3, 4], 'type': 'product'},
            {'operation': 'complex', 'data': [10, 20, 30], 'type': 'average'},
            {'operation': 'complex', 'data': [-5, 0, 5, 10], 'type': 'max'},
            {'operation': 'complex', 'data': [], 'type': 'sum'},  # Empty data
            
            # Async operations
            {'operation': 'async', 'delay': 0.1, 'steps': 3},
            {'operation': 'async', 'delay': 0.2, 'steps': 5},
            
            # Default/unknown operations
            {'operation': 'unknown'},
            {'operation': 'invalid_op', 'data': 'test'},
            {},  # Empty payload
        ]
        
        # Simple function payloads
        simple_payloads = [
            {'name': 'Alice'},
            {'name': 'Bob', 'count': 1},
            {'name': 'Charlie', 'count': 3},
            {'name': 'Diana', 'count': 0},  # Invalid count
            {'name': 'Eve', 'count': -1},   # Negative count
            {},  # Empty payload
        ]
        
        # Error function payloads
        error_payloads = [
            {'error_type': 'none'},
            {'error_type': 'value_error'},
            {'error_type': 'type_error'},
            {'error_type': 'key_error'},
            {'error_type': 'runtime_error'},
            {'error_type': 'custom_error'},
            {'error_type': 'unknown_error'},
        ]
        
        return {
            'main': main_payloads,
            'simple': simple_payloads,
            'error': error_payloads
        }
    
    def run_single_test(self, function_name: str, payload: Dict[str, Any]):
        """Run a single test invocation"""
        start_time = time.time()
        result = self.invoke_lambda(function_name, payload)
        end_time = time.time()
        
        result['duration'] = end_time - start_time
        result['timestamp'] = datetime.now().isoformat()
        
        return result
    
    def run_load_test(self, num_iterations=3, max_workers=3):
        """Run comprehensive load test across all functions"""
        print(f"Starting comprehensive load test: {num_iterations} iterations with {max_workers} workers")
        print(f"Functions: {', '.join(self.function_names)}")
        print(f"S3 Bucket: {self.s3_bucket}")
        print("-" * 80)
        
        all_payloads = self.generate_test_payloads()
        all_results = []
        
        for iteration in range(num_iterations):
            print(f"\nIteration {iteration + 1}/{num_iterations}")
            iteration_results = []
            
            # Create test tasks for all functions
            test_tasks = []
            
            # Main function tests
            if len(self.function_names) > 0:
                main_function = self.function_names[0]
                for payload in all_payloads['main']:
                    test_tasks.append((main_function, payload, 'main'))
            
            # Simple function tests
            if len(self.function_names) > 1:
                simple_function = self.function_names[1]
                for payload in all_payloads['simple']:
                    test_tasks.append((simple_function, payload, 'simple'))
            
            # Error function tests
            if len(self.function_names) > 2:
                error_function = self.function_names[2]
                for payload in all_payloads['error']:
                    test_tasks.append((error_function, payload, 'error'))
            
            # Execute tests concurrently
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_task = {
                    executor.submit(self.run_single_test, function_name, payload): (function_name, payload, func_type)
                    for function_name, payload, func_type in test_tasks
                }
                
                # Collect results
                for future in concurrent.futures.as_completed(future_to_task):
                    function_name, payload, func_type = future_to_task[future]
                    result = future.result()
                    result['function_type'] = func_type
                    iteration_results.append(result)
                    
                    # Print result summary
                    operation = payload.get('operation', payload.get('name', payload.get('error_type', 'empty')))
                    status = "✓" if result['success'] else "✗"
                    duration = result.get('duration', 0)
                    func_short = function_name.split('-')[-1] if '-' in function_name else function_name[:8]
                    
                    print(f"  {status} {func_short:8} {operation:15} - {duration:.3f}s")
                    
                    if not result['success']:
                        print(f"    Error: {result['error']}")
            
            all_results.extend(iteration_results)
            
            # Wait between iterations
            if iteration < num_iterations - 1:
                print("  Waiting 3 seconds...")
                time.sleep(3)
        
        return all_results
    
    def check_s3_coverage_files(self):
        """Check for coverage files in S3 bucket"""
        print(f"\nChecking S3 bucket '{self.s3_bucket}' for coverage files...")
        
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.s3_bucket,
                Prefix='coverage/'
            )
            
            if 'Contents' not in response:
                print("  No coverage files found in S3")
                return []
            
            coverage_files = []
            for obj in response['Contents']:
                key = obj['Key']
                size = obj['Size']
                modified = obj['LastModified']
                
                coverage_files.append({
                    'key': key,
                    'size': size,
                    'modified': modified
                })
                
                print(f"  ✓ {key} ({size} bytes, {modified})")
            
            return coverage_files
            
        except Exception as e:
            print(f"  Error checking S3: {e}")
            return []
    
    def download_latest_coverage_report(self):
        """Download and display the latest coverage report"""
        try:
            # List coverage files
            response = self.s3_client.list_objects_v2(
                Bucket=self.s3_bucket,
                Prefix='coverage/'
            )
            
            if 'Contents' not in response:
                print("No coverage files to download")
                return
            
            # Find the latest coverage report
            coverage_files = [obj for obj in response['Contents'] 
                            if obj['Key'].endswith('.json')]
            
            if not coverage_files:
                print("No JSON coverage reports found")
                return
            
            # Get the most recent file
            latest_file = max(coverage_files, key=lambda x: x['LastModified'])
            key = latest_file['Key']
            
            print(f"\nDownloading latest coverage report: {key}")
            
            # Download the file
            response = self.s3_client.get_object(Bucket=self.s3_bucket, Key=key)
            content = response['Body'].read().decode('utf-8')
            
            # Parse and display summary
            coverage_data = json.loads(content)
            
            print("\nCoverage Report Summary:")
            print("-" * 40)
            
            if 'totals' in coverage_data:
                totals = coverage_data['totals']
                print(f"Lines Covered: {totals.get('covered_lines', 0)}")
                print(f"Total Lines: {totals.get('num_statements', 0)}")
                print(f"Coverage: {totals.get('percent_covered', 0):.1f}%")
                print(f"Missing Lines: {totals.get('missing_lines', 0)}")
            
            if 'files' in coverage_data:
                print(f"\nFiles Analyzed: {len(coverage_data['files'])}")
                for filename, file_data in coverage_data['files'].items():
                    if 'summary' in file_data:
                        summary = file_data['summary']
                        coverage_pct = summary.get('percent_covered', 0)
                        print(f"  {filename}: {coverage_pct:.1f}%")
            
            # Save locally
            local_filename = f"coverage_report_{int(time.time())}.json"
            with open(local_filename, 'w') as f:
                f.write(content)
            print(f"\nSaved report to: {local_filename}")
            
        except Exception as e:
            print(f"Error downloading coverage report: {e}")
    
    def print_test_summary(self, results):
        """Print comprehensive summary of test results"""
        print("\n" + "=" * 80)
        print("COMPREHENSIVE LOAD TEST SUMMARY")
        print("=" * 80)
        
        total_tests = len(results)
        successful_tests = len([r for r in results if r['success']])
        failed_tests = total_tests - successful_tests
        
        print(f"Total Invocations: {total_tests}")
        print(f"Successful: {successful_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {(successful_tests/total_tests)*100:.1f}%")
        
        if successful_tests > 0:
            durations = [r['duration'] for r in results if r['success']]
            avg_duration = sum(durations) / len(durations)
            min_duration = min(durations)
            max_duration = max(durations)
            
            print(f"\nPerformance Metrics:")
            print(f"  Average Duration: {avg_duration:.3f}s")
            print(f"  Min Duration: {min_duration:.3f}s")
            print(f"  Max Duration: {max_duration:.3f}s")
            print(f"  Total Test Time: {sum(durations):.1f}s")
        
        # Group by function
        functions = {}
        for result in results:
            func_name = result.get('function_name', 'unknown')
            if func_name not in functions:
                functions[func_name] = {'success': 0, 'failed': 0, 'durations': []}
            
            if result['success']:
                functions[func_name]['success'] += 1
                functions[func_name]['durations'].append(result['duration'])
            else:
                functions[func_name]['failed'] += 1
        
        print(f"\nResults by Function:")
        for func_name, stats in functions.items():
            total = stats['success'] + stats['failed']
            success_rate = (stats['success'] / total) * 100 if total > 0 else 0
            avg_duration = sum(stats['durations']) / len(stats['durations']) if stats['durations'] else 0
            func_short = func_name.split('-')[-1] if '-' in func_name else func_name
            print(f"  {func_short:15}: {stats['success']:3}/{total:3} ({success_rate:5.1f}%) - avg: {avg_duration:.3f}s")
        
        # Group by operation/test type
        operations = {}
        for result in results:
            payload = result['payload']
            op = payload.get('operation', payload.get('name', payload.get('error_type', 'empty')))
            if op not in operations:
                operations[op] = {'success': 0, 'failed': 0}
            
            if result['success']:
                operations[op]['success'] += 1
            else:
                operations[op]['failed'] += 1
        
        print(f"\nResults by Operation/Test Type:")
        for op, counts in operations.items():
            total = counts['success'] + counts['failed']
            success_rate = (counts['success'] / total) * 100 if total > 0 else 0
            print(f"  {op:15}: {counts['success']:3}/{total:3} ({success_rate:5.1f}%)")
        
        # Error summary
        if failed_tests > 0:
            print(f"\nError Summary:")
            error_types = {}
            for result in results:
                if not result['success']:
                    error = result.get('error', 'Unknown error')
                    error_type = error.split(':')[0] if ':' in error else error[:50]
                    error_types[error_type] = error_types.get(error_type, 0) + 1
            
            for error_type, count in error_types.items():
                print(f"  {error_type}: {count} occurrences")


def main():
    parser = argparse.ArgumentParser(description='Comprehensive Load Test for Lambda Coverage Layer')
    parser.add_argument('--functions', required=True,
                       help='Comma-separated list of Lambda function names (main,simple,error)')
    parser.add_argument('--bucket', required=True,
                       help='S3 bucket name for coverage reports')
    parser.add_argument('--iterations', type=int, default=2,
                       help='Number of test iterations (default: 2)')
    parser.add_argument('--workers', type=int, default=3,
                       help='Number of concurrent workers (default: 3)')
    parser.add_argument('--region', default='us-east-1',
                       help='AWS region (default: us-east-1)')
    
    args = parser.parse_args()
    
    # Parse function names
    function_names = [name.strip() for name in args.functions.split(',')]
    
    print(f"Lambda Coverage Layer - Comprehensive Load Test")
    print(f"Functions to test: {len(function_names)}")
    for i, name in enumerate(function_names):
        print(f"  {i+1}. {name}")
    print()
    
    # Create load tester
    tester = LambdaCoverageLoadTest(
        function_names=function_names,
        s3_bucket=args.bucket,
        region=args.region
    )
    
    # Run comprehensive load test
    results = tester.run_load_test(
        num_iterations=args.iterations,
        max_workers=args.workers
    )
    
    # Print summary
    tester.print_test_summary(results)
    
    # Check S3 for coverage files
    coverage_files = tester.check_s3_coverage_files()
    
    # Download latest report if available
    if coverage_files:
        print(f"\nFound {len(coverage_files)} coverage files in S3")
        tester.download_latest_coverage_report()
    else:
        print("\nNo coverage files found in S3.")
        print("This might be expected if:")
        print("  1. Functions completed too quickly for coverage to upload")
        print("  2. S3 permissions are not configured correctly")
        print("  3. Coverage layer is not properly attached")
        print("\nCheck CloudWatch logs for more details.")


if __name__ == '__main__':
    main()