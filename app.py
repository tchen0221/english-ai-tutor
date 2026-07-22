import streamlit as st
from ai_service import generate_diagnostic_quiz, generate_5day_vocab_plan, generate_diagnostic_report

st.set_page_config(page_title="AI 英语智能辅导", page_icon="🎓")
st.title("🎓 初中英语 AI 智能诊断与提分系统")

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

# ---------------- Step 1: 基础情况收集 ----------------
if st.session_state.step == 1:
    st.header("Step 1: 个人学习档案")
    grade = st.selectbox("当前就读年级", ["初一", "初二", "初三"])
    # 满分修改为150分
    avg_score = st.number_input("日常英语平均分（满分150分）", min_value=0, max_value=150, value=90)
    
    if st.button("生成 AI 诊断测试卷"):
        # 根据成绩动态划分难度
        if avg_score < 90:
            st.session_state.difficulty = "简单难度"
        elif 90 <= avg_score < 120:
            st.session_state.difficulty = "中等难度"
        elif 120 <= avg_score < 140:
            st.session_state.difficulty = "中高等难度"
        else:
            st.session_state.difficulty = "高等难度"

        with st.spinner(f"AI 正在根据中考标准（设定难度：{st.session_state.difficulty}）为你定制考卷..."):
            st.session_state.quiz_data = generate_diagnostic_quiz(grade, avg_score)
            st.session_state.user_answers = {}
            st.session_state.wrong_list = []
            st.session_state.step = 2
            st.rerun()

# ---------------- Step 2: 在线测试答题 ----------------
elif st.session_state.step == 2:
    st.header("Step 2: AI 诊断测试")
    st.info("💡 提示：完形填空和短文填空已拆分为独立的小题，请直接在题目下方输入或选择对应答案。")
    quiz = st.session_state.quiz_data
    
    for q in quiz.get("questions", []):
        st.markdown("---")
        st.subheader(f"题目 {q['id']} ({q['category']})")
        
        if q.get("context"):
            st.info(q["context"])
            
        st.write(q["question"])
        
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
    # 遍历核对答案并向用户展示
    for q in quiz.get("questions", []):
        u_ans = str(st.session_state.user_answers.get(q["id"], "")).strip()
        c_ans = str(q.get("correct_answer", "")).strip()
        
        # 简单比对逻辑
        if u_ans.lower() == c_ans.lower() or (u_ans and u_ans in c_ans):
            correct_count += 1
            st.success(f"✅ 题目 {q['id']} | 你的答案: {u_ans} (正确)")
        else:
            st.error(f"❌ 题目 {q['id']} | 你的答案: {u_ans if u_ans else '未作答'} | 正确答案: {c_ans}")
            st.session_state.wrong_list.append(f"题型：[{q['category']}] 原题/考点：{q['question']} | 正确答案：{c_ans} | 学生错答：{u_ans}")

    st.markdown("---")
    st.subheader("📊 综合能力诊断报告 (各维度满分10分)")
    with st.spinner("正在生成多维度打分与诊断报告..."):
        report_data = generate_diagnostic_report(st.session_state.wrong_list, correct_count, total_count)
        st.info(report_data.get("report", "报告生成完成。"))

    # 提供进入复习单词阶段的按钮
    st.markdown("---")
    st.write("诊断看完啦？让我们针对你的错题，生成专属的词汇复习计划吧！")
    if st.button("🚀 生成复习单词表"):
        st.session_state.step = 4
        st.rerun()

# ---------------- Step 4: 5天提分词汇表 ----------------
elif st.session_state.step == 4:
    st.header("Step 4: 专属 5 天提分词汇表")
    st.success(f"已根据你的错题和当前水平（{st.session_state.difficulty}）自动滤除了已掌握词汇，合并了同根词，生成了最高效的复习计划！")

    with st.spinner("正在抓取中考题库并匹配你的错题..."):
        vocab_plan = generate_5day_vocab_plan(st.session_state.wrong_list, st.session_state.difficulty)
        
    plan = vocab_plan.get("plan", {})
    for day, items in plan.items():
        with st.expander(f"📅 {day} 学习任务", expanded=True):
            for item in items:
                st.markdown(f"### 🔹 **{item.get('word', '')}** {item.get('pronunciation', '')} `[{item.get('pos', '')}]` {item.get('meaning', '')}")
                
                # 新增：展示词性变体
                if item.get("variants") and item.get("variants") != "无":
                    st.markdown(f"🔄 **词性拓展：** `{item.get('variants', '')}`")
                
                st.info(f"💡 **中考微提示：** {item.get('micro_tip', '')}")
                st.write(f"🧮 **核心词块：** {item.get('formula', '')}")
                st.caption(f"📝 **实战微句：** {item.get('sentence', '')}")
                st.divider()

    if st.button("重新开启一轮新测试"):
        st.session_state.step = 1
        st.session_state.quiz_data = None
        st.rerun()
