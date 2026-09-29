import json
import time
import streamlit as st
from google import genai
from google.genai import types
from pypdf import PdfReader

# Configure Gemini Client
# Assumes GEMINI_API_KEY environment variable is set
client = genai.Client()

st.set_page_config(page_title="AI Mock Test Generator", layout="centered")


def extract_text_from_pdf(uploaded_file):
    reader = PdfReader(uploaded_file)
    text = ""
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted + "\n"
    return text


def parse_questions_with_ai(raw_text):
    prompt = f"""
    Extract all multiple-choice questions from the following text into valid JSON.
    Format requirements:
    Return an array of objects where each object has:
    - "id": integer
    - "question": string
    - "options": list of 4 strings (e.g. ["A) Option 1", "B) Option 2", ...])
    - "correct_answer": string matching the exact option text
    - "explanation": clear, detailed step-by-step reasoning or rectification

    Text:
    {raw_text[:15000]}  # Truncate if exceptionally large
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        ),
    )
    return json.loads(response.text)


# Initialize Session State
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
    uploaded_file = st.file_uploader("Upload Question Paper (PDF)", type=["pdf"])
    if uploaded_file and st.button("Generate Test"):
        with st.spinner("Extracting questions and formatting test..."):
            raw_text = extract_text_from_pdf(uploaded_file)
            st.session_state.quiz_data = parse_questions_with_ai(raw_text)
            st.session_state.start_time = time.time()
            st.rerun()

# Screen 2: Test Interface
elif st.session_state.quiz_data and not st.session_state.submitted:
    # 60-Minute Timer Logic
    elapsed = int(time.time() - st.session_state.start_time)
    remaining = max(0, 3600 - elapsed)
    mins, secs = divmod(remaining, 60)

    st.sidebar.metric(
        "Time Remaining",
        f"{mins:02d}:{secs:02d}",
        delta=None if remaining > 300 else "-Low Time",
    )

    if remaining == 0:
        st.warning("Time has expired! Submitting your test automatically.")
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

        submit_btn = st.form_submit_button("Submit Test")
        if submit_btn:
            st.session_state.submitted = True
            st.rerun()

# Screen 3: Results & Detailed Rectifications
else:
    st.header("Test Results & Review")

    score = 0
    total = len(st.session_state.quiz_data)

    for q in st.session_state.quiz_data:
        user_ans = st.session_state.user_answers.get(q["id"])
        if user_ans == q["correct_answer"]:
            score += 1

    st.metric("Final Score", f"{score} / {total}")

    st.subheader("Question Breakdown & Explanations")
    for q in st.session_state.quiz_data:
        user_ans = st.session_state.user_answers.get(q["id"])
        is_correct = user_ans == q["correct_answer"]

        with st.expander(
            f"Q{q['id']}: {'✅ Correct' if is_correct else '❌ Incorrect / Unattempted'}"
        ):
            st.markdown(f"**Question:** {q['question']}")
            st.write(f"**Your Answer:** {user_ans if user_ans else 'Not attempted'}")
            st.write(f"**Correct Answer:** {q['correct_answer']}")
            st.markdown("---")
            st.markdown(f"**Detailed Rectification:**\n{q['explanation']}")

    if st.button("Start New Test"):
        st.session_state.quiz_data = None
        st.session_state.user_answers = {}
        st.session_state.submitted = False
        st.session_state.start_time = None
        st.rerun()
