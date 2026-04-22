"""
Banking Chatbot Frontend — Streamlit
"""

import os
import json
import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from typing import Dict, Any, Optional

st.set_page_config(page_title="Banking Chatbot", page_icon="🏦", layout="wide",
                   initial_sidebar_state="expanded")

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")

st.markdown("""<style>
.main-header{font-size:2.2rem;color:#1a73e8;text-align:center;margin-bottom:.5rem}
.stButton>button{width:100%}
</style>""", unsafe_allow_html=True)


# ── API helper ───────────────────────────────────────────────────────
def api(endpoint: str, method="GET", data=None, files=None) -> Optional[Dict[str, Any]]:
    url = f"{API_BASE_URL}{endpoint}"
    try:
        if method == "GET":
            r = requests.get(url, timeout=30)
        elif method == "POST":
            if files:
                r = requests.post(url, files=files, timeout=60)
            else:
                r = requests.post(url, json=data, timeout=30)
        elif method == "DELETE":
            r = requests.delete(url, timeout=30)
        else:
            return None
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return None
    except requests.exceptions.Timeout:
        st.error("Request timed out.")
    except requests.exceptions.HTTPError as e:
        st.error(f"HTTP error: {e}")
    except Exception as e:
        st.error(f"Error: {e}")
    return None


def check_health() -> bool:
    r = api("/health")
    return r is not None and r.get("status") == "healthy"


