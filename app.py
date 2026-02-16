import streamlit as st
import google.generativeai as genai
from groq import Groq
from tavily import TavilyClient
import uuid
import PyPDF2
from fpdf import FPDF
import pandas as pd
import re
from gtts import gTTS
import tempfile
import os
import requests
from PIL import Image
import io
import base64

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
        "dataframe": None
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
    st.caption("v1.0 Stable Release")
    
    # A. DATA ANALYST
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

    # B. LIBRARIAN
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

    # C. VISION EYE (Temporarily Disabled for Stability)
    # st.markdown("### 👁️ Vision Eye")
    # uploaded_img = st.file_uploader("Upload Image:", type=["jpg", "jpeg", "png"])
    # if uploaded_img:
    #     st.info("Vision module is currently undergoing maintenance.")

    st.divider()
    
    # SETTINGS
    st.markdown("### ⚙️ Settings")
    deep_mode = st.toggle("🚀 Deep Research (Web)", value=False)
    enable_voice = st.toggle("🔊 Hear AI Response", value=False)
    
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

    # HISTORY CONTROLS
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
    if "GEMINI_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    if "GROQ_API_KEY" in st.secrets:
        groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    if "TAVILY_API_KEY" in st.secrets:
        tavily_client = TavilyClient(api_key=st.secrets["TAVILY_API_KEY"])
    if "HF_TOKEN" in st.secrets:
        HF_TOKEN = st.secrets["HF_TOKEN"]
except Exception as e:
    st.error(f"🚨 API Key Error: {e}")

# ------------------------------------------------------------------
# 5. LOGIC FUNCTIONS
# ------------------------------------------------------------------
def transcribe_audio(audio_bytes):
    try:
        audio_bytes.seek(0)
        return groq_client.audio.transcriptions.create(file=("voice.wav", audio_bytes), model="whisper-large-v3", response_format="text")
    except: return None

def classify_intent(user_query, has_data=False):
    uq_lower = user_query.lower()
    image_triggers = ["generate image", "create image", "image of", "draw a", "paint a", "sketch a", "picture of"]
    if any(trigger in uq_lower for trigger in image_triggers): return "IMAGE"
    if has_data:
        if any(w in uq_lower for w in ["plot", "chart", "graph"]): return "PLOT"
        if any(w in uq_lower for w in ["analyze", "summary"]): return "ANALYZE"
    return "CHAT"

def search_web(query, is_deep_mode):
    try:
        if is_deep_mode: return tavily_client.search(query, max_results=5).get("results", [])
        return tavily_client.search(query, max_results=3).get("results", [])
    except: return []

def execute_python_code(code, df):
    local_vars = {"pd": pd, "st": st, "df": df}
    try:
        exec(code, {}, local_vars)
        return "✅ Code Executed Successfully"
    except Exception as e:
        return f"❌ Code Error: {e}"

def generate_audio(text):
    try:
        clean_text = re.sub(r'[\*#`]', '', text) 
        clean_text = re.sub(r'http\S+', '', clean_text)
        clean_text = re.sub(r'[-_]{2,}', ' ', clean_text)
        clean_text = clean_text.replace("_", " ")
        clean_text = " ".join(clean_text.split())
        if len(clean_text) > 1000: clean_text = clean_text[:1000] + "..."
        tts = gTTS(text=clean_text, lang='en')
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            tts.save(fp.name)
            return fp.name
    except: return None

def generate_image(prompt):
    API_URL = "https://router.huggingface.co/hf-inference/models/stabilityai/stable-diffusion-xl-base-1.0"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    try:
        response = requests.post(API_URL, headers=headers, json={"inputs": prompt})
        if response.status_code == 200: return response.content
        else:
            clean_prompt = prompt.replace(" ", "%20")
            return f"https://image.pollinations.ai/prompt/{clean_prompt}"
    except:
        clean_prompt = prompt.replace(" ", "%20")
        return f"https://image.pollinations.ai/prompt/{clean_prompt}"

