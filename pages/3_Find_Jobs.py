import streamlit as st
from utils import get_client, resume_inputs

st.set_page_config(page_title="Find Jobs", page_icon="🔍", layout="wide")

st.title("🔍 Job Finder")
st.write("Discover relevant job postings matched to your background and preferences.")

st.divider()

col1, col2 = st.columns(2)

with col1:
    resume_content = resume_inputs()

with col2:
    st.subheader("Job Preferences")
    desired_role = st.text_input("Desired Role / Title", placeholder="e.g. Data Analyst, UX Designer")
    location = st.text_input("Preferred Location", placeholder="e.g. Austin, TX  or  Remote")
    work_type = st.selectbox("Work Type", ["Any", "Remote", "Hybrid", "On-site"])
    industry = st.text_input("Industry (optional)", placeholder="e.g. FinTech, Healthcare")
    salary = st.text_input("Salary Range (optional)", placeholder="e.g. $90k – $120k")

st.divider()

if st.button("🔍 Find Relevant Jobs", type="primary", use_container_width=True):
    prefs = {
        "Desired Role": desired_role,
        "Location": location,
        "Work Type": work_type if work_type != "Any" else None,
        "Industry": industry,
        "Salary Range": salary,
    }
    prefs_text = "\n".join(f"- {k}: {v}" for k, v in prefs.items() if v)

    prompt = f"""Search the web for real, current job postings that match this candidate.

CANDIDATE PROFILE:
{resume_content or "No resume provided — rely on preferences below."}

JOB PREFERENCES:
{prefs_text or "No specific preferences provided."}

Tasks:
1. Search LinkedIn, Indeed, Glassdoor, and company career pages for matching roles
2. Return 8–12 relevant, currently open positions
3. For each position include:
   - **Job Title** at **Company** (Location | Work Type)
   - 2–3 sentence role summary
   - Key requirements that align with the candidate's background
   - Why it's a strong match
   - Direct application link
4. Group results: **Excellent Match** / **Good Match** / **Worth Considering**
5. Close with 2–3 adjacent roles the candidate is likely qualified for but may not have considered

Be specific — use actual postings found via search, not hypothetical examples."""

    client = get_client()
    status = st.empty()
    result_area = st.empty()
    status.info("Searching job boards — this may take a moment…", icon="🔍")

    messages = [{"role": "user", "content": prompt}]
    full_text = ""

    for _ in range(5):
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=8192,
            tools=[{"type": "web_search_20260209", "name": "web_search"}],
            messages=messages,
        )

        for block in response.content:
            if getattr(block, "type", None) == "text":
                full_text += block.text
                result_area.markdown(full_text)

        if response.stop_reason == "end_turn":
            status.success("Search complete!")
            break

        if response.stop_reason == "pause_turn":
            messages = [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": response.content},
            ]
        else:
            break

    if full_text:
        st.download_button(
            "📥 Download Job List",
            full_text,
            file_name="job_recommendations.txt",
            mime="text/plain",
        )