def parse_assistant_payload(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Parse structured assistant responses from metadata or JSON text."""
    metadata = message.get("metadata") or {}
    structured = metadata.get("structured_result")
    if isinstance(structured, dict):
        return structured

    content = message.get("content", "")
    if not isinstance(content, str):
        return None

    content = content.strip()
    if not content.startswith("{"):
        return None

    try:
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def render_structured_response(payload: Dict[str, Any]):
    """Render grounded chatbot output in a readable UI format."""
    if payload.get("summary"):
        st.markdown(f"**Summary:** {payload['summary']}")

    if payload.get("result") not in (None, ""):
        if isinstance(payload["result"], (int, float)):
            st.metric("Result", payload["result"])
        else:
            st.markdown(f"**Result:** {payload['result']}")

    if payload.get("status") is not None or payload.get("impact") is not None or payload.get("message"):
        c1, c2 = st.columns(2)
        if payload.get("status") is not None:
            c1.metric("Status", str(payload.get("status")))
        if payload.get("impact") is not None:
            c2.markdown(f"**Impact:** {payload.get('impact')}")
        if payload.get("message"):
            st.info(payload["message"])

    data = payload.get("data")
    if isinstance(data, list) and data:
        st.dataframe(pd.DataFrame(data), use_container_width=True)
    elif isinstance(data, dict) and data:
        st.json(data)

    if payload.get("explanation"):
        st.caption(payload["explanation"])

    if payload.get("sources"):
        st.caption("Sources: " + ", ".join(str(source) for source in payload["sources"]))


# ── Session state ────────────────────────────────────────────────────
for key, default in [("messages", []), ("conversation_id", None),
                     ("uploaded_files", []), ("backend_healthy", False)]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Sidebar ──────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🏦 Banking Chatbot")
    st.session_state.backend_healthy = check_health()
    if st.session_state.backend_healthy:
        st.success("✅ Backend Connected")
    else:
        st.error("❌ Backend Disconnected")
    st.divider()

    page = st.radio("Navigation",
                    ["💬 Chat", "📁 Upload Files", "🤖 Agents", "📊 Statistics"],
                    label_visibility="collapsed")
    st.divider()

    st.subheader("Conversations")
    if st.button("➕ New Conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.conversation_id = None
        st.rerun()
    if st.session_state.messages:
        st.caption(f"Messages: {len(st.session_state.messages)}")
    st.divider()

    st.subheader("Quick Actions")
    quick_queries = [
        "What is my account balance?",
        "How do I apply for a loan?",
        "What are your interest rates?",
        "Help me with KYC verification",
        "Schedule an appointment",
    ]
    selected_quick = None
    for q in quick_queries:
        if st.button(q, use_container_width=True, key=f"q_{hash(q)}"):
            selected_quick = q

    st.divider()
    st.subheader("🔗 Integrations")
    oauth_status = api("/api/oauth/status")
    if oauth_status:
        if oauth_status.get("google", {}).get("configured"):
            st.link_button("🔑 Connect Google", f"{API_BASE_URL}/api/oauth/google/login",
                           use_container_width=True)
        else:
            st.caption("Google OAuth not configured")
        if oauth_status.get("slack", {}).get("configured"):
            st.link_button("💬 Connect Slack", f"{API_BASE_URL}/api/oauth/slack/login",
                           use_container_width=True)
        else:
            st.caption("Slack OAuth not configured")
    else:
        st.caption("Backend not reachable")


# ── Chat helper ──────────────────────────────────────────────────────
def handle_user_message(prompt: str):
    st.session_state.messages.append({"role": "user", "content": prompt})
    resp = api("/api/chat/message", method="POST",
               data={"message": prompt,
                     "conversation_id": st.session_state.conversation_id})
    if resp and resp.get("success"):
        st.session_state.conversation_id = resp.get("conversation_id")
        st.session_state.messages.append({
            "role": "assistant",
            "content": resp.get("response", ""),
            "metadata": resp.get("metadata", {}),
        })
    else:
        st.session_state.messages.append({
            "role": "assistant",
            "content": "Sorry, I couldn't get a response. Please try again.",
        })


# ══════════════════════════════════════════════════════════════════════
# PAGES
# ══════════════════════════════════════════════════════════════════════

if page == "💬 Chat":
    st.markdown('<h1 class="main-header">💬 Chat with Banking Assistant</h1>',
                unsafe_allow_html=True)

    if selected_quick:
        handle_user_message(selected_quick)
        st.rerun()

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            parsed_payload = parse_assistant_payload(msg) if msg["role"] == "assistant" else None
            if parsed_payload:
                render_structured_response(parsed_payload)
            else:
                st.markdown(msg["content"])
            if msg.get("metadata"):
                with st.expander("📋 Details"):
                    st.json(msg["metadata"])

    if prompt := st.chat_input("Ask me anything about banking..."):
        handle_user_message(prompt)
        st.rerun()

elif page == "📁 Upload Files":
    st.markdown('<h1 class="main-header">📁 Upload Data Files</h1>',
                unsafe_allow_html=True)
    st.markdown("Upload CSV, Excel, or XML files to enable grounded banking queries.")

    uploaded_file = st.file_uploader("Choose a file", type=["csv", "xlsx", "xls", "xml"],
                                     help="Supported: CSV, XLSX, XLS, XML")
    if uploaded_file is not None:
        st.info(f"📄 {uploaded_file.name} ({uploaded_file.size:,} bytes)")
        if st.button("🚀 Upload and Process", use_container_width=True):
            with st.spinner("Uploading and processing..."):
                result = api("/api/files/upload", method="POST",
                             files={"file": (uploaded_file.name, uploaded_file,
                                             uploaded_file.type or "application/octet-stream")})
                if result and result.get("success"):
                    st.success("✅ File uploaded and processed!")
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Rows", result.get("row_count", 0))
                    c2.metric("Columns", result.get("column_count", 0))
                    c3.metric("Chunks", result.get("chunk_count", 0))
                    c4.metric("Type", result.get("file_type", "N/A"))
                    st.session_state.uploaded_files.append({
                        "filename": result.get("filename"),
                        "file_id": result.get("file_id"),
                        "row_count": result.get("row_count"),
                        "column_count": result.get("column_count"),
                        "chunk_count": result.get("chunk_count"),
                        "columns": result.get("columns", []),
                    })
                    if result.get("columns"):
                        st.subheader("📋 Columns")
                        st.write(", ".join(result["columns"]))
                    for w in result.get("warnings", []):
                        st.warning(w)
                else:
                    st.error(f"Upload failed: {result}")

    if st.session_state.uploaded_files:
        st.divider()
        st.subheader("📚 Uploaded Files")
        for fi in st.session_state.uploaded_files:
            with st.expander(f"📄 {fi['filename']}"):
                st.write(f"Rows: {fi['row_count']} | Columns: {fi['column_count']} "
                         f"| Chunks: {fi['chunk_count']}")
                st.write(f"Columns: {', '.join(fi['columns'])}")

elif page == "🤖 Agents":
    st.markdown('<h1 class="main-header">🤖 Available Agents</h1>',
                unsafe_allow_html=True)
    with st.spinner("Loading agents..."):
        agents_resp = api("/api/chat/agents")
    if agents_resp and agents_resp.get("success"):
        caps = agents_resp.get("capabilities", {})
        if caps:
            cols = st.columns(min(len(caps), 3))
            for idx, (name, info) in enumerate(caps.items()):
                with cols[idx % len(cols)]:
                    st.subheader(info.get("name", name))
                    st.caption(info.get("description", ""))
                    for c in info.get("capabilities", []):
                        st.write(f"• {c.replace('_', ' ').title()}")
                    if info.get("requires_authentication"):
                        st.warning("🔒 Requires Auth")

    st.divider()
    st.subheader("📊 System Status")
    health = api("/health")
    if health:
        c1, c2 = st.columns(2)
        c1.metric("Status", health.get("status", "Unknown"))
        c2.metric("Version", health.get("version", "N/A"))

    services = api("/health/services")
    if services:
        st.subheader("🔧 Services")
        for sname, sinfo in services.items():
            if sinfo.get("status") == "healthy":
                st.success(f"✅ {sname}: {sinfo.get('message', '')}")
            else:
                st.error(f"❌ {sname}: {sinfo.get('message', sinfo.get('status', ''))}")

elif page == "📊 Statistics":
    st.markdown('<h1 class="main-header">📊 Statistics</h1>',
                unsafe_allow_html=True)

    st.subheader("💬 Conversation Statistics")
    if st.session_state.messages:
        user_msgs = [m for m in st.session_state.messages if m["role"] == "user"]
        bot_msgs = [m for m in st.session_state.messages if m["role"] == "assistant"]
        c1, c2, c3 = st.columns(3)
        c1.metric("User Messages", len(user_msgs))
        c2.metric("Assistant Responses", len(bot_msgs))
        c3.metric("Total", len(st.session_state.messages))

        agent_types: Dict[str, int] = {}
        for m in bot_msgs:
            at = (m.get("metadata") or {}).get("agent_type", "unknown")
            agent_types[at] = agent_types.get(at, 0) + 1
        if agent_types:
            st.subheader("🤖 Agent Usage")
            df = pd.DataFrame({"Agent": list(agent_types.keys()),
                                "Count": list(agent_types.values())})
            st.bar_chart(df.set_index("Agent"))
    else:
        st.info("No messages yet. Start chatting!")

    st.subheader("📁 File Statistics")
    if st.session_state.uploaded_files:
        c1, c2 = st.columns(2)
        c1.metric("Files", len(st.session_state.uploaded_files))
        c2.metric("Total Chunks",
                  sum(f["chunk_count"] for f in st.session_state.uploaded_files))
        st.dataframe(pd.DataFrame(st.session_state.uploaded_files),
                     use_container_width=True)
    else:
        st.info("No files uploaded yet.")

# ── Footer ───────────────────────────────────────────────────────────
st.divider()
st.caption(f"Banking Chatbot v1.0 | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
