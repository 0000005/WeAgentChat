import json
import sqlite3
import sys
import os
import struct
import time
from typing import List, Dict
from openai import OpenAI

# Try to import sqlite_vec
try:
    import sqlite_vec
except ImportError:
    print("Error: sqlite_vec not found. Please install it or run in the correct venv.")
    sys.exit(1)

# Configuration
DB_FILE = "scripts/memory_test/demo_memory.db"
TEST_CASES_FILE = "scripts/memory_test/test_cases.json"
EMBEDDING_MODEL = "BAAI/bge-m3"
EMBEDDING_DIM = 1024
BASE_URL = "https://api.siliconflow.cn/v1"

def serialize_float32(vector: List[float]) -> bytes:
    return struct.pack(f'{len(vector)}f', *vector)

def deserialize_float32(vec_blob: bytes) -> List[float]:
    return list(struct.unpack(f'{len(vec_blob)//4}f', vec_blob))

def init_vec_table(conn):
    """Ensure the sqlite-vec virtual table exists and is populated."""
    cursor = conn.cursor()
    # Check if vec_memories exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vec_memories'")
    if not cursor.fetchone():
        print("Creating virtual table vec_memories...")
        cursor.execute(f"CREATE VIRTUAL TABLE vec_memories USING vec0(embedding float[{EMBEDDING_DIM}])")
        # Populate from memories table
        # rowid in vec_memories will match rowid in memories
        cursor.execute("SELECT rowid, embedding FROM memories")
        rows = cursor.fetchall()
        for rowid, blob in rows:
            cursor.execute("INSERT INTO vec_memories(rowid, embedding) VALUES (?, ?)", (rowid, blob))
        conn.commit()
    return

def get_query_embedding(client, text: str) -> List[float]:
    resp = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
        encoding_format="float"
    )
    return resp.data[0].embedding

def search(conn, query_vec: List[float], top_k: int = 5, threshold: float = 0.5):
    cursor = conn.cursor()
    query_blob = serialize_float32(query_vec)
    
    # Using cosine distance (1 - cosine_similarity in sqlite-vec)
    # distance = 0 means perfect match (sim = 1)
    # distance = 1 means orthogonal (sim = 0)
    # distance = 2 means opposite (sim = -1)
    # similarity = 1 - distance
    
    # We use 1 - threshold as the distance limit because similarity = 1 - distance
    dist_limit = 1.0 - threshold
    
    # NOTE: Must use the function directly in WHERE clause, not the alias!
    query = """
        SELECT 
            m.content, 
            vec_distance_cosine(v.embedding, ?) as distance
        FROM vec_memories v
        JOIN memories m ON v.rowid = m.rowid
        WHERE vec_distance_cosine(v.embedding, ?) < ?
        ORDER BY distance ASC
        LIMIT ?
    """
    
    cursor.execute(query, (query_blob, query_blob, dist_limit, top_k))
    return cursor.fetchall()

def evaluate(test_case: Dict, results: List):
    """Evaluate recall results against expectations."""
    contents = [r[0] for r in results]
    distances = [r[1] for r in results]
    
    # Hit: Whether ANY expected keyword is found in ANY result
    hit = False
    expected = test_case.get('expected_keywords', [])
    relevant_count = 0
    
    for c in contents:
        is_relevant = False
        for kw in expected:
            if kw in c:
                is_relevant = True
                hit = True
                break
        if is_relevant:
            relevant_count += 1
            
    # Precision: proportion of retrieved results that are relevant
    precision = (relevant_count / len(results)) if len(results) > 0 else 0
            
    # Noise Resistance
    noise_hit = False
    noise = test_case.get('noise_keywords', [])
    for c in contents:
        for kw in noise:
            if kw in c:
                noise_hit = True
                break
        if noise_hit: break
            
    return {
        "hit": hit,
        "precision": precision,
        "noise_detected": noise_hit,
        "count": len(results),
        "best_distance": distances[0] if distances else None
    }

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
    
    init_vec_table(conn)
    
    with open(TEST_CASES_FILE, 'r', encoding='utf-8') as f:
        test_data = json.load(f)
        
    test_cases = test_data['test_cases']
    
    # Test Parameters (TopK, Threshold)
    configs = [
        (3, 0.4),
        (5, 0.4),
        (5, 0.5),
        (5, 0.6),
        (10, 0.6)
    ]
    
    summary_results = []

    print(f"\n{'='*60}")
    print(f"{'MEMORY RECALL SYSTEM TEST':^60}")
    print(f"{'='*60}")

    for top_k, threshold in configs:
        print(f"\n[Config] TopK={top_k}, Threshold={threshold}")
        hits = 0
        total = 0
        noise_failures = 0
        total_precision = 0
        
        # Group stats
        type_stats = {} # {type: {'hits': 0, 'total': 0}}

        for case in test_cases:
            total += 1
            q_type = case.get('query_type', 'unknown')
            if q_type not in type_stats:
                type_stats[q_type] = {'hits': 0, 'total': 0}
            
            type_stats[q_type]['total'] += 1
            
            query_text = case['query']
            query_vec = get_query_embedding(client, query_text)
            results = search(conn, query_vec, top_k=top_k, threshold=threshold)
            
            evaluation = evaluate(case, results)
            if evaluation['hit']:
                hits += 1
                type_stats[q_type]['hits'] += 1
                
            if evaluation['noise_detected']:
                noise_failures += 1
            total_precision += evaluation['precision']
            
        hit_rate = (hits / total) * 100 if total > 0 else 0
        avg_precision = (total_precision / total) * 100 if total > 0 else 0
        noise_resistance = ((total - noise_failures) / total) * 100 if total > 0 else 0
        
        summary_results.append({
            "top_k": top_k,
            "threshold": threshold,
            "hit_rate": hit_rate,
            "precision": avg_precision,
            "noise_resistance": noise_resistance,
            "type_stats": type_stats
        })
        
        print(f"  > Hit Rate: {hit_rate:>6.2f}%")
        print(f"  > Precision: {avg_precision:>6.2f}%")
        print(f"  > Noise Resistance: {noise_resistance:>6.2f}%")
        
        # Print breakdown
        print("    [Breakdown by Type]")
        for q_type, stats in type_stats.items():
            t_hit = (stats['hits'] / stats['total']) * 100 if stats['total'] > 0 else 0
            print(f"    - {q_type:<18}: {t_hit:6.2f}% ({stats['hits']}/{stats['total']})")

    print(f"\n{'='*60}")
    print(f"{'FINAL SUMMARY':^60}")
    print(f"{'='*60}")
    print(f"{'TopK':<5} | {'Thresh':<6} | {'HitRate':<8} | {'Prec.':<8} | {'NoiseRes':<8}")
    print("-" * 60)
    for res in summary_results:
        print(f"{res['top_k']:<5} | {res['threshold']:<6.1f} | {res['hit_rate']:<8.2f}% | {res['precision']:<8.2f}% | {res['noise_resistance']:<8.2f}%")
    
    conn.close()

if __name__ == "__main__":
    main()
