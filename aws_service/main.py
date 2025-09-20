from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from . import services
from fastapi import Form
import json

app = FastAPI(
    title="AWS Service API",
    description="Manages documents in DynamoDB/S3 and forwards to RAG",
    version="1.0.0"
)

class DocumentMetadata(BaseModel):
    doc_id: str
    filename: str
    tags: list[str] = []

class QueryRequest(BaseModel):
    doc_id: str
    query: str
@app.post("/aws/documents")
async def create_document(meta: str = Form(...), file: UploadFile = File(...)):
    """
    Receives:
    - meta: JSON string containing doc_id, filename, tags
    - file: uploaded PDF
    """
    try:
        # Convert the JSON string to Pydantic model
        meta_obj = DocumentMetadata(**json.loads(meta))
        return services.create_document(meta_obj, file)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/aws/documents/{doc_id}")
async def get_document(doc_id: str):
    return services.get_document(doc_id)

@app.put("/aws/documents/{doc_id}")
async def update_document(doc_id: str, updates: dict):
    return services.update_document(doc_id, updates)

@app.delete("/aws/documents/{doc_id}")
async def delete_document(doc_id: str):
    return services.delete_document(doc_id)

@app.post("/aws/documents/{doc_id}/index")
async def index_document(doc_id: str):
    return services.forward_to_rag_index(doc_id)

@app.post("/aws/query")
async def query_document(req: QueryRequest):
    return services.forward_to_rag_query(req.doc_id, req.query)

@app.get("/")
async def health():
    return {"status": "AWS Service running"}
