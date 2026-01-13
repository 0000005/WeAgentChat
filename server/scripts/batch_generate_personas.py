import asyncio
import os
import sys
import json
import csv
import logging
from typing import List, Dict, Optional

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add server directory to python path
current_dir = os.path.dirname(os.path.abspath(__file__))
server_root = os.path.dirname(current_dir)
sys.path.append(server_root)

from app.db.session import SessionLocal
from app.services.persona_generator_service import persona_generator_service
from app.schemas.persona_generator import PersonaGenerateRequest

# Constants
CSV_PATH = os.path.join(server_root, "..", "dev-docs", "temp", "preset_friends_list.csv")
OUTPUT_JSON_PATH = os.path.join(server_root, "..", "dev-docs", "temp", "generated_personas_text.json")

def load_csv_data(file_path: str) -> List[Dict]:
    data = []
    if not os.path.exists(file_path):
        logger.error(f"CSV file not found: {file_path}")
        return data
        
    with open(file_path, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    return data

def load_existing_results(file_path: str) -> Dict[str, Dict]:
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    return json.loads(content)
        except Exception as e:
            logger.warning(f"Failed to load existing results: {e}. Starting fresh.")
    return {}

def save_results(file_path: str, data: Dict[str, Dict]):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def generate_batch(limit: Optional[int] = None):
    # 1. 加载配置与数据
    personas = load_csv_data(CSV_PATH)
    if not personas:
        logger.error("CSV 文件中未找到任何角色数据。")
        return

    results = load_existing_results(OUTPUT_JSON_PATH)
    logger.info(f"已加载 {len(results)} 条现有结果。总待处理角色：{len(personas)}")

    db = SessionLocal()
    
    count = 0
    max_retries = 3  # 每个角色的最大重试次数
    
    # 2. 遍历并生成
    try:
        for i, p in enumerate(personas):
            if limit is not None and count >= limit:
                logger.info(f"已达到本次生成的数量限制 ({limit})，停止生成。")
                break

            name = p.get('name')
            if not name:
                continue
                
            # 如果已经存在结果，跳过
            if name in results:
                continue

            logger.info(f"[{i+1}/{len(personas)}] 正在为角色生成文案: {name}...")
            
            # 构造 AI 提示词
            description_for_ai = f"{p.get('description', '')}"
            if p.get('category'):
                description_for_ai = f"分类：{p.get('category')}\n简介：{description_for_ai}"
            if p.get('tags'):
                description_for_ai = f"标签：{p.get('tags')}\n{description_for_ai}"

            # 重试逻辑
            success = False
            for attempt in range(max_retries):
                try:
                    request = PersonaGenerateRequest(
                        name=name,
                        description=description_for_ai
                    )
                    # 调用 LLM 服务
                    response = await persona_generator_service.generate_persona(db, request)
                    
                    # 存储结果
                    results[name] = {
                        "name": response.name,
                        "original_description": p.get('description'),
                        "category": p.get('category'),
                        "tags": p.get('tags'),
                        "generated_description": response.description,
                        "system_prompt": response.system_prompt,
                        "initial_message": response.initial_message
                    }
                    
                    # 增量保存（断点续传的关键）
                    save_results(OUTPUT_JSON_PATH, results)
                    logger.info(f"   [成功] {name} (尝试第 {attempt + 1} 次)")
                    count += 1
                    success = True
                    break # 成功后跳出重试循环
                    
                except Exception as e:
                    logger.warning(f"   [失败] {name} 尝试第 {attempt + 1} 次失败: {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2) # 失败后稍作等待再重试
            
            if not success:
                logger.error(f"   [最终失败] 已达到最大重试次数，未能生成角色: {name}")

    finally:
        db.close()

    logger.info(f"批量生成任务结束。当前总共积累结果：{len(results)}")
    print(f"\n" + "="*50)
    print(f"【任务报告】")
    print(f"数据保存路径: {OUTPUT_JSON_PATH}")
    print(f"本次生成数量: {count}")
    print(f"总进度: {len(results)}/{len(personas)}")
    print("="*50)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="WeAgentChat 角色库批量生成工具")
    parser.add_argument("--limit", type=int, help="限制本次生成的角色数量")
    args = parser.parse_args()
    
    try:
        asyncio.run(generate_batch(limit=args.limit))
    except KeyboardInterrupt:
        print("\n[用户中断] 任务已停止，进度已安全保存。")
