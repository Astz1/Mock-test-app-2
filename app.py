import json
import time
import streamlit as st
from groq import Groq
from pypdf import PdfReader

st.set_page_config(
    page_title="AI Mock Test Portal",
    page_icon="📝",
    layout="centered",
)

# 1. API Key Validation
api_key = st.secrets.get("GROQ_API_KEY")
if not api_key:
    st.error(
        "Missing GROQ_API_KEY in Streamlit Secrets. Go to Settings > Secrets to add it."
    )
    st.stop()

client = Groq(api_key=api_key)


# 2. PDF Text Extraction
def extract_text_from_pdf(uploaded_file):
    reader = PdfReader(uploaded_file)
    text = ""
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted + "\n"
    return text.strip()


# 3. AI Question Parser using Groq (Llama 3.3)
def parse_questions_with_ai(raw_text):
    if len(raw_text) < 50:
        st.error(
            "Could not read text from this PDF. Please ensure it contains selectable text and is not an image-only scan."
        )
        return None

    prompt = f"""
Extract all multiple-choice questions from the following text into valid JSON.
Extract up to 20 questions.

Return a JSON object with a single key "questions" containing a list of question objects.
Each question object MUST follow this schema:
{{
  "id": 1,
  "question": "The question prompt text",
  "options": ["A) Option 1", "B) Option 2", "C) Option 3", "D) Option 4"],
  "correct_answer": "Exact string matching one of the options",
  "explanation": "Clear step-by-step reasoning or rectification"
}}

Document Text:
{raw_text[:18000]}
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        raw_json = response.choices[0].message.content
        data = json.loads(raw_json)

        # Handle outputs returned under 'questions' or directly as a list
        if isinstance(data, dict):
            return data.get("questions", list(data.values())[0])
        elif isinstance(data, list):
            return data

    except Exception as e:
        st.error(f"Failed to generate questions: {str(e)}")
        return None


# 4. Session State Setup
if "quiz_data" not in st.session_state:
    st.session_state.quiz_data = None
if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}
if "submitted" not in st.session_state:
    st.session_state.submitted = False
if "start_time" not in st.session_state:
    st.session_state.start_time = None

st.title("📝 AI Mock Test Portal")

# Screen 1: File Upload & Generation
if not st.session_state.quiz_data:
    st.write(
        "Upload any multiple-choice question paper (PDF) to start a 60-minute mock test."
    )
    uploaded_file = st.file_uploader(
        "Upload Question Paper (PDF)", type=["pdf"]
    )

    if uploaded_file and st.button("Generate Test", type="primary"):
        with st.spinner("Extracting questions and preparing your test..."):
            extracted_text = extract_text_from_pdf(uploaded_file)
            result = parse_questions_with_ai(extracted_text)

            if result:
                st.session_state.quiz_data = result
                st.session_state.user_answers = {}
                st.session_state.start_time = time.time()
                st.session_state.submitted = False
                st.rerun()

# Screen 2: Active Test with 60-Minute Countdown
elif st.session_state.quiz_data and not st.session_state.submitted:
    elapsed = int(time.time() - st.session_state.start_time)
    remaining = max(0, 3600 - elapsed)
    mins, secs = divmod(remaining, 60)

    st.metric("⏳ Time Remaining", f"{mins:02d}:{secs:02d}")

    if remaining == 0:
        st.warning("⏰ Time has expired! Automatically submitting your test.")
        st.session_state.submitted = True
        st.rerun()

    st.divider()
    st.subheader("Questions")

    with st.form("quiz_form"):
        for q in st.session_state.quiz_data:
            q_id = q["id"]
            st.markdown(f"**Q{q_id}. {q['question']}**")

            current_choice = st.session_state.user_answers.get(q_id)
            selected = st.radio(
                "Choose option:",
                options=q["options"],
                index=(
                    q["options"].index(current_choice)
                    if current_choice in q["options"]
                    else None
                ),
                key=f"radio_{q_id}",
                label_visibility="collapsed",
            )
            st.session_state.user_answers[q_id] = selected
            st.write("")

        submit_test = st.form_submit_button(
            "Submit Test", type="primary", use_container_width=True
        )
        if submit_test:
            st.session_state.submitted = True
            st.rerun()

# Screen 3: Results & Detailed Review
else:
    st.header("📊 Test Results & Review")

    total_questions = len(st.session_state.quiz_data)
    correct_count = sum(
        1
        for q in st.session_state.quiz_data
        if st.session_state.user_answers.get(q["id"]) == q["correct_answer"]
    )
    percentage = (
        (correct_count / total_questions) * 100 if total_questions > 0 else 0
    )

    col1, col2 = st.columns(2)
    col1.metric("Score", f"{correct_count} / {total_questions}")
    col2.metric("Accuracy", f"{percentage:.1f}%")

    st.divider()
    st.subheader("Detailed Solutions & Rectifications")

    for q in st.session_state.quiz_data:
        user_choice = st.session_state.user_answers.get(q["id"])
        is_correct = user_choice == q["correct_answer"]
        status_tag = (
            "✅ Correct"
            if is_correct
            else ("⚠️ Unattempted" if not user_choice else "❌ Incorrect")
        )

        with st.expander(f"Q{q['id']}: {status_tag} - {q['question'][:60]}..."):
            st.markdown(f"**Full Question:**\n{q['question']}")
            st.write(
                f"**Your Choice:** {user_choice if user_choice else 'None (Left blank)'}"
            )
            st.write(f"**Correct Answer:** {q['correct_answer']}")
            st.markdown("---")
            st.markdown(
                f"**Detailed Rectification:**\n{q.get('explanation', 'No explanation provided.')}"
            )

    st.divider()
    if st.button("Take Another Test", type="secondary"):
        st.session_state.quiz_data = None
        st.session_state.user_answers = {}
        st.session_state.submitted = False
        st.session_state.start_time = None
        st.rerun()
