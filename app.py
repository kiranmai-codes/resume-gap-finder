#!/usr/bin/env python3
"""
Streamlit web app — Resume Gap Finder.
"""
import io
import json
import re
from pathlib import Path

import streamlit as st

# ============================================================
# Config & Custom CSS
# ============================================================
st.set_page_config(
    page_title="Resume Gap Finder — India Entry-Level SDE",
    page_icon="🎯",
    layout="wide",
)

# Inject custom CSS for a cleaner, SaaS-like look
st.markdown("""
<style>
    /* Hide default Streamlit footer and menu */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Improve typography */
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* Style the title */
    h1 {
        font-weight: 800;
        color: #111827;
        letter-spacing: -0.02em;
    }
    
    /* Style the metrics to look like cards */
    div[data-testid="stMetric"] {
        background-color: white;
        border: 1px solid #E5E7EB;
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    
    /* Style the form container */
    div[data-testid="stForm"] {
        background-color: white;
        border: 1px solid #E5E7EB;
        border-radius: 16px;
        padding: 32px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    
    /* Style the submit button */
    div[data-testid="stFormSubmitButton"] button {
        background-color: #4F46E5;
        color: white;
        border-radius: 8px;
        font-weight: 600;
        border: none;
        padding: 12px 24px;
        transition: all 0.2s;
    }
    div[data-testid="stFormSubmitButton"] button:hover {
        background-color: #4338CA;
        box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3);
    }
</style>
""", unsafe_allow_html=True)

ARTIFACT_PATH = Path(__file__).parent / "outputs" / "pipeline" / "16_resume_gap_artifact.json"

# ============================================================
# Load benchmark (cached)
# ============================================================
@st.cache_data
def load_benchmark():
    with open(ARTIFACT_PATH) as f:
        return json.load(f)

@st.cache_data
def load_taxonomy():
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from core.indeed_taxonomy import TECHNOLOGY_ALIASES, TECH_CATEGORIES
        return TECHNOLOGY_ALIASES, TECH_CATEGORIES
    except Exception:
        return {}, {}

# ============================================================
# Logic
# ============================================================
def extract_text_from_pdf(pdf_bytes):
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as e:
        st.error(f"Could not read PDF: {e}")
        return ""

def extract_skills(resume_text, aliases):
    text = (resume_text or "").lower()
    found = {}
    for tech, patterns in aliases.items():
        for pat in patterns:
            if re.search(pat, text, re.I):
                found[tech] = True
                break
    return found

def compute_gap(resume_skills, benchmark_techs):
    have, missing = [], []
    stability_weight = {"high": 1.0, "medium": 0.7, "low": 0.4}
    
    for tech in benchmark_techs:
        name = tech["technology"]
        entry = {
            "technology": name,
            "benchmark_share": tech.get("benchmark_share", 0),
            "priority": tech.get("priority", "low"),
            "stability_tier": tech.get("stability_tier", "low"),
        }
        if name in resume_skills:
            have.append(entry)
        else:
            missing.append(entry)
            
    for m in missing:
        m["_score"] = m["benchmark_share"] * stability_weight.get(m["stability_tier"], 0.4)
        
    missing.sort(key=lambda x: x["_score"], reverse=True)
    have.sort(key=lambda x: x["benchmark_share"], reverse=True)
    
    # NEW: Filter out anything that requires less than 2% of jobs. 
    # It's not a "gap", it's just noise.
    missing = [m for m in missing if m["benchmark_share"] >= 0.02]
    
    return have, missing

