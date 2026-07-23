import streamlit as st
from ai_service import generate_diagnostic_quiz, generate_5day_vocab_plan, generate_diagnostic_report
import db_service  # 引入新建立的数据库大管家
import re

st.set_page_config(page_title="AI 英语智能辅导", page_icon="🎓", layout="wide")
st.title("🎓 中考英语 AI 智能诊断与自适应提分系统")

# ---------------- 初始化所有的全局状态 ----------------
if "step" not in st.session_state:
    st.session_state.step = 1
if "quiz_data" not in st.session_state:
    st.session_state.quiz_data = None
if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}
if "wrong_list" not in st.session_state:
    st.session_state.wrong_list = []
if "test_id" not in st.session_state:
    st.session_state.test_id = None
if "vocab_plan" not in st.session_state:
    st.session_state.vocab_plan = None
if "vocab_data" not in st.session_state:
    st.session_state.vocab_data = None # 用于存储当前生成的 50 个考点词汇

# ---------------- 侧边栏：词汇表中心 (Vocab Plan Center) ----------------
with st.sidebar:
    st.header("📚 词汇表中心")
    st.info("在这里可以回看你曾经生成过的专属提分词汇表。")
    
    history_list = db_service.get_vocab_plan_history_list()
    if history_list:
        options = ["(请选择历史词汇表)"] + list(history_list.keys())
        # 格式化下拉菜单显示为时间戳
        selected_plan_id = st.selectbox(
            "查看历史词汇表记录", 
            options, 
            format_func=lambda x: f"生成时间: {history_list[x]}" if x in history_list else x
        )
        
        if selected_plan_id != "(请选择历史词汇表)":
            st.success(f"当前展示词汇表生成时间：{history_list[selected_plan_id]}")
            
            # ---------------- 👇 新增：一键删除按钮 👇 ----------------
            if st.button("🗑️ 删除此词汇表记录", use_container_width=True):
                if db_service.delete_vocab_plan(selected_plan_id):
                    st.toast("✅ 词汇表已成功删除！", icon="🎉")
                    st.rerun() # 重新加载页面，自动刷新下拉列表
                else:
                    st.error("❌ 删除失败，请检查数据库连接。")
            # ---------------- 👆 新增结束 👆 ----------------
            # 直接从数据库拉取完整的详情数据
            try:
                res = db_service.db.table("vocab_plans").select("*").eq("test_id", selected_plan_id).order("day_label").execute()
                if res.data:
                    # 按天分组展示
                    days_data = {}
                    for row in res.data:
                        day = row["day_label"]
                        if day not in days_data:
                            days_data[day] = []
                        days_data[day].append(row)
                        
                    for day, items in days_data.items():
                        with st.expander(f"📅 {day} 历史记录", expanded=False):
                            for item in items:
                                item_type = "📘 单词" if item.get("type") == "word" else "📙 短语"
                                st.markdown(f"**{item_type}：{item.get('word', '')}** {item.get('pronunciation', '')}")
                                st.write(f"{item.get('pos_and_meaning', '')}")
                                if item.get("variants") and item.get("variants") != "无":
                                    st.markdown(f"🔄 **词性拓展：** `{item.get('variants', '')}`")
                                st.info(f"💡 **中考微提示：** {item.get('micro_tip', '')}")
                                st.write(f"🧮 **核心结构：** {item.get('formula', '')}")
                                st.caption(f"📝 **实战微句：** {item.get('sentence', '')}")
                                st.divider()
            except Exception as e:
                st.error("读取历史详情失败。")
    else:
        st.write("暂无历史词汇表生成记录。")


