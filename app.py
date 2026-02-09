import streamlit as st
from groq import Groq
from tavily import TavilyClient
import uuid
import json
import PyPDF2 # The new tool for reading PDFs

# ------------------------------------------------------------------
# 1. PAGE CONFIGURATION
# ------------------------------------------------------------------
st.set_page_config(page_title="Sunny's Research AI", page_icon="🧠", layout="wide")

st.markdown("""
<style>
    .stChatInput {position: fixed; bottom: 20px;}
    .stChatMessage {padding: 1rem; border-radius: 10px; margin-bottom: 1rem;}
    .stStatus {border: 1px solid #e0e0e0; border-radius: 10px; background: #f9f9f9;}
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# 2. SESSION STATE
# ------------------------------------------------------------------
if "all_chats" not in st.session_state:
    st.session_state.all_chats = {} 
if "active_chat_id" not in st.session_state:
    new_id = str(uuid.uuid4())
    st.session_state.all_chats[new_id] = {"title": "New Chat", "messages": [], "doc_text": ""}
    st.session_state.active_chat_id = new_id

# Helper to get active chat
active_id = st.session_state.active_chat_id
# Safety check
if active_id not in st.session_state.all_chats:
    st.session_state.all_chats[active_id] = {"title": "New Chat", "messages": [], "doc_text": ""}
active_chat = st.session_state.all_chats[active_id]

# ------------------------------------------------------------------
# 3. SIDEBAR
# ------------------------------------------------------------------
with st.sidebar:
    st.title("🧠 Research Center")
    
    # --- NEW FEATURE: DOCUMENT UPLOADER ---
    st.markdown("### 📂 Knowledge Base")
    uploaded_file = st.file_uploader("Upload a PDF to chat with it:", type="pdf")
    
    if uploaded_file:
        # Extract text from PDF
        try:
            reader = PyPDF2.PdfReader(uploaded_file)
            doc_text = ""
            for page in reader.pages:
                doc_text += page.extract_text() + "\n"
            
            # Save to current chat memory
            st.session_state.all_chats[active_id]["doc_text"] = doc_text
            st.success(f"✅ Loaded: {uploaded_file.name}")
        except Exception as e:
            st.error(f"Error reading PDF: {e}")

    if st.session_state.all_chats[active_id].get("doc_text"):
        st.info("📄 Document Active: The AI will answer based on this file.")

    st.divider()
    
    # Deep Mode Toggle
    st.markdown("### 🕵️ Search Mode")
    deep_mode = st.toggle("🚀 Deep Research", value=False, help="Enable for complex web searches.")
    
    st.divider()
    
    # Chat Controls
    if st.button("➕ New Discussion", use_container_width=True, type="primary"):
        new_id = str(uuid.uuid4())
        st.session_state.all_chats[new_id] = {"title": "New Chat", "messages": [], "doc_text": ""}
        st.session_state.active_chat_id = new_id
        st.rerun()

    # History
    st.markdown("### 🗂️ History")
    for chat_id in reversed(list(st.session_state.all_chats.keys())):
        chat = st.session_state.all_chats[chat_id]
        is_active = (chat_id == st.session_state.active_chat_id)
        
        col1, col2 = st.columns([0.85, 0.15]) 
        with col1:
            if st.button(f"📄 {chat['title']}", key=f"btn_{chat_id}", use_container_width=True, type="primary" if is_active else "secondary"):
                st.session_state.active_chat_id = chat_id
                st.rerun()
        with col2:
            if st.button("❌", key=f"del_{chat_id}"):
                del st.session_state.all_chats[chat_id]
                if chat_id == st.session_state.active_chat_id:
                    new_id = str(uuid.uuid4())
                    st.session_state.all_chats[new_id] = {"title": "New Chat", "messages": [], "doc_text": ""}
                    st.session_state.active_chat_id = new_id
                st.rerun()

# ------------------------------------------------------------------
# 4. API KEYS
# ------------------------------------------------------------------
try:
    groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    tavily_client = TavilyClient(api_key=st.secrets["TAVILY_API_KEY"])
except Exception:
    st.error("🚨 API Keys missing! Check Streamlit Settings.")
    st.stop()

# ------------------------------------------------------------------
# 5. LOGIC FUNCTIONS
# ------------------------------------------------------------------

def generate_sub_queries(user_query):
    # (Same as before)
    system_prompt = "You are a search expert. Return 3 search queries as a JSON list. Example: [\"q1\", \"q2\"]"
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_query}],
            temperature=0, response_format={"type": "json_object"}
        )
        json_data = json.loads(response.choices[0].message.content)
        return list(json_data.values())[0]
    except:
        return [user_query]

def search_web(query, is_deep_mode):
    # (Same as before)
    if is_deep_mode:
        with st.status("🕵️ Deep Research...", expanded=True) as status:
            sub_queries = generate_sub_queries(query)
            final_results = []
            for q in sub_queries:
                st.write(f"🔎 Searching: '{q}'...")
                try:
                    results = tavily_client.search(q, max_results=3).get("results", [])
                    final_results.extend(results)
                except: continue
            
            # Deduplicate
            seen = set()
            unique = []
            for r in final_results:
                if r['url'] not in seen:
                    unique.append(r)
                    seen.add(r['url'])
            status.update(label="✅ Research Complete", state="complete", expanded=False)
            return unique
    else:
        return tavily_client.search(query, max_results=5).get("results", [])

def stream_ai_answer(messages, search_results, doc_text):
    # --- PROMPT ENGINEERING: THE LIBRARIAN ---
    
    # 1. Format Web Results
    web_context = ""
    if search_results:
        for i, r in enumerate(search_results):
            web_context += f"WEB SOURCE {i+1}: {r['title']} | {r['content']}\n"
            
    # 2. Format Document Context
    doc_context = ""
    if doc_text:
        doc_context = f"\n\n📂 UPLOADED DOCUMENT CONTENT:\n{doc_text[:30000]}..." # Limit to 30k chars to be safe

    # 3. Build the Master Prompt
    system_prompt = {
        "role": "system",
        "content": (
            "You are an expert research assistant."
            "\n- If the user asks about the Uploaded Document, prioritize the content in '📂 UPLOADED DOCUMENT CONTENT'."
            "\n- If the user asks a general question, use the 'WEB SOURCE' information."
            "\n- Always cite your sources (e.g., [Page 2] or [Source 1])."
            f"\n\n{web_context}"
            f"\n\n{doc_context}"
        )
    }
    
    clean_history = [{"role": m["role"], "content": m["content"]} for m in messages]
    
    try:
        stream = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[system_prompt] + clean_history,
            temperature=0.6,
            stream=True,
        )
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        yield f"❌ Error: {e}"

# ------------------------------------------------------------------
# 6. MAIN UI
# ------------------------------------------------------------------
st.title(f"{active_chat['title']}")

# Display History
for message in active_chat["messages"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "sources" in message and message["sources"]:
            with st.expander(f"📚 {len(message['sources'])} Web Sources"):
                for source in message["sources"]:
                    st.markdown(f"- [{source['title']}]({source['url']})")

# Input Handling
if prompt := st.chat_input("Ask about your PDF or the web..."):
    
    with st.chat_message("user"):
        st.markdown(prompt)
    active_chat["messages"].append({"role": "user", "content": prompt})
    
    # Rename silently
    if len(active_chat["messages"]) == 1:
        st.session_state.all_chats[active_id]["title"] = " ".join(prompt.split()[:5]) + "..."
    
    with st.chat_message("assistant"):
        # 1. Decide if we need to search the web
        # (If deep mode is ON, we always search. If OFF, we only search if no doc is present OR if prompt implies it)
        search_results = []
        if deep_mode or not active_chat["doc_text"]:
             if deep_mode:
                 search_results = search_web(prompt, True)
             else:
                 with st.spinner("🔎 Searching..."):
                     search_results = search_web(prompt, False)
        
        # 2. Generate Answer (Injecting both Web + Doc context)
        full_response = st.write_stream(
            stream_ai_answer(active_chat["messages"], search_results, active_chat["doc_text"])
        )
        
        if search_results:
            with st.expander("📚 Sources Used"):
                for source in search_results:
                    st.markdown(f"- [{source['title']}]({source['url']})")
    
    active_chat["messages"].append({
        "role": "assistant", 
        "content": full_response,
        "sources": search_results
    })
    
    if len(active_chat["messages"]) == 2:
        st.rerun()
