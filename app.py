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

# 1. API Key Validation
api_key = st.secrets.get("GEMINI_API_KEY")
if not api_key:
    st.error(
        "Missing GEMINI_API_KEY in Streamlit Secrets. Go to Settings > Secrets to add it."
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


# 3. AI Question Parser with Automatic Fallback
def parse_questions_with_ai(uploaded_file, raw_text):
    prompt = """
    Extract multiple-choice questions from the provided document into a strict JSON array.
    Extract up to 20 questions.
    Return ONLY a valid JSON array without markdown formatting.

    Schema for each item:
    {
      "id": 1,
      "question": "question text",
      "options": ["A) opt1", "B) opt2", "C) opt3", "D) opt4"],
      "correct_answer": "exact string matching the correct option",
      "explanation": "step-by-step reasoning or rectification"
    }
    """

    if len(raw_text) > 50:
        contents = [prompt, f"Document Content:\n{raw_text[:15000]}"]
    else:
        uploaded_file.seek(0)
        pdf_bytes = uploaded_file.read()
        contents = [
            types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
            prompt,
        ]

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
            time.sleep(1)

    st.error(f"Failed to generate questions: {last_error}")
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
            result = parse_questions_with_ai(uploaded_file, extracted_text)

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
