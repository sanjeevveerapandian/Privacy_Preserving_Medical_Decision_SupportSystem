import os
import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

INDEX_FILE = os.path.join(DATA_DIR, "faiss.index")
META_FILE = os.path.join(DATA_DIR, "vector_meta.json")

# Load embedding model
model = SentenceTransformer("all-MiniLM-L6-v2")
DIMENSION = 384  # fixed for this model


def ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)


def load_or_create_index():
    ensure_data_dir()

    if os.path.exists(INDEX_FILE):
        return faiss.read_index(INDEX_FILE)
    else:
        return faiss.IndexFlatL2(DIMENSION)


def load_metadata():
    if not os.path.exists(META_FILE):
        return []
    with open(META_FILE, "r") as f:
        return json.load(f)


def save_metadata(meta):
    with open(META_FILE, "w") as f:
        json.dump(meta, f, indent=2)


index = load_or_create_index()
metadata = load_metadata()


def add_text(text: str, meta: dict):
    embedding = model.encode([text]).astype("float32")
    index.add(embedding)
    metadata.append(meta)

    faiss.write_index(index, INDEX_FILE)
    save_metadata(metadata)


def search_text(query: str, top_k: int = 3):
    query_vec = model.encode([query]).astype("float32")
    distances, indices = index.search(query_vec, top_k)

    results = []
    for idx in indices[0]:
        if idx < len(metadata):
            results.append(metadata[idx])

    return results
