import streamlit as st
from supabase import create_client, Client
from datetime import datetime
import random
import os

@st.cache_resource
def get_db_client():
    # 👇 优先读取 Sealos 环境变量
    url = os.environ.get("SUPABASE_URL")
    if not url:
         url = st.secrets["SUPABASE_URL"]
         
    key = os.environ.get("SUPABASE_KEY")
    if not key:
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
        return res.data[0]["id"]
    except Exception as e:
        print(f"保存测试记录失败: {e}")
        return None

# 3. 升级版：保存 5 天词汇表，新增 type 字段区分词/短语
def save_vocab_plan(test_id, vocab_json):
    if not test_id or not vocab_json:
        return
    
    records = []
    plan = vocab_json.get("plan", {})
    
    for day, items in plan.items():
        for item in items:
            # 通过内部标识判断是 word 还是 phrase (后续 ai_service 会配合输出)
            item_type = item.get("type", "word") 
            records.append({
                "test_id": test_id,
                "day_label": day,
                "word": item.get("word", ""),
                "type": item_type,
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

# 4. 获取最近测试过的词汇，作为防重黑名单
def get_recent_blacklisted_words(limit=50):
    try:
        res = db.table("vocab_plans").select("word").order("created_at", desc=True).limit(limit).execute()
        words = [record["word"] for record in res.data]
        return list(set(words))
    except Exception as e:
        print(f"获取黑名单词汇失败: {e}")
        return []

# 5. 【新增】随机抓取主词库话题
def get_random_topics(limit=3):
    try:
        # Supabase Python API 抓取去重 topic 的简便写法
        res = db.table("vocabulary_bank").select("topic").execute()
        topics = list(set([row["topic"] for row in res.data if row.get("topic")]))
        return random.sample(topics, min(limit, len(topics))) if topics else []
    except Exception as e:
        print(f"获取话题失败: {e}")
        return []

# 6. 【核心黑科技升级】生成出题专用词汇库（死守 35词 + 15短语 铁律）
def get_training_vocabulary(mode="fresh", blacklist=None):
    if blacklist is None:
        blacklist = []
        
    words_needed = 35   # 5天 x 7单词
    phrases_needed = 15 # 5天 x 3短语
    
    selected_words = []
    selected_phrases = []
    
    # 如果是错题特训模式，优先抓取未消灭的错题
    if mode == "wrong_focus":
        try:
            res = db.table("wrong_questions").select("word, type").eq("status", "unmastered").execute()
            unmastered = [row for row in res.data if row["word"] not in blacklist]
            random.shuffle(unmastered)
            
            w_pool = [item["word"] for item in unmastered if item["type"] == "word"]
            p_pool = [item["word"] for item in unmastered if item["type"] == "phrase"]
            
            selected_words.extend(w_pool[:words_needed])
            selected_phrases.extend(p_pool[:phrases_needed])
        except Exception as e:
            print(f"读取错题库失败: {e}")
            
    # 计算距目标 (35+15) 还差多少空缺
    missing_words = words_needed - len(selected_words)
    missing_phrases = phrases_needed - len(selected_phrases)
    
    # 填补空缺：如果是"全新"模式，或者错题本里词不够，从主词库补充
    if missing_words > 0 or missing_phrases > 0:
        topics = get_random_topics(3) # 随机挑 3 个标签
        try:
            exclude_list = set(blacklist + selected_words + selected_phrases)
            # 抓取选中话题里的词汇
            res = db.table("vocabulary_bank").select("word, type").in_("topic", topics).execute()
            bank_items = [row for row in res.data if row["word"] not in exclude_list]
            random.shuffle(bank_items)
            
            b_words = [row["word"] for row in bank_items if row["type"] == "word"]
            b_phrases = [row["word"] for row in bank_items if row["type"] == "phrase"]
            
            selected_words.extend(b_words[:missing_words])
            selected_phrases.extend(b_phrases[:missing_phrases])
        except Exception as e:
            print(f"主词库补充失败: {e}")

    return {
        "words": selected_words,
        "phrases": selected_phrases
    }

# 7. 【修改】错题写入机制：新增 test_id 绑定，支持级联删除
def save_wrong_question(test_id, word, item_type="word"):
    try:
        # 先查存不存在
        existing = db.table("wrong_questions").select("id, status").eq("word", word).execute()
        if not existing.data:
            # 没存过，直接写入未掌握，并绑定本次测试卷的 test_id
            db.table("wrong_questions").insert({
                "test_id": test_id,
                "word": word, 
                "type": item_type, 
                "status": "unmastered"
            }).execute()
        else:
            # 存过但之前做对了(mastered)，重新打回未掌握(unmastered)
            if existing.data[0]["status"] == "mastered":
                db.table("wrong_questions").update({
                    "test_id": test_id, # 更新时关联到最新一次错的卷子
                    "status": "unmastered"
                }).eq("word", word).execute()
    except Exception as e:
        print(f"保存错题失败: {e}")

# 8. 【新增】错题消灭机制
def mark_word_as_mastered(word):
    try:
        db.table("wrong_questions").update({"status": "mastered"}).eq("word", word).execute()
    except Exception as e:
        print(f"更新单词 {word} 状态为已消灭失败: {e}")

# 9. 【新增】获取历史词汇表列表（供用户在下拉菜单选择）
def get_vocab_plan_history_list():
    try:
        # 查询所有带有时间戳的测试表单 ID
        res = db.table("vocab_plans").select("test_id, created_at").order("created_at", desc=True).execute()
        history = {}
        for row in res.data:
            tid = row["test_id"]
            if tid not in history:
                # 转换时间格式，如: "2026-07-23 20:30"
                dt = datetime.fromisoformat(row["created_at"].replace('Z', '+00:00'))
                history[tid] = dt.strftime("%Y-%m-%d %H:%M")
        return history
    except Exception as e:
        print(f"获取词汇表历史失败: {e}")
        return {}

# 10. 【新增】读取指定历史词汇表的内容
def get_vocab_plan_by_id(test_id):
    try:
        res = db.table("vocab_plans").select("word, type").eq("test_id", test_id).execute()
        words = [r["word"] for r in res.data if r["type"] == "word"]
        phrases = [r["word"] for r in res.data if r["type"] == "phrase"]
        return {"words": words, "phrases": phrases}
    except Exception as e:
        print(f"读取历史词汇表详情失败: {e}")
        return {"words": [], "phrases": []}

# 11. 【新增】删除指定的历史词汇表
def delete_vocab_plan(test_id):
    try:
        db.table("vocab_plans").delete().eq("test_id", test_id).execute()
        return True
    except Exception as e:
        print(f"删除词汇表失败: {e}")
        return False

# 12. 专门为 Step 4 生成复习词汇表设计的抓词逻辑
def get_review_vocabulary(current_test_words=None):
    if current_test_words is None:
        current_test_words = []
        
    words_needed = 35
    phrases_needed = 15
    
    selected_words = []
    selected_phrases = []
    
    # 1. 从错题库抓取 unmastered 状态的词，并过滤掉长句子
    try:
        res = db.table("wrong_questions").select("word, type").eq("status", "unmastered").execute()
        unmastered = res.data if res.data else []
        random.shuffle(unmastered)
        
        for item in unmastered:
            w = item["word"].strip()
            # 过滤逻辑：超过 4 个单词或长度超过 30 字符的，视为整句翻译，直接排除！
            if len(w.split()) > 4 or len(w) > 30:
                continue
                
            if item["type"] == "word" and len(selected_words) < words_needed:
                if w not in selected_words:
                    selected_words.append(w)
            elif item["type"] == "phrase" and len(selected_phrases) < phrases_needed:
                if w not in selected_phrases:
                    selected_phrases.append(w)
    except Exception as e:
        print(f"读取错题库生成复习表失败: {e}")

    # 2. 计算缺额
    missing_words = words_needed - len(selected_words)
    missing_phrases = phrases_needed - len(selected_phrases)
    
    # 3. 如果错题不够 (或短语不够)，从全新的 Topic Pool 中抓取补充 (避开本次测试用过的词)
    if missing_words > 0 or missing_phrases > 0:
        try:
            # 排除黑名单：包含近期黑名单 + 本次测试词 + 已经选上的错题
            blacklist = get_recent_blacklisted_words(limit=50)
            exclude_set = set(blacklist + current_test_words + selected_words + selected_phrases)
            
            topics = get_random_topics(3)
            res = db.table("vocabulary_bank").select("word, type").in_("topic", topics).execute()
            
            bank_items = [row for row in res.data if row["word"] not in exclude_set]
            random.shuffle(bank_items)
            
            b_words = [row["word"] for row in bank_items if row["type"] == "word" and len(row["word"].split()) <= 4]
            b_phrases = [row["word"] for row in bank_items if row["type"] == "phrase" and len(row["word"].split()) <= 4]
            
            selected_words.extend(b_words[:missing_words])
            selected_phrases.extend(b_phrases[:missing_phrases])
        except Exception as e:
            print(f"补充全新话题词汇失败: {e}")
            
    return {
        "words": selected_words,
        "phrases": selected_phrases
    }

# 13. 【新增】获取所有未掌握的错题列表，供“我的错题本”视图展示
def get_unmastered_wrong_questions():
    try:
        res = db.table("wrong_questions").select("id, word, type, created_at").eq("status", "unmastered").order("created_at", desc=True).execute()
        return res.data if res.data else []
    except Exception as e:
        print(f"获取错题本数据失败: {e}")
        return []
