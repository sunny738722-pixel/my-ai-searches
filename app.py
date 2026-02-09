import streamlit as st
from groq import Groq
from tavily import TavilyClient

# ------------------------------------------------------------------
# 1. PAGE CONFIGURATION
# ------------------------------------------------------------------
st.set_page_config(
    page_title="Sunny's AI",
    page_icon="🤖",
    layout="wide"  # "Wide" layout uses more screen space
)

# ------------------------------------------------------------------
# 2. SIDEBAR (The Control Panel)
# ------------------------------------------------------------------
with st.sidebar:
    st.title("⚙️ Settings")
    
    # Feature 1: Model Selector
    st.markdown("### Choose your Brain")
    selected_model = st.selectbox(
        "Model:",
        options=["llama-3.1-8b-instant", "llama-3.3-70b-versatile", "mixtral-8x7b-32768"],
        index=0, # Default to the fast one
        help="70b is smarter but slower. 8b is fastest."
    )
    
    st.markdown("---")
    
    # Feature 2: Clear History Button
    if st.button("🧹 Clear Chat History", type="primary"):
        st.session_state.messages = []
        st.rerun() # Refreshes the app instantly

    st.markdown("---")
    st.caption("Powered by Groq & Tavily")

# ------------------------------------------------------------------
# 3. LOAD API KEYS (Safety First)
# ------------------------------------------------------------------
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
    TAVILY_API_KEY = st.secrets["TAVILY_API_KEY"]
except Exception:
    st.error("🚨 Secrets are missing! Please add them in Streamlit Settings.")
    st.stop()

# Initialize Tools
try:
    groq_client = Groq(api_key=GROQ_API_KEY)
    tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
except Exception as e:
    st.error(f"❌ Connection Error: {e}")
    st.stop()

# ------------------------------------------------------------------
# 4. CORE LOGIC (Search & Think)
# ------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

def search_web(query):
    """Searches the web and returns neat results"""
    try:
        response = tavily_client.search(query, max_results=3)
        results = response.get("results", [])
        context_text = ""
        for i, result in enumerate(results):
            context_text += f"SOURCE {i+1}: {result['title']} | URL: {result['url']} | CONTENT: {result['content']}\n\n"
        return context_text, results
    except Exception:
        return "", []

def stream_ai_answer(messages, search_context, model_name):
    """Streams the answer using the SELECTED model"""
    system_prompt = {
        "role": "system",
        "content": (
            "You are a helpful assistant. Answer based on the SEARCH RESULTS provided."
            "Always cite your sources."
            f"\n\nSEARCH RESULTS:\n{search_context}"
        )
    }
    
    # Clean history for Groq
    clean_history = [{"role": m["role"], "content": m["content"]} for m in messages]
    
    try:
        stream = groq_client.chat.completions.create(
            model=model_name,  # <--- We use the variable here!
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
# 5. MAIN INTERFACE
# ------------------------------------------------------------------
st.title("🤖 Sunny's AI")
st.caption(f"Running on: {selected_model}") # Shows which brain is active

# Draw History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "sources" in message:
            with st.expander("📚 Sources"):
                for source in message["sources"]:
                    st.markdown(f"- [{source['title']}]({source['url']})")

# Input Box
if prompt := st.chat_input("Ask me anything..."):
    
    # User message
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Assistant message
    with st.chat_message("assistant"):
        with st.spinner("🔎 Searching..."):
            search_context, sources = search_web(prompt)
        
        # We pass the 'selected_model' from the sidebar to the function
        full_response = st.write_stream(stream_ai_answer(st.session_state.messages, search_context, selected_model))
        
        if sources:
            with st.expander("📚 Sources Used"):
                for source in sources:
                    st.markdown(f"- [{source['title']}]({source['url']})")
    
    st.session_state.messages.append({
        "role": "assistant", 
        "content": full_response,
        "sources": sources
    })
