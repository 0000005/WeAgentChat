import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add server root to path so `app` imports resolve
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))

from app.services.memo.bridge import MemoService, initialize_memo_sdk
from app.services.memo.constants import DEFAULT_USER_ID, DEFAULT_SPACE_ID
from app.vendor.memobase_server.models.blob import OpenAICompatibleMessage, BlobType
from app.vendor.memobase_server.controllers.user import get_user, update_user, get_user_all_blobs
from app.vendor.memobase_server.controllers.blob import get_blob
from app.vendor.memobase_server.models.utils import PromiseUnpackError

SEED_MARKER_KEY = "seed_memories_v1"

def unwrap_promise(promise, action):
    try:
        return promise.data()
    except PromiseUnpackError as exc:
        raise RuntimeError(f"{action} failed: {exc}") from exc

async def load_existing_event_contents(user_id, space_id):
    existing_contents = set()
    page = 0
    page_size = 200
    while True:
        ids_promise = await get_user_all_blobs(
            user_id=user_id,
            project_id=space_id,
            blob_type=BlobType.chat,
            page=page,
            page_size=page_size,
        )
        ids_data = unwrap_promise(ids_promise, "List user blobs")
        if not ids_data.ids:
            break
        for blob_id in ids_data.ids:
            blob_promise = await get_blob(
                user_id=user_id,
                project_id=space_id,
                blob_id=str(blob_id),
            )
            blob_data = unwrap_promise(blob_promise, "Get blob")
            messages = (blob_data.blob_data or {}).get("messages")
            if messages:
                first = messages[0]
                if isinstance(first, dict):
                    content = first.get("content")
                else:
                    content = getattr(first, "content", None)
                if content:
                    existing_contents.add(content)
        if len(ids_data.ids) < page_size:
            break
        page += 1
    return existing_contents


async def seed_data():
    # 0. Initialize SDK
    print("Initializing Memobase SDK...")
    await initialize_memo_sdk()
    
    print(f"Starting data injection for user: {DEFAULT_USER_ID}, space: {DEFAULT_SPACE_ID}")
    
    # 1. Ensure user exists
    await MemoService.ensure_user(DEFAULT_USER_ID, DEFAULT_SPACE_ID)
    user_promise = await get_user(user_id=DEFAULT_USER_ID, project_id=DEFAULT_SPACE_ID)
    user_data = unwrap_promise(user_promise, "Get user")
    user_fields = user_data.data or {}
    if not isinstance(user_fields, dict):
        user_fields = {}
    if user_fields.get(SEED_MARKER_KEY):
        print(f"Seed marker {SEED_MARKER_KEY} found. Skipping injection.")
        return
    
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

    existing_profiles = await MemoService.get_user_profiles(DEFAULT_USER_ID, DEFAULT_SPACE_ID)
    existing_profile_contents = {p.content for p in existing_profiles.profiles}
    missing_profiles = [
        (content, attr)
        for content, attr in zip(profiles, attributes)
        if content not in existing_profile_contents
    ]
    if missing_profiles:
        missing_contents = [item[0] for item in missing_profiles]
        missing_attrs = [item[1] for item in missing_profiles]
        print(f"Injecting {len(missing_contents)} profiles...")
        await MemoService.add_user_profiles(
            DEFAULT_USER_ID,
            DEFAULT_SPACE_ID,
            missing_contents,
            missing_attrs,
        )
    else:
        print("Profiles already present. Skipping profile injection.")
    
    
    # 3. Inject Event Gists (as Chat Blobs)
    # Friend 1: Work related
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
        "写了一天的文档，感觉比写代码还要累。",
        "今天做了季度 OKR 复盘，发现交付节奏不够稳定。",
        "准备把旧的接口迁移到新版网关，评估下兼容风险。",
        "同事提醒要注意代码里的隐私字段脱敏规则。",
        "产品想加一个小实验开关，先做 AB 测试看看效果。",
        "研发排期有点挤，我在协调需求拆分。",
        "整理了一份成本优化清单，准备下周和财务对齐。",
        "我们需要给外部合作方写一份清晰的对接文档。",
        "本周线上事故复盘，主要问题是告警阈值太高。",
        "今天试着把性能瓶颈定位到数据库索引缺失。",
        "在考虑给设计系统加一套暗色方案，方便夜间使用。",
        "准备把代码审查规则再细化，减少低级问题漏网。"
    ]

    # Friend 2: Life related
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
        "正在研究空气炸锅的菜谱，打算周末大显身手。",
        "最近在控制糖分摄入，晚餐尽量少吃甜食。",
        "今天去看牙医了，医生说需要定期洗牙。",
        "手机屏幕摔碎了，准备周末去换个屏。",
        "本周运动量有点少，计划补两次慢跑。",
        "室友买了新植物，说能净化空气，我有点期待。",
        "晚上做了笔记，准备开始学习理财基础。",
        "突然很想念大学室友，打算发条消息问候。",
        "最近情绪有点低落，可能需要多晒晒太阳。",
        "周末准备整理衣柜，把旧衣服捐出去。",
        "今天做了次体检预约，想确认一下指标。",
        "雨天路滑，打算提前出门避免迟到。"
    ]
    
    total_events = len(work_events) + len(life_events)
    existing_event_contents = await load_existing_event_contents(
        DEFAULT_USER_ID,
        DEFAULT_SPACE_ID,
    )
    inserted_events = 0
    print(f"Injecting {total_events} event gists (via Chat Blobs)...")
    
    async def insert_event(content, friend_id):
        nonlocal inserted_events
        if content in existing_event_contents:
            return
        messages = [
            OpenAICompatibleMessage(role="user", content=content),
            OpenAICompatibleMessage(role="assistant", content="记录下来了。")
        ]
        await MemoService.insert_chat(
            DEFAULT_USER_ID,
            DEFAULT_SPACE_ID,
            messages,
            fields={"friend_id": str(friend_id)}
        )
        existing_event_contents.add(content)
        inserted_events += 1

    # Insert work events (Friend ID 1)
    for event in work_events:
        await insert_event(event, 1)
        
    # Insert life events (Friend ID 2)
    for event in life_events:
        await insert_event(event, 2)

    if inserted_events < total_events:
        print(f"Skipped {total_events - inserted_events} events already present.")
        
    # 4. Trigger flush to generate gists and embeddings
    print("Triggering buffer flush to generate memory items...")
    try:
        await MemoService.trigger_buffer_flush(DEFAULT_USER_ID, DEFAULT_SPACE_ID, BlobType.chat)
    except Exception as exc:
        print(f"Warning: buffer flush failed: {exc}")
        print("Data inserted, but event gists/embeddings may be incomplete.")
        return

    user_fields[SEED_MARKER_KEY] = {
        "inserted_at": datetime.utcnow().isoformat() + "Z",
        "profiles": len(profiles),
        "events": total_events,
    }
    update_promise = await update_user(
        user_id=DEFAULT_USER_ID,
        project_id=DEFAULT_SPACE_ID,
        data=user_fields,
    )
    unwrap_promise(update_promise, "Update user seed marker")
    
    print("\n" + "="*50)
    print(f"Successfully injected {len(profiles) + total_events} memory items!")
    print(f"- Profiles: {len(profiles)}")
    print(f"- Event Gists: {total_events} (Friend 1: {len(work_events)}, Friend 2: {len(life_events)})")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(seed_data())






