import streamlit as st
from ai_service import generate_module_1, generate_module_2, generate_module_3, generate_5day_vocab_plan, generate_diagnostic_report
import db_service  # 引入新建立的数据库
import re
import concurrent.futures

st.set_page_config(page_title="AI 英语智能辅导", page_icon="🎓", layout="wide")
st.title("🎓 英语 AI 智能诊断与自适应提分系统")

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
if "current_page" not in st.session_state:
    st.session_state.current_page = 1  # 新增：用于控制 Step 2 的模块闯关进度

# 👇 核心新增：定义随手记生词的回调函数 👇
def handle_spontaneous_word():
    # 从 session_state 中安全获取输入的值
    word = st.session_state.get("spontaneous_word_input", "").strip()
    if word:
        # 调用 db_service 中的新接口静默写入
        db_service.add_spontaneous_word(word)
        st.toast(f"✅ 已成功将【{word}】收入错题本！", icon="🧲")
        # 清空输入框，准备迎接下一个生词
        st.session_state.spontaneous_word_input = ""
# 👆 新增结束 👆

# 提前拉取历史词汇表列表，因为不仅侧边栏需要，第一关的“历史词汇表特训”模式也需要它
history_list = db_service.get_vocab_plan_history_list()

# ---------------- 👇 全新重构的侧边栏导航 👇 ----------------
with st.sidebar:
    st.header("🧭 系统导航")
    st.markdown("请选择你需要进入的功能模块：")
    
    # 视图选择器
    view_selection = st.radio(
        label="功能菜单",
        options=["🏠 核心测试中心", "📓 我的错题本", "📚 历史词汇表"],
        label_visibility="collapsed"
    )
    
    st.divider()
    st.info("💡 **系统提示**\n\n测试过程中请勿随意切换左侧菜单，以免丢失当前答题进度。")


