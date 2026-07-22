import json
import streamlit as st
from openai import OpenAI

# 1. 初始化 DeepSeek 客户端（从 Streamlit Secrets 安全读取）
client = OpenAI(
    api_key=st.secrets["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com"
)

# 2. 根据学生信息生成诊断测试题
def generate_diagnostic_quiz(grade, avg_score):
    prompt = f"""
    你是一位资深初中英语老师。请为一名就读【{grade}】、平时英语平均分【{avg_score}分】的学生，设计一张简短的诊断测试卷。
    测试卷需包含：
    1. 5道中译英
    2. 5道词汇变形
    3. 5道短语固定搭配
    4. 1篇简短的完形填空（5个空）
    5. 1篇短文填空（5个空）

    请严格只返回 JSON 格式，格式如下：
    {{
        "questions": [
            {{
                "id": 1,
                "type": "translate",
                "question": "题目内容",
                "correct_answer": "正确答案"
            }}
        ]
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个严格按照指定JSON格式输出的英语教研AI。"},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"出题 API 调用错误: {e}")
        return {"questions": []}

# 3. 收集错题并生成 5 天词汇表
def generate_5day_vocab_plan(wrong_questions_info):
    wrong_questions_str = "\n".join(wrong_questions_info)
    
    prompt = f"""
    根据学生做错的题目信息：
    {wrong_questions_str}
    
    请提取相关的中考核心高频词汇，生成一份 5 天的个性化词汇学习计划（每天3个短语，7个单词）。
    每个单词需要包含：单词、词性、固定搭配/语法解释、1句中考真题水平的例句。

    请严格只返回 JSON 格式，格式如下：
    {{
        "plan": {{
            "Day 1": [
                {{
                    "word": "depend",
                    "pos": "v.",
                    "grammar": "常用于 depend on ... 表示‘取决于’或‘依赖’，后面加名词或动名词。",
                    "example": "Success depends on hard work."
                }}
            ],
            "Day 2": [],
            "Day 3": [],
            "Day 4": [],
            "Day 5": []
        }}
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个严格按照指定JSON格式输出的英语教研AI。"},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"词汇表 API 调用错误: {e}")
        return {"plan": {}}
