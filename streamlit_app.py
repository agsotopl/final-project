import streamlit as st

st.set_page_config(page_title="Job Application Helper", page_icon="💼", layout="wide")

st.title("💼 Job Application Helper")
st.write("Streamline your job search with AI-powered tools.")

st.divider()

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### ✉️ Cover Letter")
    st.write("Generate a tailored cover letter from your resume and a job posting.")
    st.page_link("pages/1_Cover_Letter.py", label="Get started →")

with col2:
    st.markdown("### 📄 Tailor Resume")
    st.write("Optimize your resume for a specific role with ATS-friendly keywords.")
    st.page_link("pages/2_Tailor_Resume.py", label="Get started →")

with col3:
    st.markdown("### 🔍 Find Jobs")
    st.write("Discover relevant job postings matched to your background and preferences.")
    st.page_link("pages/3_Find_Jobs.py", label="Get started →")
