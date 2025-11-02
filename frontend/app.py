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

# A tiny key helper to keep keys unique and readable everywhere.
def K(*parts: str) -> str:
    return ":".join(parts)


# -------------------------------
# Config & Utilities
# -------------------------------
DEFAULT_API_BASE = "http://127.0.0.1:8000"

# Sidebar: API base URL (unique key)
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    api_base_url = st.text_input(
        "API Base URL",
        value=st.session_state.get("api_base_url", os.environ.get("QUALIAGENT_API_BASE", DEFAULT_API_BASE)),
        key=K("sb", "api_base_url"),
        help="Backend FastAPI base URL. Example: http://127.0.0.1:8000",
    )
    st.session_state["api_base_url"] = api_base_url

# Simple GET helper with basic error handling
def api_get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any] | List[Any]:
    url = f"{st.session_state['api_base_url'].rstrip('/')}/{path.lstrip('/')}"
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        try:
            return r.json()
        except ValueError:
            return {"non_json_response": r.text}
    except requests.RequestException as e:
        st.error(f"GET {url} failed: {e}")
        return {"error": str(e), "url": url}
    
def api_get(path: str, params=None):
    url = f"{DEFAULT_API_BASE}{path}"
    r = requests.get(url, params=params, timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(r.text)
    return r.json()

def api_post(path: str, payload=None):
    url = f"{DEFAULT_API_BASE}{path}"
    r = requests.post(url, json=payload or {}, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(r.text)
    return r.json()

# Cache wrappers (invalidate with TTL to avoid stale dev state)
@st.cache_data(ttl=5)
def cached_codebook() -> List[Dict[str, Any]] | Dict[str, Any]:
    return api_get("/codebook")

@st.cache_data(ttl=5)
def cached_review_queue() -> List[Dict[str, Any]] | Dict[str, Any]:
    return api_get("/review/queue")

@st.cache_data(ttl=5)
def cached_segments(transcript_id: str) -> List[Dict[str, Any]] | Dict[str, Any]:
    return api_get(f"/segments/{transcript_id}")


# -------------------------------
# Page Sections
# -------------------------------
def page_transcript_viewer():
    st.subheader("📜 Transcript Viewer")

    with st.container():
        cols = st.columns([2, 1, 1])
        with cols[0]:
            transcript_id = st.text_input(
                "Transcript ID",
                key=K("tv", "transcript_id"),
                value=st.session_state.get("transcript_id", "t.001"),
                help="Enter a transcript identifier, e.g., t.001",
            )
            # Keep a copy in session_state (safe; keys are namespaced)
            st.session_state["transcript_id"] = transcript_id

        with cols[1]:
            btn_load = st.button("Load Segments", key=K("tv", "load_btn"), width='stretch')

        with cols[2]:
            show_raw = st.checkbox("Show raw JSON", key=K("tv", "show_raw"), value=False)

    # Auto-load on first paint OR explicit button
    should_load = btn_load or (not st.session_state.get(K("tv", "has_loaded_once")))
    if should_load and transcript_id.strip():
        data = cached_segments(transcript_id.strip())
        st.session_state[K("tv", "has_loaded_once")] = True

        if isinstance(data, dict) and data.get("error"):
            st.error(f"Could not fetch segments for '{transcript_id}'.")
            with st.expander("Details"):
                st.write(data)
            return

        # Render segments
        if isinstance(data, list) and data:
            # Normalize to DataFrame
            df = pd.json_normalize(data)
            st.markdown(f"**{len(df)}** segments found for **{transcript_id}**.")
            st.dataframe(df, width='stretch')
        else:
            st.info("No segments returned.")

        if show_raw:
            st.code(data, language="json")


def page_review_queue():
    st.subheader("🗂️ Review Queue")

    # Controls (unique keys)
    with st.container():
        cols = st.columns([2, 1])
        with cols[0]:
            query = st.text_input(
                "Filter",
                key=K("rq", "filter"),
                placeholder="e.g., speaker:participant AND contains:'anxiety'",
                help="Client-side filter (simple contains on concatenated fields).",
            )
        with cols[1]:
            refresh = st.button("Refresh", key=K("rq", "refresh"), width='stretch')

    # Fetch queue (refresh busts cache by touching a dummy session key)
    if refresh:
        st.cache_data.clear()

    data = cached_review_queue()
    if isinstance(data, dict) and data.get("error"):
        st.error("Could not fetch review queue.")
        with st.expander("Details"):
            st.write(data)
        return

    # Display
    if isinstance(data, list) and data:
        df = pd.json_normalize(data)
        if query:
            q = query.lower()
            # naive client-side filter
            df["_concat"] = df.astype(str).agg(" ".join, axis=1).str.lower()
            df = df[df["_concat"].str.contains(q, na=False)].drop(columns=["_concat"])
        st.markdown(f"Showing **{len(df)}** items.")
        st.dataframe(df, width='stretch')
    else:
        st.info("Queue is empty.")


def page_codebook_manager():
    st.subheader("🏷️ Codebook Manager")

    with st.container():
        cols = st.columns([2, 1, 1])
        with cols[0]:
            search = st.text_input(
                "Search",
                key=K("cb", "search"),
                placeholder="Find codes, tags, or definitions...",
            )
        with cols[1]:
            # Replaced popover with expander for compatibility
            with st.expander("Info"):
                st.write("The codebook below is fetched from the backend `/codebook` mock fixture.")
        with cols[2]:
            refresh = st.button("Refresh", key=K("cb", "refresh"), width='stretch')

    if refresh:
        st.cache_data.clear()

    data = cached_codebook()
    if isinstance(data, dict) and data.get("error"):
        st.error("Could not fetch codebook.")
        with st.expander("Details"):
            st.write(data)
        return

    if not isinstance(data, list) or not data:
        st.info("No codebook items returned.")
        return

    # Filter locally
    items = data
    if search:
        s = search.lower()

        def _match(item: Dict[str, Any]) -> bool:
            blob = " ".join([
                str(item.get("code", "")),
                str(item.get("label", "")),
                str(item.get("definition", "")),
                " ".join(map(str, item.get("examples", []) or [])),
                " ".join(map(str, item.get("tags", []) or [])),
            ]).lower()
            return s in blob

        items = [it for it in data if _match(it)]

    st.markdown(f"Showing **{len(items)} / {len(data)}** items")

    # Render each item (stable unique keys)
    for idx, item in enumerate(items):
        code = str(item.get("code", f"code_{idx}"))
        with st.expander(f"{code} — {item.get('label', 'Untitled')}", expanded=False):
            col1, col2 = st.columns([2, 1])
            with col1:
                st.markdown(f"**Code**: `{code}`")
                st.write(f"**Label**: {item.get('label', '')}")
                st.write(f"**Definition**: {item.get('definition', '')}")
                examples = item.get("examples") or []
                if examples:
                    st.write("**Examples:**")
                    for j, ex in enumerate(examples):
                        st.markdown(f"- {ex}")
            with col2:
                tags = item.get("tags") or []
                st.write("**Tags**")
                st.write(", ".join(tags) if tags else "—")

            # Local notes (client only)
            st.text_area(
                "Notes (local only)",
                key=K("cb", "notes", code),
                placeholder="Add your notes about this code here…",
            )

def page_search_v2():
    st.subheader("Search (V2)")
    q = st.text_input("Query", value="项目 价值 能力")
    transcript_id = st.text_input("Transcript ID (optional)", value=st.session_state.get("transcript_id", "t.001"))
    k = st.slider("Top K", 1, 50, 10)
    if st.button("Search"):
        with st.spinner("Searching /search/v2 ..."):
            hits = api_get("/search/v2", params={"q": q, "transcript_id": transcript_id or None, "limit": k})
            if isinstance(hits, list) and not hits:
                st.info("No results yet — try a different query or import data.")
        st.write(f"Found {len(hits)} hits")
        st.dataframe([{
            "score": round(h["score"], 3),
            "segment_id": h["id"],
            "index": h["index"],
            "speaker": h.get("speaker"),
            "text": h["text"]
        } for h in hits], use_container_width=True)

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
                use_container_width=True,
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
                        st.dataframe(codes, use_container_width=True)
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
                use_container_width=True,
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
            use_container_width=True,
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
                        st.dataframe(hits, use_container_width=True)
                    else:
                        st.info("No results.")


# -------------------------------
# Router (SINGLE render path)
# -------------------------------
st.title("🧠 QualiAgent — MVP")

# Tabs (simple, prevents double render when used alone)
tabs = st.tabs(["Codebook Manager", "Review Queue", "Transcript Viewer", "Search (V2)", "Legacy"])
with tabs[0]:
    page_codebook_manager()
with tabs[1]:
    page_review_queue()
with tabs[2]:
    page_transcript_viewer()
with tabs[3]:
    page_search_v2()
with tabs[4]:
    page_legacy()

# IMPORTANT:
# Do NOT call page_* functions again below.
# Duplicate calls = duplicate widgets = duplicate keys.
