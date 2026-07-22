import streamlit as st
from ai_service import generate_diagnostic_quiz, generate_5day_vocab_plan

st.set_page_config(page_title="AI 英语智能辅导", page_icon="🎓")
st.title("🎓 初中英语 AI 智能诊断与提分系统")

# 初始化 session 状态，控制流程切换 (Step 1 -> Step 2 -> Step 3)
if "step" not in st.session_state:
    st.session_state.step = 1
if "quiz_data" not in st.session_state:
    st.session_state.quiz_data = None
if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}

# ---------------- Step 1: 基础情况收集 ----------------
if st.session_state.step == 1:
    st.header("Step 1: 个人学习档案")
    grade = st.selectbox("当前就读年级", ["初一", "初二", "初三"])
    avg_score = st.number_input("日常英语平均分（满分120）", min_value=0, max_value=120, value=75)
    
    if st.button("生成 AI 诊断测试题"):
        with st.spinner("AI 正在根据你的情况出题中..."):
            st.session_state.quiz_data = generate_diagnostic_quiz(grade, avg_score)
            st.session_state.step = 2
            st.rerun()

# ---------------- Step 2: 在线测试答题 ----------------
elif st.session_state.step == 2:
    st.header("Step 2: AI 诊断测试")
    quiz = st.session_state.quiz_data
    
    for q in quiz.get("questions", []):
        st.subheader(f"题目 {q['id']} ({q['type']})")
        st.write(q["question"])
        st.session_state.user_answers[q["id"]] = st.text_input(f"你的答案 #{q['id']}", key=f"q_{q['id']}")
    
    if st.button("提交答案，获取诊断结果"):
        st.session_state.step = 3
        st.rerun()

# ---------------- Step 3: 分析错题与 5 天词汇表 ----------------
elif st.session_state.step == 3:
    st.header("Step 3: 诊断报告与 5 天提分词汇表")
    
    # 找出做错的题目
    quiz = st.session_state.quiz_data
    wrong_list = []
    
    for q in quiz.get("questions", []):
        u_ans = st.session_state.user_answers.get(q["id"], "").strip()
        c_ans = q["correct_answer"].strip()
        if u_ans.lower() != c_ans.lower():
            wrong_list.append(f"题目：{q['question']} | 正确答案：{c_ans} | 学生错答：{u_ans}")
            
    st.warning(f"本次测试共发现 {len(wrong_list)} 处薄弱知识点。")
    
    with st.spinner("正在基于错题为你量身定制 5 天高频词汇表..."):
        vocab_plan = generate_5day_vocab_plan(wrong_list)
        
    plan = vocab_plan.get("plan", {})
    for day, words in plan.items():
        with st.expander(f"📅 {day} 学习任务", expanded=True):
            for item in words:
                st.markdown(f"### 🔹 **{item['word']}** `{item['pos']}`")
                st.info(f"**语法&搭配：** {item['grammar']}")
                st.caption(f"**中考例句：** {item['example']}")

    if st.button("重新测试"):
        st.session_state.step = 1
        st.rerun()
