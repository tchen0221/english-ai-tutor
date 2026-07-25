import json
import re
import os
import time
import streamlit as st
from openai import OpenAI
import concurrent.futures

# 👇 安全获取密钥：优先读取 Sealos 环境变量，如果为空再读取本地 secrets.toml
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    DEEPSEEK_API_KEY = st.secrets["DEEPSEEK_API_KEY"]

# 初始化 DeepSeek 客户端
client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

def _extract_json(text):
    """优化版：提取 JSON 字符串（更稳健地处理 Reasoner 模型的啰嗦文本或 Markdown 标记）"""
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    text = text.strip()
    
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
            
    try:
        return json.loads(text)
    except Exception as e:
        print(f"JSON解析失败，原始文本: {text[:200]}...")
        raise e

def _call_deepseek_with_retry(prompt, max_retries=3):
    """通用 API 调用函数，带自动重试机制防止静默崩溃"""
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="deepseek-reasoner", 
                messages=[{"role": "user", "content": prompt}],
                timeout=120 
            )
            content = response.choices[0].message.content
            if not content and hasattr(response.choices[0].message, 'reasoning_content'):
                content = response.choices[0].message.reasoning_content
                
            return _extract_json(content)
        
        except Exception as e:
            print(f"DeepSeek 请求失败 (尝试 {attempt+1}/{max_retries}): {e}") # 👈 把报错打在后台方便追踪
            if attempt == max_retries - 1:
                raise Exception(f"已重试 {max_retries} 次。最后一次报错: {str(e)}")
            time.sleep(3) # 👈 失败后强制休息 3 秒再重试，大概率能绕过频控限制
    return None

# ==============================================================================
# 模块一：词汇识记关 (10 题)
# ==============================================================================
def generate_module_1(vocab_data):
    words_str = ", ".join(vocab_data.get("words", []))
    
    prompt = f"""
    你是一位资深且严格遵循中考英语出题考核标准的教研专家。请基于我提供的【专属核心词库】，设计一张【模块一：词汇基础测试卷】。
    
    【出题最高限制指令：限定弹药库】
    本次测试的所有考点必须且只能从以下提供的词汇中挑选：
    - 核心单词 (Words): [{words_str}]
    绝对不允许考查上述列表之外的词汇作为重点！

    【题型与数量严格要求（共计 10 题，绝不可多出或少出）】：
    1. [中译英] 5题（从上述单词列表中抽取）。
    2. [英译中] 5题（从上述单词列表中抽取）。

    【阅卷强约束：答案纯净度】(极其重要！)
    JSON 中的 `correct_answer` 字段必须且只能包含最终供程序比对的纯文本答案！
    如果有多种翻译或近义词，请用斜杠 '/' 隔开，例如 "成年人/成人"。
    绝对不能包含任何标点符号或解析说明。

    【强制新增字段：tested_word (溯源考点)】(极其重要！)
    在每一题的 JSON 中，必须新增一个 `tested_word` 字段。它代表这道题实际上是在考查我提供的词库中的哪一个原始单词。
    这个词必须**原封不动**地从我提供的词汇表里复制，绝不能变形或拼错！
    - 如果是中译英，`tested_word` 就是英文答案。
    - 如果是英译中（答案是中文），`tested_word` 必须是题干里的英文。

    【输出JSON结构要求】：
    请将 10 道题平铺为一维的 "questions" 数组，type 全部为 "text"。
    必须严格输出以下 JSON 格式示例：
    {{
        "questions": [
            {{
                "category": "中译英",
                "type": "text",
                "question": "环境",
                "correct_answer": "environment",
                "tested_word": "environment"
            }},
            {{
                "category": "英译中",
                "type": "text",
                "question": "education",
                "correct_answer": "教育",
                "tested_word": "education"
            }}
        ]
    }}
    """
    try:
        return _call_deepseek_with_retry(prompt)
    except Exception as e:
        print(f"模块一生成错误: {e}")
        return {"questions": []}

