import streamlit as st
import docx
import os
import io
import re
from dotenv import load_dotenv
from openai import OpenAI  # <-- We use the OpenAI library

# --- Page Configuration ---
st.set_page_config(
    page_title="LegalEase AI (Cohere)",
    page_icon="✍️",
    layout="wide"
)

# --- Environment Variable & API Key ---
load_dotenv()
COHERE_API_KEY = os.getenv("COHERE_API_KEY")  # <-- CHANGED

# Check for API key
if not COHERE_API_KEY:
    st.error("🚨 COHERE_API_KEY not found. Please set it in your .env or Streamlit secrets.")
    st.stop()

try:
   # --- CONFIGURE OPENAI CLIENT FOR COHERE ---
client = OpenAI(
    api_key=COHERE_API_KEY,
    base_url="https://api.cohere.ai/compatibility/v1"  # <-- THIS IS CORRECT
)
COHERE_MODEL = "command-r"
# --- END CLIENT CONFIGURATION ---
except Exception as e:
    st.error(f"Failed to configure Cohere-compatible client: {e}")
    st.stop()

# --- Helper Functions (No changes here) ---

def extract_text_and_placeholders(file_bytes):
    try:
        doc = docx.Document(io.BytesIO(file_bytes))
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for para in cell.paragraphs:
                        full_text.append(para.text)
        full_text_str = "\n".join(full_text)
        placeholder_regex = r"\{.*?\}|\[.*?\]|<.*?>"
        placeholders = list(set(re.findall(placeholder_regex, full_text_str)))
        return full_text_str, placeholders
    except Exception as e:
        st.error(f"Error reading .docx file: {e}")
        return None, []

def replace_placeholders_in_doc(file_bytes, replacements):
    try:
        doc = docx.Document(io.BytesIO(file_bytes))
        for p in doc.paragraphs:
            for key, value in replacements.items():
                if key in p.text:
                    for run in p.runs:
                        if key in run.text:
                            run.text = run.text.replace(key, str(value))
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        for key, value in replacements.items():
                            if key in p.text:
                                for run in p.runs:
                                    if key in run.text:
                                        run.text = run.text.replace(key, str(value))
        file_stream = io.BytesIO()
        doc.save(file_stream)
        file_stream.seek(0)
        return file_stream.getvalue()
    except Exception as e:
        st.error(f"Error replacing placeholders: {e}")
        return None

def clear_session_state_on_upload():
    keys_to_clear = [
        "messages", "placeholders", "filled_values", 
        "current_placeholder_index", "original_doc_bytes", 
        "original_text", "api_history"
    ]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    st.session_state.messages = []
    st.session_state.placeholders = []
    st.session_state.filled_values = {}
    st.session_state.current_placeholder_index = 0
    st.session_state.api_history = []

# --- Session State Initialization ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "placeholders" not in st.session_state:
    st.session_state.placeholders = []
if "filled_values" not in st.session_state:
    st.session_state.filled_values = {}
if "current_placeholder_index" not in st.session_state:
    st.session_state.current_placeholder_index = 0
if "original_doc_bytes" not in st.session_state:
    st.session_state.original_doc_bytes = None
if "original_text" not in st.session_state:
    st.session_state.original_text = ""
if "api_history" not in st.session_state:
    st.session_state.api_history = [
        {"role": "system", "content": "You are a helpful assistant. You ask simple, one-sentence questions to fill in document placeholders."}
    ]

# --- Main App UI ---
st.title("✍️ LegalEase AI: Conversational Document Filler (Cohere)")
st.markdown("Upload your `.docx` template, and I'll help you fill in the blanks conversationally.")

col1, col2 = st.columns([1, 1], gap="large")

