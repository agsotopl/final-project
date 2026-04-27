import streamlit as st
from utils import (get_client, resume_inputs, load_repo_template,
                   extract_template_from_upload, generate_resume_pdf)
import ethics
import memory


_FEEDBACK_MARKER = "<!-- FEEDBACK -->"


def _resume_only(text: str) -> str:
    """Return only the resume portion, stripping everything after the feedback marker."""
    return text.split(_FEEDBACK_MARKER)[0].strip()

st.title("Resume Builder")
st.write("Build a resume from scratch, or tailor your existing one for a specific role.")
st.divider()

# ---------------------------------------------------------------------------
# Template — shared between both modes
# ---------------------------------------------------------------------------
with st.expander("Resume Template (optional override)"):
    st.caption("By default the agent uses the template stored in the repo. Upload your own PDF to override it.")
    custom_template_file = st.file_uploader(
        "Upload your resume template (PDF, DOCX, or TXT)",
        type=["pdf", "docx", "txt"],
        key="resume_template",
    )

if custom_template_file:
    template_text, formatting_guide = extract_template_from_upload(custom_template_file)
else:
    template_text, formatting_guide = load_repo_template("resume_template")

_template_block = ""
if template_text.strip():
    _template_block += f"""
FORMATTING TEMPLATE:
Reproduce the exact structure, section order, spacing, and layout of this template.
Do NOT copy its content — only replicate the format. Replace placeholder text with the candidate's real information.

{template_text}
"""
if formatting_guide.strip():
    _template_block += f"""
{formatting_guide}

Apply these font names and sizes to the matching content types.
Largest size = candidate name. Next level = section headers. Smallest = body text and bullets.
"""

st.divider()

tab_build, tab_tailor = st.tabs(["Build from Scratch", "Tailor Existing Resume"])


# ===========================================================================
# Helpers
# ===========================================================================

def _stream_response(client, system: str, messages: list) -> str:
    """Stream a Claude response and return the full text."""
    full = ""
    area = st.empty()
    with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=system,
        messages=messages,
    ) as stream:
        for chunk in stream.text_stream:
            full += chunk
            area.markdown(full)
    return full