# ==============================================================================
# 模块二：语法与搭配关 (12 题) - 防多解严谨版
# ==============================================================================
def generate_module_2(vocab_data):
    words_str = ", ".join(vocab_data.get("words", []))
    phrases_str = ", ".join(vocab_data.get("phrases", []))
    
    prompt = f"""
    你是一位资深且严格遵循中国福建中考英语出题标准的教研专家。请基于我提供的【专属核心词库】，设计一张【模块二：语法与短语测试卷】。
    
    【出题最高限制指令：限定弹药库】
    本次测试的所有考点必须且只能从以下词汇和短语中挑选：
    - 核心单词 (Words): [{words_str}]
    - 核心短语 (Phrases): [{phrases_str}]

    【题型与数量严格要求（共 12 题，绝不可多出或少出）】：
    
    1. [单句词汇变形] 5题（必须从单词库中抽取并考查其变形）。
       - ⚠️ 致命规范：严禁只给出原词！必须提供一个完整的英文微语境单句，将要变形的单词原形放在括号内。
       - 示例："question": "We had a wonderful ______ (celebrate) yesterday." -> 答案: "celebration"

    2. [固定搭配挖空] 5题（必须从短语库中抽取）。
       - ⚠️ 致命规范：为了避免多解，必须在题干前提供【中文释义】，再给出带空格的短语！只能挖去介词、连词或冠词。
       - 示例："question": "保护...免受...：protect ... ______" -> 答案: "from"

    3. [句子翻译] 2题（中译英，必须强制考核短语库中的核心短语）。
       - ⚠️ 致命规范：给出完整的中文句子，并在括号内提示需要使用的短语，防止学生写出其他同义表达。
       - 示例："question": "我们应该保护环境。(提示: protect the environment)" -> 答案: "We should protect the environment."

    【阅卷强约束：答案纯净度】(极其重要！)
    JSON 中的 `correct_answer` 字段必须且只能包含最终供程序比对的纯文本答案！
    如果是翻译题存在缩写差异（如 He is / He's），请用斜杠 '/' 隔开提供多解。绝对不能包含任何标点符号(除翻译题的句末标点外)或解析说明。

    【强制新增字段：tested_word (溯源考点)】(极其重要！)
    在每一题的 JSON 中，必须新增一个 `tested_word` 字段。它代表这道题实际上是在考查我提供的词库中的哪一个原始单词或短语。
    - 如果是固定搭配挖空，`tested_word` 必须填该题考查的完整短语。
    - 如果是词汇变形，`tested_word` 必须填原始词库给的单词原形。
    - 如果是句子翻译，`tested_word` 必须填该句提示的【核心短语】。

    【输出JSON结构要求】：
    请将 12 道题平铺为一个一维的 "questions" 数组。
    必须严格输出以下 JSON 格式：
    {{
        "questions": [
            {{
                "category": "词汇变形",
                "type": "text",
                "question": "He is a very ______ (care) person.",
                "correct_answer": "careful",
                "tested_word": "care"
            }},
            {{
                "category": "固定搭配",
                "type": "text",
                "question": "查明；弄清 (find ______)",
                "correct_answer": "out",
                "tested_word": "find out"
            }},
            {{
                "category": "翻译句子",
                "type": "text",
                "question": "他习惯于早起。(提示: be used to)",
                "correct_answer": "He is used to getting up early./He's used to getting up early.",
                "tested_word": "be used to"
            }}
        ]
    }}
    """
    try:
        return _call_deepseek_with_retry(prompt)
    except Exception as e:
        print(f"模块二生成错误: {e}")
        return {"questions": []}