# ---------------- Step 1: 核心参数与模式选择 ----------------
if st.session_state.step == 1:
    st.header("Step 1: 定制你的专属训练模式")
    
    # 极简 UI：只保留词汇库和模式选择
    vocab_bank = st.selectbox("1️⃣ 选择出题词汇库", ["初中中考词汇 (默认)"])
    
    st.markdown("### 2️⃣ 选择测试模式")
    test_mode = st.radio(
        "决定 AI 如何为你选取考核词汇：", 
        ["🎯 错题提分特训 (优先从错题本抽词)", 
         "🌟 全新话题诊断 (从词库抓取全新话题)", 
         "📚 历史词汇表特训 (指定某份历史词汇表进行复测)"],
        index=0
    )
    
    train_plan_id = None
    if test_mode.startswith("📚"):
        if not history_list:
            st.warning("⚠️ 你还没有生成过词汇表，请先完成一次测试并生成词汇表后，再使用此模式。")
            st.stop()
        else:
            train_plan_id = st.selectbox(
                "请选择你要复测的历史词汇表：", 
                list(history_list.keys()), 
                format_func=lambda x: history_list[x]
            )

    if st.button("🚀 生成 AI 专属测试卷", use_container_width=True):
        with st.spinner("正在联动数据库调取精选词汇，AI 正在努力编撰考卷中..."):
            # 1. 获取防重黑名单
            blacklist = db_service.get_recent_blacklisted_words(limit=50)
            
            # 2. 根据模式抓取 35单词 + 15短语
            if test_mode.startswith("🎯"):
                st.session_state.vocab_data = db_service.get_training_vocabulary("wrong_focus", blacklist)
            elif test_mode.startswith("🌟"):
                st.session_state.vocab_data = db_service.get_training_vocabulary("fresh", blacklist)
            else:
                st.session_state.vocab_data = db_service.get_vocab_plan_by_id(train_plan_id)
            
            # 3. 将抓取的专属词库发给 AI 出题
            st.session_state.quiz_data = generate_diagnostic_quiz(st.session_state.vocab_data)
            
            # 状态重置与推进
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
    
    if st.button("📝 交卷并获取诊断报告", type="primary", use_container_width=True):
        st.session_state.step = 3
        st.rerun()

# ---------------- Step 3: 对答案、诊断与错题闭环 ----------------
elif st.session_state.step == 3:
    st.header("Step 3: 答题解析与诊断报告")
    quiz = st.session_state.quiz_data
    st.session_state.wrong_list = []
    correct_count = 0
    total_count = len(quiz.get("questions", []))

    st.subheader("📝 答案核对及错题入库")
    for q in quiz.get("questions", []):
        st.markdown(f"**第 {q.get('id', '*')} 题 ({q.get('category', '')})**")
        st.info(f"题目原文：{q.get('question', '')}")
        
        u_ans = str(st.session_state.user_answers.get(q["id"], "")).strip()
        raw_c_ans = str(q.get("correct_answer", "")).strip(" .,!?")
        
        # 1. 将 AI 给出的正确答案按斜杠、逗号、顿号进行拆分，生成“允许的答案列表”
        import re
        acceptable_answers = [a.strip().lower() for a in re.split(r'[/,，、]', raw_c_ans) if a.strip()]
        
        u_ans_clean = u_ans.lower()
        
        # 2. 智能同义词比对
        is_correct = False
        if u_ans_clean:
            for cand in acceptable_answers:
                # 规则 A：完全匹配（如 "adult" == "adult"）
                # 规则 B：包含匹配（如 "成人" 属于 "成年人"，或者 "成年人" 包含 "成人"）
                if u_ans_clean == cand or (u_ans_clean in cand and len(u_ans_clean) >= 2) or (cand in u_ans_clean and len(cand) >= 2):
                    is_correct = True
                    break
        
        # 用于数据库记录的主词条（默认取第一个常见译名/单词）
        primary_word = acceptable_answers[0] if acceptable_answers else raw_c_ans
        item_type = "phrase" if " " in primary_word else "word"
        
        if is_correct:
            correct_count += 1
            st.success(f"✅ 你的答案: {u_ans} (正确) | 参考答案: {raw_c_ans} —— 🎉 已掌握此考点！")
            # 答对了，从错题本消灭
            db_service.mark_word_as_mastered(primary_word)
        else:
            st.error(f"❌ 你的答案: {u_ans if u_ans else '未作答'} | 正确答案: {raw_c_ans} —— ⚠️ 已自动录入错题本")
            # 答错了，写入错题本
            db_service.save_wrong_question(primary_word, item_type)
            st.session_state.wrong_list.append(f"题型：[{q.get('category')}] 考点：{q.get('question')} | 正确答案：{raw_c_ans} | 错答：{u_ans}")

    st.markdown("---")
    st.subheader("📊 综合能力诊断报告 (各维度满分10分)")
    with st.spinner("正在生成诊断报告，并同步测试记录至云端..."):
        report_data = generate_diagnostic_report(st.session_state.wrong_list, correct_count, total_count)
        st.info(report_data.get("report", "报告生成完成。"))
        
        # 【逻辑变更】：先生成 test_id
        if not st.session_state.test_id:
            st.session_state.test_id = db_service.save_test_record(
                grade="初中通用", score=0, difficulty="自适应模式",
                correct_count=correct_count, total_count=total_count,
                report_json=report_data
            )
            
    # 【逻辑变更】：拿到 test_id 后，统一执行错题本的数据库写入！
    if st.session_state.test_id:
        for word in mastered_words_to_update:
            db_service.mark_word_as_mastered(word)
        for word, i_type in wrong_words_to_save:
            # 现在我们有 test_id 可以传给错题库了！
            db_service.save_wrong_question(st.session_state.test_id, word, i_type)
        
        st.success("☁️ 考点状态与错题数据已成功同步至云端错题本！")

    st.markdown("---")
    st.write("🎯 **诊断完成！** 刚刚犯错的知识点都已经进入了你的云端错题本。现在，让我们把本轮测试的核心词汇打包成 5 天的复习计划吧！")
    if st.button("🚀 根据本轮考点，生成 5 天精准复习词汇表", type="primary", use_container_width=True):
        st.session_state.step = 4
        st.rerun()

