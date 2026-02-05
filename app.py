import streamlit as st
from groq import Groq
from tavily import TavilyClient

# ==============================================================================
# 🔐 PASTE YOUR KEYS HERE (If you haven't set them in Secrets yet)
# ==============================================================================
# Note: Since you set up Secrets, you technically don't need to paste them here 
# if you use st.secrets["GROQ_API_KEY"], but for now, let's keep it simple.
# ==============================================================================

st.set_page_config(
    page_title="Perplexity Clone",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed" # Hide sidebar by default
)

# --- 1. THE STEALTH MODE (CSS HACK) ---
# This hides the "Manage App" button, the hamburger menu, and the footer.
hide_streamlit_style = """
<style>
    /* Hide the top header line */
    header {visibility: hidden;}
    
    /* Hide the main menu (hamburger) */
    #MainMenu {visibility: hidden;}
    
    /* Hide the footer (Made with Streamlit) */
    footer {visibility: hidden;}
    
    /* Hide the "View Source" button on mobile */
    [data-testid="stToolbar"] {visibility: hidden; display: none;}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# --- 2. SETUP ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# Try to get keys from Secrets (Best Practice) or fall back to hardcoded
# This makes it safe to show code because keys aren't visible
try:
    GROQ_KEY = st.secrets["GROQ_API_KEY"]
    TAVILY_KEY = st.secrets["TAVILY_API_KEY"]
except:
    # If you haven't set up Secrets yet, paste them here temporarily
    GROQ_KEY = "gsk_..." 
    TAVILY_KEY = "tvly-..."

try:
    groq_client = Groq(api_key=GROQ_KEY)
    tavily_client = TavilyClient(api_key=TAVILY_KEY)
except Exception as e:
    st.error(f"❌ Connection Error: {e}")

# --- 3. HELPER FUNCTIONS ---
def search_web(query):
    try:
        response = tavily_client.search(query, max_results=3)
        results = response.get("results", [])
        context = ""
        for i, res in enumerate(results):
            context += f"SOURCE {i+1}: {res['title']} | URL: {res['url']} | CONTENT: {res['content']}\n\n"
        return context, results
    except:
        return "", []

def stream_ai_answer(messages, search_context):
    system_prompt = {
        "role": "system",
        "content": (
            "You are a helpful assistant. Answer the user's question based on the SEARCH RESULTS. "
            "Be direct and concise. Do not explicitly say 'According to the search results'."
            f"\n\nSEARCH RESULTS:\n{search_context}"
        )
    }
    clean_history = [{"role": m["role"], "content": m["content"]} for m in messages]
    
    stream = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[system_prompt] + clean_history,
        temperature=0.7,
        stream=True,
    )
    for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content

# --- 4. MAIN UI ---
st.title("🤖 AI Search Engine")
st.caption("Ask anything. I search the web for you.")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "sources" in message:
            with st.expander("📚 Sources"):
                for source in message["sources"]:
                    st.markdown(f"- [{source['title']}]({source['url']})")

if prompt := st.chat_input("What would you like to know?"):
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("assistant"):
        with st.spinner("Searching..."):
            search_context, sources = search_web(prompt)
        
        full_response = st.write_stream(stream_ai_answer(st.session_state.messages, search_context))
        
        if sources:
            with st.expander("📚 Sources"):
                for source in sources:
                    st.markdown(f"- [{source['title']}]({source['url']})")
    
    st.session_state.messages.append({"role": "assistant", "content": full_response, "sources": sources})
