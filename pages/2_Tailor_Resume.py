import streamlit as st
from utils import get_client, resume_inputs

st.title("📄 Resume Tailoring")
st.write("Optimize your resume for a specific role with ATS-friendly language and keywords.")

st.divider()

col1, col2 = st.columns(2)

with col1:
    resume_content = resume_inputs()

with col2:
    st.subheader("Target Job Posting")
    job_posting = st.text_area(
        "Paste the job description to tailor your resume for",
        height=250,
        placeholder="The more detail you provide, the better the tailoring…",
    )

st.divider()

if st.button("📄 Tailor My Resume", type="primary", use_container_width=True):
    if not resume_content:
        st.error("Please provide your resume to tailor.")
        st.stop()

    if not job_posting.strip():
        st.info("No job posting provided — optimizing for general professional impact.", icon="ℹ️")

    st.subheader("Tailored Resume")

    prompt = f"""Tailor and optimise this resume for the target job posting.

ORIGINAL RESUME:
{resume_content}

TARGET JOB POSTING:
{job_posting.strip() or "No specific posting — optimise for maximum professional impact."}

Instructions:
1. Add a professional summary at the top, targeted to this role
2. Reorder sections / bullet points to surface the most relevant experience first
3. Rewrite bullets with strong action verbs and quantifiable results (use numbers from the original where available)
4. Weave in keywords from the job posting for ATS compatibility
5. Keep all content truthful — rephrase and restructure only, do not fabricate
6. Maintain a clean, scannable format with clear section headings

Output the complete tailored resume."""

    client = get_client()
    result_area = st.empty()
    full_text = ""

    with client.messages.stream(
        model="claude-haiku-4-5",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for chunk in stream.text_stream:
            full_text += chunk
            result_area.markdown(full_text)

    st.download_button(
        "📥 Download Tailored Resume",
        full_text,
        file_name="tailored_resume.txt",
        mime="text/plain",
    )
