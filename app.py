import json
import time
import streamlit as st
from google import genai
from google.genai import types
from pypdf import PdfReader

# Page Configuration
st.set_page_config(
    page_title="AI Mock Test Portal",
    page_icon="📝",
    layout="centered",
)

# 1. API Key Setup
api_key = st.secrets.get("GEMINI_API_KEY")
if not api_key or "your_actual" in api_key:
    st.error(
        "⚠️ **Missing or Invalid API Key**: Please set your Gemini API key in Streamlit under **Settings ➔ Secrets** as:\n\n"
        '```toml\nGEMINI_API_KEY = "AIzaSy..."\n```'
    )
    st.stop()

client = genai.Client(api_key=api_key)


# 2. PDF Text Extraction
def extract_text_from_pdf(uploaded_file):
    reader = PdfReader(uploaded_file)
    text = ""
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted + "\n"
    return text.strip()


# 3. AI Question Parser with Fallback & Real Error Reporting
def parse_questions_with_ai(uploaded_file, raw_text):
    prompt = """
    Extract multiple-choice questions from the provided document into a strict JSON array.
    Extract up to 20 questions.
    Return ONLY a valid JSON array. Do not include extra conversational text.

    Schema for each array item:
    {
      "id": integer (1, 2, 3...),
      "question": "question text",
      "options": ["A) option text", "B) option text", "C) option text", "D) option text"],
      "correct_answer": "exact matching string of the correct option",
      "explanation": "detailed step-by-step reasoning or rectification"
    }
    """

    # Use direct text if available; otherwise send PDF bytes for OCR / scanned pages
    if len(raw_text) > 50:
        contents = [prompt, f"Document Content:\n{raw_text[:15000]}"]
    else:
        uploaded_file.seek(0)
        pdf_bytes = uploaded_file.read()
        contents = [
            types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
            prompt,
        ]

    # Models to try sequentially
    models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash"]
    last_error = ""

    for model_name in models_to_try:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                ),
            )

            # Clean output if wrapped in markdown code blocks
            clean_text = response.text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            elif clean_text.startswith("```"):
                clean_text = clean_text[3:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            clean_text = clean_text.strip()

            parsed = json.loads(clean_text)
            if isinstance(parsed, list) and len(parsed) > 0:
                return parsed

        except Exception as e:
            last_error = str(e)
            st.warning(f"⚠️ {model_name} notice: {last_error}")
            time.sleep(1)

    st.error(f"❌ Failed to parse question paper. Error: {last_error}")
    return None


# 4. Initialize Session State
if "quiz_data" not in st.session_state:
    st.session_state.quiz_data = None
if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}
if "submitted" not in st.session_state:
    st
