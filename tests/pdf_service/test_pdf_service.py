import os
import pytest
from fastapi.testclient import TestClient
from pdf_service.app import app

client = TestClient(app)

def test_upload_pdf():
    with open("sample.pdf", "rb") as f:  # Assume sample.pdf is in the root
        response = client.post("/pdf/upload", files={"files": ("sample.pdf", f, "application/pdf")})
        assert response.status_code == 201
        data = response.json()
        assert "documents" in data
        assert len(data["documents"]) == 1
        assert "doc_id" in data["documents"][0]

def test_get_document_not_found():
    response = client.get("/pdf/documents/invalid_id")
    assert response.status_code == 404