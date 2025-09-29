# frontend/app.py
import streamlit as st
import requests
import json

st.set_page_config(layout="wide")


# --- Helper Functions & Cache ---
@st.cache_data(ttl=60)  # Cache for 1 minute
def get_api_data(endpoint: str):
    """ ✨ 使用缓存获取API数据以提高性能 """
    try:
        res = requests.get(f"{st.session_state.api_url}/{endpoint}")
        if res.status_code == 200:
            return res.json()
    except requests.exceptions.RequestException as e:
        st.sidebar.error(f"Error fetching {endpoint}: {e}")
    return []


# --- Main UI ---
st.sidebar.header("API 配置")
# ✨ 使用 session_state 来存储 API URL
st.session_state.api_url = st.sidebar.text_input("API base URL", value="http://localhost:8000").rstrip("/")

st.title("Qualitative Research Agent")
st.markdown("---")

# =====================================================================
# Sidebar Actions
# =====================================================================
st.sidebar.title("操作菜单")

# --- AI Analysis Workflow ---
with st.sidebar.expander("🤖 AI 分析操作", expanded=False):
    st.subheader("上传数据集 (用于 AI 分析)")
    with st.form("ai_upload_form"):
        dataset_name = st.text_input("数据集名称", value=f"analysis-project-1")
        ai_uploaded_file = st.file_uploader("选择 .txt 或 .docx 文件", type=["txt", "docx"], key="ai_uploader")
        ai_submitted = st.form_submit_button("上传并处理")

    if ai_submitted and ai_uploaded_file:
        files = {"file": (ai_uploaded_file.name, ai_uploaded_file.getvalue())}
        with st.spinner("🔄 正在上传并处理数据集..."):
            res = requests.post(f"{st.session_state.api_url}/upload/", data={"name": dataset_name}, files=files)
            if res.status_code == 200:
                st.success("数据集处理成功！")
                st.cache_data.clear()  # 清除缓存
                st.rerun()
            else:
                st.error(f"数据集上传失败: {res.text}")

# --- Manual Coding Workflow ---
with st.sidebar.expander("✍️ 手动编码操作", expanded=True):
    # --- Upload Transcript ---
    st.subheader("1. 上传 Transcript")
    manual_uploaded_file = st.file_uploader("选择 .txt 或 .docx 文件", type=["txt", "docx"], key="transcript_uploader")
    if manual_uploaded_file and st.button("确认上传 Transcript"):
        files = {'file': (manual_uploaded_file.name, manual_uploaded_file.getvalue(), manual_uploaded_file.type)}
        with st.spinner("上传中..."):
            res = requests.post(f"{st.session_state.api_url}/transcripts/upload", files=files)
            if res.status_code == 200:
                st.success(f"Transcript '{manual_uploaded_file.name}' 上传成功!");
                st.cache_data.clear();
                st.rerun()
            else:
                st.error(f"上传失败: {res.text}")

    # --- Add Memo ---
    st.subheader("2. 添加 Memo")
    with st.form("add_memo_form"):
        memo_title = st.text_input("Memo 标题")
        memo_content = st.text_area("Memo 内容")
        if st.form_submit_button("保存 Memo"):
            if memo_title and memo_content:
                res = requests.post(f"{st.session_state.api_url}/memos",
                                    json={"title": memo_title, "content": memo_content})
                if res.status_code == 200:
                    st.success("Memo 保存成功!");
                    st.cache_data.clear();
                    st.rerun()
                else:
                    st.error(f"保存失败: {res.text}")

    st.markdown("---")
    # --- Add Code ---
    st.subheader("3. 添加新编码")
    transcripts = get_api_data("transcripts")
    memos = get_api_data("memos")

    with st.form("add_code_form"):
        code = st.text_input("Code Label", key="code_label")
        excerpt = st.text_area("Excerpt", key="code_excerpt")
        source_type = st.radio("Source Type", ["Transcript", "Memo"], key="code_source_type")
        source_id, choice = None, None

        if source_type == "Transcript":
            if transcripts:
                choice = st.selectbox("选择 Transcript", transcripts,
                                      format_func=lambda t: t.get("title", f"ID: {t.get('id', 'N/A')}")[:70])
                if choice: source_id = choice.get("id")
            else:
                st.warning("无可用 Transcripts。")
        elif source_type == "Memo":
            if memos:
                choice = st.selectbox("选择 Memo", memos,
                                      format_func=lambda m: m.get("title", f"ID: {m.get('id', 'N/A')}")[:70])
                if choice: source_id = choice.get("id")
            else:
                st.warning("无可用 Memos。")

        if st.form_submit_button("添加 Code"):
            if code and excerpt and source_id:
                payload = {"code": code, "excerpt": excerpt,
                           "transcript_id": source_id if source_type == "Transcript" else None,
                           "memo_id": source_id if source_type == "Memo" else None}
                res = requests.post(f"{st.session_state.api_url}/codes", json=payload)
                if res.status_code == 200:
                    st.success("编码添加成功!");
                    st.cache_data.clear();
                    st.rerun()
                else:
                    st.error(f"添加失败: {res.text}")
            else:
                st.warning("请确保所有字段都已填写/选择。")

