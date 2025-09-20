from fastapi.testclient import TestClient
from pdf_service.app import app

# Create test client
client = TestClient(app)

# Test upload endpoint
def test_upload():
    with open("sample.pdf", "rb") as f:
        response = client.post(
            "/pdf/upload",
            files={"file": ("test.pdf", f, "application/pdf")}
        )
    print("Upload Response:", response.json())
    assert response.status_code == 200

# Test document retrieval
def test_get_document(doc_id):
    response = client.get(f"/pdf/documents/{doc_id}")
    print("Get Document Response:", response.json())
    assert response.status_code == 200

# Test document listing
def test_list_documents():
    response = client.get("/pdf/documents?page=1&limit=10")
    print("List Documents Response:", response.json())
    assert response.status_code == 200

if __name__ == "__main__":
    test_upload()
    # Get the doc_id from upload response and use it in subsequent tests
    # test_get_document("your_doc_id")
    test_list_documents()