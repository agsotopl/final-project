import streamlit as st

st.title("💼 Job Application Helper")
st.write("Streamline your job search with AI-powered tools.")

st.divider()

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### ✉️ Cover Letter")
    st.write("Generate a tailored cover letter from your resume and a job posting.")

with col2:
    st.markdown("### 📄 Tailor Resume")
    st.write("Optimize your resume for a specific role with ATS-friendly keywords.")

with col3:
    st.markdown("### 🔍 Find Jobs")
    st.write("Discover relevant job postings matched to your background and preferences.")
