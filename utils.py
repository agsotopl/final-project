import io
import os
import streamlit as st
import anthropic
import openai

_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")


def get_client():
    return anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])


def get_openai_client():
    return openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])


# ---------------------------------------------------------------------------
# PDF formatting extraction
# ---------------------------------------------------------------------------

def _extract_pdf_formatting(raw: bytes) -> tuple[str, str]:
    """Parse a PDF with pdfplumber and return (plain_text, formatting_guide).

    plain_text      — full text content, line by line
    formatting_guide — structured description of fonts/sizes per content role,
                       ready to be injected into an LLM prompt.
    """
    import pdfplumber

    all_lines: list[dict] = []

    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        for page in pdf.pages:
            if not page.chars:
                continue

            # Group characters into lines by y-position (2 pt bucket tolerance)
            line_map: dict[int, list] = {}
            for char in page.chars:
                bucket = round(char["top"] / 2) * 2
                line_map.setdefault(bucket, []).append(char)

            for bucket in sorted(line_map):
                chars = line_map[bucket]
                text = "".join(c["text"] for c in chars).strip()
                if not text:
                    continue

                fontnames = [c["fontname"] for c in chars]
                sizes     = [c["size"]     for c in chars]

                raw_font = max(set(fontnames), key=fontnames.count)
                # Strip PDF subset prefix (e.g. "AAAAAA+TimesNewRomanPS-BoldMT" → "TimesNewRomanPS-BoldMT")
                dominant_font = raw_font.split("+", 1)[-1]
                avg_size      = round(sum(sizes) / len(sizes), 1)
                is_bold   = any(k in dominant_font.lower() for k in ("bold", "black", "heavy"))
                is_italic = any(k in dominant_font.lower() for k in ("italic", "oblique"))

                all_lines.append({
                    "text":   text,
                    "font":   dominant_font,
                    "size":   avg_size,
                    "bold":   is_bold,
                    "italic": is_italic,
                })

    plain_text = "\n".join(ln["text"] for ln in all_lines)

    # Build formatting guide: group by (font, size, bold, italic), sorted large→small
    seen: dict[tuple, list[str]] = {}
    for ln in all_lines:
        key = (ln["font"], ln["size"], ln["bold"], ln["italic"])
        seen.setdefault(key, []).append(ln["text"])

    guide: list[str] = [
        "TEMPLATE FORMATTING SPECIFICATION",
        "Apply these exact typographic conventions to the matching content types:\n",
    ]
    for (font, size, bold, italic), examples in sorted(seen.items(), key=lambda x: -x[0][1]):
        attrs = []
        if bold:
            attrs.append("Bold")
        if italic:
            attrs.append("Italic")
        attr_str = f", {', '.join(attrs)}" if attrs else ""
        sample = " | ".join(f'"{e[:60]}"' for e in examples[:3] if e.strip())
        guide.append(f"  • {font}{attr_str}, {size}pt\n    Used for: {sample}")

    return plain_text, "\n".join(guide)


# ---------------------------------------------------------------------------
# Template loading (repo defaults + user uploads)
# ---------------------------------------------------------------------------

def load_repo_template(name: str) -> tuple[str, str]:
    """Read a template from templates/ and return (plain_text, formatting_guide).

    Tries <name>.pdf first (richest metadata), then .docx, then .txt.
    formatting_guide is non-empty only for PDFs; empty string for other formats.
    """
    for ext in (".pdf", ".docx", ".txt"):
        path = os.path.join(_TEMPLATE_DIR, f"{name}{ext}")
        if not os.path.exists(path):
            continue
        with open(path, "rb") as f:
            raw = f.read()

        if ext == ".pdf":
            try:
                return _extract_pdf_formatting(raw)
            except Exception as e:
                st.warning(f"Could not parse PDF template formatting: {e}")
                return "", ""

        if ext == ".docx":
            try:
                import docx
                doc = docx.Document(io.BytesIO(raw))
                text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
                return text, ""
            except Exception as e:
                st.warning(f"Could not read DOCX template: {e}")
                return "", ""

        if ext == ".txt":
            return raw.decode("utf-8", errors="replace"), ""

    return "", ""


def extract_template_from_upload(uploaded_file) -> tuple[str, str]:
    """Extract (plain_text, formatting_guide) from a user-uploaded template file.

    PDF uploads get full formatting metadata; DOCX and TXT return empty guide.
    """
    raw = uploaded_file.read()
    file_type = uploaded_file.type

    if file_type == "application/pdf":
        try:
            return _extract_pdf_formatting(raw)
        except Exception as e:
            st.error(f"Could not parse uploaded PDF template: {e}")
            return "", ""

    if "wordprocessingml" in file_type:
        try:
            import docx
            doc = docx.Document(io.BytesIO(raw))
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            return text, ""
        except Exception as e:
            st.error(f"Could not read DOCX template: {e}")
            return "", ""

    # Plain text
    return raw.decode("utf-8", errors="replace"), ""


# ---------------------------------------------------------------------------
# Resume content helpers
# ---------------------------------------------------------------------------

def extract_text_from_file(uploaded_file):
    """Extract plain text from a PDF, DOCX, or TXT resume upload."""
    content = uploaded_file.read()
    file_type = uploaded_file.type

    if file_type == "text/plain":
        return content.decode("utf-8")

    if file_type == "application/pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(content))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as e:
            st.error(f"Could not read PDF: {e}")
            return ""

    if "wordprocessingml" in file_type:
        try:
            import docx
            doc = docx.Document(io.BytesIO(content))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception as e:
            st.error(f"Could not read DOCX: {e}")
            return ""

    return content.decode("utf-8", errors="replace")


def resume_inputs():
    """Render the shared resume upload + text area and return combined content.

    SHORT-TERM MEMORY  – the text area is bound to st.session_state['resume_text']
                         so it persists when the user switches between pages.
    LONG-TERM MEMORY   – on the very first script run per browser session the
                         last-saved resume is pre-loaded from SQLite via memory.py.
    """
    # --- LONG-TERM MEMORY: pre-load saved resume once per browser session ---
    import memory as _mem
    _mem.init_session_resume()

    st.subheader("Your Background")

    if st.session_state.get("_resume_from_db") and st.session_state.get("resume_text"):
        st.caption("Resume pre-loaded from your last session — edit below or upload a new file.")

    uploaded = st.file_uploader("Upload Resume (PDF, DOCX, or TXT)", type=["pdf", "docx", "txt"])

    # SHORT-TERM MEMORY: key binds to session_state so content survives page switches
    pasted = st.text_area(
        "Or paste your resume / additional context here",
        key="resume_text",
        height=250,
        placeholder="Work history, skills, education, achievements…",
    )

    parts = []
    if uploaded:
        extracted = extract_text_from_file(uploaded)
        if extracted:
            parts.append(f"[UPLOADED RESUME]\n{extracted}")
    if pasted.strip():
        parts.append(pasted.strip())

    combined = "\n\n".join(parts)

    # SHORT-TERM: cache the combined result for cross-page access
    if combined:
        st.session_state["resume_content"] = combined

    return combined