# ==============================================================================
# 视图 1：核心测试中心 (保留原有闭环逻辑，整体缩进一层)
# ==============================================================================
if view_selection == "🏠 核心测试中心":
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
            with st.spinner("正在联动数据库调取精选词汇，AI 正在努力编撰考卷中（分模块并发生成中）..."):
                # 1. 获取防重黑名单
                blacklist = db_service.get_recent_blacklisted_words(limit=50)
                
                # 2. 根据模式抓取 35单词 + 15短语
                if test_mode.startswith("🎯"):
                    st.session_state.vocab_data = db_service.get_training_vocabulary("wrong_focus", blacklist)
                elif test_mode.startswith("🌟"):
                    st.session_state.vocab_data = db_service.get_training_vocabulary("fresh", blacklist)
                else:
                    st.session_state.vocab_data = db_service.get_vocab_plan_by_id(train_plan_id)
                
                # 【核心架构更新】：物理切分词库，切断泄题可能
                words = st.session_state.vocab_data.get("words", [])
                phrases = st.session_state.vocab_data.get("phrases", [])
                
                chunk_a = {"words": words[:15], "phrases": []}
                chunk_b = {"words": words[15:25], "phrases": phrases[:10]}
                chunk_c = {"words": words[25:35], "phrases": phrases[10:15]}
                
                # 3. 引入多线程并发机制，三间独立小黑屋同时向 AI 派发任务（速度提升 3 倍！）        
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    # 同时提交三个互相绝缘的生成任务
                    future1 = executor.submit(generate_module_1, chunk_a)
                    future2 = executor.submit(generate_module_2, chunk_b)
                    future3 = executor.submit(generate_module_3, chunk_c)
                    
                    # 统一回收结果（只等待最慢的那一个，整体耗时将被压缩到 ~40-50 秒）
                    mod1 = future1.result()
                    mod2 = future2.result()
                    mod3 = future3.result()
                
                # 4. 合并试卷并重新编排 ID，使之依然是一个完整的试卷
                all_questions = mod1.get("questions", []) + mod2.get("questions", []) + mod3.get("questions", [])
                for i, q in enumerate(all_questions, 1):
                    q["id"] = str(i)
                    
                st.session_state.quiz_data = {"questions": all_questions}
                
                # 状态重置与推进
                st.session_state.user_answers = {}
                st.session_state.wrong_list = []
                st.session_state.test_id = None
                st.session_state.vocab_plan = None
                st.session_state.step = 2
                st.session_state.current_page = 1 # 从模块一开始
                st.rerun()

    # ---------------- Step 2: 在线测试答题 (分模块展示) ----------------
    elif st.session_state.step == 2:
        st.header("Step 2: AI 诊断测试")
        st.info("💡 提示：完形填空和短文填空已拆分为独立的小题，请直接在题目下方输入或选择对应答案。")
        
        # 👇 核心修改：双管齐下的移动端友好版生词捕获器 👇
        with st.expander("🧲 随手记生词捕获器 (遇到生词？一键收录错题本)", expanded=True):
            st.markdown("在阅读文章时如果遇到超纲生词，在此输入或粘贴：")
            
            # 使用 4:1 的比例进行左右排版，完美适配手机屏幕
            col_in, col_btn = st.columns([4, 1])
            with col_in:
                st.text_input(
                    "生词",
                    key="spontaneous_word_input",
                    on_change=handle_spontaneous_word,
                    placeholder="例如输入 environment...",
                    label_visibility="collapsed" # 隐藏多余的标签以对齐按钮
                )
            with col_btn:
                # 按钮绑定相同的回调函数
                st.button("📥 立即收录", on_click=handle_spontaneous_word, use_container_width=True)
        # 👆 新增结束 👆

        quiz = st.session_state.quiz_data
        questions = quiz.get("questions", [])
        
        # 假分页逻辑：根据 current_page 提取对应的题目切片
        if st.session_state.current_page == 1:
            st.subheader("🚩 第一关：词汇识记 (第 1 - 10 题)")
            current_qs = questions[0:10]
        elif st.session_state.current_page == 2:
            st.subheader("🚩 第二关：语法与搭配 (第 11 - 22 题)")
            current_qs = questions[10:22]
        else:
            st.subheader("🚩 第三关：语篇综合实战 (第 23 - 32 题)")
            current_qs = questions[22:32]

        # 渲染当前模块的题目
        for q in current_qs:
            st.markdown("---")
            st.markdown(f"**题目 {q.get('id', '*')} ({q.get('category', '未知')})**")
            
            if q.get("context"):
                st.info(q["context"])
                
            st.write(q.get("question", ""))
            
            if q.get("type") == "radio":
                options = q.get("options", ["A", "B", "C", "D"])
                # 保留用户的历史选择
                saved_val = st.session_state.user_answers.get(q["id"])
                idx = options.index(saved_val) if saved_val in options else None
                st.session_state.user_answers[q["id"]] = st.radio("请选择正确答案：", options, key=f"q_{q['id']}", index=idx)
            else:
                saved_val = st.session_state.user_answers.get(q["id"], "")
                st.session_state.user_answers[q["id"]] = st.text_input(f"请输入答案：", value=saved_val, key=f"q_{q['id']}")
        
        st.markdown("---")
        
        # 底部导航按钮组件
        col1, col2 = st.columns(2)
        if st.session_state.current_page == 1:
            with col2:
                if st.button("下一步：前往模块二 ➡️", use_container_width=True):
                    st.session_state.current_page = 2
                    st.rerun()
        elif st.session_state.current_page == 2:
            with col1:
                if st.button("⬅️ 返回修改模块一", use_container_width=True):
                    st.session_state.current_page = 1
                    st.rerun()
            with col2:
                if st.button("下一步：前往模块三 ➡️", use_container_width=True):
                    st.session_state.current_page = 3
                    st.rerun()
        elif st.session_state.current_page == 3:
            with col1:
                if st.button("⬅️ 返回修改模块二", use_container_width=True):
                    st.session_state.current_page = 2
                    st.rerun()
            with col2:
                if st.button("📝 提交全卷并获取诊断报告", type="primary", use_container_width=True):
                    st.session_state.step = 3
                    st.rerun()

    # ---------------- Step 3: 对答案、诊断与错题闭环 ----------------
    elif st.session_state.step == 3:
        st.header("Step 3: 答题解析与诊断报告")
        quiz = st.session_state.quiz_data
        st.session_state.wrong_list = []
        correct_count = 0
        total_count = len(quiz.get("questions", []))

        st.subheader("📝 答案核对")
        
        mastered_words_to_update = []
        wrong_words_to_save = []

        for q in quiz.get("questions", []):
            st.markdown(f"**第 {q.get('id', '*')} 题 ({q.get('category', '')})**")
            st.info(f"题目原文：{q.get('question', '')}")
            
            u_ans = str(st.session_state.user_answers.get(q["id"], "")).strip()
            raw_c_ans = str(q.get("correct_answer", "")).strip(" .,!?")
            
            acceptable_answers = [a.strip().lower() for a in re.split(r'[/,，、]', raw_c_ans) if a.strip()]
            u_ans_clean = u_ans.lower()
            
            is_correct = False
            if u_ans_clean:
                for cand in acceptable_answers:
                    if u_ans_clean == cand or (u_ans_clean in cand and len(u_ans_clean) >= 2) or (cand in u_ans_clean and len(cand) >= 2):
                        is_correct = True
                        break
            
            # 👇 【核心升级：AI 溯源考点提取】
            tested_word_from_ai = q.get("tested_word", "").strip()
            
            if tested_word_from_ai:
                primary_word = tested_word_from_ai
            else:
                # 如果 AI 偶尔漏了，启动完美兜底逻辑
                if "英译中" in q.get("category", ""):
                    primary_word = q.get("question").strip() # 英译中的英文在题干里
                else:
                    primary_word = acceptable_answers[0] if acceptable_answers else raw_c_ans
            
            # 👇 【新增拦截逻辑】：如果答案是一个长句子，不作为错题单词存入数据库
            is_sentence = len(primary_word.split()) > 4 or len(primary_word) > 30
            item_type = "phrase" if " " in primary_word else "word"
            
            if is_correct:
                correct_count += 1
                st.success(f"✅ 你的答案: {u_ans} (正确) | 参考答案: {raw_c_ans}")
                # 如果不是长句翻译，记录为已掌握单词
                if not is_sentence:
                    mastered_words_to_update.append(primary_word)
            else:
                st.error(f"❌ 你的答案: {u_ans if u_ans else '未作答'} | 正确答案: {raw_c_ans}")
                # 如果不是长句翻译，才将其加入错题库的更新列表
                if not is_sentence:
                    wrong_words_to_save.append((primary_word, item_type))
                
                st.session_state.wrong_list.append(f"题型：[{q.get('category')}] 考点：{q.get('question')} | 正确答案：{raw_c_ans} | 错答：{u_ans}")

        st.markdown("---")
        st.subheader("📊 综合能力诊断报告 (各维度满分10分)")
        with st.spinner("正在生成诊断报告，并同步测试记录至云端..."):
            report_data = generate_diagnostic_report(st.session_state.wrong_list, correct_count, total_count)
            st.info(report_data.get("report", "报告生成完成。"))
            
            if not st.session_state.test_id:
                st.session_state.test_id = db_service.save_test_record(
                    grade="初中通用", score=0, difficulty="自适应模式",
                    correct_count=correct_count, total_count=total_count,
                    report_json=report_data
                )
                
                if st.session_state.test_id:
                    for word in mastered_words_to_update:
                        db_service.mark_word_as_mastered(word)
                    for word, i_type in wrong_words_to_save:
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
                    
                    # 👇 【核心修改】：收集本次测试用过的所有词汇，传给查库逻辑作为黑名单
                    current_test_words = []
                    if st.session_state.vocab_data:
                        current_test_words = st.session_state.vocab_data.get("words", []) + st.session_state.vocab_data.get("phrases", [])
                    
                    # 动态抓取：错题库优先 (排查句子) + 新 Topic 补缺
                    plan_vocab_data = db_service.get_review_vocabulary(current_test_words)
                    
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

        from datetime import datetime
        current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        st.success(f"✅ 生成成功！当前生成时间：**{current_time_str}**\n\n"
                   f"计划已自动存入云端，你随时可以在左侧【词汇表中心】回看。内容严格遵循了每日 7 单词 + 3 短语结构！")

        plan = st.session_state.vocab_plan.get("plan", {})
        for day, items in plan.items():
            with st.expander(f"📅 {day} 学习任务", expanded=True):
                for item in items:
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
            st.session_state.current_page = 1 # 重置进度
            st.rerun()

