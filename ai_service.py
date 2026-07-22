import json
import streamlit as st  # 引入 streamlit 库以读取环境变量
from openai import OpenAI

# 从 Streamlit Secrets 中安全读取 API Key
client = OpenAI(
    api_key=st.secrets["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com"
)

# 2. 根据学生信息生成诊断测试题
def generate_diagnostic_quiz(grade, avg_score):
    prompt = f"""
    你是一位资深初中英语老师。请为一名就读【{grade}】、平时英语平均分【{avg_score}分】的学生，设计一张简短的诊断测试卷。
    测试卷需包含：
    1. 2道中译英
    2. 2道词汇变形与固定搭配
    3. 1篇简短的完形填空（3个空）

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
    
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "你是一个严格按照指定JSON格式输出的英语教研AI。"},
            {"role": "role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"}
    )
    
    return json.loads(response.choices[0].message.content)

# 3. 收集错题并生成 5 天词汇表
def generate_5day_vocab_plan(wrong_questions_info):
    prompt = f"""
    根据学生做错的题目信息：{wrong_questions_info}，
    请提取相关的中考核心高频词汇，生成一份 5 天的个性化词汇学习计划（每天2~3个词/短语，共10-15个）。
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
    
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "你是一个严格按照指定JSON格式输出的英语教研AI。"},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"}
    )
    
    return json.loads(response.choices[0].message.content)