# --- Column 1: Upload & Chat ---
with col1:
    st.header("1. Upload & Fill")
    
    uploaded_file = st.file_uploader(
        "Upload your .docx template", 
        type=["docx"],
        on_change=clear_session_state_on_upload
    )

    if uploaded_file is not None and st.session_state.original_doc_bytes is None:
        with st.spinner("Analyzing document..."):
            file_bytes = uploaded_file.getvalue()
            st.session_state.original_doc_bytes = file_bytes
            text, placeholders = extract_text_and_placeholders(file_bytes)
            
            if text is None:
                st.session_state.original_doc_bytes = None
            elif not placeholders:
                st.warning("📄 No placeholders (like {Name} or [Date]) found.")
                st.session_state.original_doc_bytes = None
            else:
                st.session_state.original_text = text
                st.session_state.placeholders = placeholders
                st.success(f"Found {len(placeholders)} placeholders!")
                
                with st.expander("Click to see all found placeholders"):
                    st.write(placeholders)
                
                first_ph = st.session_state.placeholders[0]
                prompt = f"I need to ask the user for a value for '{first_ph}'. Ask a simple, friendly question. For example, if it's '{{ClientName}}', ask 'What is the client's full name?'. Keep it brief."
                
                try:
                    # --- COHERE API CALL (using OpenAI library) ---
                    st.session_state.api_history.append({"role": "user", "content": prompt})
                    
                    response = client.chat.completions.create(
                        messages=st.session_state.api_history,
                        model=COHERE_MODEL
                    )
                    
                    response_text = response.choices[0].message.content
                    
                    st.session_state.api_history.append({"role": "assistant", "content": response_text})
                    st.session_state.messages.append({"role": "assistant", "content": response_text})
                    # --- END API CALL ---
                    
                except Exception as e:
                    st.error(f"Error with Cohere API: {e}")
                    # Clear history on error to avoid confusion
                    st.session_state.api_history = [] 

    if st.session_state.original_doc_bytes is not None and st.session_state.placeholders:
        st.markdown("---")
        st.subheader("💬 Chat to Fill")

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if prompt := st.chat_input("Your answer..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        current_index = st.session_state.current_placeholder_index
                        current_ph = st.session_state.placeholders[current_index]
                        st.session_state.filled_values[current_ph] = prompt
                        
                        st.session_state.current_placeholder_index += 1
                        next_index = st.session_state.current_placeholder_index
                        
                        # Add user's last answer to history
                        st.session_state.api_history.append({"role": "user", "content": prompt})
                        
                        if next_index < len(st.session_state.placeholders):
                            next_ph = st.session_state.placeholders[next_index]
                            ai_prompt = f"Great. The user provided '{prompt}' for '{current_ph}'. Now, ask a simple, friendly question for the next placeholder: '{next_ph}'. Keep it brief."
                        else:
                            ai_prompt = f"Great. The user provided '{prompt}' for '{current_ph}'. That was the last placeholder. Let the user know all fields are filled. Keep your response brief."

                        # --- COHERE API CALL (using OpenAI library) ---
                        st.session_state.api_history.append({"role": "user", "content": ai_prompt})
                        
                        response = client.chat.completions.create(
                            messages=st.session_state.api_history,
                            model=COHERE_MODEL
                        )
                        
                        response_text = response.choices[0].message.content
                        
                        st.session_state.api_history.append({"role": "assistant", "content": response_text})
                        st.session_state.messages.append({"role": "assistant", "content": response_text})
                        # --- END API CALL ---
                        
                        st.markdown(response_text)
                    
                    except Exception as e:
                        st.error(f"Error with Cohere API: {e}")
                        st.session_state.current_placeholder_index -= 1

# --- Column 2: Review & Download (No changes here) ---
with col2:
    st.header("2. Review & Download")
    
    if st.session_state.original_doc_bytes is None:
        st.info("Upload a document on the left to see a preview here.")
    else:
        with st.container(height=500, border=True):
            st.subheader("Live Preview")
            preview_text = st.session_state.original_text
            for ph, val in st.session_state.filled_values.items():
                preview_text = preview_text.replace(ph, f"**{val}**")
            for ph in st.session_state.placeholders:
                if ph not in st.session_state.filled_values:
                    preview_text = preview_text.replace(ph, f"_{ph}_")
            st.markdown(preview_text)
        
        st.markdown("---")

        all_filled = len(st.session_state.filled_values) == len(st.session_state.placeholders)
        
        if all_filled and st.session_state.placeholders:
            st.success("All fields filled! 🎉")
            
            with st.spinner("Generating final document..."):
                final_doc_bytes = replace_placeholders_in_doc(
                    st.session_state.original_doc_bytes,
                    st.session_state.filled_values
                )
            
            if final_doc_bytes:
                st.download_button(
                    label="⬇️ Download Completed Document",
                    data=final_doc_bytes,
                    file_name=f"completed_{uploaded_file.name}",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True
                )
        elif st.session_state.placeholders:
            progress = len(st.session_state.filled_values) / len(st.session_state.placeholders)
            st.progress(progress, text=f"{len(st.session_state.filled_values)} / {len(st.session_state.placeholders)} fields filled")
