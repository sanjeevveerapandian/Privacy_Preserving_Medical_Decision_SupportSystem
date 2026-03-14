import faiss
import numpy as np
import os

# Path to the index file
index_path = "/Users/pyt/Downloads/1CP25-754 2/backend/data/faiss.index"

if not os.path.exists(index_path):
    print(f"❌ Error: {index_path} not found.")
else:
    # Load the index
    index = faiss.read_index(index_path)
    
    print("==================================================")
    print("FAISS INDEX INSPECTION")
    print("==================================================")
    print(f"📊 Total Vectors stored: {index.ntotal}")
    print(f"📐 Vector Dimension: {index.d}")
    print(f"⚙️  Index Type: {type(index)}")
    print(f"🔓 Is Trained: {index.is_trained}")
    
    if index.ntotal > 0:
        print("\n🔍 Previewing first vector (first 10 components):")
        # Reconstruct the first vector (only works for Flat indexes)
        try:
            vector = index.reconstruct(0)
            print(vector[:10])
        except Exception as e:
            print(f"Cannot reconstruct vector: {e}")
    
    print("==================================================")