# ==============================================================================
# 模块三：语篇综合实战关 (10 题) - 提炼精简强约束版
# ==============================================================================
def generate_module_3(vocab_data):
    words_str = ", ".join(vocab_data.get("words", []))
    phrases_str = ", ".join(vocab_data.get("phrases", []))
    
    # --- 内部函数 1：独立生成完形填空 ---
    def _generate_cloze():
        prompt = f"""
        身份：福建中考英语命题专家。请生成1篇完形填空试题。
        考点词库优先使用：单词[{words_str}]，短语[{phrases_str}]

        【核心约束】
        1. 语篇规范：150-180词记叙文（校园生活/克服困难）。首句完整不设空。绝不可写自然环保类。符合现实物理常识。
        2. 挖空规则：严格5处，按序标记 ___1___ 至 ___5___。正确答案原词绝不可在上下文中明文出现。
        3. 选项致命规则（防多解）：4个选项词性必须一致。结合上下文必须【唯一通顺】。干扰项绝对不能是近义词或存在包含关系（如：答案是star，干扰项绝不能有sun/light/moon）！

        【强制新增字段：tested_word (溯源考点)】
        在每题的 JSON 中新增 `tested_word` 字段。代表这处挖空考查我提供的词库中的哪个原词或短语。即使答案是变形词或短语的一部分，`tested_word` 也必须原封不动填我提供的原词。

        【严格JSON输出】（只输出纯JSON，必须完整包含5题）
        {{
            "passage": "包含 ___1___ 到 ___5___ 的完整文章",
            "questions": [
                {{
                    "id": 1,
                    "options": ["A. xxx", "B. xxx", "C. xxx", "D. xxx"],
                    "answer": "xxx",
                    "tested_word": "原词或短语"
                }}
            ]
        }}
        """
        return _call_deepseek_with_retry(prompt)

    # --- 内部函数 2：独立生成短文填空 ---
    def _generate_short_text():
        prompt = f"""
        身份：福建中考英语命题专家。请生成1篇短文语法填空试题。
        考点词库优先使用：单词[{words_str}]，短语[{phrases_str}]

        【核心约束】
        1. 语篇规范：130-160词（自然环保/科技常识）。绝不可写校园人际类。
        2. ⚠️ 语篇自然度致命规则：【自然通顺】优先级高于【涵盖所有核心词】！如果给定的某些词汇（如 dictionary 等）与自然环保主题严重不符，请直接放弃使用，绝不允许生硬拼凑导致上下文逻辑断裂！严禁使用重复的句式结构（如连续出现两次 spend time doing）。
        3. 挖空规则：必须生成【完整的 5 题】。按从小到大严格递增标记 ___6___ 至 ___10___，严禁乱序。严禁连续两句设空。
        4. 考点公式硬性要求：
           - 【带提示词】3处：格式为 ___6___ (care)。分别考查：动词时态/语态(1处)、名词复数/词性转换(1处)、形容/副词变形(1处)。
           - 【无提示词】2处：格式为 ___9___。只能考查【介词、连词或固定搭配】。示例： depend ___ (on), ___ (although) it was raining。绝对禁止在不缺词的句型中强行挖空！严禁考查名词或动词！

        【严格JSON输出】（只输出纯JSON，必须完整包含5题）
        {{
            "passage": "包含 ___6___ 到 ___10___ 的完整文章（带提示词需带括号）",
            "questions": [
                {{
                    "id": 6,
                    "answer": "xxx"
                }}
            ]
        }}
        """
        return _call_deepseek_with_retry(prompt)

    # ==========================================
    # 多线程并行调用与防重复渲染组装
    # ==========================================
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_cloze = executor.submit(_generate_cloze)
            future_short = executor.submit(_generate_short_text)
            
            cloze_data = future_cloze.result()
            short_data = future_short.result()
            
        final_questions = []

        # 组装完形填空 (只在第 1 题展示文章)
        if cloze_data and "questions" in cloze_data:
            for i, q in enumerate(cloze_data["questions"]):
                final_questions.append({
                    "category": "完形填空",
                    "type": "radio",
                    "context": cloze_data.get("passage", "") if i == 0 else "",
                    "question": f"第 {q['id']} 处填空",
                    "options": q.get("options", []),
                    "correct_answer": q.get("answer", ""),
                    "tested_word": q.get("tested_word", "")  # 👈 新增提取溯源词
                })

        # 组装短文填空 (只在第 1 题展示文章)
        if short_data and "questions" in short_data:
            for i, q in enumerate(short_data["questions"]):
                final_questions.append({
                    "category": "短文填空",
                    "type": "text",
                    "context": short_data.get("passage", "") if i == 0 else "",
                    "question": f"第 {q['id']} 处填空",
                    "correct_answer": q.get("answer", ""),
                    "tested_word": q.get("tested_word", "")  # 👈 新增提取溯源词
                })
                
        return {"questions": final_questions}

    except Exception as e:
        print(f"模块三生成错误: {e}")
        return {"questions": []}

# ==============================================================================
# 报告生成与 5天复习词汇表 (原逻辑绝对保留，未做任何删减)
# ==============================================================================
def generate_diagnostic_report(wrong_questions_info, correct_count, total_count):
    wrong_questions_str = "\n".join(wrong_questions_info) if wrong_questions_info else "全对！"
    prompt = f"""
    你是一位资深的初中英语教研员。学生刚刚完成了一套测试，共 {total_count} 题，做对了 {correct_count} 题。
    以下是他做错的题目明细：
    {wrong_questions_str}
    
    请为他出具一份综合诊断报告。
    【核心要求】：
    【阅卷强约束：答案同义词包容性与纯净度】(极其重要！)
    1. 对于中文翻译题或存在多种合理译法/近义词的考点，`correct_answer` 字段必须使用斜杠 '/' 提供所有常见的正确答案！
        正确示范："成年人/成人"、"影响/作用"、"保护...免受.../保护...不受..."
    2. 绝对不能包含标点符号、选项字母(如A/B/C)或解析说明。
    3. 必须对以下四个维度进行打分（满分均为 10 分）：【词汇储备量】、【语法能力】、【阅读能力】、【写作能力】。
    4. 基于错题，给出具体的分析和鼓励性的复习建议。
    
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
