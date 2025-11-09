# frontend/app.py
import os
from typing import Any, Dict, List, Optional

import requests
import pandas as pd
import streamlit as st


# -------------------------------
# Page / App Setup
# -------------------------------
st.set_page_config(
    page_title="QualiAgent — MVP UI",
    page_icon="🧠",
    layout="wide",
)
st.title("QualiAgent — Phase 1")

# A tiny key helper to keep keys unique and readable everywhere.
def K(*parts: str) -> str:
    return ":".join(parts)


# -------------------------------
# Config & Utilities
# -------------------------------
# ===========================
# Config
# ===========================
def get_backend_base_url() -> str:
    return os.environ.get("BACKEND_BASE_URL", "http://localhost:8000")

API_BASE = get_backend_base_url()

def _handle(resp: requests.Response) -> Any:
    # ✅ FIX: Check for 400-599 status codes
    if resp.status_code >= 400:
        try:
            # Try to parse the error message from the backend
            error_json = resp.json()
            # Raise a clear, structured error
            raise RuntimeError(f"API Error {resp.status_code}: {error_json.get('detail', resp.text)}")
        except requests.exceptions.JSONDecodeError:
            # If the error isn't JSON, just raise the raw text
            raise RuntimeError(f"API Error {resp.status_code}: {resp.text}")

    ctype = resp.headers.get("Content-Type", "")
    if "application/json" in ctype or (resp.text and resp.text.strip().startswith(("{", "["))):
        try:
            return resp.json()
        except requests.exceptions.JSONDecodeError:
            # Handle case where server *says* JSON but sends bad JSON
            raise RuntimeError(f"Failed to decode JSON response from server. Text: {resp.text[:200]}...")
    return resp.text

# Sidebar: API base URL (unique key)
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    api_base_url = st.text_input(
        "API Base URL",
        value=st.session_state.get("api_base_url", os.environ.get("QUALIAGENT_API_BASE", API_BASE)),
        key=K("sb", "api_base_url"),
        help="Backend FastAPI base URL. Example: http://127.0.0.1:8000",
    )
    st.session_state["api_base_url"] = api_base_url

# Simple GET helper with basic error handling
@st.cache_data(show_spinner=False, ttl=10)
def api_get(path: str, params: Optional[Dict[str, Any]] = None):
    url = f"{API_BASE}{path}"
    return _handle(requests.get(url, params=params, timeout=30))

def api_post(path: str, payload: Optional[Dict[str, Any]] = None):
    url = f"{API_BASE}{path}"
    return _handle(requests.post(url, json=payload or {}, timeout=60))

# Cache wrappers (invalidate with TTL to avoid stale dev state)
@st.cache_data(show_spinner=False, ttl=10)
def load_codebook(include_deprecated: bool = False):
    return api_get("/codebook", params={"include_deprecated": include_deprecated})

@st.cache_data(show_spinner=False, ttl=10)
def load_segments(transcript_id: str):
    return api_get(f"/segments/{transcript_id}")

def toast_ok(msg: str):
    st.success(msg, icon="✅")

def toast_warn(msg: str):
    st.warning(msg, icon="⚠️")

# -------------------------------
# Page Sections
# -------------------------------
def page_transcript_viewer():
    st.subheader("Transcript Viewer")
    tid = st.text_input("Transcript ID", value=st.session_state.get("transcript_id", "t.docx001"), key=K("transcript_viewer", "transcript_id"),)
    st.session_state["transcript_id"] = tid

    try:
        segs = load_segments(tid)
        st.caption(f"Loaded {len(segs)} segments")
        st.dataframe(
            [{"id": s["id"], "index": s["index"], "speaker": s.get("speaker"), "text": s["text"]} for s in segs],
            width='stretch', hide_index=True
        )
    except Exception as e:
        st.error(f"Failed to load segments: {e}")
        return

    st.markdown("---")
    if st.button("Propose Missing (AI or Mock)"):
        res = api_post(f"/events_v2/propose_missing/{tid}")
        created = res.get("created", 0)
        st.success(f"Created {created} proposed events")
        if res.get("events"):
            with st.expander("View created events"):
                st.json(res["events"])
        # Clear caches so Review tab refreshes
        st.cache_data.clear()


