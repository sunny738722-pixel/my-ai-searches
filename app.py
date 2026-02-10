import streamlit as st
from groq import Groq
from tavily import TavilyClient
import uuid
import json
import PyPDF2
from fpdf import FPDF
import pandas as pd
import re
from gtts import gTTS
import tempfile
import os
import requests
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
        "dataframe": None, 
        "image_data": None
    }
    st.session_state.active_chat_id = new_id

active_id = st.session_state.active_chat_id
# Safety Check
if active_id not in st.session_state.all_chats:
    st.session_state.all_chats[active_id] = {"title": "New Chat", "messages": [], "doc_text": "", "dataframe": None, "image_data": None}
active_chat = st.session_state.all_chats[active_id]

# ------------------------------------------------------------------
# 3. SIDEBAR
# ------------------------------------------------------------------
with st.sidebar:
    st.title("🧠 Research Center")
    
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

    # C. VISION EYE
    st.markdown("### 👁️ Vision Eye")
    uploaded_img = st.file_uploader("Upload Image:", type=["jpg", "jpeg", "png"])
    if uploaded_img:
        bytes_data = uploaded_img.getvalue()
        base64_image = base64.b64encode(bytes_data).decode('utf-8')
        st.session_state.all_chats[active_id]["image_data"] = base64_image
        st.success(f"✅ Loaded Image: {uploaded_img.name}")
        st.image(uploaded_img, caption="Context Active", use_container_width=True)

    st.divider()
    
    # --- MASTER SETTINGS ---
    st.markdown("### ⚙️ Intelligence Settings")
    
    use_deepseek = st.toggle("🧠 DeepSeek R1 (Thinking Mode)", value=False)
    deep_mode = st.toggle("🚀 Deep Research (Web)", value=False)
    enable_voice = st.toggle("🔊 Hear AI Response", value=False)
    
    # MASTER MODEL CONTROL PANEL
    with st.expander("🔧 Fix Model Errors (Advanced)", expanded=False):
        st.caption("If you get Error 400 (Decommissioned), switch models here.")
        
        # 1. VISION MODEL SELECTOR
        vision_choice = st.selectbox(
            "👁️ Vision Model:", 
            ["llama-3.2-11b-vision-preview", "llama-3.2-90b-vision-preview", "Custom..."],
            index=0
        )
        if vision_choice == "Custom...":
            vision_model_name = st.text_input("Enter Vision Model Name:", value="llama-3.2-11b-vision-preview")
        else:
            vision_model_name = vision_choice
            
        # 2. DEEPSEEK MODEL SELECTOR
        deepseek_choice = st.selectbox(
            "🧠 DeepSeek Model:", 
            ["deepseek-r1-distill-qwen-32b", "deepseek-r1-distill-llama-70b", "Custom..."],
            index=0 # Default to 32b since 70b is dying
        )
        if deepseek_choice == "Custom...":
            deepseek_model_name = st.text_input("Enter DeepSeek Model Name:", value="deepseek-r1-distill-qwen-32b")
        else:
            deepseek_model_name = deepseek_choice

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
        st.session_state.all_chats[new_id] = {"title": "New Chat", "messages": [], "doc_text": "", "dataframe": None, "image_data": None}
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
    HF_TOKEN = st.secrets["HF_TOKEN"]
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
    uq_lower = user_query.lower()
    image_triggers = ["generate image", "create image", "image of", "draw a", "paint a", "sketch a", "picture of"]
    if any(trigger in uq_lower for trigger in image_triggers): return "IMAGE"
    if has_data:
        if any(w in uq_lower for w in ["plot", "chart", "graph"]): return "PLOT"
        if any(w in uq_lower for w in ["analyze", "summary"]): return "ANALYZE"
    system_prompt = "Classify intent: 'SEARCH' (facts/news), 'CHAT' (casual). Return ONLY word."
    try:
        resp = groq_client.chat.completions.create(model="llama-3.1-8b-instant", messages=[{"role":"system","content":system_prompt},{"role":"user","content":user_query}], max_tokens=10)
        return resp.choices[0].message.content.strip().upper()
    except: return "SEARCH"

def search_web(query, is_deep_mode):
    if is_deep_mode: return tavily_client.search(query, max_results=5).get("results", [])
    return tavily_client.search(query, max_results=3).get("results", [])

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

