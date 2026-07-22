import streamlit as st
from ai_service import generate_diagnostic_quiz, generate_5day_vocab_plan, generate_diagnostic_report
import db_service  # 引入新建立的数据库大管家

st.set_page_config(page_title="AI 英语智能辅导", page_icon="🎓")
st.title("🎓 初中英语 AI 智能诊断与提分系统")

# 初始化所有的全局状态
if "step" not in st.session_state:
    st.session_state.step = 1
if "quiz_data" not in st.session_state:
    st.session_state.quiz_data = None
if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}
if "wrong_list" not in st.session_state:
    st.session_state.wrong_list = []
if "difficulty" not in st.session_state:
    st.session_state.difficulty = "中等"
# 新增：用于保存基础信息和数据库联动的 ID
if "grade" not in st.session_state:
    st.session_state.grade = "初一"
if "avg_score" not in st.session_state:
    st.session_state.avg_score = 90
if "test_id" not in st.session_state:
    st.session_state.test_id = None
if "vocab_plan" not in st.session_state:
    st.session_state.vocab_plan = None

# ---------------- Step 1: 基础情况收集 ----------------
if st.session_state.step == 1:
    st.header("Step 1: 个人学习档案")
    st.session_state.grade = st.selectbox("当前就读年级", ["初一", "初二", "初三"], index=["初一", "初二", "初三"].index(st.session_state.grade))
    st.session_state.avg_score = st.number_input("日常英语平均分（满分150分）", min_value=0, max_value=150, value=st.session_state.avg_score)
    
    if st.button("生成 AI 诊断测试卷 (已开启去重)"):
        # 根据成绩动态划分难度
        if st.session_state.avg_score < 90:
            st.session_state.difficulty = "简单难度"
        elif 90 <= st.session_state.avg_score < 120:
            st.session_state.difficulty = "中等难度"
        elif 120 <= st.session_state.avg_score < 140:
            st.session_state.difficulty = "中高等难度"
        else:
            st.session_state.difficulty = "高等难度"

        with st.spinner(f"AI 正在根据中考标准（设定难度：{st.session_state.difficulty}）并排除历史词汇，为你定制考卷..."):
            st.session_state.quiz_data = generate_diagnostic_quiz(st.session_state.grade, st.session_state.avg_score)
            st.session_state.user_answers = {}
            st.session_state.wrong_list = []
            st.session_state.test_id = None
            st.session_state.vocab_plan = None
            st.session_state.step = 2
            st.rerun()

# ---------------- Step 2: 在线测试答题 ----------------
elif st.session_state.step == 2:
    st.header("Step 2: AI 诊断测试")
    st.info("💡 提示：完形填空和短文填空已拆分为独立的小题，请直接在题目下方输入或选择对应答案。")
    quiz = st.session_state.quiz_data
    
    for q in quiz.get("questions", []):
        st.markdown("---")
        st.subheader(f"题目 {q.get('id', '*')} ({q.get('category', '未知')})")
        
        if q.get("context"):
            st.info(q["context"])
            
        st.write(q.get("question", ""))
        
        if q.get("type") == "radio":
            options = q.get("options", ["A", "B", "C", "D"])
            st.session_state.user_answers[q["id"]] = st.radio("请选择正确答案：", options, key=f"q_{q['id']}", index=None)
        else:
            st.session_state.user_answers[q["id"]] = st.text_input(f"请输入答案：", key=f"q_{q['id']}")
    
    if st.button("交卷并获取诊断报告"):
        st.session_state.step = 3
        st.rerun()