def page_review_queue():
    st.subheader("Review Queue (DB-backed)")
    reviewer = st.text_input("Reviewer", value=st.session_state.get("reviewer", "Analyst-1"))
    st.session_state["reviewer"] = reviewer

    transcript_id = st.text_input("Transcript ID (optional to filter)", value=st.session_state.get("tid_filter", ""))
    st.session_state["tid_filter"] = transcript_id

    queue = api_get("/review_v2/queue", params={"transcript_id": transcript_id or None})
    st.caption(f"Loaded {len(queue)} proposed events")
    cb_items = load_codebook(include_deprecated=False)

    for item in queue:
        ev = item["event"]
        labels = item.get("labels", [])
        eid = ev["id"]

        with st.expander(f"Event {eid} • status={ev['status']} • summary={ev['summary'][:40]}", expanded=False):
            # Editable summary
            new_summary = st.text_area("Summary", value=ev["summary"], key=f"sum_{eid}", height=100)

            # Existing labels
            st.markdown("**Labels**")
            if labels:
                for lab in labels:
                    cols = st.columns([6, 2, 2])
                    with cols[0]:
                        st.write(f"- {lab['codebook_id']} (by {lab['created_by']} @ {lab['created_at']})")
                    with cols[1]:
                        if st.button("Accept label", key=f"lab_acc_{lab['id']}"):
                            api_post(f"/review_v2/label/{lab['id']}/accept", {"reviewer": reviewer})
                            toast_ok("Label accepted.")
                    with cols[2]:
                        if st.button("Reject label", key=f"lab_rej_{lab['id']}"):
                            api_post(f"/review_v2/label/{lab['id']}/reject", {"reviewer": reviewer})
                            toast_ok("Label rejected.")

            # Add a new label
            st.markdown("**Add label**")
            if cb_items:
                cb_map = {f"{x['name']} ({x['id']})": x["id"] for x in cb_items}
                chosen = st.selectbox("Pick code", options=list(cb_map.keys()), key=f"cb_{eid}")
                if st.button("Add label", key=f"addlab_{eid}"):
                    api_post(f"/review_v2/event/{eid}/add_label", {"reviewer": reviewer, "codebook_id": cb_map[chosen], "rationale": "fits"})
                    toast_ok("Label added.")

            # Actions: Accept / Reject / Save Edit
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("Accept event", type="primary", key=f"acc_{eid}"):
                    api_post(f"/review_v2/event/{eid}/accept", {"reviewer": reviewer})
                    toast_ok("Event accepted.")
                    st.cache_data.clear(); st.rerun()
            with c2:
                if st.button("Reject event", key=f"rej_{eid}"):
                    api_post(f"/review_v2/event/{eid}/reject", {"reviewer": reviewer})
                    toast_ok("Event rejected.")
                    st.cache_data.clear(); st.rerun()
            with c3:
                if st.button("Save edits", key=f"edit_{eid}"):
                    payload = {"reviewer": reviewer, "summary": new_summary, "status": "accepted"}
                    api_post(f"/review_v2/event/{eid}/edit", payload)
                    toast_ok("Event edited + accepted.")
                    st.cache_data.clear(); st.rerun()


# def page_codebook_manager():
#     st.subheader("Codebook Manager")
#     c1, c2 = st.columns([3, 2])
#     with c1:
#         include_dep = st.checkbox("Show deprecated", value=False)
#         items = load_codebook(include_dep)
#         st.caption(f"Loaded {len(items)} categories")
#         st.dataframe(
#             [{"id": x["id"], "name": x["name"], "status": x.get("status", "")} for x in items],
#             width='stretch'',
#             hide_index=True,
#         )

