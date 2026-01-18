"""
Debug script to check the actual distance distribution in vector search.
"""
import json
import sqlite3
import sys
import os
import struct
from typing import List
from openai import OpenAI

try:
    import sqlite_vec
except ImportError:
    print("Error: sqlite_vec not found.")
    sys.exit(1)

DB_FILE = "scripts/memory_test/demo_memory.db"
EMBEDDING_MODEL = "BAAI/bge-m3"
EMBEDDING_DIM = 1024
BASE_URL = "https://api.siliconflow.cn/v1"

def serialize_float32(vector: List[float]) -> bytes:
    return struct.pack(f'{len(vector)}f', *vector)

def main():
    api_key = os.getenv("SILICONFLOW_API_KEY")
    if not api_key:
        api_key = input("Enter SiliconFlow API Key: ").strip()
    
    if not api_key:
        print("API Key required.")
        sys.exit(1)
    
    client = OpenAI(api_key=api_key, base_url=BASE_URL)
    
    conn = sqlite3.connect(DB_FILE)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    
    cursor = conn.cursor()
    
    # Test queries
    test_queries = [
        "火锅",
        "我想吃火锅",
        "Python",
        "我喜欢吃苹果"
    ]
    
    print("\n" + "="*70)
    print("DISTANCE DISTRIBUTION DEBUG")
    print("="*70)
    
    for query in test_queries:
        print(f"\n>>> Query: '{query}'")
        
        resp = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=query,
            encoding_format="float"
        )
        query_vec = resp.data[0].embedding
        query_blob = serialize_float32(query_vec)
        
        # Search WITHOUT threshold filter to see raw distances
        cursor.execute("""
            SELECT 
                m.content, 
                vec_distance_cosine(v.embedding, ?) as distance
            FROM vec_memories v
            JOIN memories m ON v.rowid = m.rowid
            ORDER BY distance ASC
            LIMIT 10
        """, (query_blob,))
        
        results = cursor.fetchall()
        
        print(f"  Top 10 results (no threshold filter):")
        for i, (content, dist) in enumerate(results):
            sim = 1.0 - dist
            content_preview = content[:50] + "..." if len(content) > 50 else content
            print(f"    {i+1}. dist={dist:.4f} (sim={sim:.4f}) | {content_preview}")
        
        if results:
            distances = [r[1] for r in results]
            print(f"  Distance range: {min(distances):.4f} - {max(distances):.4f}")
            print(f"  Similarity range: {1-max(distances):.4f} - {1-min(distances):.4f}")
    
    conn.close()
    print("\n" + "="*70)

if __name__ == "__main__":
    main()
