import boto3
import os
import requests
import time
from uuid import uuid4
from datetime import datetime
from typing import Dict, Any, Optional, List
from botocore.exceptions import ClientError
from fastapi import HTTPException

# AWS Configuration
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
DYNAMO_TABLE = os.getenv("DYNAMODB_TABLE_DOCUMENTS", "DocumentsMetadata")
S3_BUCKET = os.getenv("S3_BUCKET", "my-pdf-storage")
RAG_BASE_URL = os.getenv("RAG_BASE_URL", "http://rag_module:8001")
METRICS_LAMBDA = os.getenv("METRICS_LAMBDA", "AgentMetricsLogger")

# Initialize AWS clients with error handling
try:
    # Initialize DynamoDB
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    table = dynamodb.Table(DYNAMO_TABLE)
    
    # Initialize S3 with proper configuration
    s3 = boto3.client("s3", region_name=AWS_REGION,
                     config=boto3.Config(
                         retries=dict(
                             max_attempts=3,
                             mode='standard'
                         ),
                         connect_timeout=5,
                         read_timeout=10
                     ))
    
    # Initialize Lambda client
    lambda_client = boto3.client("lambda", region_name=AWS_REGION)
    
except Exception as e:
    print(f"Error initializing AWS clients: {str(e)}")
    raise

def ensure_bucket_exists():
    """Ensure S3 bucket exists and has proper configuration"""
    try:
        s3.head_bucket(Bucket=S3_BUCKET)
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '404':
            # Create bucket if it doesn't exist
            s3.create_bucket(
                Bucket=S3_BUCKET,
                CreateBucketConfiguration={'LocationConstraint': AWS_REGION}
            )
            
            # Enable versioning
            s3.put_bucket_versioning(
                Bucket=S3_BUCKET,
                VersioningConfiguration={'Status': 'Enabled'}
            )
            
            # Enable encryption
            s3.put_bucket_encryption(
                Bucket=S3_BUCKET,
                ServerSideEncryptionConfiguration={
                    'Rules': [
                        {'ApplyServerSideEncryptionByDefault': {'SSEAlgorithm': 'AES256'}}
                    ]
                }
            )
        else:
            raise HTTPException(status_code=500, detail=f"Error accessing S3 bucket: {str(e)}")

# Ensure bucket exists on startup
ensure_bucket_exists()


def create_document(meta: Dict[str, Any], file) -> Dict[str, Any]:
    """Create a new document in S3 and DynamoDB"""
    try:
        # Generate a structured S3 key
        key = f"documents/{meta['doc_id']}/{meta['filename']}"
        
        # Upload to S3 with metadata
        s3.upload_fileobj(
            file.file,
            S3_BUCKET,
            key,
            ExtraArgs={
                'Metadata': {
                    'doc_id': meta['doc_id'],
                    'upload_timestamp': datetime.utcnow().isoformat()
                },
                'ContentType': 'application/pdf'
            }
        )

        # Create DynamoDB item
        item = {
            "doc_id": meta['doc_id'],
            "filename": meta['filename'],
            "s3_key": key,
            "upload_timestamp": datetime.utcnow().isoformat(),
            "tags": meta.get('tags', []),
            "status": "uploaded"
        }
        table.put_item(Item=item)
        
        return {"message": "Document stored successfully", "item": item}
        
    except ClientError as e:
        raise HTTPException(
            status_code=500,
            detail=f"AWS error creating document: {str(e)}"
        )

def get_document(doc_id: str) -> Dict[str, Any]:
    """Retrieve document metadata and generate S3 presigned URL"""
    try:
        # Get item from DynamoDB
        resp = table.get_item(Key={"doc_id": doc_id})
        item = resp.get("Item")
        
        if not item:
            raise HTTPException(status_code=404, detail="Document not found")
            
        # Generate presigned URL if S3 key exists
        if "s3_key" in item:
            url = s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': S3_BUCKET, 'Key': item['s3_key']},
                ExpiresIn=3600
            )
            item['presigned_url'] = url
            
        return item
        
    except ClientError as e:
        raise HTTPException(
            status_code=500,
            detail=f"AWS error retrieving document: {str(e)}"
        )

