import streamlit as st
import docx
import os
import io
import re
from dotenv import load_dotenv
from perplexity import Perplexity  # <-- CHANGED

# --- Page Configuration ---
st.set_page_config(
    page_title="LegalEase AI (Perplexity)",
    page_icon="✍️",
    layout="wide"
)

# --- Environment Variable & API Key ---
load_dotenv()
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")  # <-- CHANGED

# Check for API key and configure Perplexity client
if not PERPLEXITY_API_KEY:
    st.error("🚨 PERPLEXITY_API_KEY not found. Please set it in your .env or Streamlit secrets.")
    st.stop()

try:
    client = Perplexity(api_key=PERPLEXITY_API_KEY)  # <-- CHANGED
    # Use a fast, capable Perplexity model
    PPLX_MODEL = "llama-3-sonar-small-32k-chat"  # <-- CHANGED
except Exception as e:
    st.error(f"Failed to configure Perplexity API: {e}")
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
    st.session_state.
