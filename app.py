import streamlit as st
from groq import Groq
from tavily import TavilyClient
import uuid
import json
import PyPDF2
from fpdf import FPDF
import pandas as pd
import re

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
    st.session_state.all_chats[new_id] = {
        "title": "New Chat", 
        "messages": [], 
        "doc_text": "", 
        "dataframe": None,
        "file_name": ""
    }
    st.session_state.active_chat_id = new_id

active_id = st.session_state.active_chat_id
if active_id not in st.session_state.all_chats:
    st.session_state.all_chats[active_id] = {"title": "New Chat", "messages": [], "doc_text": "", "dataframe": None}
active_chat = st.session_state.all_chats[active_id]

# ------------------------------------------------------------------
# 3. SIDEBAR
# ------------------------------------------------------------------
with st.sidebar:
    st.title("🧠 Research Center")
    
    # A. DATA ANALYST (Path A)
    st.markdown("### 📊 Data Analyst")
    uploaded_csv = st.file_uploader("Upload CSV or Excel:", type=["csv", "xlsx"])
    
    if uploaded_csv:
        try:
            if uploaded_csv.name.endswith('.csv'):
                df = pd.read_csv(uploaded_csv)
            else:
                df = pd.read_excel(uploaded_csv)
            
            st.session_state.all_chats[active_id]["dataframe"] = df
            st.session_state.all_chats[active_id]["file_name"] = uploaded_csv.name
            st.success(f"✅ Loaded Data: {uploaded_csv.name} ({len(df)} rows)")
        except Exception as e:
            st.error(f"Error reading data: {e}")

    # B. LIBRARIAN (PDF)
    st.markdown("### 📂 Document Reader")
    uploaded_pdf = st.file_uploader("Upload PDF:", type="pdf")
    if uploaded_pdf:
        try:
            reader = PyPDF2.PdfReader(uploaded_pdf)
            doc_text = ""
            for page in reader.pages:
                doc_text += page.extract_text() + "\n"
            st.session_state.all_chats[active_id]["doc_text"] = doc_text
            st.success(f"✅ Loaded PDF: {uploaded_pdf.name}")
        except Exception as e:
            st.error(f"Error reading PDF: {e}")

    st.divider()
    
    # SETTINGS
    deep_mode = st.toggle("🚀 Deep Research", value=False)
    
    # EXPORT
    if st.button("📥 Download Chat PDF"):
        if active_chat["messages"]:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            pdf.cell(200, 10, txt=f"Report: {active_chat['title']}", ln=True, align='C')
            for msg in active_chat["messages"]:
                role = "User" if msg["role"] == "user" else "AI"
                clean_content = msg["content"].encode('latin-1', 'replace').decode('latin-1')
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(200, 10, txt=f"{role}:", ln=True)
                pdf.set_font("Arial", size=10)
                pdf.multi_cell(0, 10, txt=clean_content)
                pdf.ln(5)
            st.download_button("Click to Save PDF", data=pdf.output(dest='S').encode('latin-1'), file_name="report.pdf")

    # NEW CHAT & HISTORY
    if st.button("➕ New Discussion", use_container_width=True, type="primary"):
        new_id = str(uuid.uuid4())
        st.session_state.all_chats[new_id] = {"title": "New Chat", "messages": [], "doc_text": "", "dataframe": None}
        st.session_state.active_chat_id = new_id
        st.rerun()

    st.markdown("### 🗂️ History")
    for chat_id in reversed(list(st.session_state.all_chats.keys())):
        chat = st.session_state.all_chats[chat_id]
        is_active = (chat_id == st.session_state.active_chat_id)
        if st.button(f"📄 {chat['title']}", key=f"btn_{chat_id}", use_container_width=True, type="primary" if is_active else "secondary"):
            st.session_state.active_chat_id = chat_id
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
def transcribe_audio(audio_bytes):
    try:
        audio_bytes.seek(0)
        return groq_client.audio.transcriptions.create(file=("voice.wav", audio_bytes), model="whisper-large-v3", response_format="text")
    except: return None

def classify_intent(user_query, has_data=False):
    # If we have data, we prioritize DATA analysis
    if has_data:
        if "plot" in user_query.lower() or "chart" in user_query.lower() or "graph" in user_query.lower():
            return "PLOT"
        if "analyze" in user_query.lower() or "summary" in user_query.lower():
            return "ANALYZE"
            
    system_prompt = "Classify intent: 'SEARCH' (facts/news), 'CHAT' (casual). Return ONLY word."
    try:
        resp = groq_client.chat.completions.create(model="llama-3.1-8b-instant", messages=[{"role":"system","content":system_prompt},{"role":"user","content":user_query}], max_tokens=10)
        return resp.choices[0].message.content.strip().upper()
    except: return "SEARCH"

