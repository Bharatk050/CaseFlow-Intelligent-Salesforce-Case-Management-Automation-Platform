"""Local, content-addressed FAISS evidence retrieval. Never indexes tickets."""
from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path

MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CACHE = Path(__file__).resolve().parents[2] / ".runtime" / "faiss"
_lock = threading.RLock()
_model = None


def model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL, device="cpu", local_files_only=True)
    return _model


def windows(text, encoder):
    ids = encoder.tokenizer.encode(text, add_special_tokens=False)
    return [encoder.tokenizer.decode(ids[i:i + 180]) for i in range(0, len(ids), 150)]


def search(documents, query):
    import faiss
    import numpy as np
    with _lock:
        encoder = model()
        fingerprint = hashlib.sha256(json.dumps([MODEL, "chunks-v1", [(d["path"], d["content"]) for d in documents]], ensure_ascii=False).encode()).hexdigest()
        directory = CACHE / fingerprint
        index_path = directory / "index.faiss"
        metadata_path = directory / "metadata.json"
        if index_path.exists() and metadata_path.exists():
            index = faiss.read_index(str(index_path))
            records = json.loads(metadata_path.read_text(encoding="utf-8"))
        else:
            records = [{"slug": d["slug"], "section_id": s["section_id"], "text": d["title"] + ": " + s["heading"] + "\n" + chunk}
                       for d in documents if d["slug"] not in {"README", "SKILL"}
                       for s in d["sections"] for chunk in windows(s["content"], encoder)]
            if not records:
                return []
            vectors = encoder.encode([r["text"] for r in records], normalize_embeddings=True).astype("float32")
            index = faiss.IndexFlatIP(vectors.shape[1])
            index.add(vectors)
            directory.mkdir(parents=True, exist_ok=True)
            faiss.write_index(index, str(directory / "index.tmp"))
            (directory / "metadata.tmp").write_text(json.dumps(records), encoding="utf-8")
            os.replace(directory / "index.tmp", index_path)
            os.replace(directory / "metadata.tmp", metadata_path)
            (directory / "manifest.json").write_text(json.dumps({"model": MODEL, "fingerprint": fingerprint, "dimension": index.d, "chunks": index.ntotal}), encoding="utf-8")
        parts = windows(query, encoder)
        if not parts:
            return []
        scores, positions = index.search(np.asarray(encoder.encode(parts, normalize_embeddings=True), dtype="float32"), min(12, index.ntotal))
        hits = {}
        for row, offsets in zip(scores, positions):
            for score, offset in zip(row, offsets):
                if offset >= 0 and score >= .30:
                    record = records[int(offset)]
                    key = (record["slug"], record["section_id"])
                    hits[key] = max(hits.get(key, 0), float(score))
        return sorted(hits.items(), key=lambda item: -item[1])
