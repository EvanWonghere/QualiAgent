# frontend/app.py
import os

import pandas as pd
import streamlit as st
import requests
import json

st.set_page_config(layout="wide")


# --- Helper Functions & Cache ---
@st.cache_data(ttl=3600)  # Cache defaults for 1 hour
def get_config_defaults(api_url: str):
    """ ✨ Fetches default configurations from the backend."""
    try:
        res = requests.get(f"{api_url}/config/defaults")
        if res.status_code == 200:
            return res.json()
    except requests.exceptions.RequestException as e:
        # Don't show an error, just fail silently and use blank defaults
        print(f"Could not fetch defaults: {e}")
    return {}

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


# --- Sidebar ---
st.sidebar.header("API 配置")
api_url_default = os.getenv("API_URL", "http://localhost:8000")
st.session_state.api_url = st.sidebar.text_input("API base URL", value=api_url_default).rstrip("/")

# ✨ Fetch the defaults once
config_defaults = get_config_defaults(st.session_state.api_url)

# ✨ --- NEW: Configurable AI Settings Section ---
with st.sidebar.expander("⚙️ AI Provider Settings", expanded=True):
    # For the API key, show a placeholder if it's already set on the backend
    api_key_placeholder = "✅ Key is set on backend" if config_defaults.get("api_key_set") else "sk-..."

    st.session_state.openai_api_key = st.text_input(
        "OpenAI API Key",
        type="password",
        placeholder=api_key_placeholder,
        help="Leave blank to use the key from the backend's .env file."
    )
    st.session_state.openai_api_base_url = st.text_input(
        "API Base URL",
        # Use the fetched default as the value
        value=config_defaults.get("base_url", ""),
        placeholder="https://api.openai.com/v1",
        help="Leave blank to use the URL from the backend's .env file."
    )
    st.session_state.openai_llm_model = st.text_input(
        "LLM Model",
        # Use the fetched default as the value
        value=config_defaults.get("llm_model", "gpt-4o-mini"),
        help="e.g., gpt-4o, gpt-3.5-turbo"
    )
    st.session_state.openai_embed_model = st.text_input(
        "Embedding Model",
        # Use the fetched default as the value
        value=config_defaults.get("embed_model", "text-embedding-3-small"),
        help="e.g., text-embedding-3-large"
    )
    st.session_state.chunk_tokens = st.number_input(
        "Chunk Tokens",
        min_value=100,
        max_value=8000,
        # Use the fetched default as the value
        value=config_defaults.get("chunk_tokens", 400),
        step=50
    )


st.sidebar.title("操作菜单")

