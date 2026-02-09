import streamlit as st
from groq import Groq
from tavily import TavilyClient
import uuid
import json

# ------------------------------------------------------------------
# 1. PAGE CONFIGURATION
# ------------------------------------------------------------------
st.set_page_config(page_title="Sunny's Research AI", page_icon="🧠", layout="wide")

st.markdown("""
<style>
    .stChatInput {position: fixed; bottom: 20px;}
    .stChatMessage {padding: 1rem; border-radius: 10px; margin-bottom: 1rem;}
    /* Make the status box look cool */
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
    st.session_state.all_chats[new_id] = {"title": "New Chat", "messages": []}
    st.session_state.active_chat_id = new_id

# ------------------------------------------------------------------
# 3. SIDEBAR
# ------------------------------------------------------------------
with st.sidebar:
    st.title("🧠 Research Center")
    
    # 1. DEEP MODE TOGGLE (The New Feature)
    st.markdown("### 🕵️ Search Mode")
    deep_mode = st.toggle("🚀 Deep Research", value=False, help="Runs multiple searches for complex questions. Slower but smarter.")
    
    st.divider()
    
    # 2. CHAT CONTROLS
    if st.button("➕ New Discussion", use_container_width=True, type="primary"):
        new_id = str(uuid.uuid4())
        st.session_state.all_chats[new_id] = {"title": "New Chat", "messages": []}
        st.session_state.active_chat_id = new_id
        st.rerun()

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
                    st.session_state.all_chats[new_id] = {"title": "New Chat", "messages": []}
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
# 5. SMART LOGIC (Deep Research)
# ------------------------------------------------------------------

def generate_sub_queries(user_query):
    """Asks the AI to break the user's question into 3 search terms"""
    system_prompt = (
        "You are a search engine expert. Break the user's question into 3 distinct, high-quality search queries "
        "to gather comprehensive information. Return ONLY a JSON list of strings. "
        "Example: [\"query 1\", \"query 2\", \"query 3\"]"
    )
    
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant", # Use fast model for this simple task
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ],
            temperature=0,
            response_format={"type": "json_object"}
        )
        # Parse the JSON response
        json_data = json.loads(response.choices[0].message.content)
        # Handle cases where the AI might use different keys
        if "queries" in json_data:
            return json_data["queries"]
        elif "list" in json_data:
            return json_data["list"]
        else:
            return list(json_data.values())[0] # Grab the first list found
    except:
        # Fallback if AI fails
        return [user_query]

def search_web(query, is_deep_mode):
    """
    Standard Mode: 1 Search
    Deep Mode: 3 Searches (15+ results)
    """
    final_results = []
    status_msg = st.empty() # Placeholder for updates
    
    if is_deep_mode:
        # Step 1: Brainstorm
        with st.status("🕵️ Deep Research in progress...", expanded=True) as status:
            st.write("🤔 Breaking down the question...")
            sub_queries = generate_sub_queries(query)
            
            # Step 2: Multi-Search
            for q in sub_queries:
                st.write(f"🔎 Searching: '{q}'...")
                try:
                    response = tavily_client.search(q, max_results=4)
                    results = response.get("results", [])
                    final_results.extend(results)
                except:
                    continue
            
            # Remove duplicates based on URL
            seen_urls = set()
            unique_results = []
            for r in final_results:
                if r['url'] not in seen_urls:
                    unique_results.append(r)
                    seen_urls.add(r['url'])
            
            st.write(f"📚 Analyzed {len(unique_results)} sources.")
            status.update(label="✅ Deep Research Complete", state="complete", expanded=False)
            final_results = unique_results
            
    else:
        # Standard Mode (Fast)
        response = tavily_client.search(query, max_results=5)
        final_results = response.get("results", [])

    # Format for AI
    context_text = ""
    for i, result in enumerate(final_results):
        context_text += f"SOURCE {i+1}: {result['title']} | URL: {result['url']} | CONTENT: {result['content']}\n\n"
        
    return context_text, final_results

def stream_ai_answer(messages, search_context):
    system_prompt = {
        "role": "system",
        "content": (
            "You are a professional research assistant. "
            "Using the extensive context provided, write a comprehensive, detailed answer. "
            "\n- Use H2 and H3 headers to organize sections."
            "\n- Use bullet points for readability."
            "\n- Cite sources [1], [2] frequently."
            "\n- Be objective and thorough."
            f"\n\nSEARCH CONTEXT:\n{search_context}"
        )
    }
    
    clean_history = [{"role": m["role"], "content": m["content"]} for m in messages]
    
    try:
        stream = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile", # Always use the smart model
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
if st.session_state.active_chat_id not in st.session_state.all_chats:
    new_id = str(uuid.uuid4())
    st.session_state.all_chats[new_id] = {"title": "New Chat", "messages": []}
    st.session_state.active_chat_id = new_id

active_id = st.session_state.active_chat_id
active_chat = st.session_state.all_chats[active_id]

st.title(f"{active_chat['title']}")

# Display History
for message in active_chat["messages"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "sources" in message and message["sources"]:
            with st.expander(f"📚 {len(message['sources'])} Sources"):
                for source in message["sources"]:
                    st.markdown(f"- [{source['title']}]({source['url']})")

# Input Handling
if prompt := st.chat_input("Ask a question..."):
    
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.all_chats[active_id]["messages"].append({"role": "user", "content": prompt})
    
    # Rename silently
    if len(active_chat["messages"]) == 1:
        st.session_state.all_chats[active_id]["title"] = " ".join(prompt.split()[:5]) + "..."
    
    with st.chat_message("assistant"):
        # We pass the "deep_mode" toggle value to the search function
        if not deep_mode:
            with st.spinner("🔎 Searching..."):
                search_context, sources = search_web(prompt, False)
        else:
            # Deep mode has its own spinner inside the function
            search_context, sources = search_web(prompt, True)
            
        full_response = st.write_stream(
            stream_ai_answer(st.session_state.all_chats[active_id]["messages"], search_context)
        )
        
        if sources:
            with st.expander("📚 Sources Used"):
                for source in sources:
                    st.markdown(f"- [{source['title']}]({source['url']})")
    
    st.session_state.all_chats[active_id]["messages"].append({
        "role": "assistant", 
        "content": full_response,
        "sources": sources
    })
    
    # Sidebar refresh
    if len(active_chat["messages"]) == 2:
        st.rerun()