#     with c2:
#         st.markdown("**Merge categories**")
#         if items:
#             id2name = {x["id"]: x["name"] for x in items}
#             from_id = st.selectbox("From (will be deprecated)", options=list(id2name.keys()), format_func=lambda i: f"{id2name[i]} ({i})")
#             into_id = st.selectbox("Into (survivor)", options=list(id2name.keys()), format_func=lambda i: f"{id2name[i]} ({i})")
#             if st.button("Merge", type="primary", key="merge_btn"):
#                 if from_id == into_id:
#                     toast_warn("Cannot merge the same category into itself.")
#                 else:
#                     api_post("/codebook/merge", {"from_id": from_id, "into_id": into_id})
#                     st.cache_data.clear()
#                     toast_ok("Merged. The 'from' category is now deprecated and labels re-pointed.")
#                     st.rerun()

#         st.markdown("---")
#         st.markdown("**Deprecate category**")
#         if items:
#             dep_id = st.selectbox("Select to deprecate", options=[x["id"] for x in items], format_func=lambda i: f"{id2name.get(i,i)} ({i})", key="dep_select")
#             if st.button("Deprecate", key="dep_btn"):
#                 api_post(f"/codebook/{dep_id}/deprecate")
#                 st.cache_data.clear()
#                 toast_ok("Category deprecated.")
#                 st.rerun()

def page_search_v2():
    st.subheader("Search (V2)")
    q = st.text_input("Query", value="项目 价值")
    tid = st.text_input("Transcript ID (optional)", value=st.session_state.get("transcript_id", ""))
    k = st.slider("Top K", 1, 50, 10)
    if st.button("Search"):
        hits = api_get("/search/v2", params={"q": q, "transcript_id": tid or None, "limit": k})
        st.dataframe(
            [{"score": round(h["score"], 3), "segment_id": h["id"], "index": h["index"], "speaker": h.get("speaker"), "text": h["text"]} for h in hits],
            width='stretch', hide_index=True
        )