PROJECT_IDEAS = {
    "JavaScript": "Build a to-do list app with vanilla JS (DOM, fetch API, localStorage). Push to GitHub with a README.",
    "Java": "Build a command-line inventory manager using Java + JDBC + MySQL. Add JUnit tests.",
    "HTML": "Build a responsive portfolio site with HTML5 semantic tags + CSS grid. Deploy to Netlify.",
    "Python": "Build a FastAPI REST API that fetches from a public API, caches with Redis, returns JSON. Deploy with Docker.",
    "CSS": "Build a 3-page responsive site using only CSS (no frameworks). Add mobile menu + dark mode.",
    "REST API": "Build a CRUD REST API with GET/POST/PUT/DELETE, input validation, and error responses.",
    "SQL": "Build a movie-rating database (3+ tables, foreign keys). Queries for top-rated, per-genre rankings.",
    "React": "Build a weather dashboard with React hooks + fetch. Include city search, loading states, error handling.",
    "Git": "Fork an open-source repo, make 3 meaningful commits, submit a PR with clear commit messages.",
    "OOP": "Build a small library system using classes, inheritance, interfaces. Include UML diagram in README.",
    "Node.js": "Build a real-time chat app with Node.js + Socket.io + Express. Include rooms and message history.",
    "MySQL": "Build a booking system (users, bookings, slots) with normalized schema. Include migrations and seed data.",
    "MongoDB": "Build a task manager with MongoDB + Express + React. Use aggregation pipelines for filtering.",
    "PostgreSQL": "Extend your SQL project to PostgreSQL. Add full-text search, a view, and a stored procedure.",
    "Angular": "Build an admin dashboard with Angular + RxJS + Material. Include routing, guards, form validation.",
    "Spring": "Build a library management API with Spring Boot + JPA + MySQL. Include Swagger docs and tests.",
    "Spring Boot": "Build a payment gateway API with Spring Boot. Add JWT auth, Hibernate ORM, and integration tests.",
    "Docker": "Containerize your FastAPI/Node project. Write Dockerfile + docker-compose.yml. Deploy to a cloud VM.",
    "AWS": "Deploy one of your projects to AWS EC2 + RDS. Include a load balancer and a managed DB.",
    "TypeScript": "Migrate one of your JavaScript projects to TypeScript. Add strict mode + interfaces for all API responses.",
    "Django": "Build a blog with Django + PostgreSQL. Include user auth, admin panel, and deployment to Render.",
    "Kotlin": "Build a small Android app with Kotlin + Jetpack Compose. Publish to Play Store internal testing.",
    "Android": "Build an Android app that fetches data from your FastAPI backend. Include auth and offline cache.",
}

