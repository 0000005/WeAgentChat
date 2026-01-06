import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.memo.bridge import MemoService, initialize_memo_sdk, reload_sdk_config
from app.services.memo.constants import DEFAULT_USER_ID, DEFAULT_SPACE_ID
from app.vendor.memobase_server.models.blob import OpenAICompatibleMessage, BlobType

async def seed_data():
    # 0. Initialize SDK
    print("Initializing Memobase SDK...")
    await initialize_memo_sdk()
    
    print(f"Starting data injection for user: {DEFAULT_USER_ID}, space: {DEFAULT_SPACE_ID}")
    
    # 1. Ensure user exists
    await MemoService.ensure_user(DEFAULT_USER_ID, DEFAULT_SPACE_ID)
    
    # 2. Inject 10 Profiles
    profiles = [
        "职业是资深 UI 设计师，擅长移动端界面设计。",
        "喜欢在凌晨 2 点工作，认为深夜最有灵感。",
        "对猫毛过敏，家里不能养猫，但很喜欢在网上云吸猫。",
        "平时的爱好是摄影，特别是城市风光摄影。",
        "对咖啡因非常敏感，下午 4 点以后喝咖啡会失眠。",
        "正在学习西班牙语，计划明年去南美旅游。",
        "坚持每天阅读半小时，最近在看《三体》。",
        "平时习惯在早上 7 点去健身房晨练。",
        "是一个极简主义者，喜欢桌面上没有任何杂物。",
        "对人工智能领域非常感兴趣，经常关注最新的 AI 新闻。"
    ]
    
    # Categories/attributes for profiles
    attributes = [
        {"topic": "career", "sub_topic": "profession"},
        {"topic": "habit", "sub_topic": "work_time"},
        {"topic": "health", "sub_topic": "allergy"},
        {"topic": "hobby", "sub_topic": "photography"},
        {"topic": "health", "sub_topic": "dietary_restriction"},
        {"topic": "learning", "sub_topic": "language"},
        {"topic": "habit", "sub_topic": "reading"},
        {"topic": "habit", "sub_topic": "exercise"},
        {"topic": "personality", "sub_topic": "lifestyle"},
        {"topic": "interest", "sub_topic": "technology"}
    ]
    
    print("Injecting 10 profiles...")
    await MemoService.add_user_profiles(DEFAULT_USER_ID, DEFAULT_SPACE_ID, profiles, attributes)
    
    # 3. Inject 40 Event Gists (as Chat Blobs)
    # Friend 1: Work related (20 entries)
    work_events = [
        "关于项目 A 的进度，我们需要在下周五前完成初稿。",
        "UI 设计方案还有点小问题，需要针对登录页再优化一下。",
        "今天和 CTO 开会讨论了架构升级的事，压力有点大。",
        "我觉得我们需要更多的自动化测试来保证代码质量。",
        "刚完成了一个很难的 Bug 修复，感觉非常有成就感。",
        "正在准备下周的技术分享，主题是 Vite 的插件机制。",
        "老板对最近的交付速度比较满意，但强调了细节的重要性。",
        "设计规范需要更新了，现有的某些组件已经不再适用了。",
        "由于服务器波动，今天下午的发布延迟了半小时。",
        "今天在面试几个前端候选人，感觉优秀的开发者很难找。",
        "我们需要讨论一下新功能的优先级排序。",
        "今天整理了一份技术债务清单，发现欠账还挺多的。",
        "产品经理又改需求了，说实话，我有点想吐槽。",
        "正在研究 React Server Components 的适用场景。",
        "刚收到了协作方的反馈，需要调整 API 接口定义。",
        "今天试用了 GitHub Copilot，生成代码的速度确实快。",
        "下个月我们要启动一个新项目，代号为 'Alpha'。",
        "今天和团队一起参加了敏捷回顾会，氛围还不错。",
        "测试环境已经部署好了，可以开始进行回归测试了。",
        "写了一天的文档，感觉比写代码还要累。"
    ]
    
    # Friend 2: Life related (20 entries)
    life_events = [
        "昨晚失眠了，可能是因为睡前想得太多了。",
        "今天尝试了一家新的川菜馆，味道非常正宗。",
        "周末打算去附近的公园散散步，放松一下心情。",
        "在网上买的摄影镜头终于到了，迫不及待想去试试。",
        "今天感觉有点心累，可能是最近工作太忙了。",
        "家里的小米净化器该换滤芯了，手机已经在提醒了。",
        "今天早上起晚了，差一点就错过健身房的课程。",
        "刚看了一场非常震撼的科幻电影，脑洞大开。",
        "今天突然想吃火锅，但想到由于过敏不能吃太辣的，还是算了。",
        "最近在考虑要不要买个升降桌，保护一下腰椎。",
        "今天接到家里人的电话，说明天要来看看我。",
        "晚饭做了个红烧肉，味道比我想象的要好。",
        "今天读了《三体》的第二部，感觉逻辑更宏大了。",
        "早上跑步的时候捡到了十块钱，运气不错。",
        "今天买了很多新鲜水果，要把冰箱塞满了。",
        "最近睡眠质量不太好，打算买个好点的枕头试试。",
        "今天清理了房间，把不需要的旧东西都扔掉了。",
        "今天的天气真好，蓝天白云的，让人心情愉悦。",
        "下午想小睡一会儿，结果一觉睡到了六点。",
        "正在研究空气炸锅的菜谱，打算周末大显身手。"
    ]
    
    print("Injecting 40 event gists (via Chat Blobs)...")
    
    async def insert_event(content, friend_id):
        messages = [
            OpenAICompatibleMessage(role="user", content=content),
            OpenAICompatibleMessage(role="assistant", content="记录下来了。")
        ]
        await MemoService.insert_chat(
            DEFAULT_USER_ID, 
            DEFAULT_SPACE_ID, 
            messages, 
            fields={"friend_id": friend_id}
        )

    # Insert work events (Friend ID 1)
    for event in work_events:
        await insert_event(event, 1)
        
    # Insert life events (Friend ID 2)
    for event in life_events:
        await insert_event(event, 2)
        
    # 4. Trigger flush to generate gists and embeddings
    print("Triggering buffer flush to generate memory items...")
    await MemoService.trigger_buffer_flush(DEFAULT_USER_ID, DEFAULT_SPACE_ID, BlobType.chat)
    
    print("\n" + "="*50)
    print("Successfully injected 50 memory items!")
    print(f"- Profiles: 10")
    print(f"- Event Gists: 40 (Friend 1: 20, Friend 2: 20)")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(seed_data())
