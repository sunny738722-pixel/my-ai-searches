import streamlit as st
from groq import Groq
from tavily import TavilyClient
import uuid
import json
import PyPDF2
from fpdf import FPDF

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

active_id = st.session_state.active_chat_id
if active_id not in st.session_state.all_chats:
    st.session_state.all_chats[active_id] = {"title": "New Chat", "messages": [], "doc_text": ""}
active_chat = st.session_state.all_chats[active_id]

# ------------------------------------------------------------------
# 3. SIDEBAR
# ------------------------------------------------------------------
with st.sidebar:
    st.title("🧠 Research Center")
    
    # A. DOCUMENT UPLOADER
    st.markdown("### 📂 Knowledge Base")
    uploaded_file = st.file_uploader("Upload PDF:", type="pdf")
    if uploaded_file:
        try:
            reader = PyPDF2.PdfReader(uploaded_file)
            doc_text = ""
            for page in reader.pages:
                doc_text += page.extract_text() + "\n"
            st.session_state.all_chats[active_id]["doc_text"] = doc_text
            st.success(f"✅ Loaded: {uploaded_file.name}")
        except Exception as e:
            st.error(f"Error reading PDF: {e}")

    st.divider()
    
    # B. SETTINGS
    deep_mode = st.toggle("🚀 Deep Research", value=False)
    
    st.divider()
    
    # C. CHAT CONTROLS
    if st.button("➕ New Discussion", use_container_width=True, type="primary"):
        new_id = str(uuid.uuid4())
        st.session_state.all_chats[new_id] = {"title": "New Chat", "messages": [], "doc_text": ""}
        st.session_state.active_chat_id = new_id
        st.rerun()

    # D. EXPORT TO PDF
    if st.button("📥 Download Chat as PDF"):
        if active_chat["messages"]:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            pdf.cell(200, 10, txt=f"Report: {active_chat['title']}", ln=True, align='C')
            
            for msg in active_chat["messages"]:
                role = "User" if msg["role"] == "user" else "AI"
                # Handle unicode issues for PDF
                clean_content = msg["content"].encode('latin-1', 'replace').decode('latin-1')
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(200, 10, txt=f"{role}:", ln=True)
                pdf.set_font("Arial", size=10)
                pdf.multi_cell(0, 10, txt=clean_content)
                pdf.ln(5)
                
            pdf_bytes = pdf.output(dest='S').encode('latin-1')
            st.download_button(
                label="Click to Save PDF",
                data=pdf_bytes,
                file_name=f"research_report.pdf",
                mime="application/pdf"
            )
        else:
            st.warning("No chat history to export!")

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
def transcribe_audio(audio_bytes):
    try:
        audio_bytes.seek(0)
        return groq_client.audio.transcriptions.create(
            file=("voice.wav", audio_bytes),
            model="whisper-large-v3", 
            response_format="text"
        )
    except Exception as e:
        st.error(f"❌ Audio Error: {e}")
        return None

def classify_intent(user_query):
    """
    Decides if the user wants to CHAT or SEARCH.
    Returns: 'SEARCH' or 'CHAT'
    """
    system_prompt = (
        "You are an intent classifier. Analyze the user's input."
        "\n- If it requires facts, news, data, or research -> Return 'SEARCH'."
        "\n- If it is casual conversation, greetings, personal feelings, or creative writing -> Return 'CHAT'."
        "\n- Return ONLY the word 'SEARCH' or 'CHAT'. Do not explain."
    )
    
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant", # Fast model for quick decision
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ],
            temperature=0,
            max_tokens=10
        )
        return response.choices[0].message.content.strip().upper()
    except:
        return "SEARCH" # Default to search if error

def generate_sub_queries(user_query):
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
    web_context = ""
    if search_results:
        for i, r in enumerate(search_results):
            web_context += f"WEB SOURCE {i+1}: {r['title']} | {r['content']}\n"
            
    doc_context = ""
    if doc_text:
        doc_context = f"\n\n📂 DOCUMENT CONTENT:\n{doc_text[:30000]}..."

    # NEW: Adjust prompt based on whether we have sources or not
    if not web_context and not doc_context:
        # Chat Mode Prompt
        system_prompt_text = (
            "You are a friendly and helpful AI assistant named Sunny's AI. "
            "Engage in casual conversation. Be empathetic, funny, or professional depending on the tone. "
            "Do NOT mention 'search results' or 'sources'."
        )
    else:
        # Search Mode Prompt
        system_prompt_text = (
            "You are an expert research assistant."
            "\n- If the user asks about the Document, use '📂 DOCUMENT CONTENT'."
            "\n- If general, use 'WEB SOURCE'."
            "\n- Always cite sources."
            f"\n\n{web_context}"
            f"\n\n{doc_context}"
        )

    system_prompt = {"role": "system", "content": system_prompt_text}
    clean_history = [{"role": m["role"], "content": m["content"]} for m in messages]
    
    try:
        stream = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
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
# 6. MAIN UI
# ------------------------------------------------------------------
st.title(f"{active_chat['title']}")

# Display History
for message in active_chat["messages"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "sources" in message and message["sources"]:
            with st.expander(f"📚 {len(message['sources'])} Sources"):
                for source in message["sources"]:
                    st.markdown(f"- [{source['title']}]({source['url']})")

# INPUT HANDLING
audio_value = st.audio_input("🎙️ Record Voice Question")
prompt = st.chat_input("Ask about your PDF or the web...")

final_prompt = None
if audio_value:
    with st.spinner("🎧 Transcribing..."):
        text = transcribe_audio(audio_value)
        if text: final_prompt = text
if prompt:
    final_prompt = prompt

# IF WE HAVE A PROMPT
if final_prompt:
    
    # 1. Prevent Double-Submission Bug
    if active_chat["messages"]:
        last_msg = active_chat["messages"][-1]
        if last_msg["role"] == "assistant":
            if len(active_chat["messages"]) >= 2:
                last_user_msg = active_chat["messages"][-2]["content"]
                if final_prompt == last_user_msg:
                    st.stop()

    with st.chat_message("user"):
        st.markdown(final_prompt)
    active_chat["messages"].append({"role": "user", "content": final_prompt})
    
    if len(active_chat["messages"]) == 1:
        st.session_state.all_chats[active_id]["title"] = " ".join(final_prompt.split()[:5]) + "..."
    
    with st.chat_message("assistant"):
        search_results = []
        doc_present = bool(active_chat["doc_text"])
        
        # --- NEW: THE ROUTER LOGIC ---
        # 1. Ask the AI: "Is this chat or search?"
        intent = classify_intent(final_prompt)
        
        # 2. Only search if Intent is SEARCH or Deep Mode is ON (or if Doc is present, we skip web unless asked)
        should_search = (intent == "SEARCH" or deep_mode) and not doc_present
        
        # Override: If document is present, we usually don't need web unless specified. 
        # But if deep_mode is ON, we force web search anyway.
        
        if should_search:
             if deep_mode:
                 search_results = search_web(final_prompt, True)
             else:
                 with st.spinner("🔎 Searching..."):
                     search_results = search_web(final_prompt, False)
        
        # 3. Generate Answer
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
