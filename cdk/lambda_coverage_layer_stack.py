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