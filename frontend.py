"""Streamlit chat UI that talks to the FastAPI backend."""
import requests, streamlit as st

API = "http://127.0.0.1:8000/chat"
BADGE = {"chitchat": "💬", "irrelevant": "🚫", "guidance": "📘", "assist": "🛠️"}

st.set_page_config(page_title="Org Assistant", page_icon="🛡️")
st.title("🛡️ Internal Org Assistant")
st.caption("SAST findings · ticket timelines · LLM security report (Project 2)")

if "history" not in st.session_state:
    st.session_state.history = []

for m in st.session_state.history:
    with st.chat_message(m["role"]):
        st.markdown(m.get("badge", "") + m["content"])

if prompt := st.chat_input("Ask about SAST, a ticket timeline, or the report…"):
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    try:
        r = requests.post(API, json={"message": prompt,
                                     "history": [{"role": m["role"], "content": m["content"]}
                                                 for m in st.session_state.history[:-1]]},
                          timeout=600).json()
        badge = f"`{BADGE.get(r['category'],'')} {r['category']}` "
        reply = r["reply"]
    except Exception as e:
        badge, reply = "", f"Backend error: {e}"
    st.session_state.history.append({"role": "assistant", "content": reply, "badge": badge})
    with st.chat_message("assistant"):
        st.markdown(badge + reply)