# ==============================================================================
# 视图 2：我的错题本 (全新开发)
# ==============================================================================
elif view_selection == "📓 我的错题本":
    st.header("📓 我的错题本 (专属消灭库)")
    st.info("这里收录了你所有在历史测试中犯过错，且**尚未完全掌握**的核心知识点。\n\n如果你通过线下的复习，认为自己已经彻底搞懂了某个词汇，可以点击右侧的【✅ 已掌握】将其移出错题本。")
    
    wrong_items = db_service.get_unmastered_wrong_questions()
    
    if not wrong_items:
        st.success("🎉 太棒了！你的错题本目前空空如也，继续保持！")
    else:
        # 使用卡片式布局优美展示错题
        for item in wrong_items:
            with st.container():
                col1, col2 = st.columns([5, 2])
                with col1:
                    item_type = "📘 单词" if item.get("type") == "word" else "📙 短语"
                    
                    # 👇 核心新增：提取 error_count，并根据错误次数渲染不同级别的警告徽章
                    err_cnt = item.get("error_count") or 1 
                    if err_cnt >= 3:
                        badge = f"🔥🔥 核心痛点: 错 {err_cnt} 次"
                    elif err_cnt == 2:
                        badge = f"🔥 高频易错: 错 2 次"
                    else:
                        badge = f"⚠️ 犯错 1 次"
                        
                    st.markdown(f"**{item_type}**: &nbsp;`{item.get('word')}` &nbsp;&nbsp; **`{badge}`**")
                    
                with col2:
                    # 按钮带有独立的 key 确保操作不会冲突
                    if st.button("✅ 标记为已掌握", key=f"master_{item['id']}", use_container_width=True):
                        # 复用现有的消灭闭环接口
                        db_service.mark_word_as_mastered(item['word'])
                        st.toast(f"✅ 成功！已将 {item['word']} 移出错题本！")
                        st.rerun()
                st.divider()