def page_legacy():
    st.subheader("📚 Legacy (V1)")

    tab_gen, tab_memo, tab_search = st.tabs(
        ["Generate Codes", "Memo Preview", "Search"]
    )

    # -----------------------------
    # 1) Generate Codes (legacy)
    # -----------------------------
    with tab_gen:
        c1, c2 = st.columns([2, 1])

        with c1:
            legacy_text = st.text_area(
                "Paste text (optional)",
                key=K("legacy", "text"),
                placeholder="Paste a paragraph for legacy code generation…\n(Or leave empty and provide a Transcript ID below.)",
                height=160,
            )
            transcript_id = st.text_input(
                "Transcript ID (optional for legacy)",
                key=K("legacy", "transcript_id"),
                placeholder="e.g., t.docx001",
            )

        with c2:
            st.caption("Request payload")
            payload = {}
            if legacy_text and legacy_text.strip():
                payload["text"] = legacy_text.strip()
            if transcript_id and transcript_id.strip():
                payload["transcript_id"] = transcript_id.strip()
            st.code(payload or "{}", language="json")

            go = st.button(
                "Generate Codes (Legacy)",
                key=K("legacy", "gen_btn"),
                width='stretch',
            )

        if go:
            if not payload:
                st.warning("Provide text or a transcript_id.")
            else:
                try:
                    codes = api_post("/legacy/generate_codes", payload)
                except RuntimeError as e:
                    st.error(str(e))
                else:
                    if isinstance(codes, list) and codes:
                        st.success(f"Received {len(codes)} codes")
                        st.dataframe(codes, width='stretch')
                    else:
                        st.info("No codes returned.")

    # -----------------------------
    # 2) Memo Preview
    # -----------------------------
    with tab_memo:
        m1, m2 = st.columns([2, 1])

        with m1:
            memo_text = st.text_area(
                "Memo text",
                key=K("legacy", "memo_text"),
                placeholder="Write or paste memo text to preview…",
                height=160,
            )

        with m2:
            memo_payload = {"text": memo_text.strip()} if memo_text and memo_text.strip() else {}
            st.caption("Request payload")
            st.code(memo_payload or "{}", language="json")

            go_memo = st.button(
                "Preview Memo",
                key=K("legacy", "memo_btn"),
                width='stretch',
            )

        if go_memo:
            if not memo_payload:
                st.warning("Please provide memo text.")
            else:
                try:
                    memo = api_post("/legacy/memo_preview", memo_payload)
                except RuntimeError as e:
                    st.error(str(e))
                else:
                    if isinstance(memo, dict) and memo:
                        st.success("Memo generated")
                        # Show common fields nicely if present
                        title = memo.get("title")
                        content = memo.get("content")
                        if title:
                            st.markdown(f"**{title}**")
                        if content:
                            st.write(content)
                        with st.expander("Raw response"):
                            st.code(memo, language="json")
                    else:
                        st.info("No memo returned.")

    # -----------------------------
    # 3) Legacy Search
    # -----------------------------
    with tab_search:
        s1, s2, s3 = st.columns([2, 2, 1])

        with s1:
            q = st.text_input(
                "Query",
                key=K("legacy", "search_q"),
                placeholder="e.g., 职业 / anxiety / interview",
            )
        with s2:
            tid = st.text_input(
                "Transcript ID (optional)",
                key=K("legacy", "search_tid"),
                placeholder="e.g., t.docx001",
            )
        with s3:
            k = st.number_input(
                "Limit",
                key=K("legacy", "search_k"),
                min_value=1,
                max_value=200,
                value=10,
                step=1,
            )

        # show what we'll send
        params = {"q": q, "limit": int(k)}
        if tid and tid.strip():
            params["transcript_id"] = tid.strip()

        with st.expander("Request params"):
            st.code(params, language="json")

        go_search = st.button(
            "Search (Legacy)",
            key=K("legacy", "search_btn"),
            width='stretch',
        )

        if go_search:
            if not q or not q.strip():
                st.warning("Enter a query.")
            else:
                try:
                    hits = api_get("/legacy/search", params=params)
                except RuntimeError as e:
                    st.error(str(e))
                else:
                    if isinstance(hits, list) and hits:
                        st.success(f"{len(hits)} results")
                        st.dataframe(hits, width='stretch')
                    else:
                        st.info("No results.")

# --- keep headers and helpers from your existing app.py (as in Phase 1) ---

# Add these new pages:

def page_importer():
    st.subheader("Importer (DOCX → DB)")
    tid = st.text_input("Transcript ID", value=st.session_state.get("imp_tid", "t.docx002"))
    st.session_state["imp_tid"] = tid
    f = st.file_uploader("Upload .docx", type=["docx"])
    if f and st.button("Import"):
        with st.spinner("Uploading and importing..."):
            import requests
            url = f"{API_BASE}/import/docx"
            files = {"file": (f.name, f.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
            data = {"transcript_id": tid}
            r = requests.post(url, files=files, data=data, timeout=120)
            res = _handle(r)
        st.success(f"Imported: {res.get('counts')}")
        st.cache_data.clear()

def page_codebook_manager():  # replace Phase-1 version with this
    st.subheader("Codebook Manager")
    include_dep = st.checkbox("Show deprecated", value=False)
    items = load_codebook(include_dep)
    st.caption(f"Loaded {len(items)} categories")
    # Show definitions inline
    for x in items:
        with st.expander(f"{x['name']} ({x['id']}) • status={x.get('status','')}", expanded=False):
            st.markdown(f"**Definition:** {x.get('definition','') or '(none)'}")
            # examples
            if st.button("Show examples", key=f"ex_{x['id']}"):
                ex = api_get(f"/codebook/{x['id']}/examples", params={"limit": 5})
                if ex["examples"]:
                    st.table([{"event_id": e["event_id"], "summary": e["summary"], "excerpt": e["raw_excerpt"], "transcript": e["transcript_id"]} for e in ex["examples"]])
                else:
                    st.info("No examples yet.")

            c1, c2 = st.columns(2)
            with c1:
                # Merge
                target = st.text_input("Merge into (codebook_id)", value="", key=f"merge_into_{x['id']}")
                if st.button("Merge", key=f"merge_btn_{x['id']}") and target.strip():
                    api_post("/codebook/merge", {"from_id": x["id"], "into_id": target.strip()})
                    st.cache_data.clear(); st.rerun()
            with c2:
                if st.button("Deprecate", key=f"dep_{x['id']}"):
                    api_post(f"/codebook/{x['id']}/deprecate")
                    st.cache_data.clear(); st.rerun()

def page_irr():
    st.subheader("IRR & QA")
    st.markdown("Create a task, then submit judgments as two coders and compute metrics.")

    st.markdown("### Create IRR task")
    name = st.text_input("Task name", value="Task A")
    item_type = st.selectbox("Item type", options=["event", "segment"])
    scope_tid = st.text_input("Filter transcript_id (optional)", value="")
    source = st.selectbox("Source (events only)", options=["proposed", "accepted"]) if item_type=="event" else st.selectbox("Source (segments)", options=["all"])
    sample_size = st.slider("Sample size", 5, 200, 20)
    if st.button("Create task"):
        body = {"name": name, "item_type": item_type, "scope_transcript_id": scope_tid or None, "source": source, "sample_size": sample_size}
        res = api_post("/irr/tasks", body)
        st.success(f"Created {res['task_id']} with {res['count']} items")
        st.session_state["irr_task_id"] = res["task_id"]

    task_id = st.text_input("Current Task ID", value=st.session_state.get("irr_task_id",""))
    if task_id:
        t = api_get(f"/irr/tasks/{task_id}")
        st.caption(f"{len(t['items'])} items in task")
        st.dataframe(t["items"], width='stretch', hide_index=True)

        st.markdown("### Submit judgments")
        coder = st.text_input("Coder ID", value="coderA")
        dec = st.selectbox("Decision (for events)", options=["accept","reject","(skip)"])
        codebook_id = st.text_input("Codebook ID (optional for label agreement)", value="")
        # Just to demo: submit the same decision for all items (you can expand into a per-item UI later)
        if st.button("Submit for ALL items"):
            payload = {"coder_id": coder, "judgments": [{"item_id": it["item_id"], "decision": (None if dec=='(skip)' else dec), "codebook_id": (codebook_id or None)} for it in t["items"]]}
            api_post(f"/irr/tasks/{task_id}/judge", payload)
            st.success("Submitted")

        st.markdown("### Metrics")
        if st.button("Compute metrics"):
            m = api_get(f"/irr/tasks/{task_id}/metrics")
            st.json(m)


# -------------------------------
# Router (SINGLE render path)
# -------------------------------
st.title("🧠 QualiAgent — MVP")

# Tabs (simple, prevents double render when used alone)
tabs = st.tabs(["Importer", "Codebook Manager", "Review Queue", "Transcript Viewer", "Search (V2)", "Legacy", "IRR & QA"])
with tabs[0]: page_importer()
with tabs[1]: page_codebook_manager()
with tabs[2]: page_review_queue()
with tabs[3]: page_transcript_viewer()
with tabs[4]: page_search_v2()
with tabs[5]: page_legacy()
with tabs[6]: page_irr()


st.sidebar.markdown(f"**Backend:** {API_BASE}")
try:
    defaults = api_get("/config/defaults")
    with st.sidebar.expander("Config Defaults"):
        st.json(defaults)
except Exception as e:
    st.sidebar.warning(f"Could not load /config/defaults: {e}")

# IMPORTANT:
# Do NOT call page_* functions again below.
# Duplicate calls = duplicate widgets = duplicate keys.