# --- THE STABLE HYBRID ENGINE ---
def get_ai_response_stream(messages, search_results, doc_text, df):
    
    # Context
    context_text = ""
    if search_results:
        context_text += "\nWEB SOURCES:\n" + "\n".join([f"- {r['title']}: {r['content']}" for r in search_results])
    if doc_text:
        context_text += f"\n\nDOCUMENT CONTEXT:\n{doc_text[:20000]}..."
    if df is not None:
        context_text += f"\n\nDATAFRAME PREVIEW:\n{df.head().to_markdown()}"
        context_text += "\n\nINSTRUCTIONS: If asked to visualize/plot, write Python code wrapped in ```python ... ```."

    # --- ATTEMPT 1: GOOGLE GEMINI ---
    try:
        system_prompt = f"You are a helpful AI Assistant. Use this context to answer: {context_text}"
        prompt_content = [system_prompt]
        for msg in messages:
            prompt_content.append(f"{msg['role'].upper()}: {msg['content']}")
        
        prompt_content.append("ASSISTANT:") 

        # Using the standard stable model
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt_content, stream=True)
        for chunk in response:
            if chunk.text: yield chunk.text
            
    except Exception:
        # --- ATTEMPT 2: FALLBACK TO GROQ (LLAMA 3) ---
        try:
            groq_messages = [{"role": "system", "content": f"You are a helpful AI. {context_text}"}] 
            for m in messages:
                groq_messages.append({"role": m["role"], "content": m["content"]})
            
            stream = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=groq_messages,
                stream=True
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                        
        except Exception as e_groq:
             yield f"❌ Connectivity Error. Please refresh. (Details: {e_groq})"

# ------------------------------------------------------------------
# 6. MAIN UI
# ------------------------------------------------------------------
st.title(f"{active_chat['title']}")

# Display History
for i, message in enumerate(active_chat["messages"]):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "code_ran" in message and active_chat["dataframe"] is not None:
            with st.expander("📊 Analysis Output"):
                execute_python_code(message["code_ran"], active_chat["dataframe"])
        if "image_bytes" in message:
            st.image(message["image_bytes"], caption="Generated Art")
        if "image_url" in message:
            st.image(message["image_url"], caption="Generated Art")
        if "audio_file" in message:
             st.audio(message["audio_file"], format="audio/mp3")

# Input
audio_value = st.audio_input("🎙️")
prompt = st.chat_input("Ask anything...")
final_prompt = None

if audio_value:
    with st.spinner("Transcribing..."):
        final_prompt = transcribe_audio(audio_value)
if prompt:
    final_prompt = prompt

if final_prompt:
    with st.chat_message("user"):
        st.markdown(final_prompt)
    active_chat["messages"].append({"role": "user", "content": final_prompt})
    
    if len(active_chat["messages"]) == 1:
        st.session_state.all_chats[active_id]["title"] = " ".join(final_prompt.split()[:5]) + "..."

    with st.chat_message("assistant"):
        df = active_chat["dataframe"]
        intent = classify_intent(final_prompt, has_data=(df is not None))
        
        if intent == "IMAGE":
            with st.spinner("🎨 Painting..."):
                image_result = generate_image(final_prompt)
                if isinstance(image_result, bytes):
                    st.image(image_result, caption=final_prompt)
                    active_chat["messages"].append({"role": "assistant", "content": f"Here is your image: {final_prompt}", "image_bytes": image_result})
                else:
                    st.image(image_result, caption=final_prompt)
                    active_chat["messages"].append({"role": "assistant", "content": f"Here is your image: {final_prompt}", "image_url": image_result})
        else:
            search_results = []
            if (intent == "SEARCH" or deep_mode) and not df and not active_chat["doc_text"]:
                with st.spinner("Searching..."):
                    search_results = search_web(final_prompt, deep_mode)
            
            # CALL STABLE HYBRID ENGINE
            full_response = st.write_stream(
                get_ai_response_stream(active_chat["messages"], search_results, active_chat["doc_text"], df)
            )
            
            code_block = None
            if df is not None:
                match = re.search(r"```python(.*?)```", full_response, re.DOTALL)
                if match:
                    code_block = match.group(1).strip()
                    st.markdown("### 📊 Generating Chart...")
                    result = execute_python_code(code_block, df)
                    if "Error" in result: st.error(result)
            
            audio_file = None
            if enable_voice:
                with st.spinner("Generating audio..."):
                    audio_file = generate_audio(full_response)
                    if audio_file:
                        st.audio(audio_file, format="audio/mp3")

            msg_data = {"role": "assistant", "content": full_response, "sources": search_results}
            if code_block: msg_data["code_ran"] = code_block
            if audio_file: msg_data["audio_file"] = audio_file
            
            active_chat["messages"].append(msg_data)
            
            if len(active_chat["messages"]) == 2:
                st.rerun()
