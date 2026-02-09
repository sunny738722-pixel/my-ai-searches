import streamlit as st
from groq import Groq
from tavily import TavilyClient
import uuid # For generating unique chat IDs

# ------------------------------------------------------------------
# 1. PAGE CONFIGURATION (v7 Style)
# ------------------------------------------------------------------
st.set_page_config(
    page_title="Sunny's AI",
    page_icon="🤖",
    layout="wide"
)

# ------------------------------------------------------------------
# 2. SESSION STATE SETUP (The Multi-Chat Brain)
# ------------------------------------------------------------------
# Initialize the "Master List" of all chats if it doesn't exist
if "all_chats" not in st.session_state:
    st.session_state.all_chats = {} # Dictionary to store all convos

# Initialize the "Current Chat ID" tracker
if "active_chat_id" not in st.session_state:
    new_id = str(uuid.uuid4())
    st.session_state.all_chats[new_id] = {"title": "New Chat", "messages": []}
    st.session_state.active_chat_id = new_id

# ------------------------------------------------------------------
# 3. SIDEBAR (The Navigator)
# ------------------------------------------------------------------
with st.sidebar:
    st.title("💬 Your Chats")
    
    # [BUTTON] Create New Chat
    if st.button("➕ New Chat", use_container_width=True, type="primary"):
        new_id = str(uuid.uuid4())
        st.session_state.all_chats[new_id] = {"title": "New Chat", "messages": []}
        st.session_state.active_chat_id = new_id
        st.rerun()

    st.divider()
    
    # [LIST] Show Past Chats
    # We loop through all saved chats and make a button for each
    chat_ids = list(st.session_state.all_chats.keys())
    
    # Reverse so newest is at top
    for chat_id in reversed(chat_ids):
        chat_data = st.session_state.all_chats[chat_id]
        
        # Highlight the button if it's the active one
        button_type = "primary" if chat_id == st.session_state.active_chat_id else "secondary"
        
        col1, col2 = st.columns([0.85, 0.15]) 
        with col1:
            if st.button(f"📝 {chat_data['title']}", key=f"btn_{chat_id}", use_container_width=True, type=button_type):
                st.session_state.active_chat_id = chat_id
                st.rerun()
        with col2:
            # Delete Button (Small 'x')
            if st.button("❌", key=f"del_{chat_id}"):
                del st.session_state.all_chats[chat_id]
                # If we deleted the active chat, reset to a new one
                if chat_id == st.session_state.active_chat_id:
                    new_id = str(uuid.uuid4())
                    st.session_state.all_chats[new_id] = {"title": "New Chat", "messages": []}
                    st.session_state.active_chat_id = new_id
                st.rerun()

    st.divider()
    
    # [SETTINGS] - Kept from v7.0
    st.header("⚙️ Settings")
    selected_model = st.selectbox(
        "AI Model:",
        options=["llama-3.1-8b-instant", "llama-3.3-70b-versatile"],
        index=0
    )

# ------------------------------------------------------------------
# 4. API KEYS & TOOLS
# ------------------------------------------------------------------
try:
    groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    tavily_client = TavilyClient(api_key=st.secrets["TAVILY_API_KEY"])
except Exception:
    st.error("🚨 API Keys missing! Check Streamlit Settings.")
    st.stop()

def search_web(query):
    try:
        response = tavily_client.search(query, max_results=3)
        return response.get("results", [])
    except:
        return []

def stream_ai_answer(messages, search_context, model_name):
    system_prompt = {
        "role": "system",
        "content": (
            "You are a helpful assistant. Answer based on the SEARCH RESULTS provided."
            f"\n\nSEARCH RESULTS:\n{search_context}"
        )
    }
    clean_history = [{"role": m["role"], "content": m["content"]} for m in messages]
    
    try:
        stream = groq_client.chat.completions.create(
            model=model_name,
            messages=[system_prompt] + clean_history,
            temperature=0.7,
            stream=True,
        )
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        yield f"❌ Error: {e}"

# ------------------------------------------------------------------
# 5. MAIN CHAT INTERFACE
# ------------------------------------------------------------------
# Get the active chat data
active_id = st.session_state.active_chat_id
active_chat = st.session_state.all_chats[active_id]

st.title(f"🤖 {active_chat['title']}")

# Draw History for THIS chat only
for message in active_chat["messages"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "sources" in message and message["sources"]:
            with st.expander("📚 Sources"):
                for source in message["sources"]:
                    st.markdown(f"- [{source['title']}]({source['url']})")

# Input Box
if prompt := st.chat_input("Ask me anything..."):
    
    # 1. Update Title if it's the first message
    if len(active_chat["messages"]) == 0:
        # We take the first 4 words of the prompt as the title
        title_words = prompt.split()[:4]
        new_title = " ".join(title_words) + "..."
        st.session_state.all_chats[active_id]["title"] = new_title
        # Force rerun to update the sidebar title instantly
        st.rerun()

    # 2. Show User Message
    with st.chat_message("user"):
        st.markdown(prompt)
    # Save to SPECIFIC chat history
    st.session_state.all_chats[active_id]["messages"].append({"role": "user", "content": prompt})
    
    # 3. AI Processing
    with st.chat_message("assistant"):
        with st.spinner("🔎 Searching..."):
            search_context, sources = search_web(prompt)
        
        full_response = st.write_stream(
            stream_ai_answer(st.session_state.all_chats[active_id]["messages"], search_context, selected_model)
        )
        
        if sources:
            with st.expander("📚 Sources Used"):
                for source in sources:
                    st.markdown(f"- [{source['title']}]({source['url']})")
    
    # Save Assistant Response to SPECIFIC chat history
    st.session_state.all_chats[active_id]["messages"].append({
        "role": "assistant", 
        "content": full_response,
        "sources": sources
    })