# ===========================================================================
# TAB 1 — BUILD FROM SCRATCH
# ===========================================================================
with tab_build:

    # --- Session state init ---
    for key, default in [
        ("b_phase", "form"),
        ("b_messages", []),
        ("b_system", ""),
        ("b_draft", ""),
        ("b_got_initial", False),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    # -----------------------------------------------------------------------
    # FORM PHASE
    # -----------------------------------------------------------------------
    if st.session_state.b_phase == "form":
        st.subheader("Your Information")

        with st.expander("Personal Information", expanded=True):
            c1, c2 = st.columns(2)
            with c1:
                b_name     = st.text_input("Full Name",              key="b_name")
                b_email    = st.text_input("Email",                   key="b_email")
                b_phone    = st.text_input("Phone",                   key="b_phone")
            with c2:
                b_location = st.text_input("City, State",             key="b_location")
                b_linkedin = st.text_input("LinkedIn URL",             key="b_linkedin")
                b_portfolio= st.text_input("Portfolio / GitHub (opt)",key="b_portfolio")

        with st.expander("Education", expanded=True):
            c1, c2 = st.columns(2)
            with c1:
                b_school   = st.text_input("School / University",     key="b_school")
                b_degree   = st.text_input("Degree & Major",          key="b_degree")
            with c2:
                b_grad     = st.text_input("Graduation Date",          key="b_grad",
                                           placeholder="e.g. May 2026")
                b_gpa      = st.text_input("GPA (optional)",           key="b_gpa")
            b_courses  = st.text_area("Relevant Courses (optional)",   key="b_courses", height=70)

        with st.expander("Work Experience", expanded=True):
            b_num_exp = int(st.number_input("Number of positions", 0, 6, 1, key="b_num_exp"))
            experiences = []
            for i in range(b_num_exp):
                st.markdown(f"**Position {i + 1}**")
                c1, c2 = st.columns(2)
                with c1:
                    co   = st.text_input("Company",    key=f"b_co_{i}")
                    title= st.text_input("Job Title",  key=f"b_ttl_{i}")
                with c2:
                    dates= st.text_input("Dates",      key=f"b_dt_{i}",
                                         placeholder="Jun 2024 – Aug 2024")
                    etype= st.selectbox("Type", ["Full-time","Internship","Part-time","Contract"],
                                        key=f"b_et_{i}")
                desc = st.text_area("What did you do? (one bullet per line)",
                                    key=f"b_desc_{i}", height=90)
                experiences.append(dict(company=co, title=title, dates=dates, type=etype, desc=desc))
                if i < b_num_exp - 1:
                    st.divider()

        with st.expander("Projects"):
            b_num_proj = int(st.number_input("Number of projects", 0, 6, 1, key="b_num_proj"))
            projects = []
            for i in range(b_num_proj):
                st.markdown(f"**Project {i + 1}**")
                c1, c2 = st.columns(2)
                with c1:
                    pname = st.text_input("Project Name", key=f"b_pn_{i}")
                    ptech = st.text_input("Technologies", key=f"b_pt_{i}")
                with c2:
                    pdates= st.text_input("Dates (opt)",  key=f"b_pd_{i}")
                pdesc = st.text_area("Description",       key=f"b_pdesc_{i}", height=70)
                projects.append(dict(name=pname, tech=ptech, dates=pdates, desc=pdesc))
                if i < b_num_proj - 1:
                    st.divider()

        with st.expander("Skills", expanded=True):
            b_skills = st.text_area("Skills (comma-separated or free text)", key="b_skills",
                                    height=70,
                                    placeholder="Python, SQL, Tableau, Machine Learning…")

        b_target = st.text_input("Target Role / Job Title (optional — helps tailor the output)",
                                 key="b_target")

        if st.button("Build My Resume", type="primary", use_container_width=True):
            if not b_name:
                st.warning("Please enter your name.")
                st.stop()

            exp_block = "\n\n".join(
                f"{e['title']} at {e['company']} ({e['dates']}, {e['type']})\n{e['desc']}"
                for e in experiences if e["company"] or e["title"]
            )
            proj_block = "\n\n".join(
                f"{p['name']} — {p['tech']} {p['dates']}\n{p['desc']}"
                for p in projects if p["name"]
            )

            background = f"""PERSONAL:
Name: {b_name} | Email: {b_email} | Phone: {b_phone}
Location: {b_location} | LinkedIn: {b_linkedin}{f' | Portfolio: {b_portfolio}' if b_portfolio else ''}

EDUCATION:
{b_school} — {b_degree}, {b_grad}{f', GPA: {b_gpa}' if b_gpa else ''}
{f'Relevant Courses: {b_courses}' if b_courses else ''}

WORK EXPERIENCE:
{exp_block or 'None provided'}

PROJECTS:
{proj_block or 'None provided'}

SKILLS:
{b_skills or 'None provided'}
{f'Target role: {b_target}' if b_target else ''}"""

            system = f"""You are an expert resume writer and career coach.

Step 1 — Compile a polished, ATS-optimized resume from the candidate's background.
Step 2 — Identify exactly 2–3 specific gaps that would meaningfully strengthen the resume (missing metrics, unlisted skills, thin sections, etc.).
Step 3 — Ask the candidate targeted follow-up questions about those gaps, numbered and concise.

{_template_block}

IMPORTANT: After the resume, output the exact token {_FEEDBACK_MARKER} on its own line, then write your feedback and questions below it.
After the candidate answers, output the revised resume followed by {_FEEDBACK_MARKER} and a brief summary of what changed."""

            st.session_state.b_system   = system
            st.session_state.b_messages = [{"role": "user", "content":
                f"Here is my background. Please compile my resume and tell me what would strengthen it.\n\n{background}"}]
            st.session_state.b_got_initial = False
            st.session_state.b_draft       = ""
            st.session_state.b_phase       = "chat"
            st.rerun()

    # -----------------------------------------------------------------------
    # CHAT PHASE
    # -----------------------------------------------------------------------
    elif st.session_state.b_phase == "chat":
        client = get_client()

        # Fire initial response exactly once
        if not st.session_state.b_got_initial:
            with st.chat_message("assistant"):
                response = _stream_response(client, st.session_state.b_system,
                                            st.session_state.b_messages)
            st.session_state.b_messages.append({"role": "assistant", "content": response})
            st.session_state.b_draft       = response
            st.session_state.b_got_initial = True
            memory.save_resume(response)

        # Render conversation (skip index 0 — raw form dump the user already knows)
        for msg in st.session_state.b_messages[1:]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        # Follow-up input
        if user_input := st.chat_input("Answer the questions or request changes…", key="b_chat"):
            st.session_state.b_messages.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)
            with st.chat_message("assistant"):
                response = _stream_response(client, st.session_state.b_system,
                                            st.session_state.b_messages)
            st.session_state.b_messages.append({"role": "assistant", "content": response})
            st.session_state.b_draft = response
            memory.save_resume(response)

        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Start Over", key="b_reset"):
                for k in ["b_phase","b_messages","b_system","b_draft","b_got_initial"]:
                    st.session_state[k] = (
                        "form" if k == "b_phase" else
                        []     if k == "b_messages" else
                        False  if k == "b_got_initial" else ""
                    )
                st.rerun()
        with c2:
            if st.session_state.b_draft:
                st.download_button("Download Resume (PDF)",
                                   generate_resume_pdf(_resume_only(st.session_state.b_draft)),
                                   file_name="resume.pdf", mime="application/pdf", key="b_dl")


