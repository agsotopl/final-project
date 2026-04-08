import streamlit as st
from utils import get_client, resume_inputs

st.title("✉️ Cover Letter Generator")
st.write("Paste a job posting and your background — get a tailored cover letter instantly.")

st.divider()

col1, col2 = st.columns(2)

with col1:
    resume_content = resume_inputs()

with col2:
    st.subheader("Job Posting")
    job_posting = st.text_area(
        "Paste the job description here",
        height=250,
        placeholder="Include responsibilities, requirements, and company info…",
    )

st.divider()

if st.button("✉️ Generate Cover Letter", type="primary", use_container_width=True):
    if not resume_content:
        st.warning("Please upload your resume or paste your background information.", icon="⚠️")
        st.stop()

    if not job_posting.strip():
        st.info("No job posting provided — generating a general version.", icon="ℹ️")

    st.subheader("Your Cover Letter")

    prompt = f"""Write a professional, compelling cover letter.

CANDIDATE BACKGROUND:
{resume_content or "No resume provided — write a strong general-purpose cover letter framework."}

TARGET JOB POSTING:
{job_posting.strip() or "No specific posting — highlight professional strengths broadly."}

Requirements:
- Strong opening paragraph that immediately grabs attention
- Connect the candidate's specific experience to the role's requirements
- Quantify achievements wherever the resume supports it
- Show genuine enthusiasm for the company and role
- Confident closing with a clear call to action
- 3–4 paragraphs, professional tone, ~300–400 words
- Use placeholder brackets like [Your Name], [Date], [Hiring Manager] where needed

Output only the cover letter text."""

    client = get_client()
    result_area = st.empty()
    full_text = ""

    with client.messages.stream(
        model="claude-haiku-4-5",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for chunk in stream.text_stream:
            full_text += chunk
            result_area.markdown(full_text)

    st.download_button(
        "📥 Download Cover Letter",
        full_text,
        file_name="cover_letter.txt",
        mime="text/plain",
    )
