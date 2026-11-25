#!/usr/bin/env python3
"""
Streamlit web app — Resume Gap Finder.
"""
import urllib.request
import io
import json
import re
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

# ============================================================
# Google Analytics
# ============================================================
GA_ID = "G-33JG5NZW8J" 

ga_script = f"""
    <script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{dataLayer.push(arguments);}}
      gtag('js', new Date());
      gtag('config', '{GA_ID}', {{ 'send_page_view': true }});
    </script>
"""
components.html(ga_script, height=0, width=0)

# ============================================================
# Config & Custom CSS
# ============================================================
st.set_page_config(
    page_title="Resume Gap Finder — India Entry-Level SDE",
    page_icon="🎯",
    layout="wide",
)

st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    html, body, [class*="css"] { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
    h1 { font-weight: 800; color: #111827; letter-spacing: -0.02em; }
    div[data-testid="stMetric"] {
        background-color: white; border: 1px solid #E5E7EB; border-radius: 12px;
        padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    div[data-testid="stForm"] {
        background-color: white; border: 1px solid #E5E7EB; border-radius: 16px;
        padding: 32px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    div[data-testid="stFormSubmitButton"] button {
        background-color: #4F46E5; color: white; border-radius: 8px;
        font-weight: 600; border: none; padding: 12px 24px; transition: all 0.2s;
    }
    div[data-testid="stFormSubmitButton"] button:hover {
        background-color: #4338CA; box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3);
    }
</style>
""", unsafe_allow_html=True)

ARTIFACT_PATH = Path(__file__).parent / "outputs" / "pipeline" / "16_resume_gap_artifact.json"

# ============================================================
# Load benchmark
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
    except Exception:
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
    
    missing = [m for m in missing if m["benchmark_share"] >= 0.02]
    return have, missing

PROJECT_IDEAS = {
    "JavaScript": "Build a to-do list app with vanilla JS.",
    "Java": "Build a CLI inventory manager using Java + JDBC.",
    "HTML": "Build a responsive portfolio site.",
    "Python": "Build a FastAPI REST API with Redis.",
    "CSS": "Build a 3-page responsive site using only CSS.",
    "REST API": "Build a CRUD REST API with validation.",
    "SQL": "Build a movie-rating database (3+ tables).",
    "React": "Build a weather dashboard with React hooks.",
    "Git": "Fork a repo, make 3 commits, submit a PR.",
    "OOP": "Build a small library system using classes.",
    "Node.js": "Build a real-time chat app with Socket.io.",
    "MySQL": "Build a booking system with normalized schema.",
    "MongoDB": "Build a task manager with MongoDB + Express.",
    "PostgreSQL": "Extend your SQL project to PostgreSQL.",
    "Angular": "Build an admin dashboard with Angular.",
    "Spring": "Build a library API with Spring Boot.",
    "Spring Boot": "Build a payment gateway API.",
    "Docker": "Containerize your FastAPI/Node project.",
    "AWS": "Deploy to AWS EC2 + RDS.",
    "TypeScript": "Migrate a JS project to TypeScript.",
    "Django": "Build a blog with Django + PostgreSQL.",
    "Kotlin": "Build an Android app with Jetpack Compose.",
    "Android": "Build an Android app with auth.",
}

IMPLIED_SKILLS = {
    "GitHub": ["Git"], "GitLab": ["Git"], "React": ["JavaScript"],
    "Angular": ["JavaScript", "TypeScript"], "Vue.js": ["JavaScript"],
    "Next.js": ["JavaScript", "React"], "Node.js": ["JavaScript"],
    "Express.js": ["Node.js"], "Django": ["Python"], "Flask": ["Python"],
    "FastAPI": ["Python"], "Spring": ["Java"], "Spring Boot": ["Java", "Spring"],
    ".NET": ["C#"], "ASP.NET": ["C#", ".NET"],
}

# ============================================================
# UI Layout
# ============================================================
def main():
    artifact = load_benchmark()
    aliases, categories = load_taxonomy()
    
    # Use st.secrets for security
    try:
        WEBHOOK_URL = st.secrets["WEBHOOK_URL"]
    except Exception:
        WEBHOOK_URL = "" 

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
            st.subheader("1. Add your resume")
            
            input_method = st.radio("Choose input method:", ["Upload File", "Paste Text"], horizontal=True)
            
            uploaded = None
            pasted_text = ""
            
            if input_method == "Upload File":
                uploaded = st.file_uploader("PDF or plain text", type=["pdf", "txt"], label_visibility="collapsed")
            else:
                pasted_text = st.text_area("Paste your resume text here:", height=200, label_visibility="collapsed")

            st.subheader("2. Pick your target role")
            role_options = ["All software roles (overview)"] + sorted(
                artifact.get("role_meta", {}).keys()
            )
            role_choice = st.selectbox(
                "Which kind of role are you targeting?",
                role_options,
                index=0,
                label_visibility="collapsed"
            )

            submitted = st.form_submit_button("Analyze my resume", use_container_width=True)

    if submitted:
        resume_text = ""
        
        if input_method == "Upload File":
            if not uploaded:
                st.warning("Please upload a resume first.")
                return
            if uploaded.type == "application/pdf":
                resume_text = extract_text_from_pdf(uploaded.read())
            else:
                resume_text = uploaded.read().decode("utf-8", errors="ignore")
        else:
            if not pasted_text.strip():
                st.warning("Please paste your resume text first.")
                return
            resume_text = pasted_text

        if not resume_text.strip() or len(resume_text) < 100:
            st.error("Couldn't extract enough text. If you uploaded a PDF, it might be an image. Try the 'Paste Text' option instead!")
            return

        # Ping Discord when someone actually uses the tool
        try:
            track_payload = {"content": f"🚀 **Someone just analyzed a resume!** Target Role: {role_choice}"}
            req = urllib.request.Request(
                WEBHOOK_URL, 
                data=json.dumps(track_payload).encode(), 
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
            )
            urllib.request.urlopen(req)
        except Exception:
            pass 

        resume_skills = extract_skills(resume_text, aliases)
        
        implied_added = []
        for skill in list(resume_skills.keys()):
            if skill in IMPLIED_SKILLS:
                for implied_skill in IMPLIED_SKILLS[skill]:
                    if implied_skill not in resume_skills:
                        resume_skills[implied_skill] = True
                        implied_added.append(implied_skill)
                        
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
                st.caption("Focus on these first. Copy the checklist below into Notion or your notes app to track your progress.")
                
                # Initialize the Markdown roadmap
                roadmap_md = f"# My Learning Roadmap\n\nGenerated from the Resume Gap Finder Benchmark ({denominator} jobs).\n\n"
                
                for i, m in enumerate(missing[:5], 1):
                    pct = m["benchmark_share"] * 100
                    
                    # Add the skill to the Markdown roadmap
                    roadmap_md += f"- [ ] **{m['technology']}** (Required by {pct:.0f}% of jobs)\n"
                    
                    with st.expander(f"View project ideas for {m['technology']}"):
                        st.markdown(f"**Priority:** `{m['priority']}` · **Stability:** `{m['stability_tier']}`")
                        if m["technology"] in PROJECT_IDEAS:
                            tech_query = m['technology'].replace(' ', '+')
                            yt_search_url = f"https://www.youtube.com/results?search_query=learn+{tech_query}+real+world+project+for+beginners"
                            
                            st.info(f"💡 **Project idea:** {PROJECT_IDEAS[m['technology']]}")
                            st.markdown(f"▶️ **[Watch a step-by-step YouTube tutorial for this project]({yt_search_url})**")
                            
                            # Add the project to the Markdown roadmap
                            roadmap_md += f"  - *Project:* {PROJECT_IDEAS[m['technology']]}\n"
                        else:
                            st.info(f"No project template yet — search \"{m['technology']} beginner project\" on YouTube.")

                st.write("")
                st.markdown("#### 📋 Copy this checklist to Notion or Notes:")
                
                # Display the text so they can copy-paste it directly from the browser
                st.code(roadmap_md, language="markdown")
                
                st.download_button(
                    label="📥 Download as .md file",
                    data=roadmap_md,
                    file_name="my_learning_roadmap.md",
                    mime="text/markdown"
                )

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

    # ============================================================
    # FEEDBACK SECTION
    # ============================================================
    st.divider()
    st.subheader("Was this helpful?")
    st.markdown("I built this as a side project. Let me know if this report helped you, or if you have ideas to make it better!")
    
    col1, col2 = st.columns([1, 3])
    with col1:
        stars = st.feedback("stars")
    with col2:
        comment = st.text_input("Any other feedback? (Optional)", placeholder="Your feedback here...")
        
    if st.button("Submit Feedback"):
        if stars is None and not comment:
            st.warning("Please leave a rating or a comment first!")
        else:
            rating_str = f"{stars} Stars" if stars is not None else "No rating"
            
            payload = {
                "content": f"**New Feedback for Resume Gap Finder!**\n**Role:** {role_choice if 'role_choice' in locals() else 'None'}\n**Rating:** {rating_str}\n**Comment:** {comment}"
            }
            
            try:
                req = urllib.request.Request(
                    WEBHOOK_URL, 
                    data=json.dumps(payload).encode(), 
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                    }
                )
                urllib.request.urlopen(req)
                st.success("✅ Thank you! Your feedback has been received.")
            except Exception as e:
                st.error(f"Failed to send feedback: {e}")

    st.write("")
    st.caption("🔒 **Privacy:** Your resume is parsed in memory only. Nothing is stored, logged, or sent to any third party.")
    st.caption(f"Benchmark: {artifact['benchmark_size']} jobs · 4 job portals (Naukri, Indeed, Foundit, JobSpy).")

if __name__ == "__main__":
    main()
