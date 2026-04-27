import time
from datetime import date, datetime, timezone
import streamlit as st
import anthropic
from utils import get_client, resume_inputs


def _senior_base_year() -> int:
    """Return the graduation year for a current senior.

    Seniors graduate at the end of the current academic year:
    - Jan–Jul  → spring/summer/fall of *this* calendar year
    - Aug–Dec  → spring/summer/fall of *next* calendar year (fall semester is underway)
    """
    today = date.today()
    return today.year if today.month < 8 else today.year + 1


# Maps a class-standing key to years-until-graduation relative to a senior.
_STANDING_OFFSETS: dict[str, int] = {
    "Senior": 0,
    "Junior": 1,
    "Sophomore": 2,
    "Freshman": 3,
}


def graduation_window(class_key: str) -> str | None:
    """Return a human-readable graduation window for *class_key*.

    Includes both season names and the specific months that job postings use
    (May for Spring, August for Summer, December for Fall/Winter).
    Returns None for 'N/A'.
    """
    if class_key == "N/A":
        return None

    base = _senior_base_year()

    if class_key == "Graduate Student":
        return f"May or December {base}–{base + 2} (graduate student, 1–2 year program)"

    offset = _STANDING_OFFSETS.get(class_key)
    if offset is None:
        return None

    yr = base + offset
    return (
        f"May {yr} (Spring), August {yr} (Summer), or December {yr} (Fall/Winter)"
    )


def _standing_label(class_key: str) -> str:
    """Build the selectbox display label, e.g. 'Senior (Class of 2026)'."""
    offset = _STANDING_OFFSETS.get(class_key)
    if offset is not None:
        return f"{class_key} (Class of {_senior_base_year() + offset})"
    return class_key  # 'N/A' and 'Graduate Student' shown as-is


# Keys used internally; labels are computed so they stay correct every year.
_STANDING_KEYS = ["N/A", "Freshman", "Sophomore", "Junior", "Senior", "Graduate Student"]
_STANDING_LABELS = [_standing_label(k) for k in _STANDING_KEYS]

# ---------------------------------------------------------------------------
# Compatibility checks: (experience_level, class_standing_key) → warning msg
# Hard blocks return (message, True); soft warnings return (message, False).
# ---------------------------------------------------------------------------
_INCOMPATIBLE: list[tuple[set, set, str, bool]] = [
    # experience levels that make no sense for internships
    (
        {"Lead / Principal", "Manager / Director"},
        {"Freshman", "Sophomore", "Junior", "Senior", "Graduate Student", "N/A"},
        "Internship-level searches are unlikely to return results for Lead / Principal or Manager / Director roles.",
        False,
    ),
    # senior graduating this cycle + internship — recruiting already closed
    (
        {"Internship"},
        {"Senior"},
        "Seniors graduating this cycle are rarely eligible for new internships — most recruiting for the current summer has already closed. Consider 'Entry Level' or 'New Grad' instead.",
        False,
    ),
    # senior or grad + internship is a soft warning, not a hard block
    (
        {"Internship"},
        {"Graduate Student"},
        "Graduate student internship postings exist but are limited — results may be sparse. Consider broadening to 'Entry Level' if you don't find enough.",
        False,
    ),
]


def check_compatibility(experience: str, class_key: str) -> tuple[str | None, bool]:
    """Return (warning_message, is_hard_block) or (None, False) if compatible."""
    for exp_set, standing_set, msg, hard in _INCOMPATIBLE:
        if experience in exp_set and class_key in standing_set:
            return msg, hard
    return None, False


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
    class_standing_label = st.selectbox("Class Standing (optional)", _STANDING_LABELS)
    class_standing_key = _STANDING_KEYS[_STANDING_LABELS.index(class_standing_label)]
    industry = st.text_input("Industry (optional)", placeholder="e.g. FinTech, Healthcare")
    salary = st.text_input("Salary Range (optional)", placeholder="e.g. $90k – $120k")

st.divider()

