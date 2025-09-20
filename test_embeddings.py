import google.generativeai as genai
import os

# Make sure your .env has GOOGLE_API_KEY set
from dotenv import load_dotenv
load_dotenv()

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

try:
    result = genai.embed_content(
        model="models/embedding-001",
        content="Hello, embeddings!",
        task_type="RETRIEVAL_DOCUMENT"
    )
    print("✅ Embedding length:", len(result["embedding"]))
except Exception as e:
    print("❌ Error:", e)
