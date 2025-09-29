# frontend/app.py
import streamlit as st
import requests

# 帮助函数，用于处理API请求和显示结果
def handle_request(method, url, **kwargs):
    """一个通用的请求处理函数，包含错误检查"""
    try:
        response = requests.request(method, url, **kwargs)
        # 检查 HTTP 状态码
        if response.status_code == 200:
            try:
                # 尝试解析 JSON 并用 st.json() 显示
                st.json(response.json())
            except requests.exceptions.JSONDecodeError:
                st.error("❌ 解析 JSON 失败。服务器返回了非 JSON 格式的内容。")
                st.code(response.text)
        else:
            # 如果状态码不是 200，显示错误信息
            st.error(f"服务器错误，状态码: {response.status_code}")
            st.code(response.text) # 将服务器返回的原始错误文本显示出来
    except requests.exceptions.RequestException as e:
        st.error(f"❌ 请求失败: {e}")

# --- Streamlit UI ---

API = st.text_input("API base URL", value="http://localhost:8000").rstrip("/")

st.title("Qualitative Research Agent — UI")

# --- 1) Upload ---
st.header("1. 上传文字记录")
with st.form("upload"):
    name = st.text_input("数据集名称", value="interview-1")
    uploaded = st.file_uploader("选择 .txt 或 .docx 文件", type=["txt", "docx"])
    submitted = st.form_submit_button("上传")

if submitted and uploaded:
    files = {"file": (uploaded.name, uploaded.getvalue())}
    st.info("🔄 正在上传并处理文件，请稍候...")
    handle_request("POST", f"{API}/upload/", data={"name": name}, files=files)

# --- 2) List Datasets ---
st.header("2. 查看所有数据集")
if st.button("刷新数据集列表"):
    st.info("🔄 正在获取数据集列表...")
    handle_request("GET", f"{API}/datasets/")

# --- 3) Analyze Dataset ---
st.header("3. 运行分析 (聚合编码)")
analyze_ds_id = st.number_input("要分析的数据集 ID", min_value=1, step=1, value=1, key="analyze_id")
if st.button("运行分析"):
    st.info(f"🔄 正在分析数据集 {analyze_ds_id}，这可能需要一些时间...")
    handle_request("POST", f"{API}/analyze/{int(analyze_ds_id)}")

# --- 4) Search / Query ---
st.header("4. 搜索查询")
search_ds_id = st.number_input("要搜索的数据集 ID", min_value=1, step=1, value=1, key="search_id")
query = st.text_input("你的问题")
k = st.slider("返回最相关的 K 个结果", 1, 10, 5)
if st.button("搜索"):
    st.info(f"🔄 正在数据集 {search_ds_id} 中搜索...")
    params = {"dataset_id": int(search_ds_id), "q": query, "k": k}
    handle_request("GET", f"{API}/search/", params=params)

st.header("5. 生成备忘录")
memo_ds = st.number_input("Dataset id for memo", min_value=1, step=1, value=1, key="memo_ds")
if st.button("Generate memo"):
    r = requests.post(f"{API}/memo/{int(memo_ds)}")
    st.json(r.json())
