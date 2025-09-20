import os, time, random, json, hashlib
from uuid import uuid4
from datetime import datetime
import requests
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from dotenv import load_dotenv
import google.generativeai as genai
from pinecone import Pinecone
from langchain_text_splitters import RecursiveCharacterTextSplitter

dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path=dotenv_path)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or GEMINI_API_KEY
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX = os.getenv("PINECONE_INDEX")
METRICS_LAMBDA_URL = os.getenv("METRICS_LAMBDA_URL")
AGENT_NAME = os.getenv("AGENT_NAME", "RAGQueryAgent")

# Gemini model configuration
GEMINI_GEN_MODEL = os.getenv("GEMINI_GEN_MODEL", "gemini-1.5-flash")
GEMINI_EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "models/text-embedding-004")

PINECONE_DIM = int(os.getenv("PINECONE_DIM", "768"))

genai.configure(api_key=GOOGLE_API_KEY)

# Decide backend: use in-memory fallback when env is missing to avoid 500s during local testing
USE_LOCAL = not (GOOGLE_API_KEY and PINECONE_API_KEY and PINECONE_INDEX)

if USE_LOCAL:
    # Minimal in-memory vector index to support local/dev without external services
    class _Match:
        def __init__(self, metadata: Dict[str, Any], score: float):
            self.metadata = metadata
            self.score = score

    class _QueryResponse:
        def __init__(self, matches: List["_Match"]):
            self.matches = matches

    class LocalIndex:
        def __init__(self):
            self._vectors: List[Dict[str, Any]] = []

        def upsert(self, vectors: List[Dict[str, Any]]):
            self._vectors.extend(vectors)

        def _cosine(self, a: List[float], b: List[float]) -> float:
            if not a or not b or len(a) != len(b):
                return 0.0
            dot = sum(x*y for x, y in zip(a, b))
            na = (sum(x*x for x in a) ** 0.5) or 1.0
            nb = (sum(x*x for x in b) ** 0.5) or 1.0
            return dot / (na * nb)

        def query(self, vector: List[float], top_k: int = 3, include_metadata: bool = True, filter: Optional[Dict[str, Any]] = None):
            results: List["_Match"] = []
            for v in self._vectors:
                md = v.get("metadata", {})
                if filter:
                    pdf_filter = filter.get("pdf_id")
                    if isinstance(pdf_filter, dict):
                        if "$eq" in pdf_filter and md.get("pdf_id") != pdf_filter["$eq"]:
                            continue
                        if "$in" in pdf_filter and md.get("pdf_id") not in pdf_filter["$in"]:
                            continue
                score = self._cosine(vector, v.get("values", []))
                results.append(_Match(metadata=md, score=score))
            results.sort(key=lambda m: m.score, reverse=True)
            return _QueryResponse(matches=results[:top_k])

    index = LocalIndex()
else:
    pc = Pinecone(api_key=PINECONE_API_KEY)
    index = pc.Index(PINECONE_INDEX)

# Target embedding dimension: ensure consistency between embeddings and index
# Gemini embedding-001 commonly returns 768-d vectors; when Pinecone is active, use PINECONE_DIM (default 768).
# In local fallback mode (no external services), we can use a lighter 128-d vector.
TARGET_EMBED_DIM = (PINECONE_DIM if not USE_LOCAL else 128)

class QueryMetrics(BaseModel):
    run_id: str
    agent_name: str
    tokens_consumed: int
    tokens_generated: int
    response_time_ms: int
    confidence_score: float
    status: str = "completed"
    timestamp: str

def submit_metrics(metrics: QueryMetrics):
    """Submit metrics to Lambda function"""
    try:
        response = requests.post(
            METRICS_LAMBDA_URL,
            json=metrics.dict(),
            timeout=5
        )
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Error submitting metrics: {str(e)}")
        return False

def calculate_confidence_score(context_similarity: float, answer_length: int) -> float:
    """Calculate confidence score based on context similarity and answer completeness"""
    # Base confidence from context similarity (0-1)
    base_confidence = context_similarity
    
    # Adjust based on answer length (penalize very short or very long answers)
    length_factor = 1.0
    if answer_length < 50:  # Too short
        length_factor = answer_length / 50
    elif answer_length > 1000:  # Too long
        length_factor = 1000 / answer_length
        
    return min(base_confidence * length_factor, 1.0)