# ---------------- Step 4: 5天提分词汇表 ----------------
elif st.session_state.step == 4:
    st.header("Step 4: 专属 5 天 (35词+15短语) 提分词汇表")
    
    if not st.session_state.vocab_plan:
        try:
            with st.spinner("正在按照 [7单词 + 3短语] 的严苛标准生成专属排版中，请稍候..."):
                # 注意：这里我们使用刚才在 Step 1 抓好并考查过的 50 个核心词汇发给 AI 生成复习排版
                plan_vocab_data = st.session_state.vocab_data
                
                # 如果因为某种原因没抓到，触发紧急补救抓取
                if not plan_vocab_data:
                    plan_vocab_data = db_service.get_training_vocabulary("wrong_focus", db_service.get_recent_blacklisted_words(50))
                
                vocab_plan = generate_5day_vocab_plan(plan_vocab_data)
                
                if not vocab_plan or "plan" not in vocab_plan:
                    raise ValueError("AI 返回了无法解析的空数据格式。")
                
                st.session_state.vocab_plan = vocab_plan
                
                if st.session_state.test_id:
                    db_service.save_vocab_plan(st.session_state.test_id, vocab_plan)
                    
        except Exception as e:
            st.error(f"⚠️ AI 生成排版时中断，请点击下方按钮重新生成。报错详情：{e}")
            if st.button("🔄 重新尝试生成排版"):
                st.rerun()
            st.stop()

    # 此处利用 datetime 动态获取当前时间展示给用户看 (仅前端展示，数据库有真正的 created_at)
    from datetime import datetime
    current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    st.success(f"✅ 生成成功！当前生成时间：**{current_time_str}**\n\n"
               f"计划已自动存入云端，你随时可以在左侧【词汇表中心】回看。内容严格遵循了每日 7 单词 + 3 短语结构！")

    plan = st.session_state.vocab_plan.get("plan", {})
    for day, items in plan.items():
        with st.expander(f"📅 {day} 学习任务", expanded=True):
            for item in items:
                # 区分词汇和短语的不同展示，强制维持原格式！
                item_type = "📘 单词" if item.get("type") == "word" else "📙 短语"
                st.markdown(f"### {item_type}：**{item.get('word', '')}** {item.get('pronunciation', '')} `[{item.get('pos', '')}]` {item.get('meaning', '')}")
                
                if item.get("variants") and item.get("variants") != "无":
                    st.markdown(f"🔄 **词性拓展：** `{item.get('variants', '')}`")
                
                st.info(f"💡 **中考微提示：** {item.get('micro_tip', '')}")
                st.write(f"🧮 **核心结构：** {item.get('formula', '')}")
                st.caption(f"📝 **实战微句：** {item.get('sentence', '')}")
                st.divider()

    st.markdown("---")
    if st.button("🔁 开启一轮新测试", use_container_width=True):
        st.session_state.step = 1
        st.session_state.quiz_data = None
        st.session_state.vocab_plan = None
        st.session_state.test_id = None
        st.session_state.vocab_data = None
        st.rerun()
