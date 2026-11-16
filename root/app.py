#!/usr/bin/env python3
"""
Streamlit web app — Resume Gap Finder.

Wraps the pipeline's 16_resume_gap_artifact.json in a fresher-friendly UI.
Public, mobile-friendly, no signup required.

Deploy to: https://streamlit.io/cloud
"""
import io
import json
import re
from pathlib import Path

import streamlit as st

# ============================================================
# Config
# ============================================================
st.set_page_config(
    page_title="Resume Gap Finder — India Entry-Level SDE",
    page_icon="🎯",
    layout="wide",
)

ARTIFACT_PATH = Path(__file__).parent / "outputs" / "pipeline" / "16_resume_gap_artifact.json"


# ============================================================
# Load benchmark (cached — runs once per server)
# ============================================================
@st.cache_data
def load_benchmark():
    with open(ARTIFACT_PATH) as f:
        return json.load(f)


@st.cache_data
def load_taxonomy():
    """Inline minimal tech aliases so we don't import the heavy pipeline code."""
    # Import from core — but wrap in try/except so the deployed app doesn't
    # crash if core/ isn't uploaded. Fall back to empty.
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from core.indeed_taxonomy import TECHNOLOGY_ALIASES, TECH_CATEGORIES
        return TECHNOLOGY_ALIASES, TECH_CATEGORIES
    except Exception:
        return {}, {}


