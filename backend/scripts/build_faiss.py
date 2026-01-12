import json
from pathlib import Path
from typing import List, Dict
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

CHUNKS_PATH = Path("data/processed-data/chunks.jsonl")
INDEX_PATH = Path("data/processed-data/faiss.index")
META_PATH = Path("data/processed-data/meta.json")

# 완전 무료 로컬 임베딩 모델 (성능 좋음, 다만 CPU면 느릴 수 있음)
EMBED_MODEL = "BAAI/bge-m3"

def load_chunks() -> List[Dict]:
    items = []
    with CHUNKS_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            items.append(json.loads(line))
    return items

def main():
    assert CHUNKS_PATH.exists(), f"missing: {CHUNKS_PATH}"

    chunks = load_chunks()
    texts = [c["text"] for c in chunks]
    print(f"[INFO] chunks: {len(chunks)}")

    model = SentenceTransformer(EMBED_MODEL)
    vecs = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=True,
        normalize_embeddings=True
    ).astype("float32")

    dim = vecs.shape[1]
    index = faiss.IndexFlatIP(dim)   # cosine 유사도(정규화된 벡터)
    index.add(vecs)

    faiss.write_index(index, str(INDEX_PATH))
    with META_PATH.open("w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False)

    print(f"[OK] saved: {INDEX_PATH}")
    print(f"[OK] saved: {META_PATH}")

if __name__ == "__main__":
    main()
