"""Download the public embedding model once, then build the private local index."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sentence_transformers import SentenceTransformer
from backend.code import vector_store
from backend.code.rag import load_documents

if __name__ == "__main__":
    vector_store._model = SentenceTransformer(vector_store.MODEL, device="cpu")
    documents = load_documents(Path(__file__).parent / "data" / "CA")
    hits = vector_store.search(documents, "Why does Clever sign in to the highest admin role?")
    print(f"Local FAISS index ready: {len(documents)} documents, {len(hits)} smoke-query matches.")