# ============================================================
# UI Layout
# ============================================================
def main():
    artifact = load_benchmark()
    aliases, categories = load_taxonomy()

    st.title("🎯 Resume Gap Finder")
    st.markdown(
        f"Compare your resume to **{artifact['benchmark_size']} verified "
        f"entry-level software engineering jobs** in India — and find out "
        f"exactly what to learn next."
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Jobs in benchmark", artifact["benchmark_size"])
    col2.metric("Companies", artifact["unique_companies"])
    col3.metric("Confirmed entry-level", artifact["confirmed_tier"])
    col4.metric("Role families", len(artifact.get("role_meta", {})))

    st.write("") 

    form_col1, form_col2, form_col3 = st.columns([1, 2, 1])
    
    with form_col2:
        with st.form("resume_form"):
            st.subheader("1. Upload your resume")
            uploaded = st.file_uploader(
                "PDF or plain text",
                type=["pdf", "txt"],
                help="Upload your resume. Nothing is stored — it's parsed in memory only.",
                label_visibility="collapsed"
            )

            st.subheader("2. Pick your target role")
            role_options = ["All software roles (overview)"] + sorted(
                artifact.get("role_meta", {}).keys()
            )
            role_choice = st.selectbox(
                "Which kind of role are you targeting?",
                role_options,
                index=0,
                help="Backend, Frontend, Full Stack, Mobile — pick what you want to apply to.",
                label_visibility="collapsed"
            )

            submitted = st.form_submit_button("Analyze my resume", use_container_width=True)

    if submitted:
        if not uploaded:
            st.warning("Please upload a resume first.")
            return

        if uploaded.type == "application/pdf":
            resume_text = extract_text_from_pdf(uploaded.read())
        else:
            resume_text = uploaded.read().decode("utf-8", errors="ignore")

        if not resume_text.strip() or len(resume_text) < 100:
            st.error("Couldn't extract text from your resume. Try a text version.")
            return

        resume_skills = extract_skills(resume_text, aliases)

        if role_choice.startswith("All software"):
            benchmark_techs = artifact["technologies"]
            denominator = artifact["benchmark_size"]
            scope_label = "all entry-level SDE jobs"
        else:
            benchmark_techs = artifact["role_technologies"][role_choice]
            denominator = artifact["role_meta"][role_choice]["n_jobs"]
            scope_label = f"{role_choice} roles"

        have, missing = compute_gap(resume_skills, benchmark_techs)

        st.divider()
        st.header("Your gap report")
        
                # Calculate match rate against the Top 10 core skills for this role
        top_10_core = benchmark_techs[:10] 
        core_matches = sum(1 for tech in top_10_core if tech["technology"] in resume_skills)
        match_rate = (core_matches / len(top_10_core)) * 100 if top_10_core else 0
        
        top_gap = missing[0]["technology"] if missing else "None!"

        c1, c2, c3 = st.columns(3)
        c1.metric("Skills matched", len(have))
        c2.metric("Core Stack Match", f"{match_rate:.0f}%", help="Your match rate against the Top 10 most in-demand skills for this role.")
        c3.metric("Top gap to fill", top_gap)

        st.markdown(f"Comparing against **{denominator} jobs** in the {scope_label} benchmark.")
        st.write("")

        tab1, tab2 = st.tabs(["⚠️ What to learn", "✅ What you have"])

        with tab1:
            if not missing:
                st.success("You have every technology the benchmark cares about. 🎉")
            else:
                st.markdown("### Your Top 5 Priorities")
                st.caption("Focus on these first. They are the highest-leverage skills for your target role.")
                
                for i, m in enumerate(missing[:5], 1):
                    pct = m["benchmark_share"] * 100
                    with st.expander(f"{i}. {m['technology']} — required by {pct:.0f}% of jobs", expanded=(i == 1)):
                        st.markdown(f"**Priority:** `{m['priority']}` · **Stability:** `{m['stability_tier']}`")
                        if m["technology"] in PROJECT_IDEAS:
                            st.info(f"💡 **Project idea:** {PROJECT_IDEAS[m['technology']]}")
                        else:
                            st.info(f"No project template yet — search \"{m['technology']} beginner project\" on YouTube.")

                if len(missing) > 5:
                    with st.expander(f"➕ View other {len(missing) - 5} lower-priority skills in the benchmark"):
                        st.caption("These appear in fewer jobs. Learn them later if you have time.")
                        for i, m in enumerate(missing[5:], 6):
                            pct = m["benchmark_share"] * 100
                            st.markdown(f"- **{m['technology']}** — required by {pct:.0f}% of jobs")

        with tab2:
            if not have:
                st.info("No benchmark technologies detected in your resume yet.")
            else:
                st.markdown("### Skills you already have")
                for h in have[:15]:
                    pct = h["benchmark_share"] * 100
                    st.markdown(f"- **{h['technology']}** — in {pct:.0f}% of jobs ({h['priority']} priority)")

        st.divider()
        st.subheader("How to use this")
        st.markdown("""
            1. Pick **2 skills** from your Top 5 priorities
            2. Build the suggested project for each — one project per skill
            3. Add both projects to your resume with GitHub links
            4. Come back and re-run this after you've built them
        """)

        report_text = f"RESUME GAP REPORT\nScope: {scope_label} ({denominator} jobs)\n\nTOP GAPS TO LEARN:\n"
        for i, m in enumerate(missing[:5], 1):
            report_text += f"{i}. {m['technology']} ({m['benchmark_share']*100:.0f}%)\n"
            
        st.download_button(
            "📥 Download report as text",
            data=report_text,
            file_name="resume_gap_report.txt",
            mime="text/plain",
        )

    st.write("")
    st.caption("🔒 **Privacy:** Your resume is parsed in memory only. Nothing is stored, logged, or sent to any third party.")
    st.caption(f"Benchmark: {artifact['benchmark_size']} jobs · 4 job portals (Naukri, Indeed, Foundit, JobSpy).")

if __name__ == "__main__":
    main()
