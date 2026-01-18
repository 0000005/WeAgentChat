"""
Minimal test to verify sqlite-vec query works
"""
import sqlite3
import sys
import struct
from openai import OpenAI

try:
    import sqlite_vec
except ImportError:
    print("Error: sqlite_vec not found.")
    sys.exit(1)

DB_FILE = "scripts/memory_test/demo_memory.db"
EMBEDDING_MODEL = "BAAI/bge-m3"
BASE_URL = "https://api.siliconflow.cn/v1"

def serialize_float32(vector):
    return struct.pack(f'{len(vector)}f', *vector)

api_key = input("Enter API Key: ").strip()
client = OpenAI(api_key=api_key, base_url=BASE_URL)

conn = sqlite3.connect(DB_FILE)
conn.enable_load_extension(True)
sqlite_vec.load(conn)
conn.enable_load_extension(False)

cursor = conn.cursor()

# Get query embedding
resp = client.embeddings.create(model=EMBEDDING_MODEL, input="火锅", encoding_format="float")
query_vec = resp.data[0].embedding
query_blob = serialize_float32(query_vec)

print(f"\nQuery vector length: {len(query_vec)}")
print(f"Query blob length: {len(query_blob)}")

# Test 1: Simple query without WHERE
print("\n--- Test 1: No WHERE clause ---")
cursor.execute("""
    SELECT 
        m.content, 
        vec_distance_cosine(v.embedding, ?) as distance
    FROM vec_memories v
    JOIN memories m ON v.rowid = m.rowid
    ORDER BY distance ASC
    LIMIT 5
""", (query_blob,))
for row in cursor.fetchall():
    print(f"  dist={row[1]:.4f} | {row[0][:50]}")

# Test 2: With WHERE distance < 0.5
print("\n--- Test 2: WHERE distance < 0.5 ---")
cursor.execute("""
    SELECT 
        m.content, 
        vec_distance_cosine(v.embedding, ?) as distance
    FROM vec_memories v
    JOIN memories m ON v.rowid = m.rowid
    WHERE vec_distance_cosine(v.embedding, ?) < 0.5
    ORDER BY distance ASC
    LIMIT 5
""", (query_blob, query_blob))
results = cursor.fetchall()
print(f"  Found {len(results)} results")
for row in results:
    print(f"  dist={row[1]:.4f} | {row[0][:50]}")

# Test 3: Using subquery approach
print("\n--- Test 3: Subquery approach ---")
cursor.execute("""
    SELECT content, distance FROM (
        SELECT 
            m.content, 
            vec_distance_cosine(v.embedding, ?) as distance
        FROM vec_memories v
        JOIN memories m ON v.rowid = m.rowid
    ) WHERE distance < 0.5
    ORDER BY distance ASC
    LIMIT 5
""", (query_blob,))
results = cursor.fetchall()
print(f"  Found {len(results)} results")
for row in results:
    print(f"  dist={row[1]:.4f} | {row[0][:50]}")

conn.close()
