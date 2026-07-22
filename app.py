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

# ---------------- Step 1: 基础情况收集 ----------------
if st.session_state.step == 1:
    st.header("Step 1: 个人学习档案")
    grade = st.selectbox("当前就读年级", ["初一", "初二", "初三"])
    avg_score = st.number_input("日常英语平均分（满分150）", min_value=0, max_value=150, value=75)
    
    if st.button("生成 AI 诊断测试卷"):
        with st.spinner("AI 严格根据中考标准为你定制考卷中，请稍候..."):
            st.session_state.quiz_data = generate_diagnostic_quiz(grade, avg_score)
            st.session_state.user_answers = {} # 清空上次答案
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
        
        # 如果大模型返回了文章上下文，渲染文章
        if q.get("context"):
            st.info(q["context"])
            
        st.write(q["question"])
        
        # 根据题型动态渲染输入框（文本输入 vs 单选题）
        if q.get("type") == "radio":
            options = q.get("options", ["A", "B", "C", "D"])
            st.session_state.user_answers[q["id"]] = st.radio("请选择正确答案：", options, key=f"q_{q['id']}", index=None)
        else:
            st.session_state.user_answers[q["id"]] = st.text_input(f"请输入答案：", key=f"q_{q['id']}")
    
    if st.button("提交试卷，获取诊断报告"):
        st.session_state.step = 3
        st.rerun()

# ---------------- Step 3: 分析错题与 5 天词汇表 ----------------
elif st.session_state.step == 3:
    st.header("Step 3: 诊断报告与提分计划")
    
    quiz = st.session_state.quiz_data
    wrong_list = []
    
    # 强制转化为字符串并检查错题（修复之前的 Bug）
    for q in quiz.get("questions", []):
        u_ans = str(st.session_state.user_answers.get(q["id"], "")).strip()
        c_ans = str(q.get("correct_answer", "")).strip()
        
        if u_ans.lower() != c_ans.lower():
            wrong_list.append(f"题型：[{q['category']}] {q['question']} | 正确答案：{c_ans} | 学生错答：{u_ans}")
            
    st.warning(f"本次测试共完成 {len(quiz.get('questions', []))} 题，发现 {len(wrong_list)} 处薄弱知识点。")
    
    # 新增特征 C：多维度诊断报告
    st.subheader("📊 综合能力诊断报告")
    with st.spinner("正在生成多维度诊断报告..."):
        report_data = generate_diagnostic_report(wrong_list)
        st.success(report_data.get("report", "报告生成完成。"))

    # 特征 D：5天高频错题词汇表
    st.subheader("🗓️ 5天高频词汇攻克计划 (基于错题+中考精选)")
    with st.spinner("正在基于错题为你量身定制专属提分词汇表..."):
        vocab_plan = generate_5day_vocab_plan(wrong_list)
        
    plan = vocab_plan.get("plan", {})
    for day, items in plan.items():
        with st.expander(f"📅 {day} 学习任务", expanded=True):
            for item in items:
                st.markdown(f"### 🔹 **{item.get('word', '')}** {item.get('pronunciation', '')} `[{item.get('pos', '')}]` {item.get('meaning', '')}")
                st.info(f"💡 **中考微提示：** {item.get('micro_tip', '')}")
                st.write(f"🧮 **核心词块公式：** {item.get('formula', '')}")
                st.caption(f"📝 **实战微句：** {item.get('sentence', '')}")
                st.divider()

    if st.button("重新测试"):
        st.session_state.step = 1
        st.rerun()
