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
    你是一位资深且严格遵循中考英语出题考核标准的教研专家。请为一名就读【{grade}】、平时英语平均分【{avg_score}分】（满分150分）的学生，设计一张高度定制化测试卷。
    
    【题型与数量严格要求（共计32题，绝不可多出或少出）】：
    1. [中译英] 5题（中考高频词汇）。
    2. [英译中] 5题（中考高频词汇）。
    3. [词汇变形] 5题（给出原词，要求写出名词/形容词等变体）。
    4. [固定搭配] 5题（短语挖空，如 pay attention ___）。
    5. [完形填空] 1篇约100词短文，挖空5处。
       - ⚠️ 严禁考查语法或同根词变形（如 care/careful/careless）。
       - ⚠️ 必须纯粹考查词汇辨析（如同义词、近义词、符合上下文逻辑的完全不同的单词）。每空提供A/B/C/D四个选项。
    6. [短文填空] 1篇约100词短文，挖空5处。
       - ⚠️ 致命要求：文本 "context" 中必须且只能包含 5 个明确的挖空标记（例如：___26___，一直到 ___30___），绝对不能只挖2个空！
       - ⚠️ JSON 中的题目数量必须严格为 5 题，与文本内的 5 个标记完美对应。
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
            }}
        ]
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个严格按照指定JSON格式输出的英语教研AI，绝不偏离规定的题数和考点要求。"},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"出题 API 调用错误: {e}")
        return {"questions": []}

def generate_diagnostic_report(wrong_questions_info, correct_count, total_count):
    wrong_questions_str = "\n".join(wrong_questions_info) if wrong_questions_info else "全对！"
    prompt = f"""
    你是一位资深的初中英语教研员。学生刚刚完成了一套测试，共 {total_count} 题，做对了 {correct_count} 题。
    以下是他做错的题目明细：
    {wrong_questions_str}
    
    请为他出具一份综合诊断报告。
    【核心要求】：
    1. 必须对以下四个维度进行打分（满分均为 10 分）：【词汇储备量】、【语法能力】、【阅读能力】、【写作能力】。
    2. 基于错题，给出具体的分析和鼓励性的复习建议。
    
    请严格返回 JSON 格式：
    {{
        "report": "在这里写下包含四项打分（满分10分）和具体分析的诊断报告正文（支持 Markdown排版）"
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

def generate_5day_vocab_plan(wrong_questions_info, difficulty):
    wrong_questions_str = "\n".join(wrong_questions_info) if wrong_questions_info else "无错题"
    prompt = f"""
    根据学生做错的题目信息：
    {wrong_questions_str}
    
    请生成一份 5 天的个性化词汇学习计划。
    【核心要求与规则，不可违背】：
    1. **优先且只针对错题**中暴露的词汇盲点进行拓展。如果学生做对的词汇，绝对不要放进复习表！
    2. 当错题词汇不足以填满 5 天的任务量时，请根据该学生当前的水平层级【{difficulty}】，从中考词库中抽取相应难度的词汇进行补充。
    3. 每天严格生成 10 个学习项（包含短语和单词）。
    4. **同源词绝对去重**：如果有单词存在词性变化（例如 education 和 educational），必须合并为一个主词条（education），并将变体写在 `variants` 字段中。绝不能让教育和教育的占用两个新单词名额！
    
    请严格返回 JSON 格式，字段名必须匹配以下示例：
    {{
        "plan": {{
            "Day 1": [
                {{
                    "word": "education",
                    "pronunciation": "/ˌedʒuˈkeɪʃn/",
                    "pos": "n.",
                    "meaning": "教育",
                    "variants": "educational (adj. 有教育意义的) / educate (v. 教育)",
                    "micro_tip": "注意名词后缀 -tion。",
                    "formula": "receive a good education (接受良好的教育)",
                    "sentence": "He received a good education in Beijing."
                }}
            ]
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