# ------------------------------
# Embeddings (real or local fallback)
# ------------------------------
def _cheap_embed(content: str, dim: int = TARGET_EMBED_DIM) -> List[float]:
    """
    Deterministic lightweight embedding for local/dev mode without external APIs.
    The dimension defaults to TARGET_EMBED_DIM to match the active index backend.
    """
    try:
        data = hashlib.sha256(content.encode("utf-8")).digest()
    except Exception:
        data = bytes([42]) * 32
    arr: List[float] = []
    for i in range(dim):
        b = data[i % len(data)]
        arr.append((b + (i * 31 % 256)) / 255.0)
    # L2 normalize
    norm = (sum(v*v for v in arr) ** 0.5) or 1.0
    return [v / norm for v in arr]

def embed_with_retry(content, retries=3, delay=5):
    # Use local embedding when GOOGLE_API_KEY is not set
    if not GOOGLE_API_KEY:
        return _cheap_embed(content)
    for attempt in range(retries):
        try:
            response = genai.embed_content(
                model=GEMINI_EMBED_MODEL,
                content=content,
                task_type="RETRIEVAL_DOCUMENT",
            )
            return response["embedding"]
        except Exception as e:
            if "429" in str(e):
                time.sleep(delay * (attempt + 1) + random.uniform(0, 2))
            else:
                # fall back to local embedding on hard error
                return _cheap_embed(content)
    return _cheap_embed(content)


def _ensure_dim(vec: List[float], dim: int) -> List[float]:
    """
    Ensure the vector matches the target dimension by truncating or padding with zeros.
    Safeguards against embedding/index dimension mismatch (e.g., Pinecone expects 768).
    """
    try:
        if not isinstance(vec, (list, tuple)):
            return _cheap_embed(str(vec), dim=dim)
        v = list(vec)
        if len(v) == dim:
            return v
        if len(v) > dim:
            return v[:dim]
        # pad with zeros
        return v + [0.0] * (dim - len(v))
    except Exception:
        # last-resort: generate a deterministic local vector of the right size
        return _cheap_embed("fallback", dim=dim)


def process_and_embed(text: str, pdf_id: str) -> bool:
    """
    Split text into chunks, embed, and upsert into Pinecone under the given pdf_id.
    Returns True on success, raises Exception on failure.
    """
    try:
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        chunks = splitter.split_text(text)

        vectors = []
        for i, chunk in enumerate(chunks):
            emb = embed_with_retry(chunk)
            # Fallback to local embedding if external embedding fails
            if not emb:
                emb = _cheap_embed(chunk, dim=TARGET_EMBED_DIM)
            # Ensure vector matches index dimension (pad/truncate as needed)
            emb = _ensure_dim(emb, TARGET_EMBED_DIM)
            vectors.append({
                "id": f"{pdf_id}-{i}",
                "values": emb,
                "metadata": {"text": chunk, "pdf_id": pdf_id}
            })

        if not vectors:
            raise Exception(f"No vectors generated for document {pdf_id}")

        # Upsert vectors to Pinecone
        index.upsert(vectors=vectors)
        return True
    except Exception as e:
        raise Exception(f"Error processing document {pdf_id}: {str(e)}")

