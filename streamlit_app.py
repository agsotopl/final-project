import streamlit as st

st.set_page_config(page_title="Job Application Helper", layout="wide")

pg = st.navigation([
    st.Page("pages/home.py",             title="Home"),
    st.Page("pages/1_Cover_Letter.py",   title="Cover Letter"),
    st.Page("pages/2_Tailor_Resume.py",  title="Tailor Resume"),
    st.Page("pages/3_Find_Jobs.py",      title="Find Jobs"),
])
pg.run()
