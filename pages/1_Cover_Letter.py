import streamlit as st
from utils import (get_openai_client, resume_inputs, load_repo_template,
                   extract_template_from_upload, generate_cover_letter_pdf)

st.title("Cover Letter Generator")
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

with st.expander("Cover Letter Template (optional override)"):
    st.caption("By default the agent uses the template stored in the repo. Upload your own PDF to override it.")
    custom_template_file = st.file_uploader(
        "Upload your cover letter template (PDF, DOCX, or TXT)",
        type=["pdf", "docx", "txt"],
        key="cl_template",
    )

st.divider()

if st.button("Generate Cover Letter", type="primary", use_container_width=True):
    if not resume_content:
        st.warning("Please upload your resume or paste your background information.")
        st.stop()

    if not job_posting.strip():
        st.info("No job posting provided — generating a general version.")

    st.subheader("Your Cover Letter")

    # Load template — user upload takes priority over repo default
    if custom_template_file:
        template_text, formatting_guide = extract_template_from_upload(custom_template_file)
    else:
        template_text, formatting_guide = load_repo_template("cover_letter_template")

    # Build the template injection block for the prompt
    template_block = ""
    if template_text.strip():
        template_block += f"""
FORMATTING TEMPLATE:
Reproduce the exact structure, section order, spacing, and layout of this template.
Do NOT copy its content — only replicate the format. Replace all placeholder text
with the candidate's real information.

{template_text}
"""
    if formatting_guide.strip():
        template_block += f"""
{formatting_guide}

Apply the font names and sizes above to the matching content types in your output.
"""

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
{template_block}
Output only the cover letter text."""

    client = get_openai_client()
    result_area = st.empty()
    full_text = ""

    stream = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            full_text += delta
            result_area.markdown(full_text)

    st.download_button("Download Cover Letter (PDF)",
                       generate_cover_letter_pdf(full_text),
                       file_name="cover_letter.pdf", mime="application/pdf")
