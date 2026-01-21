"""
最朴素的 SSE 测试脚本
直接使用 httpx 调用 GLM 接口，打印每个 chunk 的时间戳
用于验证首 token 延迟 (TTFT) 是模型问题还是框架问题
"""
import time
import sqlite3
import httpx
import json
from datetime import datetime
from pathlib import Path
import os
import pytest


def get_llm_config():
    """从数据库读取 LLM 配置"""
    db_path = Path(__file__).resolve().parents[1] / "data" / "doudou.db"
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT base_url, api_key, model_name FROM llm_configs WHERE deleted = 0 ORDER BY id DESC LIMIT 1"
        )
        row = cursor.fetchone()
        conn.close()
        if row and row[0] and row[1] and row[2]:
            return {
                "base_url": row[0],
                "api_key": row[1],
                "model_name": row[2],
            }

    base_url = os.getenv("SSE_LLM_BASE_URL") or os.getenv("MEMOBASE_LLM_BASE_URL")
    api_key = os.getenv("SSE_LLM_API_KEY") or os.getenv("MEMOBASE_LLM_API_KEY")
    model_name = os.getenv("SSE_LLM_MODEL") or os.getenv("MEMOBASE_BEST_LLM_MODEL")
    if base_url and api_key and model_name:
        return {"base_url": base_url, "api_key": api_key, "model_name": model_name}
    pytest.skip("Missing LLM config for SSE test (DB or SSE_LLM_* env vars).")


def test_raw_sse():
    """使用最朴素的 httpx 直接调用 GLM 流式接口"""
    config = get_llm_config()
    
    print("=" * 60)
    print("朴素 SSE 测试 - 直接调用 GLM 接口")
    print("=" * 60)
    print(f"Base URL: {config['base_url']}")
    print(f"Model: {config['model_name']}")
    print(f"API Key: {config['api_key'][:10]}...{config['api_key'][-5:]}")
    print("=" * 60)
    
    # 构建请求
    url = f"{config['base_url'].rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    payload = {
        "model": config["model_name"],
        "messages": [
            {"role": "system", "content": "你是一个有帮助的助手。"},
            {"role": "user", "content": "简单介绍一下你自己，用3句话。"},
        ],
        "stream": True,
        "temperature": 0.7,
    }
    
    print(f"\n[{datetime.now().isoformat()}] 开始发送请求...")
    request_start = time.perf_counter()
    
    first_chunk_time = None
    chunk_count = 0
    full_content = ""
    
    try:
        with httpx.Client(timeout=60.0) as client:
            with client.stream("POST", url, headers=headers, json=payload) as response:
                connection_time = time.perf_counter() - request_start
                print(f"[{datetime.now().isoformat()}] 连接建立完成 (耗时: {connection_time:.3f}s)")
                print(f"[{datetime.now().isoformat()}] HTTP Status: {response.status_code}")
                print(f"\n{'='*60}")
                print("开始接收 SSE 事件:")
                print("=" * 60)
                
                for line in response.iter_lines():
                    if not line:
                        continue
                    
                    current_time = time.perf_counter()
                    elapsed = current_time - request_start
                    
                    # SSE 格式: "data: {...}"
                    if line.startswith("data: "):
                        data_str = line[6:]  # 移除 "data: " 前缀
                        
                        if data_str == "[DONE]":
                            print(f"\n[{elapsed:.3f}s] 收到 [DONE] 信号")
                            break
                        
                        try:
                            data = json.loads(data_str)
                            chunk_count += 1
                            
                            # 记录首 chunk 时间
                            if first_chunk_time is None:
                                first_chunk_time = elapsed
                                print(f"\n>>> [FIRST CHUNK] Time: {first_chunk_time:.3f}s <<<")
                            
                            # 提取内容
                            choices = data.get("choices", [])
                            
                            # 打印前20个和每个有content的chunk
                            if chunk_count <= 20:
                                print(f"[{elapsed:.3f}s] chunk#{chunk_count}: {json.dumps(data, ensure_ascii=False)[:200]}")
                            
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    full_content += content
                                    # 打印每个有内容的 chunk
                                    if chunk_count > 20:
                                        print(f"[{elapsed:.3f}s] chunk#{chunk_count}: {repr(content)}")
                                    
                        except json.JSONDecodeError:
                            print(f"[{elapsed:.3f}s] 无法解析 JSON: {data_str[:50]}...")
                    
                    elif line.startswith("event:"):
                        print(f"[{elapsed:.3f}s] Event: {line}")
                        
    except Exception as e:
        elapsed = time.perf_counter() - request_start
        print(f"[{elapsed:.3f}s] 错误: {type(e).__name__}: {e}")
        raise
    
    total_time = time.perf_counter() - request_start
    
    print("\n" + "=" * 60)
    print("测试结果汇总:")
    print("=" * 60)
    print(f"总 chunk 数: {chunk_count}")
    print(f"首 chunk 延迟 (TTFT): {first_chunk_time:.3f}s" if first_chunk_time else "未收到任何 chunk")
    print(f"总耗时: {total_time:.3f}s")
    print(f"\n完整响应内容:")
    print("-" * 40)
    print(full_content)
    print("-" * 40)


if __name__ == "__main__":
    test_raw_sse()
