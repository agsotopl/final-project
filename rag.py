# =============================================================================
# rag.py  –  Job-description vector store with cosine-similarity reranking
#
# Uses sentence-transformers (all-MiniLM-L6-v2) to embed job descriptions and
# resume text, then ranks stored postings by cosine similarity so the most
# relevant cached results are surfaced before the live agentic search runs.
# =============================================================================

import os
import pickle
from typing import Optional

import numpy as np

STORE_PATH = os.path.join(os.path.dirname(__file__), "job_vectors.pkl")

# ---------------------------------------------------------------------------
# Seed job descriptions  (pre-populate the store on first run)
# ---------------------------------------------------------------------------

SEED_JOBS: list[dict] = [
    {
        "title": "Data Analyst",
        "company": "Apex Analytics",
        "location": "Remote",
        "description": (
            "Analyze large datasets to uncover business insights using SQL, Python, and Tableau. "
            "Build dashboards, run A/B tests, and present findings to stakeholders. "
            "Requires 1–3 years experience with pandas, Excel, and data visualization."
        ),
    },
    {
        "title": "Software Engineer – Backend",
        "company": "CloudCore",
        "location": "San Francisco, CA",
        "description": (
            "Design and maintain RESTful APIs and microservices in Python/FastAPI and Go. "
            "Work with PostgreSQL, Redis, and Kubernetes in a CI/CD environment. "
            "2+ years of production backend experience required."
        ),
    },
    {
        "title": "Machine Learning Engineer",
        "company": "Neuron AI",
        "location": "New York, NY (Hybrid)",
        "description": (
            "Train, evaluate, and deploy ML models using PyTorch and scikit-learn. "
            "Build data pipelines with Spark and manage experiments in MLflow. "
            "MS or PhD in CS, statistics, or related field preferred."
        ),
    },
    {
        "title": "UX Designer",
        "company": "Pixel Studio",
        "location": "Austin, TX",
        "description": (
            "Create wireframes, prototypes, and high-fidelity designs in Figma. "
            "Conduct user research, usability tests, and collaborate with product and engineering. "
            "3+ years of UX/product-design experience; portfolio required."
        ),
    },
    {
        "title": "Product Manager",
        "company": "Launchpad Tech",
        "location": "Remote",
        "description": (
            "Own the roadmap for a B2B SaaS product: write PRDs, prioritize features, "
            "and coordinate cross-functional sprints. "
            "3+ years of PM experience in a fast-paced software environment."
        ),
    },
    {
        "title": "Financial Analyst",
        "company": "Sterling Capital",
        "location": "Chicago, IL",
        "description": (
            "Build financial models, perform variance analysis, and support FP&A reporting. "
            "Work with Excel, Power BI, and ERP systems. "
            "CFA candidate preferred; 2+ years of corporate finance experience."
        ),
    },
    {
        "title": "Marketing Manager – Digital",
        "company": "GrowthLoop",
        "location": "Remote",
        "description": (
            "Plan and execute paid-search, social, and email campaigns. "
            "Analyze funnel metrics with Google Analytics and HubSpot, optimize CAC/LTV. "
            "4+ years of B2C digital-marketing experience."
        ),
    },
    {
        "title": "Cybersecurity Analyst",
        "company": "ShieldNet",
        "location": "Washington, DC (Hybrid)",
        "description": (
            "Monitor SIEM alerts, conduct vulnerability assessments, and lead incident response. "
            "Experience with Splunk, Nessus, and NIST CSF required. "
            "CompTIA Security+ or CISSP preferred."
        ),
    },
    {
        "title": "DevOps Engineer",
        "company": "InfraShift",
        "location": "Remote",
        "description": (
            "Manage cloud infrastructure on AWS with Terraform and Ansible. "
            "Design CI/CD pipelines in GitHub Actions and Jenkins; oversee Docker/Kubernetes fleets. "
            "3+ years of infrastructure-as-code experience."
        ),
    },
    {
        "title": "Full-Stack Developer",
        "company": "BuildIt Labs",
        "location": "Seattle, WA",
        "description": (
            "Build features across a React/TypeScript frontend and a Node.js/Express backend. "
            "Work with MongoDB, GraphQL, and AWS S3. "
            "2+ years of full-stack experience; experience with agile sprints."
        ),
    },
    {
        "title": "Business Analyst",
        "company": "Meridian Consulting",
        "location": "Atlanta, GA (Hybrid)",
        "description": (
            "Gather and document business requirements, map as-is/to-be processes, "
            "and translate stakeholder needs into user stories for development teams. "
            "PMP or CBAP certification a plus."
        ),
    },
    {
        "title": "Supply Chain Analyst",
        "company": "Nexus Logistics",
        "location": "Dallas, TX",
        "description": (
            "Optimize inventory levels, analyze supplier performance, and build forecasting models. "
            "Proficiency in SAP, Tableau, and advanced Excel required. "
            "1–3 years of supply-chain or operations-analysis experience."
        ),
    },
    {
        "title": "Data Science Intern",
        "company": "Insight Labs",
        "location": "Remote",
        "description": (
            "Support data scientists in cleaning datasets, running statistical analyses, "
            "and building preliminary ML models. Python, R, and SQL required. "
            "Open to junior/senior undergrad and MS students."
        ),
    },
    {
        "title": "HR Business Partner",
        "company": "PeopleFirst Corp",
        "location": "Boston, MA",
        "description": (
            "Partner with business leaders on talent planning, performance management, "
            "and employee-relations matters. "
            "PHR/SPHR certification preferred; 4+ years HRBP experience."
        ),
    },
    {
        "title": "Software Engineering Intern",
        "company": "Orion Systems",
        "location": "Austin, TX (On-site)",
        "description": (
            "Work alongside senior engineers to ship features in a Python/Django codebase. "
            "Write unit tests, participate in code review, and attend daily standups. "
            "Must be an undergraduate student graduating within the next two years."
        ),
    },
    {
        "title": "Cloud Solutions Architect",
        "company": "Stratosphere Tech",
        "location": "Remote",
        "description": (
            "Design multi-region AWS and Azure architectures for enterprise clients. "
            "Lead migrations, define IAM policies, and produce Well-Architected review reports. "
            "AWS Solutions Architect Professional certification required."
        ),
    },
    {
        "title": "Content Strategist",
        "company": "Narrative Agency",
        "location": "New York, NY",
        "description": (
            "Develop editorial calendars, write long-form content, and manage SEO strategy. "
            "Collaborate with design and social teams; track performance with Google Analytics. "
            "Strong writing portfolio and 3+ years of content-marketing experience required."
        ),
    },
    {
        "title": "Project Manager – IT",
        "company": "Catalyst Solutions",
        "location": "Denver, CO (Hybrid)",
        "description": (
            "Lead cross-functional IT implementation projects using Agile and Waterfall methods. "
            "Manage scope, schedule, budget, and risk registers in Jira. "
            "PMP required; 5+ years of IT project-management experience."
        ),
    },
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_model = None  # module-level cache: survives Streamlit reruns in the same process


def _get_model():
    """Lazy-load the SentenceTransformer model (downloaded once, then cached)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _load_store() -> dict:
    if os.path.exists(STORE_PATH):
        with open(STORE_PATH, "rb") as f:
            return pickle.load(f)
    return {"jobs": [], "embeddings": None}


def _save_store(store: dict) -> None:
    with open(STORE_PATH, "wb") as f:
        pickle.dump(store, f)


def _job_text(job: dict) -> str:
    """Concatenate the fields used for embedding."""
    return " ".join(filter(None, [
        job.get("title", ""),
        job.get("company", ""),
        job.get("location", ""),
        job.get("description", ""),
    ]))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ensure_seeded() -> None:
    """Populate the vector store with seed jobs if it is empty."""
    store = _load_store()
    if store["jobs"]:
        return
    model = _get_model()
    for job in SEED_JOBS:
        emb = model.encode(_job_text(job), normalize_embeddings=True)
        store["jobs"].append(job)
        if store["embeddings"] is None:
            store["embeddings"] = emb.reshape(1, -1)
        else:
            store["embeddings"] = np.vstack([store["embeddings"], emb])
    _save_store(store)


def add_job(job: dict) -> None:
    """Embed and append a job posting dict to the persistent vector store.

    Call this after a live agent search completes so future RAG lookups
    benefit from real postings the app has already retrieved.
    """
    store = _load_store()
    model = _get_model()
    emb = model.encode(_job_text(job), normalize_embeddings=True)
    store["jobs"].append(job)
    if store["embeddings"] is None:
        store["embeddings"] = emb.reshape(1, -1)
    else:
        store["embeddings"] = np.vstack([store["embeddings"], emb])
    _save_store(store)


def retrieve_similar_jobs(query: str, top_k: int = 5) -> list[dict]:
    """Return the *top_k* stored jobs most similar to *query*, ranked by cosine similarity.

    Each returned dict is a copy of the stored job plus a 'similarity_score' key (0–1).
    Returns an empty list if the store is empty or sentence-transformers is unavailable.
    """
    try:
        ensure_seeded()
        store = _load_store()
        if not store["jobs"] or store["embeddings"] is None:
            return []

        model = _get_model()
        # Truncate long queries to stay within the model's 256-token limit
        query_emb = model.encode(query[:2000], normalize_embeddings=True)

        # Cosine similarity: dot product of L2-normalised vectors
        scores: np.ndarray = store["embeddings"] @ query_emb
        top_k = min(top_k, len(store["jobs"]))
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            job = store["jobs"][idx].copy()
            job["similarity_score"] = float(scores[idx])
            results.append(job)

        return results

    except Exception:
        return []
