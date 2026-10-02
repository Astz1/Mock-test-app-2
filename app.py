import json
import time
import streamlit as st
from google import genai
from google.genai import types
from pypdf import PdfReader

st.set_page_config(page_title="AI Mock Test Generator", layout="centered")

# 1. API Key Validation
api_key = st.secrets.get("GEMINI_API_KEY")
if not api_key or "your_actual" in api_key:
    st.error(
        "⚠️️ **Missing API Key**: Add your real Gemini API key in Streamlit Cloud under **App Settings ➔ Secrets** as `GEMINI_API_KEY = \"AIzaSy...\"`"
    )
    st.stop()

client = genai.Client(api_key=api_key)


def extract_text_from_pdf(uploaded_file):
    reader = PdfReader(uploaded_file)
    text = ""
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted + "\n"
    return text.strip()


def parse_questions_with_ai(uploaded_file, raw_text):
    prompt = """
    Extract all multiple-choice questions from the provided document into a JSON array.
    Each element must be an object with these exact keys:
    - "id": integer
    - "question": string
    - "options": list of 4 option strings (e.g. ["A) Option 1", "B) Option 2", "C) Option 3", "D) Option 4"])
    - "correct_answer": string matching the exact option text
    - "explanation": detailed step-by-step reasoning or rectification
    """

    try:
        # If pypdf extracted text, use text-based processing
        if len(raw_text) > 50:
            contents = [prompt, f"Document Text:\n{raw_text[:20000]}"]
        else:
            # Fallback for scanned PDFs: pass the raw PDF file directly to Gemini
            uploaded_file.seek(0)
            pdf_bytes = uploaded_file.read()
            contents = [
                types.Part.from_bytes(
                    data=pdf_bytes, mime_type="application/pdf"
                ),
                prompt,
            ]

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            ),
        )

        return json.loads(response.text)

    except Exception as e:
        st.error(f"❌ **API Error Details**: {str(e)}")
        return None


# Session State Initialization
if "quiz_data" not in st.session_state:
    st.session_state.quiz_data = None
if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}
if "submitted" not in st.session_state:
    st.session_state.submitted = False
if "start_time" not in st.session_state:
    st.session_state.start_time = None

st.title("Mock Test Portal")

# Screen 1: File Upload
if not st.session_state.quiz_data:
    uploaded_file = st.file_uploader(
        "Upload Question Paper (PDF)", type=["pdf"]
    )
    if uploaded_file and st.button("Generate Test"):
        with st.spinner("Processing questions with Gemini..."):
            extracted_text = extract_text_from_pdf(uploaded_file)
            result = parse_questions_with_ai(uploaded_file, extracted_text)

            if result:
                st.session_state.quiz_data = result
                st.session_state.start_time = time.time()
                st.rerun()

# Screen 2: Test Interface
elif st.session_state.quiz_data and not st.session_state.submitted:
    elapsed = int(time.time() - st.session_state.start_time)
    remaining = max(0, 3600 - elapsed)
    mins, secs = divmod(remaining, 60)

    st.sidebar.metric("Time Remaining", f"{mins:02d}:{secs:02d}")

    if remaining == 0:
        st.warning("Time has expired! Submitting test.")
        st.session_state.submitted = True
        st.rerun()

    st.subheader("Answer the Questions Below:")

    with st.form("test_form"):
        for q in st.session_state.quiz_data:
            st.markdown(f"**Q{q['id']}. {q['question']}**")
            st.session_state.user_answers[q["id"]] = st.radio(
                "Select option:",
                options=q["options"],
                key=f"q_{q['id']}",
                index=None,
            )
            st.write("---")

        if st.form_submit_button("Submit Test"):
            st.session_state.submitted = True
            st.rerun()

# Screen 3: Results & Explanations
else:
    st.header("Test Results & Review")

    score = sum(
        1
        for q in st.session_state.quiz_data
        if st.session_state.user_answers.get(q["id"]) == q["correct_answer"]
    )
    st.metric("Final Score", f"{score} / {len(st.session_state.quiz_data)}")

    st.subheader("Question Breakdown & Explanations")
    for q in st.session_state.quiz_data:
        user_ans = st.session_state.user_answers.get(q["id"])
        is_correct = user_ans == q["correct_answer"]

        with st.expander(
            f"Q{q['id']}: {'✅ Correct' if is_correct else '❌ Incorrect / Unattempted'}"
        ):
            st.markdown(f"**Question:** {q['question']}")
            st.write(
                f"**Your Answer:** {user_ans if user_ans else 'Not attempted'}"
            )
            st.write(f"**Correct Answer:** {q['correct_answer']}")
            st.markdown("---")
            st.markdown(f"**Detailed Rectification:**\n{q['explanation']}")

    if st.button("Start New Test"):
        st.session_state.quiz_data = None
        st.session_state.user_answers = {}
        st.session_state.submitted = False
        st.session_state.start_time = None
        st.rerun()