# =====================================================================
# Main Page Display
# =====================================================================
tab1, tab2 = st.tabs(["🤖 AI 分析与搜索", "✍️ 手动编码管理"])

with tab1:
    st.header("数据集 AI 分析")
    st.info("对通过侧边栏“AI分析操作”上传的`数据集 (Dataset)` 进行分析。")

    st.subheader("所有数据集 (Datasets)")
    datasets = get_api_data("datasets")
    if datasets:
        st.dataframe(datasets)
    else:
        st.info("暂无数据集，请在侧边栏上传。")

    st.divider()

    st.subheader("AI 分析功能")
    if datasets:
        ds_id = st.selectbox("选择要进行分析的数据集", options=datasets,
                             format_func=lambda ds: f"{ds['id']}: {ds['name']}")
        if ds_id:
            selected_ds_id = ds_id['id']

            # --- AI Generate & Save Codes ---
            st.markdown("##### 🤖 生成并保存 AI 编码")
            if st.button("开始 AI 编码"):
                with st.spinner("正在调用 AI 分析并保存编码..."):
                    res = requests.post(f"{st.session_state.api_url}/codes/ai-generate/{selected_ds_id}")
                    if res.status_code == 200:
                        st.success(res.json().get("message", "操作成功！"));
                        st.cache_data.clear();
                        st.rerun()
                    else:
                        st.error(f"操作失败: {res.text}")

            # --- AI Generate Memo ---
            st.markdown("##### 📝 生成 AI 备忘录 (Memo)")
            if st.button("生成备忘录预览"):
                with st.spinner("正在调用 AI 生成备忘录预览..."):
                    res = requests.post(f"{st.session_state.api_url}/memo/{selected_ds_id}")
                    if res.status_code == 200:
                        st.session_state.ai_memo = res.json()  # 保存到会话状态
                    else:
                        st.error(f"生成预览失败: {res.text}")

            # ✨ 如果备忘录已生成，则显示内容和保存按钮
            if 'ai_memo' in st.session_state and st.session_state.ai_memo:
                memo_data = json.loads(st.session_state.ai_memo['content'])
                with st.container(border=True):
                    st.markdown("#### AI 生成的备忘录预览")
                    st.markdown(f"**Summary:** {memo_data.get('summary')}")
                    st.markdown("**Contradictions:**")
                    for item in memo_data.get('contradictions', []): st.markdown(f"- {item}")
                    st.markdown("**Follow-up Questions:**")
                    for item in memo_data.get('followups', []): st.markdown(f"- {item}")

                    if st.button("💾 保存此备忘录到数据库"):
                        with st.spinner("保存中..."):
                            save_res = requests.post(f"{st.session_state.api_url}/memos/ai-generate",
                                                     params={"dataset_id": selected_ds_id})
                            if save_res.status_code == 200:
                                st.success("备忘录已成功保存！");
                                del st.session_state.ai_memo;
                                st.cache_data.clear();
                                st.rerun()
                            else:
                                st.error(f"保存失败: {save_res.text}")

            st.divider()
            # --- Semantic Search ---
            st.markdown("##### 🔍 语义搜索查询")
            query = st.text_input("输入你的问题或关键词", key="search_query")
            k = st.slider("返回最相关的 K 个结果", 1, 10, 5)
            if st.button("搜索"):
                with st.spinner("正在进行语义搜索..."):
                    params = {"dataset_id": selected_ds_id, "q": query, "k": k}
                    res = requests.get(f"{st.session_state.api_url}/search/", params=params)
                    if res.status_code == 200:
                        st.success("搜索完成！")
                        st.json(res.json())
                    else:
                        st.error(f"搜索失败: {res.text}")
    else:
        st.info("请先上传一个数据集以启用 AI 分析功能。")

with tab2:
    st.header("所有手动编码 (Codes)")
    st.info("展示通过侧边栏“手动编码操作”创建的所有`编码 (Codes)`。")
    if st.button("刷新编码列表"):
        st.cache_data.clear()
        st.rerun()

    codes = get_api_data("codes")
    if not codes:
        st.info("暂无编码。请在左侧侧边栏添加。")
    else:
        for c in codes:
            with st.container(border=True):
                st.markdown(f"**Code:** `{c.get('code', 'N/A')}`")
                st.markdown(f"**Excerpt:**\n> {c.get('excerpt', '')}")
                col1, col2 = st.columns([0.8, 0.2])
                with col1:
                    # ✨ 修复了这里的bug，直接使用后端返回的 source 字段
                    st.caption(f"Source: {c.get('source', 'N/A')} | DB ID: {c.get('id')}")
                with col2:
                    if st.button("删除", key=f"delete_{c.get('id')}", use_container_width=True, type="secondary"):
                        delete_res = requests.delete(f"{st.session_state.api_url}/codes/{c.get('id')}")
                        if delete_res.status_code == 200:
                            st.cache_data.clear();
                            st.rerun()
                        else:
                            st.error("删除失败")