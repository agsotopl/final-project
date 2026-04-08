import time
import streamlit as st
import anthropic
from utils import get_client, resume_inputs

st.title("🔍 Job Finder")
st.write("Finds 5 real, open job postings with direct application links.")

st.divider()

col1, col2 = st.columns(2)

with col1:
    resume_content = resume_inputs()

with col2:
    st.subheader("Job Preferences")
    desired_role = st.text_input("Desired Role / Title", placeholder="e.g. Data Analyst, UX Designer")
    location = st.text_input("Preferred Location", placeholder="e.g. Austin, TX  or  Remote")
    work_type = st.selectbox("Work Type", ["Any", "Remote", "Hybrid", "On-site"])
    experience = st.selectbox("Experience Level", ["Any", "Internship", "Entry Level", "Mid Level", "Senior", "Lead / Principal", "Manager / Director"])
    industry = st.text_input("Industry (optional)", placeholder="e.g. FinTech, Healthcare")
    salary = st.text_input("Salary Range (optional)", placeholder="e.g. $90k – $120k")

st.divider()

if st.button("🔍 Find Relevant Jobs", type="primary", use_container_width=True):
    if not desired_role:
        st.warning("Please enter a desired role to search for.", icon="⚠️")
        st.stop()

    location_str = location or "remote"
    work_type_str = f" {work_type.lower()}" if work_type != "Any" else ""
    experience_str = f" {experience}" if experience != "Any" else ""

    prompt = f"""You are a job search assistant. Your goal is to return exactly 5 real, currently open job postings with direct apply links. Follow every step below precisely.

--- ROLE TO SEARCH FOR ---
{experience_str.strip() + " " if experience_str else ""}{desired_role}{work_type_str}, {location_str}{f', {industry}' if industry else ''}
{f'Salary preference: {salary}' if salary else ''}

--- STEP-BY-STEP INSTRUCTIONS ---

STEP 1: Search for individual job postings on ATS platforms and company career pages.
Run ALL of these searches one at a time using web_search:
  a) "{experience_str.strip() + " " if experience_str else ""}{desired_role} {location_str} site:greenhouse.io"
  b) "{experience_str.strip() + " " if experience_str else ""}{desired_role} {location_str} site:lever.co"
  c) "{experience_str.strip() + " " if experience_str else ""}{desired_role} {location_str} site:jobs.ashbyhq.com"
  d) "{experience_str.strip() + " " if experience_str else ""}{desired_role} {location_str} site:amazon.jobs"
  e) "{experience_str.strip() + " " if experience_str else ""}{desired_role} {location_str} site:jpmorganchase.com/careers"
  f) "{experience_str.strip() + " " if experience_str else ""}{desired_role} {location_str} careers site:google.com OR site:microsoft.com OR site:apple.com OR site:meta.com"

STEP 2: From the search results, collect direct links to individual job posting pages (not search result pages). Valid URLs include:
  - https://boards.greenhouse.io/[company]/jobs/[id]
  - https://jobs.lever.co/[company]/[id]
  - https://jobs.ashbyhq.com/[company]/[id]
  - https://www.amazon.jobs/en/jobs/[id]/...
  - https://www.jpmorganchase.com/careers/jobs/[id]
  - https://careers.google.com/jobs/results/[id]
  - Any direct company careers page with a specific job ID in the URL

Discard any URL that points to a search results page (e.g. indeed.com/jobs?q=..., linkedin.com/jobs/search, amazon.jobs/en/search).

STEP 3: Use web_fetch to visit each individual posting URL and extract:
  - Exact job title
  - Company name
  - Location and work type
  - A 2–3 sentence summary of the role
  - Direct application link (the URL you fetched)

STEP 4: Output exactly 5 postings using this format:

### 1. [Job Title] — [Company]
**Location:** [city / remote]
**Apply:** [direct URL]
[2–3 sentence description from the actual posting]

---

{f'CANDIDATE BACKGROUND (to assess fit):{chr(10)}{resume_content}' if resume_content else ''}

RULES:
- Every listing must come from a page you actually fetched with web_fetch
- Every listing must have a working direct URL (not a search results page)
- Do not list a job unless you have fetched its page and confirmed it is open
- Do not give job search advice or general recommendations
- Output only the 5 job listings, nothing else"""

    def create_with_retry(client, delay=15, **kwargs):
        """Call messages.create, retrying once after a wait on rate limit errors."""
        try:
            return client.messages.create(**kwargs)
        except anthropic.RateLimitError:
            status.warning(f"Rate limit hit — waiting {delay}s before retrying…", icon="⏳")
            time.sleep(delay)
            return client.messages.create(**kwargs)

    client = get_client()
    status = st.empty()
    result_area = st.empty()
    status.info("Searching Greenhouse, Lever, Ashby, Amazon, JPMorgan, and more…", icon="🔍")

    messages = [{"role": "user", "content": prompt}]
    full_text = ""
    search_count = 0
    fetch_count = 0

    for _ in range(15):
        response = create_with_retry(
            client,
            model="claude-haiku-4-5",
            max_tokens=4096,
            tool_choice={"type": "any"} if (search_count + fetch_count) < 3 else {"type": "auto"},
            tools=[
                {"type": "web_search_20260209", "name": "web_search", "allowed_callers": ["direct"]},
                {"type": "web_fetch_20260209",  "name": "web_fetch",  "allowed_callers": ["direct"]},
            ],
            messages=messages,
        )

        for block in response.content:
            block_type = getattr(block, "type", None)
            if block_type == "server_tool_use":
                tool_name = getattr(block, "name", "")
                inp = getattr(block, "input", {})
                if tool_name == "web_search":
                    search_count += 1
                    status.info(f"Searching: *{inp.get('query', '')}*", icon="🔍")
                elif tool_name == "web_fetch":
                    fetch_count += 1
                    status.info(f"Reading posting {fetch_count}: {inp.get('url', '')}", icon="📄")

        for block in response.content:
            if getattr(block, "type", None) == "text":
                full_text += block.text
                result_area.markdown(full_text)

        if response.stop_reason == "end_turn":
            status.success(f"Done — {search_count} searches, {fetch_count} postings read.")
            break

        if response.stop_reason == "pause_turn":
            messages = [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": response.content},
            ]
            # Brief pause between turns to avoid burst rate limiting
            time.sleep(3)
        else:
            break

    if full_text:
        st.download_button(
            "📥 Download Job List",
            full_text,
            file_name="job_postings.txt",
            mime="text/plain",
        )
