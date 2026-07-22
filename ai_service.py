import json
import streamlit as st
from openai import OpenAI

# 初始化 DeepSeek 客户端
client = OpenAI(
    api_key=st.secrets["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com"
)

def generate_diagnostic_quiz(grade, avg_score):
    prompt = f"""
    你是一位资深且严格遵循中考英语出题考核标准的教研专家。请为一名就读【{grade}】、平时英语平均分【{avg_score}分】的学生，设计一张高度定制化测试卷。
    
    【题型与数量严格要求（共计32题）】：
    1. [中译英] 5题（中考高频词汇）。
    2. [英译中] 5题（中考高频词汇）。
    3. [词汇变形] 5题（给出原词，要求写出名词/形容词等变体）。
    4. [固定搭配] 5题（短语挖空，如 pay attention ___）。
    5. [完形填空] 1篇约100词短文，挖空5处。每空提供A/B/C/D四个选项。
    6. [短文填空] 1篇约100词短文，挖空5处。考核固定搭配与词性变化，无选项。
    7. [翻译句子] 2题（中译英，考核写作能力）。

    【输出JSON结构要求】：
    为了前端直接渲染，请将32道题平铺为一维的 "questions" 数组。
    - 完形和短文填空，请将文章内容放在首个题目的 "context" 字段中，后续题目为空。
    - 完形填空的 type 必须是 "radio" 并提供 "options" 数组，其余题目 type 为 "text"。

    必须严格输出以下 JSON 格式：
    {{
        "questions": [
            {{
                "id": 1,
                "category": "中译英",
                "type": "text",
                "question": "环境",
                "correct_answer": "environment"
            }},
            {{
                "id": 21,
                "category": "完形填空 第1空",
                "type": "radio",
                "context": "Here is the text. I like playing ___21___ basketball...",
                "question": "请选择第21空的答案",
                "options": ["A. a", "B. an", "C. the", "D. /"],
                "correct_answer": "D. /"
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

def generate_diagnostic_report(wrong_questions_info):
    wrong_questions_str = "\n".join(wrong_questions_info)
    prompt = f"""
    你是一位温柔、鼓励学生的初中英语老师。学生刚刚做完一套中考难度的测试，以下是他做错的题目明细：
    {wrong_questions_str}
    
    请根据错题，为他出具一份综合诊断报告。
    1. 必须包含对以下四个维度的具体评价：【词汇储备量】、【语法能力】、【阅读能力】、【写作能力】。
    2. 语气必须缓和、以鼓励为主，不要让初一学生感到挫败。
    
    请严格返回 JSON 格式：
    {{
        "report": "在这里写下几百字的诊断报告正文（支持 Markdown 换行和排版）"
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
        return {"report": "生成诊断报告失败，请稍后再试。"}

def generate_5day_vocab_plan(wrong_questions_info):
    wrong_questions_str = "\n".join(wrong_questions_info)
    prompt = f"""
    根据学生做错的题目信息：
    {wrong_questions_str}
    
    请生成一份 5 天的个性化词汇学习计划。
    【核心要求】：
    1. 优先提取错题中暴露的薄弱词汇，然后从中考高频词汇/短语中随机抓取补充。
    2. 每天严格生成 10 个学习项（必须包含 4 个短语，6 个单词）。
    
    请严格返回 JSON 格式，字段名必须匹配以下示例：
    {{
        "plan": {{
            "Day 1": [
                {{
                    "word": "pronunciation",
                    "pronunciation": "/prəˌnʌnsiˈeɪʃn/",
                    "pos": "n.",
                    "meaning": "发音",
                    "micro_tip": "中考高频易错拼写，注意中间是 -nun- 而不是 -noun-（千万别和动词pronounce搞混）！",
                    "formula": "have a good pronunciation (有好的发音)",
                    "sentence": "Your English pronunciation is excellent."
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