async def query_documents(doc_ids: List[str], question: str) -> Dict[str, Any]:
    start_time = time.time()
    run_id = str(uuid4())
    tokens_consumed = 0
    tokens_generated = 0
    max_similarity = 0.0
    
    try:
        # Generate question embedding
        question_embedding = embed_with_retry(question)
        if not question_embedding:
            raise Exception("Failed to generate question embedding")
        # Ensure query vector matches index dimension
        question_embedding = _ensure_dim(question_embedding, TARGET_EMBED_DIM)
            
        # Query Pinecone
        query_response = index.query(
            vector=question_embedding,
            filter={"pdf_id": {"$in": doc_ids}},
            top_k=5,
            include_metadata=True
        )
        
        # Extract relevant contexts
        contexts = []
        for match in query_response.matches:
            contexts.append(match.metadata["text"])
            max_similarity = max(max_similarity, match.score)
            
        if not contexts:
            raise Exception("No relevant contexts found")
            
        # Generate answer using Gemini
        model = genai.GenerativeModel(GEMINI_GEN_MODEL)
        prompt = f"""Based on the following contexts, answer the question. If the answer cannot be found in the contexts, say so.

Contexts:
{' '.join(contexts)}

Question: {question}"""

        response = model.generate_content(prompt)
        answer = response.text
        
        # Calculate metrics
        tokens_consumed = len(prompt.split())  # Rough estimate
        tokens_generated = len(answer.split())
        response_time_ms = int((time.time() - start_time) * 1000)
        confidence_score = calculate_confidence_score(max_similarity, len(answer))
        
        # Submit metrics
        metrics = QueryMetrics(
            run_id=run_id,
            agent_name=AGENT_NAME,
            tokens_consumed=tokens_consumed,
            tokens_generated=tokens_generated,
            response_time_ms=response_time_ms,
            confidence_score=confidence_score,
            timestamp=datetime.utcnow().isoformat()
        )
        submit_metrics(metrics)
        
        return {
            "run_id": run_id,
            "answer": answer,
            "tokens_consumed": tokens_consumed,
            "tokens_generated": tokens_generated,
            "response_time_ms": response_time_ms,
            "confidence_score": confidence_score
        }
        
    except Exception as e:
        error_metrics = QueryMetrics(
            run_id=run_id,
            agent_name=AGENT_NAME,
            tokens_consumed=tokens_consumed,
            tokens_generated=tokens_generated,
            response_time_ms=int((time.time() - start_time) * 1000),
            confidence_score=0.0,
            status="failed",
            timestamp=datetime.utcnow().isoformat()
        )
        submit_metrics(error_metrics)
        raise Exception(f"Error processing query: {str(e)}")



# ------------------------------
# Process query
# ------------------------------
def process_query(query: str, pdf_id: str) -> Dict[str, Any]:
    """Perform RAG query for a specific pdf_id and return enriched response."""
    start_time = time.time()
    try:
        # 1. Embed the query
        query_emb = embed_with_retry(query)
        if not query_emb:
            return {"error": "Embedding failed"}
        # Ensure query vector matches index dimension
        query_emb = _ensure_dim(query_emb, TARGET_EMBED_DIM)

        # 2. Search in Pinecone limited to this PDF
        results = index.query(
            vector=query_emb,
            top_k=3,
            include_metadata=True,
            filter={"pdf_id": {"$eq": pdf_id}}
        )

        matches = getattr(results, "matches", []) or []
        contexts = [getattr(m, "metadata", {}).get("text", "") for m in matches]
        confidence = 0.0
        if matches:
            confidence = sum(getattr(m, "score", 0.0) for m in matches) / len(matches)

        context_text = "\n\n".join(contexts) if contexts else "No relevant context found."

        # 3. Ask Gemini with basic retry on rate limit
        if not GOOGLE_API_KEY:
            # Local fallback: return concatenated contexts as the answer without external LLM
            elapsed = int((time.time() - start_time) * 1000)
            answer_text = context_text
            return {
                "answer": answer_text,
                "confidence_score": round(confidence, 3),
                "tokens_consumed": 0,
                "tokens_generated": len(answer_text.split()) if answer_text else 0,
                "response_time_ms": elapsed
            }

        model = genai.GenerativeModel(GEMINI_GEN_MODEL)

        def generate_with_retry(prompt: str, retries: int = 3, delay: int = 5):
            last_err = None
            for attempt in range(retries):
                try:
                    return model.generate_content(prompt)
                except Exception as e:
                    msg = str(e)
                    last_err = e
                    if "429" in msg or "rate" in msg.lower():
                        time.sleep(delay * (attempt + 1) + random.uniform(0, 2))
                        continue
                    raise
            raise last_err

        prompt = f"Context:\n{context_text}\n\nQuestion: {query}"
        response = generate_with_retry(prompt)
        elapsed = int((time.time() - start_time) * 1000)

        usage = getattr(response, "usage_metadata", {})
        tokens_consumed = usage.get("prompt_token_count", 0)
        tokens_generated = usage.get("candidates_token_count", 0)

        return {
            "answer": getattr(response, "text", ""),
            "confidence_score": round(confidence, 3),
            "tokens_consumed": tokens_consumed,
            "tokens_generated": tokens_generated,
            "response_time_ms": elapsed
        }

    except Exception as e:
        return {"error": str(e)}
