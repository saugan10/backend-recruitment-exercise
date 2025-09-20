# tests/test_rag_module.py

import pytest
from httpx import AsyncClient
from unittest.mock import patch
import asyncio

# Import the FastAPI app
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))
from rag_module.main import app

client = AsyncClient(base_url="http://test")

@pytest.mark.asyncio
async def test_health_check():
    """Tests the root health check endpoint."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/")
        assert response.status_code == 200
        assert response.json() == {"status": "RAG Module is running"}

@patch('rag_module.services.process_and_embed')
def test_index_document_success(mock_process_and_embed):
    """
    Tests the /index endpoint for a successful case.
    It mocks the service function to avoid real external calls.
    """
    # Configure the mock to return True, simulating a successful indexing
    mock_process_and_embed.return_value = True

    test_payload = {
        "pdf_id": "test-doc-01",
        "text": "This is a sample text for testing."
    }
    response = client.post("/rag/index", json={"document_ids": ["test-doc-01"]})

    # Assert that the response is what we expect
    assert response.status_code == 200
    assert response.json()["results"]["test-doc-01"] == "success"
    
    # Assert that our service function was called correctly
    mock_process_and_embed.assert_called_once_with(
        "Dummy text for testing",
        "test-doc-01"
    )

@patch('rag_module.services.process_query')
def test_query_document_success(mock_process_query):
    """
    Tests the /query endpoint for a successful case.
    It mocks the service function to provide a predictable answer.
    """
    # Configure the mock to return a sample answer
    mock_answer = "The mock answer is that testing is important."
    mock_process_query.return_value = mock_answer

    test_payload = {
        "pdf_id": "test-doc-01",
        "query": "What is the answer?"
    }
    response = client.post("/rag/query", json=test_payload)

    # Assert that the response is what we expect
    assert response.status_code == 200
    assert "pdf_id" in response.json()
    assert "query" in response.json()
    
    # Assert that our service function was called correctly
    mock_process_query.assert_called_once_with(
        pdf_id="test-doc-01",
        query="What is the answer?"
    )

@patch('rag_module.main.services.process_and_embed')
def test_index_document_failure(mock_process_and_embed):
    """
    Tests the /index endpoint for a failure case.
    """
    # Configure the mock to return False, simulating a failure
    mock_process_and_embed.return_value = False

    test_payload = {"pdf_id": "fail-doc", "text": "This will fail."}
    response = client.post("/index", json=test_payload)

    # Assert that the API returns a 500 Internal Server Error
    assert response.status_code == 500
    assert "Failed to process and index the document" in response.json()["detail"]