def update_document(doc_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Update document metadata in DynamoDB"""
    try:
        # Verify document exists
        if not get_document(doc_id):
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Build update expression
        update_attrs = {k: v for k, v in updates.items() if k != 'doc_id'}
        if not update_attrs:
            return {"message": "No updates provided"}
            
        expr = "SET " + ", ".join(f"#{k} = :{k}" for k in update_attrs.keys())
        names = {f"#{k}": k for k in update_attrs.keys()}
        values = {f":{k}": v for k, v in update_attrs.items()}
        
        response = table.update_item(
            Key={"doc_id": doc_id},
            UpdateExpression=expr,
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
            ReturnValues="ALL_NEW"
        )
        
        return {"message": "Document updated", "item": response.get("Attributes", {})}
        
    except ClientError as e:
        raise HTTPException(
            status_code=500,
            detail=f"AWS error updating document: {str(e)}"
        )

def delete_document(doc_id: str) -> Dict[str, Any]:
    """Delete document from S3 and DynamoDB"""
    try:
        # Get item first to check S3 key
        item = get_document(doc_id)
        
        # Delete from S3 if key exists
        if "s3_key" in item:
            s3.delete_object(Bucket=S3_BUCKET, Key=item["s3_key"])
            
        # Delete from DynamoDB
        table.delete_item(Key={"doc_id": doc_id})
        
        return {"message": "Document deleted successfully"}
        
    except ClientError as e:
        raise HTTPException(
            status_code=500,
            detail=f"AWS error deleting document: {str(e)}"
        )

def forward_to_rag_index(doc_id: str) -> Dict[str, Any]:
    """Forward document to RAG module for indexing"""
    try:
        # Verify document exists
        doc = get_document(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
            
        # Call RAG indexing endpoint
        url = f"{RAG_BASE_URL}/rag/index"
        response = requests.post(
            url,
            json={"document_ids": [doc_id]},
            timeout=30
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"RAG indexing failed: {response.text}"
            )
            
        # Update document status in DynamoDB
        update_document(doc_id, {"status": "indexed"})
        
        return response.json()
        
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=503,
            detail=f"Error communicating with RAG service: {str(e)}"
        )

def forward_query(document_ids: List[str], question: str) -> Dict[str, Any]:
    """Forward query to RAG module"""
    try:
        # Verify all documents exist
        for doc_id in document_ids:
            if not get_document(doc_id):
                raise HTTPException(
                    status_code=404,
                    detail=f"Document not found: {doc_id}"
                )
        
        # Call RAG query endpoint
        url = f"{RAG_BASE_URL}/rag/query"
        response = requests.post(
            url,
            json={
                "document_ids": document_ids,
                "question": question
            },
            timeout=30
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"RAG query failed: {response.text}"
            )
            
        return response.json()
        
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=503,
            detail=f"Error communicating with RAG service: {str(e)}"
        )
    doc = get_document(doc_id)
    if not doc:
        return {"error": "Document not found"}
    payload = {"pdf_id": doc_id, "text": "TODO: fetch text from PDF via S3"}
    return requests.post(url, json=payload).json()


def forward_to_rag_query(doc_id, query):
    url = f"{RAG_BASE_URL}/query"
    payload = {"pdf_id": doc_id, "query": query}

    start_time = time.time()
    response = requests.post(url, json=payload)
    elapsed = int((time.time() - start_time) * 1000)  # ms

    result = response.json()

    # --- NEW: Send metrics to Lambda ---
    try:
        metrics_event = {
            "agent_name": "RAGQueryAgent",
            "tokens_consumed": result.get("tokens_consumed", 0),   # if available
            "tokens_generated": result.get("tokens_generated", 0), # if available
            "response_time_ms": elapsed,
            "confidence_score": result.get("confidence_score", 0.0), # if available
            "status": "success" if response.status_code == 200 else "error"
        }

        lambda_client.invoke(
            FunctionName=METRICS_LAMBDA,
            InvocationType="Event",  # async
            Payload=str(metrics_event).encode("utf-8")
        )
    except Exception as e:
        print(f"⚠️ Failed to send metrics to Lambda: {e}")

    return result