if st.button("🔍 Find Relevant Jobs", type="primary", use_container_width=True):
    if not desired_role:
        st.warning("Please enter a desired role to search for.", icon="⚠️")
        st.stop()

    compat_msg, is_hard_block = check_compatibility(experience, class_standing_key)
    if compat_msg:
        if is_hard_block:
            st.error(compat_msg, icon="🚫")
            st.stop()
        else:
            st.warning(compat_msg, icon="⚠️")

    graduation_str = graduation_window(class_standing_key)

    location_str = location or "remote"
    work_type_str = f" {work_type.lower()}" if work_type != "Any" else ""
    experience_str = f" {experience}" if experience != "Any" else ""

    prompt = f"""You are a job search assistant. Your goal is to return exactly 5 real, currently open job postings with direct apply links. Follow every step below precisely.

--- ROLE TO SEARCH FOR ---
{experience_str.strip() + " " if experience_str else ""}{desired_role}{work_type_str}, {location_str}{f', {industry}' if industry else ''}
{f'Salary preference: {salary}' if salary else ''}
{f'Candidate graduation window: {graduation_str} — prioritize postings that explicitly target this graduation cohort or are open to candidates graduating in this range (especially relevant for internships and new grad roles).' if graduation_str else ''}

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
- If fewer than 5 verified postings exist for this search, output however many you found (even 1 or 2) and add a short note explaining that results were limited for this criteria — do NOT fabricate listings to reach 5
- Output only the job listings (and the note if applicable), nothing else"""

    def trim_tool_results(content_blocks, max_chars: int = 800):
        """Truncate server_tool_result text so conversation history stays small.

        web_fetch responses are full HTML pages (10k–50k tokens each).  The model
        has already processed them; resending the full HTML on every subsequent turn
        is what exhausts the 50k input-token-per-minute limit.
        """
        trimmed = []
        for block in content_blocks:
            if getattr(block, "type", None) == "server_tool_result":
                d = block.model_dump()
                content = d.get("content", "")
                if isinstance(content, str) and len(content) > max_chars:
                    d["content"] = content[:max_chars] + "\n…[truncated to preserve token budget]"
                elif isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            text = item.get("text", "")
                            if len(text) > max_chars:
                                item["text"] = text[:max_chars] + "\n…[truncated to preserve token budget]"
                trimmed.append(d)
            else:
                trimmed.append(block)
        return trimmed

    def create_with_retry(client, **kwargs):
        """Call messages.create with proactive throttling + exponential backoff.

        Uses the rate-limit headers returned on every response to sleep *before*
        hitting the limit.  Falls back to reactive backoff (15 → 30 → 60 s) if a
        429 slips through anyway.
        """
        delays = [15, 30, 60]
        # Tokens-remaining threshold below which we pause until the window resets.
        # 10 000 gives roughly one more large request before the cap is hit.
        LOW_TOKEN_THRESHOLD = 10_000

        for i, delay in enumerate(delays):
            try:
                raw = client.messages.with_raw_response.create(**kwargs)

                # --- proactive throttle ---
                remaining = raw.headers.get("x-ratelimit-remaining-input-tokens")
                reset_at  = raw.headers.get("x-ratelimit-reset-input-tokens")
                if remaining is not None and int(remaining) < LOW_TOKEN_THRESHOLD and reset_at:
                    try:
                        reset_dt = datetime.fromisoformat(reset_at.replace("Z", "+00:00"))
                        wait = (reset_dt - datetime.now(timezone.utc)).total_seconds()
                        if wait > 0:
                            status.warning(
                                f"Approaching rate limit ({remaining} tokens left) — "
                                f"pausing {wait:.0f}s until window resets…",
                                icon="⏳",
                            )
                            time.sleep(wait + 1)
                    except ValueError:
                        pass  # malformed header — skip the proactive wait

                return raw.parse()

            except anthropic.RateLimitError:
                if i == len(delays) - 1:
                    raise
                status.warning(
                    f"Rate limit hit — waiting {delay}s before retrying… "
                    f"(attempt {i + 1}/{len(delays)})",
                    icon="⏳",
                )
                time.sleep(delay)

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
                {"role": "assistant", "content": trim_tool_results(response.content)},
            ]
            # Pause between turns to avoid burst rate limiting
            time.sleep(10)
        else:
            break

    if full_text:
        st.download_button(
            "📥 Download Job List",
            full_text,
            file_name="job_postings.txt",
            mime="text/plain",
        )