# ===========================================================================
# TAB 2 — TAILOR EXISTING RESUME
# ===========================================================================
with tab_tailor:

    # --- Session state init ---
    for key, default in [
        ("t_phase", "form"),
        ("t_messages", []),
        ("t_system", ""),
        ("t_draft", ""),
        ("t_job", ""),
        ("t_got_initial", False),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    # -----------------------------------------------------------------------
    # FORM PHASE
    # -----------------------------------------------------------------------
    if st.session_state.t_phase == "form":
        c1, c2 = st.columns(2)
        with c1:
            resume_content = resume_inputs()
        with c2:
            st.subheader("Job Posting (optional)")
            job_posting = st.text_area(
                "Paste a job description to tailor your resume for a specific role, or leave blank for a general review.",
                height=300,
                placeholder="Leave blank for a general resume review and improvement…",
                key="t_job_input",
            )

        if st.button("Start", type="primary", use_container_width=True):
            if not resume_content:
                st.error("Please provide your resume.")
                st.stop()

            memory.save_resume(resume_content)

            has_posting = bool(job_posting.strip())

            if has_posting:
                system = f"""You are an expert resume coach and ATS optimization specialist.

Step 1 — Analyze the resume against the job posting. Briefly note: what's strong, what's missing, what should be reframed.
Step 2 — Ask exactly 2–3 targeted follow-up questions about specific gaps (unlisted experience, hidden skills, relevant projects not mentioned, quantifiable results that could be added). Reference exact keywords from the posting.
Step 3 — After the candidate responds, produce the complete tailored resume in full.

{_template_block}

IMPORTANT: When you include a resume in your response, output it first, then place the exact token {_FEEDBACK_MARKER} on its own line, then write your analysis and questions below it.
When outputting the final resume, write it in full — do not summarise or truncate."""
            else:
                system = f"""You are an expert resume coach.

Step 1 — Review the resume holistically. Note what's strong and identify 2–3 specific weaknesses (thin sections, missing metrics, weak action verbs, formatting inconsistencies, etc.).
Step 2 — Ask exactly 2–3 targeted follow-up questions to gather information that would fill those gaps (e.g. "Do you have GPA or any academic awards we could add?" or "Can you quantify the impact of your work at [Company]?").
Step 3 — After the candidate responds, produce the complete improved resume in full.

{_template_block}

IMPORTANT: When you include a resume in your response, output it first, then place the exact token {_FEEDBACK_MARKER} on its own line, then write your analysis and questions below it.
When outputting the final resume, write it in full — do not summarise or truncate."""

            if has_posting:
                initial_msg = (
                    f"Please analyse my resume for this job posting and tell me what could be strengthened.\n\n"
                    f"MY RESUME:\n{resume_content}\n\nTARGET JOB POSTING:\n{job_posting}"
                )
            else:
                initial_msg = (
                    f"Please review my resume and tell me what could be improved or strengthened.\n\n"
                    f"MY RESUME:\n{resume_content}"
                )

            st.session_state.t_system  = system
            st.session_state.t_job     = job_posting
            st.session_state.t_messages= [{"role": "user", "content": initial_msg}]
            st.session_state.t_got_initial = False
            st.session_state.t_draft       = ""
            st.session_state.t_phase       = "chat"
            st.rerun()

    # -----------------------------------------------------------------------
    # CHAT PHASE
    # -----------------------------------------------------------------------
    elif st.session_state.t_phase == "chat":
        client = get_client()

        # Fire initial response exactly once
        if not st.session_state.t_got_initial:
            with st.chat_message("assistant"):
                response = _stream_response(client, st.session_state.t_system,
                                            st.session_state.t_messages)
            st.session_state.t_messages.append({"role": "assistant", "content": response})
            st.session_state.t_draft       = response
            st.session_state.t_got_initial = True

        # Render conversation (skip index 0 — raw resume + job posting)
        for msg in st.session_state.t_messages[1:]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        # Follow-up input
        if user_input := st.chat_input("Answer the agent's questions or ask for changes…", key="t_chat"):
            st.session_state.t_messages.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)
            with st.chat_message("assistant"):
                response = _stream_response(client, st.session_state.t_system,
                                            st.session_state.t_messages)
            st.session_state.t_messages.append({"role": "assistant", "content": response})
            st.session_state.t_draft = response

        st.divider()
        c1, c2, c3 = st.columns(3)

        with c1:
            if st.button("Start Over", key="t_reset"):
                for k in ["t_phase","t_messages","t_system","t_draft","t_job","t_got_initial"]:
                    st.session_state[k] = (
                        "form"  if k == "t_phase" else
                        []      if k == "t_messages" else
                        False   if k == "t_got_initial" else ""
                    )
                st.rerun()

        with c2:
            if st.button("Generate Final Resume", key="t_finalize", type="primary"):
                final_msg = "Based on everything we've discussed, please now output the complete, polished, tailored resume in full."
                st.session_state.t_messages.append({"role": "user", "content": final_msg})
                with st.chat_message("user"):
                    st.markdown(final_msg)
                with st.chat_message("assistant"):
                    response = _stream_response(client, st.session_state.t_system,
                                                st.session_state.t_messages)
                st.session_state.t_messages.append({"role": "assistant", "content": response})
                st.session_state.t_draft = response

                # Ethics audit on the final output
                st.divider()
                with st.spinner("Running ethics rubric check…"):
                    ethics_result = ethics.evaluate_resume_ethics(response, st.session_state.t_job)
                ethics.display_ethics_result(ethics_result)

        with c3:
            if st.session_state.t_draft:
                st.download_button("Download Resume (PDF)",
                                   generate_resume_pdf(_resume_only(st.session_state.t_draft)),
                                   file_name="tailored_resume.pdf", mime="application/pdf",
                                   key="t_dl")
