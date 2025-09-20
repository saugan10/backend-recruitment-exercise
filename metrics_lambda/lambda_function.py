import json
import boto3
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any
from botocore.exceptions import ClientError

# DynamoDB table name from environment
DYNAMO_TABLE = os.getenv("DYNAMO_TABLE", "AgentMetrics")

# DynamoDB client with proper configuration
dynamodb = boto3.resource(
    "dynamodb",
    config=boto3.Config(
        retries=dict(
            max_attempts=3,
            mode='standard'
        )
    )
)
table = dynamodb.Table(DYNAMO_TABLE)

def create_table_if_not_exists():
    """Create DynamoDB table with proper schema if it doesn't exist"""
    try:
        # Check if table exists
        dynamodb.meta.client.describe_table(TableName=DYNAMO_TABLE)
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            # Create table with proper schema
            table = dynamodb.create_table(
                TableName=DYNAMO_TABLE,
                KeySchema=[
                    {'AttributeName': 'run_id', 'KeyType': 'HASH'},  # Partition key
                    {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}  # Sort key
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'run_id', 'AttributeType': 'S'},
                    {'AttributeName': 'timestamp', 'AttributeType': 'S'}
                ],
                BillingMode='PAY_PER_REQUEST'
            )
            table.wait_until_exists()

def validate_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and process the incoming event"""
    required_fields = ['run_id', 'agent_name', 'tokens_consumed', 'tokens_generated', 
                      'response_time_ms', 'confidence_score']
    
    # Check for required fields
    missing_fields = [field for field in required_fields if field not in event]
    if missing_fields:
        raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
    
    return event

def lambda_handler(event, context):
    """
    Lambda entry point for logging agent metrics into DynamoDB.
    Expected event payload:
    {
        "run_id": "unique-run-id",
        "agent_name": "RAGQueryAgent",
        "tokens_consumed": 142,
        "tokens_generated": 67,
        "response_time_ms": 934,
        "confidence_score": 0.82,
        "status": "completed"  # optional, defaults to "completed"
    }
    """
    try:
        # Ensure table exists
        create_table_if_not_exists()
        
        # Parse event if it's a string
        if isinstance(event, str):
            event = json.loads(event)
            
        # Validate event
        event = validate_event(event)
        
        # Create item with proper schema
        item = {
            "run_id": event["run_id"],
            "timestamp": datetime.now(timezone.utc).isoformat(),  # ISO 8601 UTC
            "agent_name": event["agent_name"],
            "tokens_consumed": int(event["tokens_consumed"]),
            "tokens_generated": int(event["tokens_generated"]),
            "response_time_ms": int(event["response_time_ms"]),
            "confidence_score": Decimal(str(event["confidence_score"])),
            "status": event.get("status", "completed")
        }
        
        # Store metrics in DynamoDB
        table.put_item(Item=item)
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Metrics stored successfully",
                "run_id": event["run_id"]
            })
        }
        
    except ValueError as e:
        return {
            "statusCode": 400,
            "body": json.dumps({
                "error": "Validation error",
                "message": str(e)
            })
        }
    except ClientError as e:
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "Database error",
                "message": str(e)
            })
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "Internal error",
                "message": str(e)
            })
        }

        table.put_item(Item=item)

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Metrics stored successfully", "item": item}, default=str)
        }

    except ClientError as e:
        print(f"❌ DynamoDB error: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