# ============================================================
# Resume parsing
# ============================================================
def extract_text_from_pdf(pdf_bytes):
    """Extract text from uploaded PDF. Returns '' on failure."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as e:
        st.error(f"Could not read PDF: {e}")
        return ""


def extract_skills(resume_text, aliases):
    """Find technologies mentioned in resume."""
    text = (resume_text or "").lower()
    found = {}
    for tech, patterns in aliases.items():
        for pat in patterns:
            if re.search(pat, text, re.I):
                found[tech] = True
                break
    return found


def compute_gap(resume_skills, benchmark_techs):
    """Split benchmark techs into 'have' and 'missing'."""
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
        m["_score"] = (
            m["benchmark_share"]
            * stability_weight.get(m["stability_tier"], 0.4)
        )
    missing.sort(key=lambda x: x["_score"], reverse=True)
    have.sort(key=lambda x: x["benchmark_share"], reverse=True)
    return have, missing


# ============================================================
# Project ideas (reuse from CLI)
# ============================================================
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
# Page layout
# ============================================================
def main():
    artifact = load_benchmark()
    aliases, categories = load_taxonomy()

    # Header
    st.title("🎯 Resume Gap Finder")
    st.caption(
        f"Compare your resume to **{artifact['benchmark_size']} verified "
        f"entry-level software engineering jobs** in India — and find out "
        f"exactly what to learn next."
    )

    # Meta strip
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Jobs in benchmark", artifact["benchmark_size"])
    col2.metric("Companies", artifact["unique_companies"])
    col3.metric("Confirmed entry-level", artifact["confirmed_tier"])
    col4.metric("Role families", len(artifact.get("role_meta", {})))

    st.divider()

    # Input section
    with st.form("resume_form"):
        st.subheader("1. Upload your resume")
        uploaded = st.file_uploader(
            "PDF or plain text",
            type=["pdf", "txt"],
            help="Upload your resume. Nothing is stored — it's parsed in memory only.",
        )

        st.subheader("2. Pick your target role")
        role_options = ["All software roles (overview)"] + sorted(
            artifact.get("role_meta", {}).keys()
        )
        role_choice = st.selectbox(
            "Which kind of role are you targeting?",
            role_options,
            index=0,
            help="Backend, Frontend, Full Stack, Mobile — pick what you want "
                 "to apply to. Different targets → different skill priorities.",
        )

        submitted = st.form_submit_button("Analyze my resume", use_container_width=True)

    # Run analysis
    if submitted:
        if not uploaded:
            st.warning("Please upload a resume first.")
            return

        # Extract text
        if uploaded.type == "application/pdf":
            resume_text = extract_text_from_pdf(uploaded.read())
        else:
            resume_text = uploaded.read().decode("utf-8", errors="ignore")

        if not resume_text.strip() or len(resume_text) < 100:
            st.error(
                "Couldn't extract text from your resume. "
                "If it's a scanned PDF (image-only), try uploading a text version instead."
            )
            return

        resume_skills = extract_skills(resume_text, aliases)

        # Choose benchmark table
        if role_choice.startswith("All software"):
            benchmark_techs = artifact["technologies"]
            denominator = artifact["benchmark_size"]
            scope_label = "all entry-level SDE jobs"
        else:
            benchmark_techs = artifact["role_technologies"][role_choice]
            denominator = artifact["role_meta"][role_choice]["n_jobs"]
            scope_label = f"{role_choice} roles"

        have, missing = compute_gap(resume_skills, benchmark_techs)

        # Show results
        st.divider()
        st.header("Your gap report")
        st.caption(
            f"Comparing against **{denominator} jobs** in the {scope_label} benchmark."
        )

        # Quick stats
        c1, c2, c3 = st.columns(3)
        c1.metric("Skills you have", len(have))
        c2.metric("Skills missing", len(missing))
        top_gap = missing[0]["technology"] if missing else "None — you're covered!"
        c3.metric("Top priority to learn", top_gap)

        # Tabs
        tab1, tab2 = st.tabs(["⚠️ What to learn", "✅ What you have"])

        with tab1:
            if not missing:
                st.success("You have every technology the benchmark cares about. 🎉")
            else:
                st.subheader("Top skills to learn next")
                for i, m in enumerate(missing[:8], 1):
                    pct = m["benchmark_share"] * 100
                    with st.expander(
                        f"{i}. {m['technology']} — required by {pct:.0f}% of jobs",
                        expanded=(i <= 2),
                    ):
                        st.markdown(
                            f"**Priority:** `{m['priority']}` · "
                            f"**Stability:** `{m['stability_tier']}`"
                        )
                        if m["technology"] in PROJECT_IDEAS:
                            st.info(f"💡 **Project idea:** {PROJECT_IDEAS[m['technology']]}")
                        else:
                            st.info(
                                "No project template yet — search "
                                f"\"{m['technology']} beginner project\" on YouTube."
                            )

        with tab2:
            if not have:
                st.info("No benchmark technologies detected in your resume yet.")
            else:
                for h in have[:15]:
                    pct = h["benchmark_share"] * 100
                    st.markdown(
                        f"- **{h['technology']}** — in {pct:.0f}% of jobs "
                        f"({h['priority']} priority)"
                    )

        # How to use
        st.divider()
        st.subheader("How to use this")
        st.markdown(
            """
            1. Pick **2 skills** from your top priorities
            2. Build the suggested project for each — one project per skill
            3. Add both projects to your resume with GitHub links
            4. Come back and re-run this after you've built them

            **The percentages are real.** They come from 232 hand-verified jobs,
            bootstrap-validated so you're not chasing noise. If a skill says
            "36% of jobs" with `high` stability, that's the actual market, not
            one company's quirk.
            """
        )

        # Download button
        report_text = _build_text_report(have, missing, scope_label, denominator)
        st.download_button(
            "📥 Download report as text",
            data=report_text,
            file_name="resume_gap_report.txt",
            mime="text/plain",
        )

    # Privacy note at bottom
    st.divider()
    st.caption(
        "🔒 **Privacy:** Your resume is parsed in memory only. Nothing is stored, "
        "logged, or sent to any third party. Refresh the page to clear everything."
    )
    st.caption(
        f"Benchmark: {artifact['benchmark_size']} jobs · "
        f"{artifact['confirmed_tier']} confirmed · "
        f"{artifact['probable_tier']} probable · "
        f"4 job portals (Naukri, Indeed, Foundit, JobSpy)."
    )


def _build_text_report(have, missing, scope_label, denominator):
    lines = [
        "=" * 60,
        "RESUME GAP REPORT",
        f"Scope: {scope_label} ({denominator} jobs)",
        "=" * 60,
        "",
        f"SKILLS YOU HAVE ({len(have)}):",
    ]
    for h in have[:15]:
        lines.append(f"  • {h['technology']:15s} {h['benchmark_share']*100:.0f}%")
    lines.append("")
    lines.append(f"SKILLS TO LEARN ({len(missing)}):")
    for i, m in enumerate(missing[:8], 1):
        lines.append(
            f"  {i}. {m['technology']:15s} "
            f"{m['benchmark_share']*100:.0f}%  [{m['priority']}]"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    main()