def stream_ai_answer(messages, search_results, doc_text, df, image_data, vision_model_name, use_deepseek, deepseek_model_name):
    context_text = ""
    if search_results:
        context_text += "\nWEB SOURCES:\n" + "\n".join([f"- {r['title']}: {r['content']}" for r in search_results])
    if doc_text:
        context_text += f"\n\nDOCUMENT CONTEXT:\n{doc_text[:20000]}..."
    if df is not None:
        context_text += f"\n\nDATAFRAME PREVIEW:\n{df.head().to_markdown()}"
        context_text += "\n\nINSTRUCTIONS: If asked to visualize/plot, write Python code wrapped in ```python ... ```."

    # --- BRAIN SELECTION LOGIC ---
    if image_data:
        # VISION MODE
        model = vision_model_name 
        system_content = f"You are a helpful AI Assistant. Analyze the image provided. Use this context if available: {context_text}"
        user_content = [
            {"type": "text", "text": messages[-1]["content"]},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
        ]
        final_messages = [{"role": "system", "content": system_content}, {"role": "user", "content": user_content}]
    
    elif use_deepseek:
        # DEEPSEEK MODE
        model = deepseek_model_name
        final_messages = [{"role": "system", "content": "You are a reasoning AI. Think step-by-step."}] + [{"role": m["role"], "content": m["content"]} for m in messages]
        final_messages[-1]["content"] += f"\n\nCONTEXT:\n{context_text}"
    
    else:
        # STANDARD LLAMA MODE
        model = "llama-3.3-70b-versatile"
        system_content = f"You are a helpful AI Assistant. Use context to answer. {context_text}"
        final_messages = [{"role": "system", "content": system_content}] + [{"role": m["role"], "content": m["content"]} for m in messages]

    try:
        stream = groq_client.chat.completions.create(
            model=model,
            messages=final_messages,
            temperature=0.6,
            stream=True,
            max_tokens=6000 # Stop infinite thinking
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
for i, message in enumerate(active_chat["messages"]):
    with st.chat_message(message["role"]):
        content = message["content"]
        # DeepSeek Parsing
        if "<think>" in content and "</think>" in content:
            try:
                parts = re.split(r'</?think>', content)
                thought = parts[1].strip()
                answer = parts[2].strip()
                with st.expander("💭 Thinking Process"):
                    st.markdown(thought)
                st.markdown(answer)
            except:
                st.markdown(content)
        else:
            st.markdown(content)
        
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
    if active_chat["messages"]:
        if active_chat["messages"][-1]["role"] == "assistant":
            if len(active_chat["messages"]) >= 2 and final_prompt == active_chat["messages"][-2]["content"]:
                st.stop()

    with st.chat_message("user"):
        st.markdown(final_prompt)
    active_chat["messages"].append({"role": "user", "content": final_prompt})
    
    if len(active_chat["messages"]) == 1:
        st.session_state.all_chats[active_id]["title"] = " ".join(final_prompt.split()[:5]) + "..."

    with st.chat_message("assistant"):
        df = active_chat["dataframe"]
        img_data = active_chat.get("image_data")
        intent = classify_intent(final_prompt, has_data=(df is not None))
        
        # --- IMAGE GENERATION ---
        if intent == "IMAGE":
            with st.spinner("🎨 Painting..."):
                image_result = generate_image(final_prompt)
                if isinstance(image_result, bytes):
                    st.image(image_result, caption=final_prompt)
                    active_chat["messages"].append({"role": "assistant", "content": f"Here is your image: {final_prompt}", "image_bytes": image_result})
                else:
                    st.image(image_result, caption=final_prompt)
                    active_chat["messages"].append({"role": "assistant", "content": f"Here is your image: {final_prompt}", "image_url": image_result})
        
        # --- STANDARD / DEEPSEEK / VISION PATH ---
        else:
            search_results = []
            if (intent == "SEARCH" or deep_mode) and not df and not active_chat["doc_text"] and not img_data:
                with st.spinner("Searching..."):
                    search_results = search_web(final_prompt, deep_mode)
            
            full_response = ""
            placeholder = st.empty()
            
            stream = stream_ai_answer(active_chat["messages"], search_results, active_chat["doc_text"], df, img_data, vision_model_name, use_deepseek, deepseek_model_name)
            
            for chunk in stream:
                full_response += chunk
                placeholder.markdown(full_response + "▌")
            
            # Post-Processing
            if "<think>" in full_response and "</think>" in full_response:
                placeholder.empty()
                try:
                    parts = re.split(r'</?think>', full_response)
                    thought = parts[1].strip()
                    answer = parts[2].strip() if len(parts) > 2 else ""
                    with st.expander("💭 Thinking Process"):
                        st.markdown(thought)
                    st.markdown(answer)
                except:
                     placeholder.markdown(full_response)
            else:
                placeholder.markdown(full_response)
            
            # Code Execution
            code_block = None
            if df is not None:
                match = re.search(r"```python(.*?)```", full_response, re.DOTALL)
                if match:
                    code_block = match.group(1).strip()
                    st.markdown("### 📊 Generating Chart...")
                    result = execute_python_code(code_block, df)
                    if "Error" in result: st.error(result)
            
            # Voice
            audio_file = None
            if enable_voice:
                text_to_speak = full_response
                if "<think>" in full_response:
                     text_to_speak = full_response.split("</think>")[-1]
                with st.spinner("Generating audio..."):
                    audio_file = generate_audio(text_to_speak)
                    if audio_file:
                        st.audio(audio_file, format="audio/mp3")

            msg_data = {"role": "assistant", "content": full_response, "sources": search_results}
            if code_block: msg_data["code_ran"] = code_block
            if audio_file: msg_data["audio_file"] = audio_file
            
            active_chat["messages"].append(msg_data)
            
            if len(active_chat["messages"]) == 2:
                st.rerun()
