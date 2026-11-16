# ... (keep all the imports, config, CSS, and load functions the same) ...

# ============================================================
# Logic
# ============================================================
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
    return have, missing

# ... (keep PROJECT_IDEAS the same) ...

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

        # --- NEW UI METRICS ---
        st.divider()
        st.header("Your gap report")
        
        total_relevant = len(have) + len(missing)
        match_rate = (len(have) / total_relevant) * 100 if total_relevant > 0 else 0
        top_gap = missing[0]["technology"] if missing else "None!"

        c1, c2, c3 = st.columns(3)
        c1.metric("Skills matched", len(have))
        c2.metric("Match Rate", f"{match_rate:.0f}%", help="Percentage of the benchmark's key skills found in your resume.")
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
                
                # Only show top 5 by default
                for i, m in enumerate(missing[:5], 1):
                    pct = m["benchmark_share"] * 100
                    with st.expander(f"{i}. {m['technology']} — required by {pct:.0f}% of jobs", expanded=(i == 1)):
                        st.markdown(f"**Priority:** `{m['priority']}` · **Stability:** `{m['stability_tier']}`")
                        if m["technology"] in PROJECT_IDEAS:
                            st.info(f"💡 **Project idea:** {PROJECT_IDEAS[m['technology']]}")
                        else:
                            st.info(f"No project template yet — search \"{m['technology']} beginner project\" on YouTube.")

                # Hide the rest behind an expander
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

        # Footer
        st.divider()
        st.subheader("How to use this")
        st.markdown("""
            1. Pick **2 skills** from your Top 5 priorities
            2. Build the suggested project for each — one project per skill
            3. Add both projects to your resume with GitHub links
            4. Come back and re-run this after you've built them
        """)

        # Download logic
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
