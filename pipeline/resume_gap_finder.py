#!/usr/bin/env python3
"""
Resume Gap Finder — the consumer of the 16-stage benchmark pipeline.

Reads: outputs/pipeline/16_resume_gap_artifact.json

Usage:
    # Overall market report
    python3 pipeline/resume_gap_finder.py --resume sample_resume.txt

    # Role-targeted report
    python3 pipeline/resume_gap_finder.py --resume sample_resume.txt --role backend

    # See what roles are available
    python3 pipeline/resume_gap_finder.py --list-roles
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.indeed_taxonomy import TECHNOLOGY_ALIASES, TECH_CATEGORIES

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_PATH = ROOT / "outputs" / "pipeline" / "16_resume_gap_artifact.json"


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
    "OOP": "Build a small library system in your language of choice using classes, inheritance, interfaces. Include UML diagram.",
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
    "GraphQL": "Build a GraphQL API for your existing SQL project. Include queries, mutations, and subscriptions.",
    "React Native": "Build a simple weather app in React Native. Ship to TestFlight / Play Store internal testing.",
    "Flutter": "Build a to-do app in Flutter. Include SQLite storage, state management, and dark mode.",
    "Kotlin": "Build a small Android app with Kotlin + Jetpack Compose. Publish to Play Store internal testing.",
    "Android": "Build an Android app that fetches data from your FastAPI backend. Include auth and offline cache.",
}


def extract_skills_from_resume(resume_text):
    text = (resume_text or "").lower()
    found = {}
    for tech, patterns in TECHNOLOGY_ALIASES.items():
        for pat in patterns:
            m = re.search(pat, text, re.I)
            if m:
                start = max(0, m.start() - 40)
                end = min(len(text), m.end() + 60)
                snippet = re.sub(r"\s+", " ", resume_text[start:end]).strip()
                found[tech] = snippet
                break
    return found


def compute_gap(resume_skills, benchmark_techs):
    have, missing = [], []
    stability_weight = {"high": 1.0, "medium": 0.7, "low": 0.4}

    for tech in benchmark_techs:
        name = tech["technology"]
        entry = {
            "technology": name,
            "job_share": tech.get("job_share", 0),
            "benchmark_share": tech.get("benchmark_share", 0),
            "priority": tech.get("priority", "low"),
            "stability_tier": tech.get("stability_tier", "low"),
            "category": TECH_CATEGORIES.get(name, "Other"),
        }
        if name in resume_skills:
            entry["evidence"] = resume_skills[name]
            have.append(entry)
        else:
            missing.append(entry)

    for m in missing:
        m["_score"] = (m["benchmark_share"] *
                       stability_weight.get(m["stability_tier"], 0.4))
    missing.sort(key=lambda x: x["_score"], reverse=True)
    have.sort(key=lambda x: x["benchmark_share"], reverse=True)
    return have, missing


def resolve_role(user_input, available_roles):
    """Fuzzy-match user's role input to an available family."""
    if not user_input:
        return None
    norm = user_input.lower().replace("-", " ").replace("_", " ").strip()

    # Exact match (case-insensitive)
    for role in available_roles:
        if norm == role.lower():
            return role

    # Substring match
    for role in available_roles:
        role_norm = role.lower().replace("-", " ").replace("_", " ")
        if norm in role_norm or role_norm in norm:
            return role

    # Synonym map
    synonyms = {
        "backend": "Backend", "back end": "Backend",
        "frontend": "Frontend", "front end": "Frontend",
        "full stack": "Full Stack", "fullstack": "Full Stack",
        "mobile": "Mobile", "android": "Mobile", "ios": "Mobile",
        "general": "General Software Development",
        "general software": "General Software Development",
        "software": "General Software Development",
    }
    for syn, role in synonyms.items():
        if syn in norm and role in available_roles:
            return role

    return None


