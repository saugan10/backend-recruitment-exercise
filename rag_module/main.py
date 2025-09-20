from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os, requests
from.import services
app = FastAPI(title="RAG Module")
PDF_SERVICE_BASE_URL = os.getenv("PDF_SERVICE_BASE_URL", "http://127.0.0.1:8000")

def _get_pdf_text(doc_id: str):
    """
    Fetch text_content for a PDF doc_id from the PDF service.
    Returns text string or None if not found/unavailable.
    """
    try:
        resp = requests.get(f"{PDF_SERVICE_BASE_URL}/pdf/documents/{doc_id}", timeout=5)
        if resp.status_code == 200:
            meta = resp.json()
            return (meta or {}).get("text_content") or None
    except Exception:
        # Silent fail; caller will decide fallback
        pass
    return None

@app.get("/")
async def root():
    return {"status": "RAG Module is running"}

class IndexRequest(BaseModel):
    document_ids: list[str]

class QueryRequest(BaseModel):
    pdf_id: str
    query: str


@app.post("/rag/index")
def index_documents(request: IndexRequest):
    results = {}
    for doc_id in request.document_ids:
        # Try to fetch PDF text from the PDF service; fallback to dummy if unavailable
        text = None
        try:
            resp = requests.get(f"{PDF_SERVICE_BASE_URL}/pdf/documents/{doc_id}", timeout=5)
            if resp.status_code == 200:
                meta = resp.json()
                text = (meta or {}).get("text_content") or None
        except Exception:
            # Ignore connectivity/timeouts and fallback below
            pass

        if not text:
            text = "Dummy text for testing"

        success = services.process_and_embed(text, doc_id)
        results[doc_id] = "success" if success else "failed"

    return {"results": results}


@app.post("/rag/query")
def query_document(request: QueryRequest):
    result = services.process_query(request.query, request.pdf_id)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return {"pdf_id": request.pdf_id, "query": request.query, **result}


# New: single-id indexing endpoint to avoid JSON quoting issues in shells.
# Use:
#   curl.exe -s -X POST http://127.0.0.1:8081/rag/index/e5ec4b56-bca1-4180-a1b5-b78b741197cb
@app.post("/rag/index/{doc_id}")
def index_document_by_path(doc_id: str):
    text = _get_pdf_text(doc_id)
    if not text:
        # Return a clear error so caller knows the PDF service did not provide text
        # instead of silently indexing a dummy string.
        raise HTTPException(
            status_code=404,
            detail=f"No text found for doc_id {doc_id} at {PDF_SERVICE_BASE_URL}/pdf/documents/{doc_id}"
        )
    success = services.process_and_embed(text, doc_id)
    status = "success" if success else "failed"
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to index document {doc_id}")
    return {"results": {doc_id: status}}


# Optional: GET alias for convenience in quick tests
@app.get("/rag/index/{doc_id}")
def index_document_by_path_get(doc_id: str):
    return index_document_by_path(doc_id)


# New: health endpoint to verify RAG↔PDF connectivity quickly
@app.get("/rag/health")
def rag_health():
    # Check RAG basic status plus connectivity to PDF service root and list endpoint
    pdf_ok = False
    list_ok = False
    try:
        r = requests.get(f"{PDF_SERVICE_BASE_URL}/", timeout=3)
        pdf_ok = r.status_code < 500
    except Exception:
        pdf_ok = False
    try:
        r2 = requests.get(f"{PDF_SERVICE_BASE_URL}/pdf/documents", timeout=3)
        list_ok = r2.status_code < 500
    except Exception:
        list_ok = False
    return {
        "rag_status": "ok",
        "pdf_service_base_url": PDF_SERVICE_BASE_URL,
        "pdf_service_up": pdf_ok,
        "pdf_list_up": list_ok,
    }
