import sqlite3
import os
from app.core.config import settings

def init_db():
    db_path = os.path.join(settings.DATA_DIR, "doudou.db")
    sql_path = os.path.join(os.path.dirname(__file__), "init.sql")
    
    # Check if we need to initialize
    # We can check if the file exists or if it's empty
    needs_init = not os.path.exists(db_path) or os.path.getsize(db_path) == 0
    
    if needs_init:
        print(f"Initializing database at {db_path}...")
        # Ensure directory exists
        os.makedirs(settings.DATA_DIR, exist_ok=True)
        
        try:
            conn = sqlite3.connect(db_path)
            with open(sql_path, 'r', encoding='utf-8') as f:
                sql_script = f.read()
            
            conn.executescript(sql_script)
            conn.commit()
            conn.close()
            print("Database initialized successfully with init.sql.")
        except Exception as e:
            print(f"Error initializing database: {e}")
    else:
        print("Database already exists. Skipping initialization.")
