#!/bin/bash

# Create DynamoDB tables
echo "Creating DynamoDB tables..."

# Documents metadata table
awslocal dynamodb create-table \
    --table-name DocumentsMetadata \
    --attribute-definitions \
        AttributeName=doc_id,AttributeType=S \
    --key-schema \
        AttributeName=doc_id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST

# Agent metrics table
awslocal dynamodb create-table \
    --table-name AgentMetrics \
    --attribute-definitions \
        AttributeName=run_id,AttributeType=S \
        AttributeName=timestamp,AttributeType=S \
    --key-schema \
        AttributeName=run_id,KeyType=HASH \
        AttributeName=timestamp,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST

# Create S3 bucket
echo "Creating S3 bucket..."
awslocal s3 mb s3://my-pdf-storage

# Enable versioning on the bucket
awslocal s3api put-bucket-versioning \
    --bucket my-pdf-storage \
    --versioning-configuration Status=Enabled

# Create Lambda function
echo "Creating Lambda function..."
cd /docker-entrypoint-initaws.d/metrics_lambda

# Create Lambda function
awslocal lambda create-function \
    --function-name AgentMetricsLogger \
    --runtime python3.11 \
    --handler lambda_function.lambda_handler \
    --role arn:aws:iam::000000000000:role/lambda-role \
    --zip-file fileb://function.zip

# Create Lambda permission for API Gateway
awslocal lambda add-permission \
    --function-name AgentMetricsLogger \
    --statement-id AllowAPIGateway \
    --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com

echo "LocalStack initialization complete!"