# ✨ --- Unified Uploader ---
with st.sidebar.expander("📄 上传新文档", expanded=True):
    uploaded_file = st.file_uploader("选择 .txt 或 .docx 文件", type=["txt", "docx"], key="main_uploader")
    if uploaded_file and st.button("上传文档"):
        files = {'file': (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
        with st.spinner("正在上传文档..."):
            res = requests.post(f"{st.session_state.api_url}/transcripts/upload", files=files)
            if res.status_code == 200:
                st.success(f"文档 '{uploaded_file.name}' 上传成功!")
                st.session_state.new_transcript_id = res.json()['id']
                st.cache_data.clear()
            else:
                st.error(f"上传失败: {res.text}")

        # ✨ NEW: Button to trigger AI processing after upload
        if 'new_transcript_id' in st.session_state:
            st.info("⬆️ 文档已上传。点击下方按钮为其生成 AI 可用数据 (Chunks 和 Embeddings)。")
            if st.button("🤖 开始 AI 处理"):
                with st.spinner("正在处理文档以用于 AI分析..."):
                    transcript_id = st.session_state.new_transcript_id
                    res = requests.post(f"{st.session_state.api_url}/transcripts/process-ai/{transcript_id}")
                    if res.status_code == 200:
                        st.success("AI 处理完成！")
                        del st.session_state.new_transcript_id
                        # ✅ FIX: Clear the cache to ensure the status update is visible
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(f"AI 处理失败: {res.text}")
                        del st.session_state.new_transcript_id

# ✨ --- Manual Actions ---
with st.sidebar.expander("✍️ 手动添加", expanded=False):
    # # --- Upload Transcript ---
    # st.subheader("1. 上传 Transcript")
    # manual_uploaded_file = st.file_uploader("选择 .txt 或 .docx 文件", type=["txt", "docx"], key="transcript_uploader")
    # if manual_uploaded_file and st.button("确认上传 Transcript"):
    #     files = {'file': (manual_uploaded_file.name, manual_uploaded_file.getvalue(), manual_uploaded_file.type)}
    #     with st.spinner("上传中..."):
    #         res = requests.post(f"{st.session_state.api_url}/transcripts/upload", files=files)
    #         if res.status_code == 200:
    #             st.success(f"Transcript '{manual_uploaded_file.name}' 上传成功!");
    #             st.cache_data.clear();
    #             st.rerun()
    #         else:
    #             st.error(f"上传失败: {res.text}")
    # --- Add Memo ---
    st.subheader("添加 Memo")
    with st.form("add_memo_form"):
        memo_title = st.text_input("Memo 标题")
        memo_content = st.text_area("Memo 内容")
        if st.form_submit_button("保存 Memo"):
            if memo_title and memo_content:
                res = requests.post(f"{st.session_state.api_url}/memos",
                                    json={"title": memo_title, "content": memo_content})
                if res.status_code == 200:
                    st.success("Memo 保存成功!")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(f"保存失败: {res.text}")

    st.markdown("---")
    # --- Add Code ---
    st.subheader("添加新编码")
    transcripts = get_api_data("transcripts")
    memos = get_api_data("memos")

    # ✅ FIX: Move the radio button OUTSIDE and ABOVE the form.
    # Its state is automatically saved to st.session_state thanks to the 'key'.
    # Changing this will now trigger an immediate rerun.
    st.radio(
        "1. 选择来源类型 (Select Source Type)",
        ["Transcript", "Memo"],
        key="code_source_type",
        horizontal=True,
    )

    # The form is now built based on the state of the radio button above.
    with st.form("add_code_form", clear_on_submit=True):
        st.write("填写编码详情 (Enter Code Details)")
        code = st.text_input("Code Label", key="code_label")
        excerpt = st.text_area("Excerpt", key="code_excerpt")

        # Read the source type from the session state
        source_type = st.session_state.code_source_type
        source_id = None
        choice = None

        # This block now correctly displays the right selectbox on each rerun
        if source_type == "Transcript":
            if transcripts:
                choice = st.selectbox(
                    "选择 Transcript",
                    transcripts,
                    format_func=lambda t: t.get("title", f"ID: {t.get('id', 'N/A')}")[:70]
                )
                if choice:
                    source_id = choice.get("id")
            else:
                st.warning("无可用 Transcripts。")
        elif source_type == "Memo":
            if memos:
                choice = st.selectbox(
                    "选择 Memo",
                    memos,
                    format_func=lambda m: m.get("title", f"ID: {m.get('id', 'N/A')}")[:70]
                )
                if choice:
                    source_id = choice.get("id")
            else:
                st.warning("无可用 Memos。")

        # The submit button and its logic remain inside the form.
        submitted = st.form_submit_button("添加 Code")
        if submitted:
            if code and excerpt and source_id:
                payload = {
                    "code": code,
                    "excerpt": excerpt,
                    "transcript_id": source_id if source_type == "Transcript" else None,
                    "memo_id": source_id if source_type == "Memo" else None
                }
                res = requests.post(f"{st.session_state.api_url}/codes", json=payload)
                if res.status_code == 200:
                    st.toast("✅ 编码添加成功!", icon="✍️")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(f"添加失败: {res.text}")
            else:
                st.warning("请确保所有字段都已填写/选择。")

# =====================================================================
# Main Page Display
# =====================================================================
st.title("Qualitative Research Agent")

tab1, tab2 = st.tabs(["🤖 AI 分析与搜索", "✍️ 手动编码管理"])

with tab1:
    st.header("AI 分析与搜索")
    st.info("首先上传文档，然后在这里处理并分析。")

    # ✨ --- FIX: Replaced ActionColumn with a manual button layout ---
    st.subheader("文档处理状态")
    transcripts = get_api_data("transcripts")
    if not transcripts:
        st.info("暂无文档。请在侧边栏上传一个新文档。")
    else:
        # Create a header for our manual table
        col1, col2, col3, col4 = st.columns([1, 4, 2, 2])
        col1.markdown("**ID**")
        col2.markdown("**Title**")
        col3.markdown("**Status**")
        col4.markdown("**Action**")
        st.divider()

        # Loop through each transcript to create a row with a button
        for t in transcripts:
            col1, col2, col3, col4 = st.columns([1, 4, 2, 2])
            with col1:
                st.write(t['id'])
            with col2:
                st.write(t['title'])
            with col3:
                # Add some color to the status for better readability
                if t['status'] == 'processed':
                    st.success(t['status'])
                elif t['status'] == 'failed':
                    st.error(t['status'])
                else:
                    st.warning(t['status'])
            with col4:
                # Only show the button if the status is 'new' or 'failed'
                if t['status'] in ['new', 'failed']:
                    if st.button("🤖 Process for AI", key=f"process_{t['id']}"):
                        with st.spinner(f"正在处理 Transcript ID: {t['id']}..."):
                            res = requests.post(f"{st.session_state.api_url}/transcripts/process-ai/{t['id']}")
                            if res.status_code == 200:
                                st.toast("✅ AI 处理完成!", icon="🤖")
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error(f"AI 处理失败: {res.text}")

        # This is a workaround to get the ID from the button click in st.dataframe
        if st.button("Manually trigger button state check"):
            st.rerun()
        st.caption("Note: 'Process for AI' button only appears for documents with 'new' status.")

    st.divider()

    # --- Analysis Section ---
    st.subheader("AI 分析功能")
    # Filter for transcripts that are ready for analysis
    processed_transcripts = [t for t in transcripts if t.get('status') == 'processed']

    if processed_transcripts:
        selected_transcript = st.selectbox(
            "选择一个已处理的 Transcript 进行分析",
            options=processed_transcripts,
            format_func=lambda t: f"{t.get('id')}: {t.get('title', 'N/A')}"
        )
        if selected_transcript:
            st_id = selected_transcript['id']

            # ✨ Create the config payload from session state
            ai_config = {
                "api_key": st.session_state.openai_api_key,
                "base_url": st.session_state.openai_api_base_url,
                "llm_model": st.session_state.openai_llm_model,
                "embed_model": st.session_state.openai_embed_model
            }

            # --- AI Generate & Save Codes ---
            if st.button("🤖 生成并保存 AI 编码"):
                with st.spinner("正在调用 AI 分析并保存编码..."):
                    payload = {"transcript_id": st_id, "config": ai_config}
                    res = requests.post(f"{st.session_state.api_url}/codes/ai-generate", json=payload)
                    if res.status_code == 200:
                        # ✨ FIX: Use st.toast for visible confirmation
                        st.toast('✅ AI 编码已成功保存!', icon='🤖')
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(f"操作失败: {res.text}")

            # --- AI Generate Memo ---
            if st.button("📝 生成 AI 备忘录预览"):
                with st.spinner("正在调用 AI 生成备忘录预览..."):
                    payload = {"transcript_id": st_id, "config": ai_config}
                    res = requests.post(f"{st.session_state.api_url}/memo/preview", json=payload)
                    if res.status_code == 200:
                        st.session_state.ai_memo_preview = res.json()
                    else:
                        st.error(f"生成预览失败: {res.text}")

            # ✨ 如果备忘录已生成，则显示内容和保存按钮
            # ✨ --- AI Memo Preview Bug Fix ---
            if 'ai_memo_preview' in st.session_state and st.session_state.ai_memo_preview:
                preview = st.session_state.ai_memo_preview
                with st.container(border=True):
                    st.markdown("#### AI 生成的备忘录预览")
                    st.markdown(preview['content'])
                    if st.button("💾 保存此备忘录到数据库"):
                        with st.spinner("保存中..."):
                            payload = {"transcript_id": st_id, "config": ai_config}
                            save_res = requests.post(f"{st.session_state.api_url}/memos/ai-generate", json=payload)
                            if save_res.status_code == 200:
                                # ✨ FIX: Use st.toast for visible confirmation
                                st.toast('✅ AI 备忘录已成功保存!', icon='📝')
                                del st.session_state.ai_memo_preview
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error(f"保存失败: {save_res.text}")
            # --- Semantic Search ---
            st.markdown("##### 🔍 语义搜索查询")
            query = st.text_input("输入你的问题或关键词", key="search_query")
            k = st.slider("返回最相关的 K 个结果", 1, 10, 5)
            if st.button("搜索"):
                with st.spinner("正在进行语义搜索..."):
                    payload = {
                        "transcript_id": st_id,
                        "query": query,
                        "top_k": k,
                        "config": ai_config
                    }
                    res = requests.post(f"{st.session_state.api_url}/search/", json=payload)
                    if res.status_code == 200:
                        st.success("搜索完成！")
                        results = res.json()
                        if not results:
                            st.info("没有找到相关结果。")
                        else:
                            for item in results:
                                with st.container(border=True):
                                    st.caption(f"相似度分数: {item.get('score', 0):.4f}")
                                    st.markdown(item.get('text', 'N/A'))
                    else:
                        st.error(f"搜索失败: {res.text}")
    else:
        st.info("没有已处理的文档可供分析。请先上传并点击 'Process for AI'。")

with tab2:
    st.header("手动管理")

    # ✨ --- Redesigned Transcript Viewer with Checkbox Toggle ---
    st.subheader("📄 所有 Transcripts")
    transcripts = get_api_data("transcripts")
    if not transcripts:
        st.info("暂无 Transcripts。请在侧边栏上传。")
    for t in transcripts:
        with st.expander(t['title']):
            content_key = f"content_t_{t['id']}"

            # ✨ Use a checkbox to control the visibility of the content
            if st.checkbox("查看内容", key=f"view_t_{t['id']}", value=content_key in st.session_state):
                # If the checkbox is checked but we don't have the content yet, fetch it.
                if content_key not in st.session_state:
                    with st.spinner("正在加载内容..."):
                        res = requests.get(f"{st.session_state.api_url}/transcripts/{t['id']}")
                        if res.status_code == 200:
                            st.session_state[content_key] = res.json().get('content', 'No content found.')
                        else:
                            st.error(f"无法加载内容: {res.text}")
                            # Put a placeholder to prevent re-fetching on the next rerun
                            st.session_state[content_key] = f"Error loading content. Status: {res.status_code}"

                # If content is in the session state, display it.
                if content_key in st.session_state:
                    st.text_area("Content", st.session_state[content_key], height=300, key=f"text_t_{t['id']}")

            # If the checkbox is unchecked, make sure the content is cleared from the session state.
            else:
                if content_key in st.session_state:
                    del st.session_state[content_key]

            # Delete button remains at the bottom of the expander
            if st.button("❌ 删除", key=f"del_t_{t['id']}", type="secondary", use_container_width=True):
                requests.delete(f"{st.session_state.api_url}/transcripts/{t['id']}")
                st.cache_data.clear()
                st.rerun()

    st.divider()

    # ✨ --- Redesigned Memo Viewer with Checkbox Toggle ---
    st.subheader("📝 所有 Memos")
    memos = get_api_data("memos")
    if not memos:
        st.info("暂无 Memos。请在侧边栏手动添加。")
    for m in memos:
        with st.expander(m['title']):
            content_key = f"content_m_{m['id']}"

            # ✨ Use a checkbox to control the visibility of the content
            if st.checkbox("查看内容", key=f"view_m_{m['id']}", value=content_key in st.session_state):
                if content_key not in st.session_state:
                    with st.spinner("正在加载内容..."):
                        res = requests.get(f"{st.session_state.api_url}/memos/{m['id']}")
                        if res.status_code == 200:
                            st.session_state[content_key] = res.json().get('content', 'No content found.')
                        else:
                            st.error(f"无法加载内容: {res.text}")
                            st.session_state[content_key] = f"Error loading content. Status: {res.status_code}"

                if content_key in st.session_state:
                    st.text_area("Content", st.session_state[content_key], height=300, key=f"text_m_{m['id']}")

            else:
                if content_key in st.session_state:
                    del st.session_state[content_key]

            if st.button("❌ 删除", key=f"del_m_{m['id']}", type="secondary", use_container_width=True):
                requests.delete(f"{st.session_state.api_url}/memos/{m['id']}")
                st.cache_data.clear()
                st.rerun()

    st.divider()

    st.subheader("✍️ 所有编码 (Codes)")
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
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error("删除失败")