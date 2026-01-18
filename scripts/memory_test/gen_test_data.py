import json
import random
from datetime import datetime, timedelta

# Output file
OUTPUT_FILE = "scripts/memory_test/test_data_source.json"

# Helper to generate random date string
def random_date_str(start_year=2024, end_year=2026):
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)
    random_date = start + timedelta(days=random.randint(0, (end - start).days))
    return random_date.strftime("%Y/%m/%d")

def generate_core_data():
    data = []
    
    # 1. Programming (Python, C++, Web, AI)
    langs = ["Python", "C++", "Java", "Rust", "JavaScript", "TypeScript", "Go"]
    actions = ["正在学习", "讨厌调试", "精通", "刚刚重构了", "想要放弃", "觉得很难", "写了一个Demo关于"]
    topics = ["异步编程", "内存管理", "面向对象", "前端框架", "后端API", "神经网络", "设计模式"]
    
    for _ in range(80):
        lang = random.choice(langs)
        action = random.choice(actions)
        topic = random.choice(topics)
        text = f"用户{action}{lang}的{topic}。"
        data.append(text)

    # 2. Food (Spicy, Sweet, Specific dishes)
    foods = ["四川火锅", "麻辣烫", "日式拉面", "美式汉堡", "意大利面", "广东早茶", "湖南小炒肉", "北京烤鸭"]
    preferences = ["最喜欢吃", "最近很想吃", "昨天去吃了", "计划周末去吃", "觉得太辣了", "吃腻了"]
    
    for _ in range(60):
        food = random.choice(foods)
        pref = random.choice(preferences)
        text = f"用户{pref}{food}。"
        data.append(text)

    # 3. Gaming
    games = ["《只狼》", "《艾尔登法环》", "《黑神话：悟空》", "《塞尔达传说》", "《最终幻想》", "《魔兽世界》", "《英雄联盟》"]
    game_actions = ["通关了", "卡关在BOSS", "正在预购", "想要玩", "觉得画面很赞", "和朋友联机"]
    
    for _ in range(60):
        game = random.choice(games)
        action = random.choice(game_actions)
        text = f"用户{action}{game}。"
        data.append(text)

    # 4. Travel
    places = ["日本", "泰国", "欧洲", "西藏", "云南", "海边", "迪士尼"]
    travel_plans = ["想去", "刚刚从", "计划明年去", "回忆起在", "不想去"]
    
    for _ in range(50):
        place = random.choice(places)
        plan = random.choice(travel_plans)
        text = f"用户{plan}{place}旅游。"
        data.append(text)
        
    # 5. Work/Daily
    daily_events = ["加班", "开会", "写报告", "摸鱼", "失眠", "早起", "去健身房"]
    daily_feelings = ["很累", "很开心", "无聊", "充满干劲", "不想动"]
    
    for _ in range(50):
        event = random.choice(daily_events)
        feeling = random.choice(daily_feelings)
        text = f"用户因为{event}觉得{feeling}。"
        data.append(text)

    return data

def generate_noise_data():
    data = []
    
    # 1. Similarity/Ambiguity (Apple vs Apple Phone, Python snake vs Python code)
    # 苹果 (Fruit vs Phone)
    for _ in range(30):
        if random.random() > 0.5:
            text = "用户新买了一部苹果手机，感觉拍照不错。" # Phone
        else:
            text = "用户早上去超市买了几个红富士苹果，很甜。" # Fruit
        data.append(text)
        
    # 蛇 (Animal vs Lang - though context usually clears it, pure keyword search might fail)
    for _ in range(20):
        if random.random() > 0.5:
            text = "用户在动物园看到了一条巨大的蟒蛇。"
        else:
            text = "用户正在安装 Anaconda环境来运行Python。"
        data.append(text)

    # 2. Opposing Sentiments (Love vs Hate) - to test if search for "Likes X" retrieves "Hates X"
    subjects = ["香菜", "榴莲", "下雨天", "恐怖片", "数学"]
    for sub in subjects:
        # Generate pairs or mix
        for _ in range(5):
            data.append(f"用户非常讨厌吃{sub}。")
            data.append(f"用户超级喜欢{sub}。")
            
    # 3. Time Confusion / Irrelevant Past
    # Future dates or logic errors (as text content)
    for _ in range(30):
        data.append(f"用户说明年({random.randint(2028, 2030)}年)才打算买房。")
        data.append(f"用户回忆起10年前的高考，那是2014年的夏天。")

    # 4. Random distracting daily trivia (Noise)
    trivia = ["用户看到楼下的猫在打架。", "用户丢了一把雨伞。", "用户换了一个蓝色的手机壳。", "用户今天喝了三杯水。", "用户忘记带钥匙了。"]
    for _ in range(70):
        data.append(random.choice(trivia))
        
    return data

def main():
    core = generate_core_data() # ~300
    noise = generate_noise_data() # ~200+
    
    all_texts = core + noise
    
    final_data = []
    for i, text in enumerate(all_texts):
        # Attach "Mentioned on" date
        date_str = random_date_str()
        full_text = f"{text}[提及于 {date_str}]"
        
        final_data.append({
            "id": i + 1,
            "content": full_text
        })
        
    # Shuffle
    random.shuffle(final_data)
    
    # Write to file
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)
        
    print(f"Generated {len(final_data)} test items in {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
