import streamlit as st
from utils import get_client, resume_inputs, load_repo_template, extract_template_from_upload

# --- NEW: ethics rubric module ---
import ethics
import memory

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

with st.expander("📎 Resume Template (optional override)"):
    st.caption("By default the agent uses the template stored in the repo. Upload your own PDF to override it.")
    custom_template_file = st.file_uploader(
        "Upload your resume template (PDF, DOCX, or TXT)",
        type=["pdf", "docx", "txt"],
        key="resume_template",
    )

st.divider()

if st.button("📄 Tailor My Resume", type="primary", use_container_width=True):
    if not resume_content:
        st.error("Please provide your resume to tailor.")
        st.stop()

    if not job_posting.strip():
        st.info("No job posting provided — optimizing for general professional impact.", icon="ℹ️")

    # --- LONG-TERM MEMORY: save resume on each generation run ---
    memory.save_resume(resume_content)

    st.subheader("Tailored Resume")

    # Load template — user upload takes priority over repo default
    if custom_template_file:
        template_text, formatting_guide = extract_template_from_upload(custom_template_file)
    else:
        template_text, formatting_guide = load_repo_template("resume_template")

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
The largest font size is the candidate's name. The next level down is section headers.
Body text and bullet points use the smallest size listed.
"""

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
{template_block}
Output the complete tailored resume."""

    client = get_client()
    result_area = st.empty()
    full_text = ""

    with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for chunk in stream.text_stream:
            full_text += chunk
            result_area.markdown(full_text)

    st.divider()

    # --- NEW: ETHICS RUBRIC EVALUATION ---
    # Run a secondary Claude call to audit the tailored output before download.
    with st.spinner("Running ethics rubric check…"):
        ethics_result = ethics.evaluate_resume_ethics(full_text, job_posting)

    ethics.display_ethics_result(ethics_result)

    st.divider()

    # Download is shown after the ethics result so the user sees it first.
    st.download_button(
        "📥 Download Tailored Resume",
        full_text,
        file_name="tailored_resume.txt",
        mime="text/plain",
    )
