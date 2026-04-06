import io
import streamlit as st
import anthropic


def get_client():
    return anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])


def extract_text_from_file(uploaded_file):
    """Extract plain text from a PDF, DOCX, or TXT upload."""
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
    """Render the shared resume upload + text area and return combined content."""
    st.subheader("Your Background")
    uploaded = st.file_uploader("Upload Resume (PDF, DOCX, or TXT)", type=["pdf", "docx", "txt"])
    pasted = st.text_area(
        "Or paste your resume / additional context here",
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

    return "\n\n".join(parts)
