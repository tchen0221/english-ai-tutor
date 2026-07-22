import streamlit as st
from supabase import create_client, Client
from datetime import datetime

# 1. 初始化并缓存数据库连接 (避免每次刷新网页都重新连接)
@st.cache_resource
def get_db_client() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

db = get_db_client()

# 2. 保存测试报告 (记录成绩，方便你远程追踪打分)
def save_test_record(grade, score, difficulty, correct_count, total_count, report_json):
    data = {
        "grade": grade,
        "score": score,
        "difficulty": difficulty,
        "correct_count": correct_count,
        "total_count": total_count,
        "report_json": report_json
    }
    try:
        res = db.table("test_records").insert(data).execute()
        # 返回刚创建的测试记录的唯一 ID
        return res.data[0]["id"]
    except Exception as e:
        print(f"保存测试记录失败: {e}")
        return None

# 3. 保存 5 天词汇表 (方便你异地网页直接读取和打印)
def save_vocab_plan(test_id, vocab_json):
    if not test_id or not vocab_json:
        return
    
    records = []
    plan = vocab_json.get("plan", {})
    
    for day, items in plan.items():
        for item in items:
            records.append({
                "test_id": test_id,
                "day_label": day,
                "word": item.get("word", ""),
                "pronunciation": item.get("pronunciation", ""),
                "pos_and_meaning": f"[{item.get('pos', '')}] {item.get('meaning', '')}",
                "variants": item.get("variants", ""),
                "micro_tip": item.get("micro_tip", ""),
                "formula": item.get("formula", ""),
                "sentence": item.get("sentence", "")
            })
            
    try:
        if records:
            db.table("vocab_plans").insert(records).execute()
    except Exception as e:
        print(f"保存词汇表失败: {e}")

# 4. 【核心黑科技】获取最近测试过的词汇，作为防重黑名单
def get_recent_blacklisted_words(limit=50):
    """
    抓取数据库里最近生成的 50 个单词。
    我们将把这些单词喂给 DeepSeek 的提示词，让它绝对不要再出这些词。
    """
    try:
        # 按时间倒序，抓取最近的词汇
        res = db.table("vocab_plans").select("word").order("created_at", desc=True).limit(limit).execute()
        words = [record["word"] for record in res.data]
        # 去重并返回
        return list(set(words))
    except Exception as e:
        print(f"获取黑名单词汇失败: {e}")
        return []

# 5. 读取历史成绩 (为日后的家长/教师看板准备)
def get_all_test_records():
    try:
        res = db.table("test_records").select("*").order("created_at", desc=True).execute()
        return res.data
    except Exception as e:
        return []
