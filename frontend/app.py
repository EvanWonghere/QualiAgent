# frontend/app.py
import streamlit as st
import requests

# --- Streamlit UI ---
st.set_page_config(layout="wide")

# 将API URL输入框移到侧边栏，避免占用主屏幕空间
st.sidebar.header("API 配置")
API = st.sidebar.text_input("API base URL", value="http://localhost:8000").rstrip("/")

st.title("Qualitative Research Agent")
st.markdown("---")

# =====================================================================
# 功能操作区 (侧边栏)
# =====================================================================

st.sidebar.title("操作菜单")

# --- AI 分析工作流 ---
with st.sidebar.expander("🤖 AI 分析操作", expanded=False):
    st.subheader("上传数据集 (用于 AI 分析)")
    with st.form("ai_upload_form"):
        dataset_name = st.text_input("数据集名称", value=f"analysis-project-1")
        ai_uploaded_file = st.file_uploader("选择 .txt 或 .docx 文件", type=["txt", "docx"], key="ai_uploader")
        ai_submitted = st.form_submit_button("上传并处理")

    if ai_submitted and ai_uploaded_file:
        files = {"file": (ai_uploaded_file.name, ai_uploaded_file.getvalue())}
        st.info("🔄 正在上传并处理数据集，请稍候...")
        # 这个请求会调用后端的 /upload/ 路由
        res = requests.post(f"{API}/upload/", data={"name": dataset_name}, files=files)
        if res and res.status_code == 200:
            st.success("数据集处理成功！")
            st.rerun()
        else:
            st.error("数据集上传失败。")
            if res: st.code(res.text)


# --- 手动编码工作流 ---
with st.sidebar.expander("✍️ 手动编码操作", expanded=True):
    # --- 功能1: 上传 Transcript ---
    st.subheader("1. 上传 Transcript")
    manual_uploaded_file = st.file_uploader("选择 .txt 或 .docx 文件", type=["txt", "docx"], key="transcript_uploader")
    if manual_uploaded_file:
        files = {'file': (manual_uploaded_file.name, manual_uploaded_file.getvalue(), manual_uploaded_file.type)}
        if st.button("确认上传 Transcript"):
            res = requests.post(f"{API}/transcripts/upload", files=files)
            if res.status_code == 200:
                st.success(f"Transcript '{manual_uploaded_file.name}' 上传成功!")
                st.rerun()
            else:
                st.error("上传失败。")
                st.code(res.text)

    # --- 功能2: 添加 Memo ---
    st.subheader("2. 添加 Memo")
    with st.form("add_memo_form"):
        memo_title = st.text_input("Memo 标题")
        memo_content = st.text_area("Memo 内容")
        memo_submitted = st.form_submit_button("保存 Memo")
        if memo_submitted and memo_title and memo_content:
            payload = {"title": memo_title, "content": memo_content}
            res = requests.post(f"{API}/memos", json=payload)
            if res.status_code == 200:
                st.success("Memo 保存成功!")
                st.rerun()
            else:
                st.error("保存 Memo 失败。")
                st.code(res.text)

    st.markdown("---")

    # --- 功能3: 添加 Code ---
    st.subheader("3. 添加新编码")
    try:
        transcripts_res = requests.get(f"{API}/transcripts")
        memos_res = requests.get(f"{API}/memos")
        transcripts = transcripts_res.json() if transcripts_res.status_code == 200 else []
        memos = memos_res.json() if memos_res.status_code == 200 else []

        with st.form("add_code_form"):
            code = st.text_input("Code Label", key="code_label")
            excerpt = st.text_area("Excerpt", key="code_excerpt")
            source_type = st.radio("Source Type", ["Transcript", "Memo"], key="code_source_type")
            source_id, choice = None, None

            if source_type == "Transcript":
                if transcripts and isinstance(transcripts, list) and (not transcripts or isinstance(transcripts[0], dict)):
                    choice = st.selectbox("选择 Transcript", transcripts, format_func=lambda t: t.get("title", f"ID: {t.get('id', 'N/A')}"))
                    if choice: source_id = choice.get("id")
                else: st.warning("无可用 Transcripts。")
            elif source_type == "Memo":
                if memos and isinstance(memos, list) and (not memos or isinstance(memos[0], dict)):
                    choice = st.selectbox("选择 Memo", memos, format_func=lambda m: m.get("title", f"ID: {m.get('id', 'N/A')}"))
                    if choice: source_id = choice.get("id")
                else: st.warning("无可用 Memos。")

            code_submitted = st.form_submit_button("添加 Code")
            if code_submitted:
                if code and excerpt and source_id:
                    payload = {"code": code, "excerpt": excerpt, "transcript_id": source_id if source_type == "Transcript" else None, "memo_id": source_id if source_type == "Memo" else None}
                    res = requests.post(f"{API}/codes", json=payload)
                    if res.status_code == 200:
                        st.success("编码添加成功！")
                        st.rerun()
                    else:
                        st.error("添加编码失败。"); st.code(res.text)
                else:
                    st.warning("请确保所有字段都已填写/选择。")

    except requests.exceptions.RequestException as e:
        st.sidebar.error(f"无法连接到 API: {e}")


