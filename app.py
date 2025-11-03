import streamlit as st
import google.generativeai as genai
import docx
import os
import io
import re
from dotenv import load_dotenv

# --- Page Configuration ---
st.set_page_config(
    page_title="LegalEase AI",
    page_icon="✍️",
    layout="wide"
)

# --- Environment Variable & API Key ---
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Check for API key and configure Gemini
if not GEMINI_API_KEY:
    st.error("🚨 GEMINI_API_KEY not found. Please set it in your .env file or Streamlit secrets.")
    st.stop()

try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error(f"Failed to configure Gemini API: {e}")
    st.stop()

# --- Helper Functions ---

def extract_text_and_placeholders(file_bytes):
    """
    Extracts text and unique placeholders from a .docx file.
    Placeholders are in the format {placeholder}, [placeholder], or <placeholder>.
    """
    try:
        doc = docx.Document(io.BytesIO(file_bytes))
        full_text = []

        # Extract from paragraphs
        for para in doc.paragraphs:
            full_text.append(para.text)
        
        # Extract from tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for para in cell.paragraphs:
                        full_text.append(para.text)

        full_text_str = "\n".join(full_text)
        
        # Regex to find all three types of placeholders
        placeholder_regex = r"\{.*?\}|\[.*?\]|<.*?>"
        placeholders = list(set(re.findall(placeholder_regex, full_text_str))) # Unique list
        
        return full_text_str, placeholders
    except Exception as e:
        st.error(f"Error reading .docx file: {e}")
        return None, []

def replace_placeholders_in_doc(file_bytes, replacements):
    """
    Replaces placeholders in a docx file (in memory) and returns the new file bytes.
    This function replaces text while attempting to preserve formatting by operating on runs.
    """
    try:
        doc = docx.Document(io.BytesIO(file_bytes))
        
        # Process paragraphs
        for p in doc.paragraphs:
            for key, value in replacements.items():
                if key in p.text:
                    for run in p.runs:
                        if key in run.text:
                            run.text = run.text.replace(key, str(value))
                            
        # Process tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        for key, value in replacements.items():
                            if key in p.text:
                                for run in p.runs:
                                    if key in run.text:
                                        run.text = run.text.replace(key, str(value))
        
        # Save the modified document to a byte stream
        file_stream = io.BytesIO()
        doc.save(file_stream)
        file_stream.seek(0)
        return file_stream.getvalue()
    except Exception as e:
        st.error(f"Error replacing placeholders: {e}")
        return None

def get_doc_as_bytes(doc):
    """Saves a docx.Document object to bytes."""
    bio = io.BytesIO()
    doc.save(bio)
    bio.seek(0)
    return bio.getvalue()

def clear_session_state_on_upload():
    """Resets the session state when a new file is uploaded."""
    keys_to_clear = [
        "messages", "placeholders", "filled_values", 
        "current_placeholder_index", "original_doc_bytes", 
        "original_text", "chat_session"
    ]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    # Re-initialize
    st.session_state.messages = []
    st.session_state.placeholders = []
    st.session_state.filled_values = {}
    st.session_state.current_placeholder_index = 0
    st.session_state.chat_session = model.start_chat(history=[])


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
if "chat_session" not in st.session_state:
    st.session_state.chat_session = model.start_chat(history=[])


# --- Main App UI ---
st.title("✍️ LegalEase AI: Conversational Document Filler")
st.markdown("Upload your `.docx` template, and I'll help you fill in the blanks conversationally.")

# --- Layout ---
col1, col2 = st.columns([1, 1], gap="large")

