from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict
from pydantic import BaseModel
import os
from uuid import uuid4
import datetime
from PyPDF2 import PdfReader

app = FastAPI(title="PDF Service")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Storage configuration
STORAGE_PATH = "./storage/pdfs"
os.makedirs(STORAGE_PATH, exist_ok=True)

# In-memory storage for document metadata
documents: Dict[str, Dict] = {}

class DocumentMetadata(BaseModel):
    doc_id: str
    filename: str
    upload_timestamp: str
    text_content: Optional[str] = None
    page_count: Optional[int] = None
    file_size: Optional[int] = None

@app.post("/pdf/upload")
async def upload_pdf(files: List[UploadFile] = File(...)):
    results = []
    for file in files:
        try:
            if not file.filename.endswith('.pdf'):
                raise HTTPException(status_code=400, detail="Only PDF files are allowed")
            
            doc_id = str(uuid4())
            timestamp = datetime.datetime.utcnow().isoformat()
            
            # Save file
            file_path = os.path.join(STORAGE_PATH, f"{doc_id}.pdf")
            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)
            
            # Extract text and metadata
            with open(file_path, "rb") as f:
                pdf = PdfReader(f)
                text_content = ""
                for page in pdf.pages:
                    text_content += page.extract_text() or ""
                
            doc_metadata = DocumentMetadata(
                doc_id=doc_id,
                filename=file.filename,
                upload_timestamp=timestamp,
                text_content=text_content,
                page_count=len(pdf.pages),
                file_size=len(content)
            )
            documents[doc_id] = doc_metadata.dict()
            results.append(doc_metadata)
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error processing file {file.filename}: {str(e)}")
    
    return results

@app.get("/pdf/documents/{doc_id}")
async def get_document(doc_id: str):
    if doc_id not in documents:
        raise HTTPException(status_code=404, detail="Document not found")
    return documents[doc_id]

@app.get("/pdf/documents")
async def list_documents(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page")
):
    total = len(documents)
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    
    items = list(documents.values())[start_idx:end_idx]
    
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "items": items,
        "total_pages": (total + limit - 1) // limit
    }