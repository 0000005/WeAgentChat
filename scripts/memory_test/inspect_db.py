
import sqlite3
import sys

# Try to import sqlite_vec to load the extension
try:
    import sqlite_vec
except ImportError:
    print("Error: sqlite_vec not found. Run in the correct environment.")
    sys.exit(1)

DB_FILE = "scripts/memory_test/demo_memory.db"

def inspect():
    print(f"Inspecting {DB_FILE}...")
    conn = sqlite3.connect(DB_FILE)
    
    # Load extension
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    
    cursor = conn.cursor()
    
    # 1. Check Standard Table
    try:
        cursor.execute("SELECT count(*) FROM memories")
        count_mem = cursor.fetchone()[0]
        print(f"[memories] Table Count: {count_mem}")
        
        cursor.execute("SELECT * FROM memories LIMIT 1")
        sample_mem = cursor.fetchone()
        print(f"[memories] Sample Data: {sample_mem}")
    except Exception as e:
        print(f"[memories] Error: {e}")

    print("-" * 20)

    # 2. Check Vector Table
    try:
        cursor.execute("SELECT count(*) FROM vec_memories")
        count_vec = cursor.fetchone()[0]
        print(f"[vec_memories] Table Count: {count_vec}")
        
        # Check actual embedding data existence
        # rowid, embedding
        cursor.execute("SELECT rowid, length(embedding) FROM vec_memories LIMIT 1")
        sample_vec = cursor.fetchone()
        if sample_vec:
            print(f"[vec_memories] Sample RowID: {sample_vec[0]}")
            print(f"[vec_memories] Sample Embedding Blob Length: {sample_vec[1]} bytes")
        else:
            print("[vec_memories] Table is empty!")
            
    except Exception as e:
        print(f"[vec_memories] Error: {e}")

    conn.close()

if __name__ == "__main__":
    inspect()
