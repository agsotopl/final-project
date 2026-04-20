# =============================================================================
# ethics.py  –  Secondary Claude API call to evaluate a tailored resume
#               against an ethics rubric before the user can download it.
#
# Checks for: fabricated experience, inflated job titles, misleading phrasing,
# and keyword stuffing.  Returns a structured verdict: "pass", "warn", or "flag".
# =============================================================================

import json

import streamlit as st


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate_resume_ethics(resume_text: str, job_posting: str = "") -> dict:
    """Run a secondary Claude call to audit the tailored resume for ethical issues.

    Returns a dict with keys:
        verdict     : "pass" | "warn" | "flag"
        explanation : one-to-two sentence overall assessment
        issues      : list of specific issue strings (may be empty)
    """
    from utils import get_client  # imported here to avoid circular imports

    client = get_client()

    job_section = (
        f"\nTARGET JOB POSTING (for context):\n{job_posting.strip()}"
        if job_posting and job_posting.strip()
        else ""
    )

    rubric_prompt = f"""You are an ethics auditor reviewing an AI-tailored resume for honest, fair representation.

TAILORED RESUME:
{resume_text}
{job_section}

Evaluate the resume against each criterion below:

1. FABRICATED EXPERIENCE
   Flag if the resume invents roles, projects, degrees, or achievements that are implausible,
   internally inconsistent, or not derivable from honest rewording of typical experience.

2. INFLATED JOB TITLES
   Flag if titles are exaggerated beyond industry norms (e.g. "CEO" for a side project,
   "Director" for an individual-contributor role).

3. MISLEADING PHRASING
   Flag if the language implies a scope, budget, or impact far beyond what is realistic
   (e.g. "Led a $50M initiative" based on thin evidence, or passive work reframed as sole ownership).

4. KEYWORD STUFFING
   Flag if high-value keywords appear unnaturally densely or without supporting context,
   suggesting manipulation of ATS filters rather than authentic description.

Respond with a single JSON object only — no markdown fences, no explanation outside the JSON:
{{
  "verdict": "pass" | "warn" | "flag",
  "explanation": "<one or two sentences summarising the overall assessment>",
  "issues": ["<specific issue>", "..."]
}}

Verdict guidelines:
  pass  – No meaningful ethical concerns; content is honest and well-phrased.
  warn  – One or two minor issues worth the candidate's attention before submitting.
  flag  – One or more significant issues that should be corrected before submission."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            messages=[{"role": "user", "content": rubric_prompt}],
        )
        raw = response.content[0].text.strip()
        # Strip accidental markdown fences if the model adds them
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw)
    except (json.JSONDecodeError, IndexError, KeyError, Exception):
        result = {
            "verdict": "warn",
            "explanation": "Ethics evaluation could not be completed — please review manually.",
            "issues": [],
        }

    # Normalise verdict to a known value
    if result.get("verdict") not in ("pass", "warn", "flag"):
        result["verdict"] = "warn"

    return result


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def display_ethics_result(result: dict) -> None:
    """Render the ethics rubric verdict inside the Streamlit UI."""
    verdict = result.get("verdict", "warn")
    explanation = result.get("explanation", "")
    issues = result.get("issues") or []

    st.subheader("Ethics Rubric Check")

    if verdict == "pass":
        st.success(f"**PASS** — {explanation}", icon="✅")

    elif verdict == "warn":
        st.warning(f"**WARN** — {explanation}", icon="⚠️")
        if issues:
            for issue in issues:
                st.caption(f"• {issue}")

    else:  # "flag"
        st.error(f"**FLAG** — {explanation}", icon="🚩")
        if issues:
            for issue in issues:
                st.caption(f"• {issue}")

    st.caption(
        "This automated check looks for common ethical concerns in AI-tailored resumes. "
        "It is not a substitute for your own review."
    )
