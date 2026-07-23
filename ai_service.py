import json
import re
import streamlit as st
from openai import OpenAI

# 初始化 DeepSeek 客户端
client = OpenAI(
    api_key=st.secrets["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com"
)

def _extract_json(text):
    """优化版：提取 JSON 字符串（更稳健地处理 Reasoner 模型的啰嗦文本或 Markdown 标记）"""
    # 移除可能存在的 markdown 代码块包裹
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    text = text.strip()
    
    # 尝试匹配大括号包裹的内容
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass # 如果匹配到的不是合法 JSON，退回直接解析
            
    try:
        return json.loads(text)
    except Exception as e:
        print(f"JSON解析失败，原始文本: {text[:200]}...")
        raise e

def _call_deepseek_with_retry(prompt, max_retries=3):
    """通用 API 调用函数，带自动重试机制防止静默崩溃"""
    for attempt in range(max_retries):
        try:
            # 统一使用 reasoner 深度思考模型
            response = client.chat.completions.create(
                model="deepseek-reasoner", 
                messages=[{"role": "user", "content": prompt}],
                timeout=120 # 生成长卷子和词汇表需要较多时间，进一步放宽至 120 秒
            )
            content = response.choices[0].message.content
            # 处理极端情况下 reasoner 模型只返回 reasoning_content 的问题
            if not content and hasattr(response.choices[0].message, 'reasoning_content'):
                content = response.choices[0].message.reasoning_content
                
            return _extract_json(content)
        
        except Exception as e:
            if attempt == max_retries - 1:
                raise Exception(f"已重试 {max_retries} 次。最后一次报错: {str(e)}")
    return None

def generate_diagnostic_quiz(vocab_data):
    """
    【升级版出题逻辑】：不再让 AI 瞎编，而是直接传入 db_service 抓取的 50 个词汇。
    """
    words_str = ", ".join(vocab_data.get("words", []))
    phrases_str = ", ".join(vocab_data.get("phrases", []))
    
    prompt = f"""
    你是一位资深且严格遵循中考英语出题考核标准的教研专家。请基于我提供的【专属核心词库】，设计一张高度定制化测试卷。
    
    【出题最高限制指令：限定弹药库】
    本次测试的所有核心考点（填空题的答案、词汇变形的目标词、完形填空考察的词等），**必须且只能**从以下提供的词汇和短语中挑选：
    - 核心单词 (Words): [{words_str}]
    - 核心短语 (Phrases): [{phrases_str}]
    绝对不允许考查上述列表之外的词汇作为重点！

    【题型与数量严格要求（共计32题，绝不可多出或少出）】：
    1. [中译英] 5题（从中考高频词汇/上述单词列表中抽取）。
    2. [英译中] 5题（从中考高频词汇/上述单词列表中抽取）。
    3. [词汇变形] 5题（给出原词，要求写出名词/形容词等变体）。
    4. [固定搭配] 5题（短语挖空，如 pay attention ___，优先从上述短语列表中抽取）。
    5. [完形填空] 1篇约100词短文，挖空5处。
       - ⚠️ 严禁考查语法或同根词变形（如 care/careful/careless）。
       - ⚠️ 必须纯粹考查词汇辨析（如同义词、近义词、符合上下文逻辑的完全不同的单词）。每空提供A/B/C/D四个选项。
    6. [短文填空] 1篇约100词短文，挖空5处。
       - ⚠️ 致命要求：文本 "context" 中必须且只能包含 5 个明确的挖空标记（例如：___26___，一直到 ___30___），绝对不能只挖2个空！
       - ⚠️ 填空格式约束：如果是考查词汇变形（如动词时态、名词复数等），必须在括号内给出提示词原形。例：He is an ___26___ (interest) person. 如果考查介词/连词/冠词，直接挖空不给任何提示词。例：He went to school ___27___ bus.
    7. [翻译句子] 2题（中译英，考核写作能力，尽量融入提供的短语）。

    【阅卷强约束：答案纯净度】(极其重要！)
    JSON 中的 `correct_answer` 字段必须且只能包含最终供程序比对的纯文本答案！
    **绝对不能**包含任何标点符号、选项字母(如A/B/C)或解析说明。
    错误示范："A. careful" 或 "careful."
    正确示范："careful"

    【输出JSON结构要求】：
    为了前端直接渲染，请将32道题平铺为一维的 "questions" 数组。
    - 完形和短文填空，请将文章内容放在首个题目的 "context" 字段中，后续题目为空。
    - 完形填空的 type 必须是 "radio" 并提供 "options" 数组，其余题目 type 为 "text"。

    必须严格输出以下 JSON 格式示例：
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
        return _call_deepseek_with_retry(prompt)
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
        return _call_deepseek_with_retry(prompt)
    except Exception as e:
        return {"report": "生成诊断报告失败，请检查网络或稍后再试。"}

def generate_5day_vocab_plan(vocab_data):
    """
    【升级版计划生成】：完全使用 db_service 给定的 35 单词 + 15 短语。不再让 AI 随机发挥。
    """
    words_list = vocab_data.get("words", [])
    phrases_list = vocab_data.get("phrases", [])
    
    prompt = f"""
    作为一名英语教研专家，你需要为学生整理一份为期 5 天的个性化词汇学习与复习计划。
    
    【限定使用的词汇库】：
    我已经为你准备好了这 5 天需要学习的所有词汇，你**必须且只能**对以下列表中的内容进行详细解析排版，绝对不可增加新词，也不可遗漏任何一个词！
    - 需要排版的 35 个单词: {", ".join(words_list)}
    - 需要排版的 15 个短语: {", ".join(phrases_list)}

    【核心要求与规则，不可违背】：
    1. 将上述词汇分配到 5 天（Day 1 到 Day 5）的学习计划中。
    2. 同源词去重：如果列表中出现了词性变化的同源词（例如 education 和 educational），请将它们合并在一个单词主词条下（将变体写在 variants 字段中），不要让它们占用多个词条名额。
    
    【强制输出结构】(极其重要！不可瞎改配比！)
    1. 必须输出一个纯 JSON 对象，根节点为 "plan"。
    2. "plan" 包含 "Day 1" 到 "Day 5" 五个键。
    3. 每天的数组**必须严格包含 10 个 JSON Object**。
    4. 这 10 个 Object 中，**必须精确包含 7 个单词 (type="word") 和 3 个短语 (type="phrase")**，不能多也不能少！每天的总量加起来一定是 10。
    
    请严格返回 JSON 格式，字段名必须匹配以下示例：
    {{
        "plan": {{
            "Day 1": [
                {{
                    "type": "word",
                    "word": "education",
                    "pronunciation": "/ˌedʒuˈkeɪʃn/",
                    "pos": "n.",
                    "meaning": "教育",
                    "variants": "educational (adj. 有教育意义的) / educate (v. 教育)",
                    "micro_tip": "注意名词后缀 -tion。",
                    "formula": "receive a good education (接受良好的教育)",
                    "sentence": "He received a good education in Beijing."
                }},
                {{
                    "type": "phrase",
                    "word": "protect the environment",
                    "pronunciation": "",
                    "pos": "phrase",
                    "meaning": "保护环境",
                    "variants": "",
                    "micro_tip": "protect ... from ... (保护...免受...)",
                    "formula": "It is our duty to protect the environment.",
                    "sentence": "We should take action to protect the environment."
                }}
            ]
        }}
    }}
    """
    
    try:
        return _call_deepseek_with_retry(prompt)
    except Exception as e:
        print(f"词汇表 API 调用错误: {e}")
        return {"plan": {}}