def render_section(title, have, missing, benchmark_size, top_n,
                   sample_warning=""):
    lines = []
    lines.append(title)
    if sample_warning:
        lines.append(f"⚠️  {sample_warning}")
    lines.append("=" * 70)
    lines.append("")

    lines.append(f"✅ YOU HAVE ({len(have)} skills matched):")
    if have:
        for h in have[:10]:
            share = f"{h['benchmark_share'] * 100:.0f}%"
            lines.append(f"   • {h['technology']:15s} {share:>5}  [{h['priority']}]")
    else:
        lines.append("   (none matched)")
    lines.append("")

    lines.append(f"⚠️  YOU'RE MISSING — prioritized ({len(missing)} total, "
                 f"showing top {top_n}):")
    lines.append("")
    for i, m in enumerate(missing[:top_n], 1):
        share = f"{m['benchmark_share'] * 100:.0f}%"
        lines.append(f"   {i}. {m['technology']:15s} {share:>5} of jobs require it")
        lines.append(f"      Priority: {m['priority']:6s}  |  "
                     f"Stability: {m['stability_tier']:6s}  |  "
                     f"Category: {m['category']}")
        if m["technology"] in PROJECT_IDEAS:
            lines.append(f"      💡 Project: {PROJECT_IDEAS[m['technology']]}")
        lines.append("")

    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume", default=None,
                help="Path to resume text file, or '-' for stdin")
    ap.add_argument("--role", default=None,
                    help="Target role family (backend, frontend, full-stack, "
                         "mobile, general). See --list-roles.")
    ap.add_argument("--list-roles", action="store_true",
                    help="Show available role families and exit.")
    ap.add_argument("--top", type=int, default=8,
                    help="Number of missing skills to show per section")
    args = ap.parse_args()

    # --list-roles special case
    if not args.list_roles and not args.resume:
        print("❌ Either --resume or --list-roles is required.")
        return 1
    if args.list_roles:
        with open(ARTIFACT_PATH) as f:
            artifact = json.load(f)
        print("Available role families:")
        print("=" * 70)
        for family, meta in artifact.get("role_meta", {}).items():
            techs = artifact["role_technologies"].get(family, [])[:3]
            top3 = ", ".join(f"{t['technology']} ({t['benchmark_share']*100:.0f}%)"
                            for t in techs)
            print(f"  {family:32s}  n={meta['n_jobs']:3d}  {top3}")
        print()
        print("Use with: --role <name>")
        return 0

    # Load artifact + resume
    with open(ARTIFACT_PATH) as f:
        artifact = json.load(f)

    if args.resume == "-":
        resume_text = sys.stdin.read()
    else:
        with open(args.resume) as f:
            resume_text = f.read()
    if not resume_text.strip():
        print("❌ Empty resume.")
        return 1

    resume_skills = extract_skills_from_resume(resume_text)

    # =========================================================
    # Section 1 — Overall market report
    # =========================================================
    overall_techs = artifact["technologies"]
    overall_size = artifact["benchmark_size"]

    have_o, missing_o = compute_gap(resume_skills, overall_techs)
    lines = []
    lines.extend(render_section(
        "RESUME GAP REPORT — ALL ENTRY-LEVEL SDE JOBS",
        have_o, missing_o, overall_size, args.top))
    lines.append("─" * 70)
    lines.append(f"Benchmark: {overall_size} jobs · "
                 f"{artifact['confirmed_tier']} confirmed · "
                 f"{artifact['probable_tier']} probable · "
                 f"{artifact['unique_companies']} companies")
    lines.append("")

    # =========================================================
    # Section 2 — Role-specific (if requested)
    # =========================================================
    available_roles = list(artifact.get("role_meta", {}).keys())

    if args.role:
        resolved = resolve_role(args.role, available_roles)
        if not resolved:
            lines.append(f"❌ Role '{args.role}' not found in benchmark.")
            lines.append(f"   Available: {', '.join(available_roles)}")
            print("\n".join(lines))
            return 1

        meta = artifact["role_meta"][resolved]
        role_techs = artifact["role_technologies"][resolved]
        n = meta["n_jobs"]
        warning = (f"small sample — {n} jobs" if n < 20 else "")

        have_r, missing_r = compute_gap(resume_skills, role_techs)

        lines.append("")
        lines.extend(render_section(
            f"ROLE-SPECIFIC GAPS — {resolved.upper()}",
            have_r, missing_r, n, args.top,
            sample_warning=warning))
        lines.append("─" * 70)
        lines.append(f"Benchmark: {n} {resolved.lower()}-focused jobs")

    else:
        # No role specified — nudge user toward role-specific reports
        lines.append("─" * 70)
        lines.append("💡 WANT A MORE SPECIFIC REPORT?")
        lines.append("─" * 70)
        lines.append("The overall report above mixes all SDE roles. For a")
        lines.append("targeted report, add --role:")
        lines.append("")
        for family, meta in artifact.get("role_meta", {}).items():
            techs = artifact["role_technologies"].get(family, [])[:2]
            top2 = " · ".join(t["technology"] for t in techs)
            lines.append(f"   --role {family.lower():28s} "
                        f"({meta['n_jobs']} jobs) {top2}")

    # =========================================================
    # Footer — how to use
    # =========================================================
    lines.append("")
    lines.append("─" * 70)
    lines.append("HOW TO USE THIS REPORT")
    lines.append("─" * 70)
    lines.append("1. Pick 2 missing skills from the TOP PRIORITIES list")
    lines.append("2. Build the suggested project for each — one per skill")
    lines.append("3. Add both projects to your resume with links")
    lines.append("4. Re-run this analysis after you've built them")
    lines.append("")
    lines.append("All percentages come from a bootstrap-validated benchmark.")
    lines.append("Stability 'high' means the share is stable across random")
    lines.append("resamples — the technology is a real market signal, not noise.")

    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