# ---------------- Step 3: 对答案与诊断报告 ----------------
elif st.session_state.step == 3:
    st.header("Step 3: 答题解析与诊断报告")
    quiz = st.session_state.quiz_data
    st.session_state.wrong_list = []
    correct_count = 0
    total_count = len(quiz.get("questions", []))

    st.subheader("📝 答案核对")
    # 遍历核对答案并向用户展示，已修复“盲判”引起的困惑
    for q in quiz.get("questions", []):
        st.markdown(f"**第 {q.get('id', '*')} 题 ({q.get('category', '')})**")
        
        # 【Bug 修复】展现原题语境，避免学生不知道系统在判哪道题
        st.info(f"题目原文：{q.get('question', '')}")
        
        u_ans = str(st.session_state.user_answers.get(q["id"], "")).strip()
        c_ans = str(q.get("correct_answer", "")).strip()
        
        # 简单比对逻辑
        if u_ans.lower() == c_ans.lower() or (u_ans and u_ans in c_ans):
            correct_count += 1
            st.success(f"✅ 你的答案: {u_ans} (正确)")
        else:
            st.error(f"❌ 你的答案: {u_ans if u_ans else '未作答'} | 正确答案: {c_ans}")
            st.session_state.wrong_list.append(f"题型：[{q.get('category')}] 原题/考点：{q.get('question')} | 正确答案：{c_ans} | 学生错答：{u_ans}")

    st.markdown("---")
    st.subheader("📊 综合能力诊断报告 (各维度满分10分)")
    with st.spinner("正在生成多维度打分与诊断报告，并同步至云端..."):
        report_data = generate_diagnostic_report(st.session_state.wrong_list, correct_count, total_count)
        report_text = report_data.get("report", "报告生成完成。")
        st.info(report_text)
        
        # 【数据库接入】保存本次测试成绩，生成唯一 test_id
        if not st.session_state.test_id:
            st.session_state.test_id = db_service.save_test_record(
                grade=st.session_state.grade,
                score=st.session_state.avg_score,
                difficulty=st.session_state.difficulty,
                correct_count=correct_count,
                total_count=total_count,
                report_json=report_data
            )

    # 提供进入复习单词阶段的按钮
    st.markdown("---")
    st.write("诊断看完啦？让我们针对你的错题，生成专属的词汇复习计划！云端已就绪，支持一键排版导出，方便带去学校复习。")
    if st.button("🚀 生成 5 天提分词汇表"):
        st.session_state.step = 4
        st.rerun()

# ---------------- Step 4: 5天提分词汇表 ----------------
elif st.session_state.step == 4:
    st.header("Step 4: 专属 5 天提分词汇表")
    
    # 【Bug 修复】加入 Try-Except 和判空逻辑，拦截 AI 静默崩溃
    if not st.session_state.vocab_plan:
        try:
            with st.spinner("正在结合错题与历史数据，生成中..."):
                vocab_plan = generate_5day_vocab_plan(st.session_state.wrong_list, st.session_state.difficulty)
                
                if not vocab_plan or "plan" not in vocab_plan:
                    raise ValueError("AI 返回了无法解析的空数据格式。")
                
                st.session_state.vocab_plan = vocab_plan
                
                # 【数据库接入】后台静默保存生成的词汇表，关联刚才的测试成绩
                if st.session_state.test_id:
                    db_service.save_vocab_plan(st.session_state.test_id, vocab_plan)
                    
        except Exception as e:
            st.error(f"⚠️ AI 生成中断，请点击下方按钮重新生成。报错详情：{e}")
            if st.button("🔄 重新尝试生成词汇表"):
                st.rerun()
            st.stop() # 阻止代码往下运行渲染空页面

    st.success(f"生成成功！已自动存入云端数据库，你可以随时导出并打印纸质版。\n\n"
               f"本次生成已根据水平（{st.session_state.difficulty}）滤除了已掌握词汇，严格遵循了 4 短语 + 6 单词结构！")

    plan = st.session_state.vocab_plan.get("plan", {})
    for day, items in plan.items():
        with st.expander(f"📅 {day} 学习任务", expanded=True):
            for item in items:
                # 区分词汇和短语的不同展示
                item_type = "📘 单词" if item.get("type") == "word" else "📙 短语"
                st.markdown(f"### {item_type}：**{item.get('word', '')}** {item.get('pronunciation', '')} `[{item.get('pos', '')}]` {item.get('meaning', '')}")
                
                # 展示词性变体
                if item.get("variants") and item.get("variants") != "无":
                    st.markdown(f"🔄 **词性拓展：** `{item.get('variants', '')}`")
                
                st.info(f"💡 **中考微提示：** {item.get('micro_tip', '')}")
                st.write(f"🧮 **核心结构：** {item.get('formula', '')}")
                st.caption(f"📝 **实战微句：** {item.get('sentence', '')}")
                st.divider()

    st.markdown("---")
    if st.button("重新开启一轮新测试"):
        st.session_state.step = 1
        st.session_state.quiz_data = None
        st.session_state.vocab_plan = None
        st.session_state.test_id = None
        st.rerun()