# --- Column 1: Upload & Chat ---
with col1:
    st.header("1. Upload & Fill")
    
    uploaded_file = st.file_uploader(
        "Upload your .docx template", 
        type=["docx"],
        on_change=clear_session_state_on_upload # Reset session on new file
    )

    # Step 1: File Upload and Analysis
    if uploaded_file is not None and st.session_state.original_doc_bytes is None:
        with st.spinner("Analyzing document..."):
            file_bytes = uploaded_file.getvalue()
            st.session_state.original_doc_bytes = file_bytes
            
            text, placeholders = extract_text_and_placeholders(file_bytes)
            
            if text is None:
                st.session_state.original_doc_bytes = None # Reset on error
            elif not placeholders:
                st.warning("📄 No placeholders (like {Name} or [Date]) found in this document.")
                st.session_state.original_doc_bytes = None # Reset
            else:
                st.session_state.original_text = text
                st.session_state.placeholders = placeholders
                st.success(f"Found {len(placeholders)} placeholders!")
                
                # Display found placeholders
                with st.expander("Click to see all found placeholders"):
                    st.write(placeholders)
                
                # Kick off the chat
                first_ph = st.session_state.placeholders[0]
                prompt = f"I need to ask the user for a value for the placeholder '{first_ph}'. Ask me a simple, friendly question to get this information. For example, if the placeholder is '{{ClientName}}', you could ask 'What is the client's full name?'."
                
                try:
                    response = st.session_state.chat_session.send_message(prompt)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.error(f"Error with Gemini API: {e}")

    # Step 2: Conversational Chat
    if st.session_state.original_doc_bytes is not None and st.session_state.placeholders:
        
        st.markdown("---")
        st.subheader("💬 Chat to Fill")

        # Display chat history
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # Chat input
        if prompt := st.chat_input("Your answer..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            # Process the user's answer
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        current_index = st.session_state.current_placeholder_index
                        current_ph = st.session_state.placeholders[current_index]
                        
                        # Store the value
                        st.session_state.filled_values[current_ph] = prompt
                        
                        # Move to the next placeholder
                        st.session_state.current_placeholder_index += 1
                        next_index = st.session_state.current_placeholder_index
                        
                        if next_index < len(st.session_state.placeholders):
                            # Ask for the next one
                            next_ph = st.session_state.placeholders[next_index]
                            ai_prompt = f"Great. The user provided '{prompt}' for '{current_ph}'. Now, ask me a simple, friendly question for the next placeholder: '{next_ph}'."
                            response = st.session_state.chat_session.send_message(ai_prompt)
                            response_text = response.text
                        else:
                            # We are done!
                            ai_prompt = f"Great. The user provided '{prompt}' for '{current_ph}'. That was the last placeholder. Let the user know all fields are filled and they can review and download the document on the right."
                            response = st.session_state.chat_session.send_message(ai_prompt)
                            response_text = response.text

                        st.session_state.messages.append({"role": "assistant", "content": response_text})
                        st.markdown(response_text)
                    
                    except Exception as e:
                        st.error(f"Error with Gemini API: {e}")
                        st.session_state.current_placeholder_index -= 1 # Roll back index on error


# --- Column 2: Review & Download ---
with col2:
    st.header("2. Review & Download")
    
    if st.session_state.original_doc_bytes is None:
        st.info("Upload a document on the left to see a preview here.")
    else:
        # Live Preview
        with st.container(height=500, border=True):
            st.subheader("Live Preview")
            preview_text = st.session_state.original_text
            
            # Dynamically replace filled values for the preview
            for ph, val in st.session_state.filled_values.items():
                # Bold the filled value for visibility in the preview
                preview_text = preview_text.replace(ph, f"**{val}**") 
            
            # Highlight remaining placeholders
            for ph in st.session_state.placeholders:
                if ph not in st.session_state.filled_values:
                    preview_text = preview_text.replace(ph, f"_{ph}_") # Italicize unfilled

            st.markdown(preview_text)
        
        st.markdown("---")

        # Download Button (only appears when all fields are filled)
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
            # Progress Bar
            progress = len(st.session_state.filled_values) / len(st.session_state.placeholders)
            st.progress(progress, text=f"{len(st.session_state.filled_values)} / {len(st.session_state.placeholders)} fields filled")
