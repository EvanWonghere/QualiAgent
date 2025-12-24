# frontend/app.py
# frontend/app.py
import os
import requests
import pandas as pd
import streamlit as st

# -------------------------------
# Config & Utilities
# -------------------------------
st.set_page_config(page_title="QualiAgent", page_icon="🧠", layout="wide")
st.title("QualiAgent — AI Copilot")

API_BASE = os.environ.get("BACKEND_BASE_URL", "http://localhost:8000")


def K(*parts):
    return ":".join(map(str, parts))


def _handle_response(resp: requests.Response):
    if resp.status_code >= 400:
        try:
            err = resp.json()
            msg = err.get("detail", str(err))
        except:
            msg = resp.text
        st.error(f"API Error {resp.status_code}: {msg}")
        return None
    try:
        return resp.json()
    except:
        return resp.text


def api_get(path, params=None):
    try:
        if not path.startswith("/"): path = "/" + path
        r = requests.get(f"{API_BASE}{path}", params=params, timeout=120)
        return _handle_response(r)
    except Exception as e:
        st.error(f"Connection Failed: {e}")
        return None


def api_post(path, json=None, data=None, files=None):
    try:
        if not path.startswith("/"): path = "/" + path
        r = requests.post(f"{API_BASE}{path}", json=json, data=data, files=files, timeout=300)
        return _handle_response(r)
    except Exception as e:
        st.error(f"Connection Failed: {e}")
        return None


