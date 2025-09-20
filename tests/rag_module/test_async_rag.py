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

pytestmark = pytest.mark.asyncio

@pytest.mark.asyncio
async def test_health_check():
    """Tests the root health check endpoint."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/")
        assert response.status_code == 200
        assert response.json() == {"status": "RAG Module is running"}

@pytest.mark.asyncio
@patch('rag_module.services.process_and_embed')
async def test_index_document_success(mock_process_and_embed):
    """
    Tests the /index endpoint for a successful case.
    It mocks the service function to avoid real external calls.
    """
    # Configure the mock to return True, simulating a successful indexing
    mock_process_and_embed.return_value = True

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/rag/index", json={"document_ids": ["test-doc-01"]})

        # Assert that the response is what we expect
        assert response.status_code == 200
        assert response.json()["results"]["test-doc-01"] == "success"
        
        # Assert that our service function was called correctly
        mock_process_and_embed.assert_called_once_with(
            "Dummy text for testing",
            "test-doc-01"
        )

@pytest.mark.asyncio
@patch('rag_module.services.process_query')
async def test_query_document_success(mock_process_query):
    """
    Tests the /query endpoint for a successful case.
    It mocks the service function to provide a predictable answer.
    """
    # Configure the mock to return a sample answer
    mock_answer = {"answer": "The mock answer is that testing is important."}
    mock_process_query.return_value = mock_answer

    test_payload = {
        "pdf_id": "test-doc-01",
        "query": "What is the answer?"
    }

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/rag/query", json=test_payload)

        # Assert that the response is what we expect
        assert response.status_code == 200
        assert "pdf_id" in response.json()
        assert "query" in response.json()

        # Assert that our service function was called correctly
        mock_process_query.assert_called_once_with(
            test_payload["query"],
            test_payload["pdf_id"]
        )

@pytest.mark.asyncio
@patch('rag_module.services.process_and_embed')
async def test_index_document_failure(mock_process_and_embed):
    """
    Tests the /index endpoint for a failure case.
    """
    # Configure the mock to return False, simulating a failure
    mock_process_and_embed.return_value = False

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/rag/index", json={"document_ids": ["fail-doc"]})

        # Assert that the response still returns 200 but with failed status
        assert response.status_code == 200
        assert response.json()["results"]["fail-doc"] == "failed"