# ==============================================================================
# 视图 3：历史词汇表 (从侧边栏平移过来)
# ==============================================================================
elif view_selection == "📚 历史词汇表":
    st.header("📚 历史词汇表中心")
    st.info("在这里你可以查阅以往生成的所有专属提分词汇表，支持随时回顾复习。")
    
    if history_list:
        options = ["(请选择你要查看的历史记录)"] + list(history_list.keys())
        
        # 格式化下拉菜单显示为时间戳
        selected_plan_id = st.selectbox(
            "查看历史词汇表", 
            options, 
            format_func=lambda x: f"生成时间: {history_list[x]}" if x in history_list else x
        )
        
        if selected_plan_id != "(请选择你要查看的历史记录)":
            st.success(f"当前正在展示：**{history_list[selected_plan_id]}** 生成的专属复习计划")
            
            # 删除按钮
            col_blank, col_del = st.columns([3, 1])
            with col_del:
                if st.button("🗑️ 删除此记录", use_container_width=True):
                    if db_service.delete_vocab_plan(selected_plan_id):
                        st.toast("✅ 词汇表已成功删除！", icon="🎉")
                        st.rerun() 
                    else:
                        st.error("❌ 删除失败，请检查数据库连接。")
            
            # 直接从数据库拉取完整的详情数据并渲染
            try:
                res = db_service.db.table("vocab_plans").select("*").eq("test_id", selected_plan_id).order("day_label").execute()
                if res.data:
                    days_data = {}
                    for row in res.data:
                        day = row["day_label"]
                        if day not in days_data:
                            days_data[day] = []
                        days_data[day].append(row)
                        
                    for day, items in days_data.items():
                        with st.expander(f"📅 {day} 复习任务", expanded=True):
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
        st.warning("暂无任何历史词汇表生成记录。快去【核心测试中心】完成一次测试吧！")
