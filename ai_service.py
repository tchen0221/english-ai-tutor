import json
import re
import streamlit as st
from openai import OpenAI
import concurrent.futures

# 初始化 DeepSeek 客户端
client = OpenAI(
    api_key=st.secrets["DEEPSEEK_API_KEY"],
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
            if attempt == max_retries - 1:
                raise Exception(f"已重试 {max_retries} 次。最后一次报错: {str(e)}")
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

    【输出JSON结构要求】：
    请将 10 道题平铺为一维的 "questions" 数组，type 全部为 "text"。
    必须严格输出以下 JSON 格式示例：
    {{
        "questions": [
            {{
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
        print(f"模块一生成错误: {e}")
        return {"questions": []}

# ==============================================================================
# 模块二：语法与搭配关 (12 题)
# ==============================================================================
def generate_module_2(vocab_data):
    words_str = ", ".join(vocab_data.get("words", []))
    phrases_str = ", ".join(vocab_data.get("phrases", []))
    
    prompt = f"""
    你是一位资深且严格遵循中考英语出题考核标准的教研专家。请基于我提供的【专属核心词库】，设计一张【模块二：语法与短语测试卷】。
    
    【出题最高限制指令：限定弹药库】
    本次测试的所有考点必须且只能从以下提供的词汇和短语中挑选：
    - 核心单词 (Words): [{words_str}]
    - 核心短语 (Phrases): [{phrases_str}]
    绝对不允许考查上述列表之外的词汇作为重点！

    【题型与数量严格要求（共计 12 题，绝不可多出或少出）】：
    1. [词汇变形] 5题（给出原词，要求写出名词/形容词等变体，从单词库抽取）。
    2. [固定搭配] 5题（短语挖空，如 pay attention ___，优先从短语库抽取）。
    3. [翻译句子] 2题（中译英，考核写作能力，强制融入提供的短语）。

    【阅卷强约束：答案纯净度】(极其重要！)
    JSON 中的 `correct_answer` 字段必须且只能包含最终供程序比对的纯文本答案！
    如果是词汇变形或挖空，直接填目标词。如果是句子翻译，可以保留基础的标点。
    绝对不能包含选项字母(如A/B/C)或多余的解析说明。

    【输出JSON结构要求】：
    请将 12 道题平铺为一维的 "questions" 数组，type 全部为 "text"。
    必须严格输出以下 JSON 格式示例：
    {{
        "questions": [
            {{
                "category": "词汇变形",
                "type": "text",
                "question": "care (adj.)",
                "correct_answer": "careful"
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
# 模块三：语篇综合实战关 (10 题) - 拆分并行版
# ==============================================================================
def generate_module_3(vocab_data):
    words_str = ", ".join(vocab_data.get("words", []))
    phrases_str = ", ".join(vocab_data.get("phrases", []))
    
    # --- 内部函数 1：独立生成完形填空 ---
    def _generate_cloze():
        prompt = f"""
        你是一位资深福建中考英语命题专家。请生成 1 篇完形填空试题。

        【限定弹药库】
        本次测试的答案考点必须优先从以下词汇中挑选：
        - 核心单词: [{words_str}]
        - 核心短语: [{phrases_str}]

        【核心要求】
        1. 篇幅150-180词，完整故事情节（起因-冲突-解决-感悟）。首句必须完整，严禁挖空。
        2. 挖空 5 处（编号 1 到 5），标记为 ___1___。
        3. 上下文强锁死：单看所在句应有多个选项通顺，但结合上下文情节，【必须有且仅有 1 个】合乎逻辑的答案。
        4. 严禁明文泄题，正确答案原词不可在上下文中出现。四个选项词性必须严格一致。

        【输出JSON格式严格要求】（只输出纯JSON，不要解析说明，注意答案必须是选项里的单词纯文本）
        {{
            "passage": "短文正文，包含 ___1___ 到 ___5___",
            "questions": [
                {{
                    "id": 1,
                    "options": ["A. happy", "B. sad", "C. angry", "D. tired"],
                    "answer": "happy" 
                }}
            ]
        }}
        """
        return _call_deepseek_with_retry(prompt)

    # --- 内部函数 2：独立生成短文填空 ---
    def _generate_short_text():
        prompt = f"""
        你是一位资深福建中考英语命题专家。请生成 1 篇短文语法填空试题。

        【限定弹药库】
        本次测试的考点必须优先从以下词汇中挑选：
        - 核心单词: [{words_str}]
        - 核心短语: [{phrases_str}]

        【核心要求】
        1. 篇幅130-160词，主题围绕生活启发/科普。挖空必须均匀分布，严禁连续两句挖空。
        2. 严格挖空 5 处（编号 6 到 10）。
        3. 考点公式硬性要求（必须严格遵守！）：
           - 【带提示词】3 处：必须在括号内给原形，如 ___6___ (care)。1处动词时态/语态，1处名词复数/词性转换，1处形容词/副词比较级或转换。
           - 【无提示词】2 处：无括号，如 ___9___。只能考查【介词】、【连词】或【固定搭配】。严禁考无提示词的名词或动词，必须保证全国考生只能填出唯一虚词解！

        【输出JSON格式严格要求】（只输出纯JSON，答案直接给纯文本）
        {{
            "passage": "短文正文，带提示词示例 ___6___ (care)；无提示词示例 ___9___",
            "questions": [
                {{
                    "id": 6,
                    "answer": "careful"
                }}
            ]
        }}
        """
        return _call_deepseek_with_retry(prompt)

    # ==========================================
    # 多线程并行调用 (核心优化点：提速 50% 以上)
    # ==========================================
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_cloze = executor.submit(_generate_cloze)
            future_short = executor.submit(_generate_short_text)
            
            cloze_data = future_cloze.result()
            short_data = future_short.result()
            
        final_questions = []

        # 组装前端需要的 完形填空 格式
        if cloze_data and "questions" in cloze_data:
            for q in cloze_data["questions"]:
                final_questions.append({
                    "category": "完形填空",
                    "type": "radio",
                    "context": cloze_data.get("passage", ""),
                    "question": f"第 {q['id']} 处填空",
                    "options": q.get("options", []),
                    "correct_answer": q.get("answer", "")
                })

        # 组装前端需要的 短文填空 格式
        if short_data and "questions" in short_data:
            for q in short_data["questions"]:
                final_questions.append({
                    "category": "短文填空",
                    "type": "text",
                    "context": short_data.get("passage", ""),
                    "question": f"第 {q['id']} 处填空",
                    "correct_answer": q.get("answer", "")
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
