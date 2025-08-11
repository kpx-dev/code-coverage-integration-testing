#!/usr/bin/env python3
"""
CDK App for Lambda Coverage Layer Infrastructure
"""
import aws_cdk as cdk
from lambda_coverage_layer_stack import LambdaCoverageLayerStack

app = cdk.App()

# Deploy the Lambda Coverage Layer stack
LambdaCoverageLayerStack(
    app, 
    "LambdaCoverageLayerStack",
    description="Lambda layer for automated code coverage tracking with S3 storage"
)

app.synth()