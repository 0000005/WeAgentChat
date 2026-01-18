import json
import sqlite3
import sys
import os
import time
import struct

from openai import OpenAI

# Configuration
INPUT_FILE = "scripts/memory_test/test_data_source.json"
DB_FILE = "scripts/memory_test/demo_memory.db"
EMBEDDING_MODEL = "BAAI/bge-m3"
EMBEDDING_DIM = 1024
BASE_URL = "https://api.siliconflow.cn/v1"


def serialize_float32(vector: list) -> bytes:
    """将浮点数列表序列化为二进制格式（与 Memobase 的 Vector TypeDecorator 一致）"""
    return struct.pack(f'{len(vector)}f', *vector)


def init_db():
    """初始化数据库，创建单一表结构"""
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 只有一张表，两个字段
    cursor.execute("""
        CREATE TABLE memories (
            content TEXT NOT NULL,
            embedding BLOB
        )
    """)
    
    conn.commit()
    print(f"数据库已初始化: {DB_FILE}")
    return conn


def get_embeddings(client, texts, model=EMBEDDING_MODEL):
    """批量获取 Embedding"""
    batch_size = 10 
    results = []
    
    total = len(texts)
    print(f"正在为 {total} 条数据生成向量...")
    
    for i in range(0, total, batch_size):
        batch = texts[i:i+batch_size]
        try:
            resp = client.embeddings.create(
                model=model,
                input=batch,
                encoding_format="float"
            )
            for data in resp.data:
                results.append(data.embedding)
            
            print(f"已处理 {min(i+batch_size, total)}/{total}", end='\r')
            time.sleep(0.3)  # Rate limit
            
        except Exception as e:
            print(f"\n处理批次 {i} 时出错: {e}")
            sys.exit(1)
            
    print("\n向量生成完成。")
    return results


def main():
    # 1. 获取 API Key
    api_key = input("请输入 SiliconFlow API Key: ").strip()
    if not api_key:
        print("API Key 不能为空。")
        sys.exit(1)
        
    client = OpenAI(
        api_key=api_key,
        base_url=BASE_URL
    )
    
    # 2. 读取测试数据
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    texts = [item['content'] for item in data]
    
    # 3. 生成向量
    vectors = get_embeddings(client, texts)
    
    if len(vectors) != len(texts):
        print("错误：向量数量与文本数量不匹配！")
        sys.exit(1)
        
    # 4. 写入数据库
    print(f"正在写入数据库 {DB_FILE}...")
    conn = init_db()
    cursor = conn.cursor()
    
    try:
        for i in range(len(texts)):
            content = texts[i]
            vector = vectors[i]
            
            # 使用 struct.pack 序列化向量为 BLOB
            vec_blob = serialize_float32(vector)
            cursor.execute("INSERT INTO memories (content, embedding) VALUES (?, ?)", (content, vec_blob))
             
        conn.commit()
        
        # 验证
        cursor.execute("SELECT count(*) FROM memories")
        cnt = cursor.fetchone()[0]
        print(f"成功！共写入 {cnt} 条记忆数据。")
        
        # 校验一条数据的向量长度
        cursor.execute("SELECT length(embedding) FROM memories LIMIT 1")
        blob_len = cursor.fetchone()[0]
        expected_len = EMBEDDING_DIM * 4  # float32 = 4 bytes
        if blob_len == expected_len:
            print(f"向量维度校验通过 ({EMBEDDING_DIM} 维 x 4 字节 = {expected_len} 字节)")
        else:
            print(f"警告：向量长度 {blob_len} 与预期 {expected_len} 不符！")
        
    except Exception as e:
        print(f"数据库写入错误: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