# -------------------------------
# Page: Importer
# -------------------------------
def page_importer():
    st.header("📄 Import Data")

    tid = st.text_input("New Transcript ID (e.g. t.001)", value="t.docx001")
    uploaded_file = st.file_uploader("Upload Word Doc (.docx)", type=["docx"])

    if st.button("Upload & Parse"):
        if not uploaded_file:
            st.warning("Please select a file.")
            return

        files = {"file": (uploaded_file.name, uploaded_file,
                          "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        res = api_post("/import/docx", data={"transcript_id": tid}, files=files)
        if res:
            st.success(f"Imported successfully! Stats: {res}")


# -------------------------------
# Page: Transcript Viewer (Core)
# -------------------------------
def page_transcript_viewer():
    st.header("📝 Transcript Viewer")

    tid = st.text_input("Transcript ID", value=st.session_state.get("curr_tid", "t.docx001"))
    st.session_state["curr_tid"] = tid

    if not tid: return

    segs = api_get(f"/segments/{tid}")
    events_with_labels = api_get(f"/events_v2/with_labels/{tid}")

    if not segs:
        st.info("No segments found. Try importing a document first.")
        return

    evt_map = {}
    if events_with_labels:
        for item in events_with_labels:
            ev = item["event"]
            sid = ev["segment_id"]
            if sid not in evt_map: evt_map[sid] = []
            evt_map[sid].append(item)

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("✨ AI Auto-Code (Batch 100)", type="primary"):
            with st.spinner("AI is reading and coding..."):
                res = api_post(f"/events_v2/propose_missing/{tid}")
                if res:
                    st.success(f"AI Created {res.get('created', 0)} events!")
                    st.rerun()

    st.divider()

    page_size = 50
    page_num = st.number_input("Page", min_value=1, value=1)
    start = (page_num - 1) * page_size
    current_segs = segs[start: start + page_size]

    for s in current_segs:
        sid = s["id"]
        idx = s["index"]
        text = s.get("text") or ""
        speaker = s.get("speaker") or ""

        st.markdown(f"**[{idx}] {speaker}**: {text}")

        if sid in evt_map:
            for item in evt_map[sid]:
                ev = item["event"]
                labels = item.get("labels", [])

                status_color = "orange" if ev["status"] == "proposed" else "green"
                status_icon = "🤖" if ev["status"] == "proposed" else "✅"

                codes_str = ", ".join(
                    [f"`{l.get('code_name', l.get('codebook_id'))}`" for l in labels]) if labels else "(no code)"

                st.caption(
                    f":{status_color}[{status_icon} **{ev['summary']}**] — Codes: {codes_str}"
                )
        st.write("---")


# -------------------------------
# Page: Review Queue
# -------------------------------
def page_review_queue():
    st.header("🧐 Review Queue")

    tid_filter = st.text_input("Filter by Transcript ID (optional)", value=st.session_state.get("curr_tid", ""))
    params = {"transcript_id": tid_filter} if tid_filter else {}

    queue = api_get("/review/queue", params=params)

    if not queue:
        st.success("🎉 No pending items! All clear.")
        return

    st.write(f"**Pending Items: {len(queue)}**")

    for i, item in enumerate(queue):
        ev = item["event"]
        labels = item.get("labels", [])
        raw_text = ev.get("raw_excerpt", "(No snapshot)")

        # ✨ 修复点：这里原来是 ev['event_id']，现在改为 ev['id']
        event_db_id = ev['id']

        with st.container(border=True):
            c1, c2 = st.columns([3, 2])
            with c1:
                st.caption("Origin Text:")
                st.info(f"“{raw_text}”")

            with c2:
                st.caption("AI Proposal:")

                edit_key = K("edit_mode", event_db_id)
                is_editing = st.session_state.get(edit_key, False)

                if not is_editing:
                    st.write(f"**Summary**: {ev['summary']}")
                    if labels:
                        for l in labels:
                            st.code(l.get('code_name') or l.get('codebook_id') or "Unknown")
                    else:
                        st.write("(No code)")

                    b1, b2, b3 = st.columns(3)
                    if b1.button("✅ Accept", key=K("acc", i)):
                        api_post(f"/review/event/{event_db_id}/accept", {"reviewer": "admin"})
                        st.rerun()
                    if b2.button("✏️ Edit", key=K("edt", i)):
                        st.session_state[edit_key] = True
                        st.rerun()
                    if b3.button("❌ Reject", key=K("rej", i)):
                        api_post(f"/review/event/{event_db_id}/reject", {"reviewer": "admin"})
                        st.rerun()
                else:
                    new_sum = st.text_input("Summary", value=ev['summary'], key=K("new_sum", i))
                    # 允许输入新代码
                    new_code = st.text_input("Code Name (Create new if not exists)", key=K("new_code", i))

                    bx, by = st.columns(2)
                    if bx.button("Save", type="primary", key=K("save", i)):
                        payload = {
                            "reviewer": "admin",
                            "summary": new_sum,
                            "new_code_name": new_code if new_code.strip() else None
                        }
                        api_post(f"/review/event/{event_db_id}/edit", json=payload)
                        st.session_state[edit_key] = False
                        st.rerun()
                    if by.button("Cancel", key=K("cnl", i)):
                        st.session_state[edit_key] = False
                        st.rerun()


# -------------------------------
# Page: Codebook Manager
# -------------------------------
# frontend/app.py (局部替换)

# frontend/app.py (局部替换 page_codebook_manager)

def page_codebook_manager():
    st.header("📚 Codebook Manager")

    # 1. 顶部操作栏
    col1, col2 = st.columns([1, 3])
    with col1:
        # ✨ 新功能：提取主题
        if st.button("✨ Analyze & Extract Themes", type="primary",
                     help="Ask AI to group your codes into high-level themes"):
            with st.spinner("AI is analyzing your codebook structure..."):
                res = api_get("/ai/synthesize_codebook")
                if res and "themes" in res:
                    st.session_state["theme_analysis"] = res["themes"]
                    st.success("Analysis complete!")

    # 2. 展示分析结果 (如果有)
    if "theme_analysis" in st.session_state:
        themes = st.session_state["theme_analysis"]
        st.subheader("🤖 AI Theme Suggestions")
        st.info(
            "AI has grouped your codes into the following Core Themes. (This is for your reference to organize data)")

        for t in themes:
            with st.expander(f"📂 {t['theme_name']}"):
                st.markdown(f"**Definition**: {t['description']}")
                st.markdown("**Contains Codes**:")
                # 渲染为标签云
                st.write(", ".join([f"`{c}`" for c in t['child_codes']]))
        st.divider()

    # 3. 展示原始 Codebook 表格
    codes = api_get("/codebook")
    if codes:
        st.subheader(f"All Codes ({len(codes)})")
        df = pd.DataFrame(codes)

        target_cols = ["name", "definition", "status"]
        if "n_uses" in df.columns:
            target_cols.append("n_uses")
            # 默认按使用次数倒序
            df = df.sort_values("n_uses", ascending=False)

        valid_cols = [c for c in target_cols if c in df.columns]
        st.dataframe(df[valid_cols], use_container_width=True)
    else:
        st.info("Codebook is empty.")


# -------------------------------
# Main
# -------------------------------
# frontend/app.py (局部替换 main 函数)

def main():
    with st.sidebar:
        st.header("⚙️ Settings")

        # 1. API 设置
        api_base = st.text_input("API Base URL", value=API_BASE)
        os.environ["BACKEND_BASE_URL"] = api_base

        st.divider()
        st.subheader("🧹 Maintenance")

        # ✨ 新增：强力重置按钮
        st.caption("Duplicates? Messy IDs? Click below to delete ALL 'Proposed' AI events and start fresh.")
        # ✨ 修改后的按钮逻辑
        if st.button("🚨 Reset All AI Proposals", type="primary"):
            # 使用 requests.delete 发送请求
            try:
                with st.spinner("Nuking all proposed events... (Instant Mode)"):
                    # 直接调用刚才写的后端新接口
                    # 注意：requests.delete 没有 json 参数，一般直接发
                    url = f"{API_BASE}/review/queue/clear"
                    resp = requests.delete(url, timeout=30)

                    if resp.status_code == 200:
                        data = resp.json()
                        st.success(f"Boom! 💥 Deleted {data.get('deleted_count', 'many')} events instantly.")
                        st.cache_data.clear()  # 清除缓存
                        st.rerun()  # 刷新页面
                    else:
                        st.error(f"Failed: {resp.text}")
            except Exception as e:
                st.error(f"Connection error: {e}")

    # --- 主界面 ---
    tabs = st.tabs(["📂 Importer", "📝 Transcript Viewer", "🧐 Review Queue", "📚 Codebook"])

    with tabs[0]:
        page_importer()
    with tabs[1]:
        page_transcript_viewer()
    with tabs[2]:
        page_review_queue()
    with tabs[3]:
        page_codebook_manager()


if __name__ == "__main__":
    main()