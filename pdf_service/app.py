import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from uuid import uuid4
import datetime
from PyPDF2 import PdfReader

# Load environment variables
load_dotenv()
STORAGE_PATH = os.getenv("PDF_STORAGE_PATH", "./storage/pdfs")

# Ensure storage directory exists
os.makedirs(STORAGE_PATH, exist_ok=True)

app = FastAPI()

class DocumentMetadata(BaseModel):
    doc_id: str
    filename: str
    upload_timestamp: str
    text: str

# In-memory storage for simplicity (replace with DB/S3 later)
documents = {}

@app.post("/pdf/upload")
async def upload_pdf(files: list[UploadFile] = File(...)):
    results = []
    for file in files:
        if not file.filename.endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")
        
        doc_id = str(uuid4())
        timestamp = datetime.datetime.utcnow().isoformat()
        
        # Extract text
        pdf_reader = PdfReader(file.file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() or ""
        
        # Store file locally
        file_path = os.path.join(STORAGE_PATH, f"{doc_id}.pdf")
        with open(file_path, "wb") as f:
            f.write(await file.read())
        
        metadata = DocumentMetadata(
            doc_id=doc_id,
            filename=file.filename,
            upload_timestamp=timestamp,
            text=text
        )
        documents[doc_id] = metadata
        results.append(metadata.dict())
    
    return JSONResponse(content={"documents": results}, status_code=201)

@app.get("/pdf/documents/{doc_id}")
async def get_document(doc_id: str):
    if doc_id not in documents:
        raise HTTPException(status_code=404, detail="Document not found")
    return documents[doc_id]

@app.get("/pdf/documents")
async def list_documents(page: int = 1, limit: int = 10):
    if page < 1 or limit < 1:
        raise HTTPException(status_code=400, detail="Invalid pagination parameters")
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    paginated_docs = list(documents.values())[start_idx:end_idx]
    return {"page": page, "limit": limit, "documents": paginated_docs}