# =====================================================================
# 数据展示区 (主页面)
# =====================================================================

tab1, tab2 = st.tabs(["🤖 AI 分析与搜索", "✍️ 手动编码管理"])

with tab1:
    st.header("数据集 AI 分析")
    st.info("这里的功能是对通过侧边栏“AI分析操作”上传的`数据集 (Dataset)` 进行分析。")

    # --- 查看所有数据集 ---
    st.subheader("所有数据集 (Datasets)")
    if st.button("刷新数据集列表"):
        try:
            res = requests.get(f"{API}/datasets/")
            if res.status_code == 200:
                st.json(res.json())
            else:
                st.error("获取失败"); st.code(res.text)
        except Exception as e:
            st.error(f"请求失败: {e}")

    st.divider()

    # --- 运行分析 (聚合编码) ---
    st.subheader("运行分析 (AI 自动编码)")
    analyze_ds_id = st.number_input("输入要分析的数据集 ID", min_value=1, step=1, key="analyze_id")
    if st.button("开始分析"):
        with st.spinner("正在调用 AI进行分析，请稍候..."):
            try:
                res = requests.post(f"{API}/analyze/{int(analyze_ds_id)}")
                if res.status_code == 200:
                    st.success("分析完成！")
                    st.json(res.json())
                else:
                    st.error("分析失败"); st.code(res.text)
            except Exception as e:
                st.error(f"请求失败: {e}")

    st.divider()

    # --- 搜索查询 ---
    st.subheader("语义搜索查询")
    search_ds_id = st.number_input("输入要搜索的数据集 ID", min_value=1, step=1, key="search_id")
    query = st.text_input("输入你的问题或关键词")
    k = st.slider("返回最相关的 K 个结果", 1, 10, 5)
    if st.button("搜索"):
        with st.spinner("正在进行语义搜索..."):
            try:
                params = {"dataset_id": int(search_ds_id), "q": query, "k": k}
                res = requests.get(f"{API}/search/", params=params)
                if res.status_code == 200:
                    st.success("搜索完成！")
                    st.json(res.json())
                else:
                    st.error("搜索失败"); st.code(res.text)
            except Exception as e:
                st.error(f"请求失败: {e}")

    st.divider()

    # --- AI 生成 Memo ---
    st.subheader("AI 生成备忘录 (Memo)")
    memo_ds_id = st.number_input("输入用于生成备忘录的数据集 ID", min_value=1, step=1, key="memo_ds_id")
    if st.button("生成备忘录"):
        with st.spinner("正在调用 AI 生成备忘lit, 请稍候..."):
            try:
                res = requests.post(f"{API}/memo/{int(memo_ds_id)}")
                if res.status_code == 200:
                    st.success("备忘录生成成功！")
                    st.json(res.json())
                else:
                    st.error("生成失败"); st.code(res.text)
            except Exception as e:
                st.error(f"请求失败: {e}")


with tab2:
    st.header("所有手动编码 (Codes)")
    st.info("这里展示的是通过侧边栏“手动编码操作”创建的所有`编码 (Codes)`。")

    try:
        res = requests.get(f"{API}/codes")
        if res.status_code == 200:
            codes = res.json()
            if not codes:
                st.info("暂无编码。请在左侧侧边栏添加。")

            for c in codes:
                source_info = f"Transcript ID: {c.get('transcript_id')}" if c.get('transcript_id') else f"Memo ID: {c.get('memo_id')}"
                with st.container(border=True):
                    st.markdown(f"**Code:** `{c.get('code', 'N/A')}`")
                    st.markdown(f"**Excerpt:**\n> {c.get('excerpt', '')}")
                    col1, col2 = st.columns([0.8, 0.2])
                    with col1:
                        st.caption(f"Source: {c.get('source')} | DB ID: {c.get('id')}")
                    with col2:
                        if st.button("删除", key=f"delete_{c.get('id')}", use_container_width=True, type="secondary"):
                            delete_res = requests.delete(f"{API}/codes/{c.get('id')}")
                            if delete_res.status_code == 200:
                                st.rerun()
                            else:
                                st.error("删除失败")
        else:
            st.error("获取编码列表失败。")
            st.code(res.text)
    except requests.exceptions.RequestException as e:
        st.error(f"无法连接到 API 获取编码列表: {e}")