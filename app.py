ard Mode - No hiding)
st.set_page_config(page_title="Sunny's AI", page_icon="🤖")
st.title("🤖 Sunny's AI")

# 2. LOAD KEYS (We still need this for Cloud)
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
    TAVILY_API_KEY = st.secrets["TAVILY_API_KEY"]
except:
    st.error("❌ Secrets are missing. Please add them in Streamlit Settings.")
    st.stop()

# 3. INITIALIZE TOOLS
groq_client = Groq(api_key=GROQ_API_KEY)
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

if "messages" not in st.session_state:
    st.session_state.messages = []

# 4. SEARCH FUNCTION
def search_web(query):
    try:
        response = tavily_client.search(query, max_results=3)
        results = response.get("results", [])
        context_text = ""
        for i, result in enumerate(results):
            context_text += f"SOURCE {i+1}: {result['title']} | URL: {result['url']} | CONTENT: {result['content']}\n\n"
        return context_text, results
    except Exception as e:
        return f"Error: {e}", []

# 5. AI FUNCTION
def get_ai_answer(messages, search_context):
    system_prompt = {
        "role": "system",
        "content": (
            "You are a helpful assistant. Answer based on the SEARCH RESULTS provided."
            f"\n\nSEARCH RESULTS:\n{search_context}"
        )
    }
    # Clean history for Groq
    clean_history = [{"role": m["role"], "content": m["content"]} for m in messages]
    
    # Generate answer
    completion = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[system_prompt] + clean_history,
        temperature=0.7,
    )
    return completion.choices[0].message.content

# 6. DRAW CHAT HISTORY
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "sources" in message:
            with st.expander("📚 Sources"):
                for source in message["sources"]:
                    st.markdown(f"- [{source['title']}]({source['url']})")

# 7. THE INPUT BAR (This must be at the bottom)
if prompt := st.chat_input("Ask a question..."):
    
    # Show User Message
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Process Answer
    with st.chat_message("assistant"):
        with st.spinner("🔎 Searching & Thinking..."):
            search_context, sources = search_web(prompt)
            answer = get_ai_answer(st.session_state.messages, search_context)
            st.markdown(answer)
            
            if sources:
                with st.expander("📚 Sources Used"):
                    for source in sources:
                        st.markdown(f"- [{source['title']}]({source['url']})")
    
    # Save History
    st.session_state.messages.append({
        "role": "assistant", 
        "content": answer,
        "sources": sources
    })