def search_web(query, is_deep_mode):
    if is_deep_mode: return tavily_client.search(query, max_results=5).get("results", []) # Simplified for brevity
    return tavily_client.search(query, max_results=3).get("results", [])

def execute_python_code(code, df):
    """
    Executes AI-generated Python code safely.
    The code has access to: 'pd', 'st', 'df'
    """
    local_vars = {"pd": pd, "st": st, "df": df}
    try:
        exec(code, {}, local_vars)
        return "✅ Code Executed Successfully"
    except Exception as e:
        return f"❌ Code Error: {e}"

def stream_ai_answer(messages, search_results, doc_text, df):
    # 1. Build Context
    context = ""
    if search_results:
        context += "\nWEB SOURCES:\n" + "\n".join([f"- {r['title']}: {r['content']}" for r in search_results])
    if doc_text:
        context += f"\n\nDOCUMENT CONTEXT:\n{doc_text[:20000]}..."
    if df is not None:
        context += f"\n\nDATAFRAME PREVIEW:\n{df.head().to_markdown()}"
        context += "\n\nINSTRUCTIONS: If asked to visualize/plot, write Python code wrapped in ```python ... ``` blocks. Use 'st.bar_chart(df)', 'st.line_chart(df)', or 'st.write(df)'. Do NOT use plt.show()."

    system_prompt = {
        "role": "system",
        "content": (
            "You are a helpful AI Assistant. "
            "Use the provided context to answer. "
            "If writing code, keep it simple and use Streamlit functions."
            f"{context}"
        )
    }
    
    clean_history = [{"role": m["role"], "content": m["content"]} for m in messages]
    
    try:
        stream = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[system_prompt] + clean_history,
            temperature=0.5,
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

# Display History (and Charts!)
for i, message in enumerate(active_chat["messages"]):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        # Check for saved charts/code execution in history
        if "code_ran" in message and active_chat["dataframe"] is not None:
            with st.expander("📊 Analysis Output"):
                execute_python_code(message["code_ran"], active_chat["dataframe"])

# Input
audio_value = st.audio_input("🎙️")
prompt = st.chat_input("Ask about data, docs, or web...")
final_prompt = None

if audio_value:
    with st.spinner("Transcribing..."):
        final_prompt = transcribe_audio(audio_value)
if prompt:
    final_prompt = prompt

if final_prompt:
    # Double-submission check
    if active_chat["messages"]:
        if active_chat["messages"][-1]["role"] == "assistant":
            if len(active_chat["messages"]) >= 2 and final_prompt == active_chat["messages"][-2]["content"]:
                st.stop()

    with st.chat_message("user"):
        st.markdown(final_prompt)
    active_chat["messages"].append({"role": "user", "content": final_prompt})
    
    if len(active_chat["messages"]) == 1:
        st.session_state.all_chats[active_id]["title"] = " ".join(final_prompt.split()[:5]) + "..."

    # LOGIC: Decide what to do
    with st.chat_message("assistant"):
        df = active_chat["dataframe"]
        intent = classify_intent(final_prompt, has_data=(df is not None))
        
        search_results = []
        if intent == "SEARCH" or (deep_mode and not df and not active_chat["doc_text"]):
            with st.spinner("Searching..."):
                search_results = search_web(final_prompt, deep_mode)
        
        # Stream Response
        full_response = st.write_stream(
            stream_ai_answer(active_chat["messages"], search_results, active_chat["doc_text"], df)
        )
        
        # CODE EXECUTION LOGIC (The "Analyst" Magic)
        code_block = None
        if df is not None:
            # Look for python code in the response
            match = re.search(r"```python(.*?)```", full_response, re.DOTALL)
            if match:
                code_block = match.group(1).strip()
                st.markdown("### 📊 Generating Chart...")
                result = execute_python_code(code_block, df)
                if "Error" in result:
                    st.error(result)
        
    # Save message
    msg_data = {"role": "assistant", "content": full_response, "sources": search_results}
    if code_block:
        msg_data["code_ran"] = code_block # Save the code so we can re-run it when history loads
        
    active_chat["messages"].append(msg_data)
    
    if len(active_chat["messages"]) == 2:
        st.rerun()
