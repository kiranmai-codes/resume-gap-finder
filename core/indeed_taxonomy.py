#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Indeed India — Resume Gap Finder benchmark scraper V22 (DB-integrated)
"""

import asyncio
import os
import random
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

"""Indeed domain taxonomy — pure data + pure classifiers. No scraping."""
import re
import pandas as pd

def clean(x):
    return re.sub(r"\s+", " ", str(x or "")).strip()


def now():
    return __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc).isoformat()

# Add project root so pipeline imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.db import JobDatabase

# ============================================================
# CONFIG
# ============================================================

COUNTRY = "India"
PORTAL = "Indeed"
TARGET_ROLE = "software_engineer"

SEARCH_URLS = [
    "https://in.indeed.com/jobs?q=sde+fresher&l=India&from=searchOnHP&vjk=9495519b08aad2d5",
    "https://in.indeed.com/jobs?q=sde&l=India&sc=0kf%3Aattr%287EQCZ%29%3B&from=searchOnDesktopSerp&vjk=7a577c18954a7b09",
    "https://in.indeed.com/jobs?q=software+developer+fresher&l=India&from=searchOnDesktopSerp%2Cwhatautocomplete%2CwhatautocompleteSourceStandard&vjk=add10afaee68003b",
    "https://in.indeed.com/jobs?q=software+developer&l=India&sc=0kf%3Aattr%287EQCZ%29%3B&from=searchOnDesktopSerp&vjk=e77f827aaf550f04",
    "https://in.indeed.com/jobs?q=Software+Engineer&l=India&sc=0kf%3Aattr%287EQCZ%29%3B&from=searchOnDesktopSerp&vjk=e77f827aaf550f04",
    "https://in.indeed.com/jobs?q=software+engineer+fresher&l=India&from=searchOnDesktopSerp%2Cwhatautocomplete%2CwhatautocompleteSourceStandard&vjk=e77f827aaf550f04",
    "https://in.indeed.com/jobs?q=Graduate+Software+Developer&l=India&from=searchOnDesktopSerp&vjk=e77f827aaf550f04",
    "https://in.indeed.com/jobs?q=Graduate+Software+Developer&l=India&sc=0kf%3Aattr%287EQCZ%29%3B&from=searchOnDesktopSerp&vjk=b2e46de2c73da3ba",
    "https://in.indeed.com/jobs?q=Junior+Software+Developer&l=India&sc=0kf%3Aattr%287EQCZ%29%3B&from=searchOnDesktopSerp&vjk=b2e46de2c73da3ba",
    "https://in.indeed.com/jobs?q=Junior+Software+Developer+fresher&l=India&from=searchOnDesktopSerp&vjk=fc8baa6b27a130a5",
    "https://in.indeed.com/jobs?q=Trainee+Software+Engineer&l=India&from=searchOnDesktopSerp&vjk=7a577c18954a7b09",
    "https://in.indeed.com/jobs?q=Trainee+Software+Engineer&l=India&sc=0kf%3Aattr%287EQCZ%29%3B&from=searchOnDesktopSerp&vjk=b2e46de2c73da3ba",
    "https://in.indeed.com/jobs?q=Java+Developer&l=India&sc=0kf%3Aattr%287EQCZ%29%3B&from=searchOnDesktopSerp&vjk=7a577c18954a7b09",
    "https://in.indeed.com/jobs?q=Java+Developer+fresher&l=India&from=searchOnDesktopSerp&vjk=7663a01171ee7f3b",
    "https://in.indeed.com/jobs?q=Python+Developer+fresher&l=India&from=searchOnDesktopSerp&vjk=7663a01171ee7f3b",
    "https://in.indeed.com/jobs?q=Python+Developer&l=India&sc=0kf%3Aattr%287EQCZ%29%3B&from=searchOnDesktopSerp&vjk=7a577c18954a7b09",
    "https://in.indeed.com/jobs?q=net+developer+fresher&l=India&from=searchOnDesktopSerp%2Cwhatautocomplete%2CwhatautocompleteSourceStandard&vjk=9bd828d640fc3a0b",
    "https://in.indeed.com/jobs?q=net+developer&l=India&sc=0kf%3Aattr%287EQCZ%29%3B&from=searchOnDesktopSerp&vjk=5d86bb131d1534e2",
    "https://in.indeed.com/jobs?q=mern+stack+developer+fresher&l=India&from=searchOnDesktopSerp%2Cwhatautocomplete%2CwhatautocompleteSourceStandard&vjk=7abfa42fef87fadf",
    "https://in.indeed.com/jobs?q=mern+stack+developer&l=India&sc=0kf%3Aattr%287EQCZ%29%3B&from=searchOnDesktopSerp&vjk=c4283c69c96b2cf0",
    "https://in.indeed.com/jobs?q=react+developer+fresher&l=India&from=searchOnDesktopSerp%2Cwhatautocomplete%2CwhatautocompleteSourceStandard&vjk=7abfa42fef87fadf",
    "https://in.indeed.com/jobs?q=react+developer&l=India&sc=0kf%3Aattr%287EQCZ%29%3B&from=searchOnDesktopSerp&vjk=c4283c69c96b2cf0",
    "https://in.indeed.com/jobs?q=Full+Stack+Developer+fresher&l=India&from=searchOnDesktopSerp&vjk=7663a01171ee7f3b",
    "https://in.indeed.com/jobs?q=Full+Stack+Developer&l=India&sc=0kf%3Aattr%287EQCZ%29%3B&from=searchOnDesktopSerp&vjk=fc67b785774cc6a7",
    "https://in.indeed.com/jobs?q=backend+developer+fresher&l=India&from=searchOnDesktopSerp%2Cwhatautocomplete%2CwhatautocompleteSourceStandard&vjk=7663a01171ee7f3b",
    "https://in.indeed.com/jobs?q=backend+developer&l=India&sc=0kf%3Aattr%287EQCZ%29%3B&from=searchOnDesktopSerp&vjk=2f7491780401a6cf",
    "https://in.indeed.com/jobs?q=Frontend+Developer+fresher&l=India&from=searchOnDesktopSerp&vjk=7663a01171ee7f3b",
    "https://in.indeed.com/jobs?q=Frontend+Developer&l=India&sc=0kf%3Aattr%287EQCZ%29%3B&from=searchOnDesktopSerp&vjk=cccb6badd86f6ae9",
    "https://in.indeed.com/jobs?q=Software+Developer+2026&l=India&from=searchOnDesktopSerp&vjk=2f7491780401a6cf",
    "https://in.indeed.com/jobs?q=2026+fresher+software&l=India&from=searchOnDesktopSerp%2Cwhatautocomplete%2CwhatautocompleteSourceStandard&vjk=753028d46b877cfb",
]

MANIFEST_PATH = Path(__file__).with_name("v22_manifest.csv")
OUT_DIR = Path("./indeed_v22_output")
OUT_DIR.mkdir(parents=True, exist_ok=True)
DISCOVERY_PROVENANCE_OUTPUT = OUT_DIR / "indeed_discovery_provenance_v22.csv"
DUPLICATE_AUDIT_OUTPUT = OUT_DIR / "indeed_duplicate_audit_v22.csv"


def load_search_manifest():
    if MANIFEST_PATH.exists():
        df = pd.read_csv(MANIFEST_PATH).fillna("")
        return df.to_dict("records")
    return [
        {"discovery_family": "SDE", "mode": "Fresher Query", "search_url": u}
        for u in SEARCH_URLS
    ]

SEARCH_MANIFEST = load_search_manifest()
SEARCH_URLS = [row["search_url"] for row in SEARCH_MANIFEST]

TARGET_DISCOVERED_JOBS = 500
MAX_DISCOVERY_PAGES_PER_URL = 10
MAX_DETAIL_ATTEMPTS = 500
CHECKPOINT_EVERY = 50

PROFILE_DIR = os.path.expanduser("~/indeed_gap_finder_chrome_profile")
CHROME_BINARY = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CDP_PORT = 9222
BLOCK_RECOVERY_ATTEMPTS = 2

RAW_OUTPUT = OUT_DIR / "indeed_raw_jobs_v22.csv"
CLEAN_OUTPUT = OUT_DIR / "indeed_jobs_clean_v22.csv"
TECH_OUTPUT = OUT_DIR / "indeed_technologies_v22.csv"
TECH_FREQ_OUTPUT = OUT_DIR / "indeed_technology_frequency_v22.csv"
TECH_CONTEXT_FREQ_OUTPUT = OUT_DIR / "indeed_technology_context_frequency_v22.csv"
ROLE_FREQ_OUTPUT = OUT_DIR / "indeed_role_family_frequency_v22.csv"
CAREER_TECH_FREQ_OUTPUT = OUT_DIR / "indeed_career_level_technology_frequency_v22.csv"
AMBIGUOUS_OUTPUT = OUT_DIR / "indeed_manual_review_v22.csv"
STABILITY_OUTPUT = OUT_DIR / "indeed_benchmark_stability_v22.csv"


# ============================================================
# CANONICAL TECHNOLOGY VOCABULARY
# ============================================================

TECHNOLOGY_ALIASES = {
    "Python": [r"\bpython(?:\s*3(?:\.\d+)?)?\b"],
    "Java": [r"\bjava\b"],
    "JavaScript": [r"\bjavascript\b", r"(?<![A-Za-z0-9_.])js(?![A-Za-z0-9_])"],
    "TypeScript": [r"\btypescript\b", r"\bts\b"],
    "C": [r"(?<![A-Za-z0-9+#])C(?![A-Za-z0-9+#])"],
    "C++": [r"\bc\+\+\b", r"\bcpp\b", r"\bc plus plus\b"],
    "C#": [r"\bc#\b", r"\bc-sharp\b", r"\bcsharp\b"],
    "Go": [r"\bgolang\b", r"\bgo\s+(?:programming|language)\b"],
    "Rust": [r"\brust\b"],
    "PHP": [r"\bphp\b"],
    "Ruby": [r"\bruby\b", r"\bruby on rails\b"],
    "VB6": [r"\bvb\s*6(?:\.0)?\b", r"\bvisual basic\s*6(?:\.0)?\b"],
    "HTML": [r"\bhtml5?\b"],
    "CSS": [r"\bcss3?\b"],
    "React": [r"\breact(?:\.js|js)?\b"],
    "Angular": [r"\bangular(?:\.js|js)?\b"],
    "Vue.js": [r"\bvue\.js\b", r"\bvuejs\b"],
    "Next.js": [r"\bnext\.js\b", r"\bnextjs\b"],
    "jQuery": [r"\bjquery\b", r"\bjquery\.js\b"],
    "Bootstrap": [r"\bbootstrap\b"],
    "Tailwind CSS": [r"\btailwind(?:\s+css)?\b"],
    "Sass": [r"\bsass\b", r"\bscss\b"],
    "Node.js": [r"\bnode\.js\b", r"\bnodejs\b"],
    "Express.js": [r"\bexpress\.js\b", r"\bexpressjs\b"],
    "Django": [r"\bdjango\b"],
    "Flask": [r"\bflask\b"],
    "FastAPI": [r"\bfastapi\b"],
    "Spring": [r"\bspring\s+(?:boot|framework)\b", r"\bspringboot\b"],
    "Hibernate": [r"\bhibernate\b"],
    ".NET": [r"(?<![a-zA-Z])\.net\b", r"\bdotnet\b"],
    "ASP.NET": [r"\basp\.?\s*net\b(?!\s+core\b)"],
    "ASP.NET Core": [r"\basp\.?\s*net\s+core\b"],
    "JSP": [r"\bjsp\b", r"\bjava server pages\b"],
    "Servlets": [r"\bservlets?\b"],
    "Odoo": [r"\bodoo\b"],
    "AWS": [r"\baws\b", r"\bamazon web services\b"],
    "Azure": [r"\bazure\b", r"\bmicrosoft azure\b"],
    "Google Cloud": [r"\bgoogle cloud\b", r"\bgcp\b"],
    "Docker": [r"\bdocker\b"],
    "Kubernetes": [r"\bkubernetes\b", r"\bk8s\b"],
    "Jenkins": [r"\bjenkins\b"],
    "Terraform": [r"\bterraform\b"],
    "Ansible": [r"\bansible\b"],
    "GitHub Actions": [r"\bgithub actions\b"],
    "Git": [r"\bgit\b"],
    "GitHub": [r"\bgithub\b"],
    "GitLab": [r"\bgitlab\b"],
    "IIS": [r"\biis\b", r"\binternet information services\b"],
    "Visual Studio": [r"\bvisual studio\b"],
    "SQL": [r"\bsql\b"],
    "PostgreSQL": [r"\bpostgres(?:ql)?\b"],
    "MySQL": [r"\bmysql\b"],
    "Microsoft SQL Server": [r"\bsql server\b", r"\bmssql\b", r"\bmicrosoft sql server\b"],
    "Oracle": [r"\boracle database\b", r"\boracle db\b"],
    "MongoDB": [r"\bmongodb\b", r"\bmongo db\b"],
    "Redis": [r"\bredis\b"],
    "Elasticsearch": [r"\belasticsearch\b", r"\belastic search\b"],
    "MS Access": [r"\bms\s+access\b", r"\bmicrosoft access\b"],
    "REST API": [r"\brest(?:ful)?\s+api(?:s)?\b", r"\brestful web services?\b"],
    "Web API": [r"\bweb\s+api(?:s)?\b"],
    "GraphQL": [r"\bgraphql\b"],
    "Microservices": [r"\bmicroservices?\b"],
    "MVC": [r"\bmvc\b"],
    "OOP": [r"\boop\b", r"\bobject[- ]oriented programming\b"],
    "DSA": [r"\bdsa\b", r"\bdata structures?\s+(?:and|&)\s+algorithms?\b"],
    "SDLC": [r"\bsdlc\b", r"\bsoftware development life cycle\b"],
    "Linux": [r"\blinux\b"],
    "Unix": [r"\bunix\b"],
    "Bash": [r"\bbash\b", r"\bshell scripting\b"],
    "Selenium": [r"\bselenium\b"],
    "Cypress": [r"\bcypress\b"],
    "Playwright": [r"\bplaywright\b"],
    "JUnit": [r"\bjunit\b"],
    "PyTest": [r"\bpytest\b", r"\bpy\.test\b"],
    "TensorFlow": [r"\btensorflow\b"],
    "PyTorch": [r"\bpytorch\b"],
    "Scikit-learn": [r"\bscikit[- ]learn\b", r"\bsklearn\b"],
    "Pandas": [r"\bpandas\b"],
    "NumPy": [r"\bnumpy\b"],
    "OpenCV": [r"\bopencv\b"],
    "LLM": [r"\blarge language models?\b", r"\bllms?\b"],
    "Generative AI": [r"\bgenerative ai\b", r"\bgenai\b"],
    "Machine Learning": [r"\bmachine learning\b"],
    "Deep Learning": [r"\bdeep learning\b"],
    "Prompt Engineering": [r"\bprompt engineering\b"],
    "Power BI": [r"\bpower\s*bi\b"],
    "Tableau": [r"\btableau\b"],
    "Excel": [r"\bmicrosoft excel\b", r"\bexcel\b"],
    "Android": [r"\bandroid\b"],
    "Flutter": [r"\bflutter\b"],
}

TECH_CATEGORIES = {
    "Python": "Programming Language", "Java": "Programming Language",
    "JavaScript": "Programming Language", "TypeScript": "Programming Language",
    "C": "Programming Language", "C++": "Programming Language",
    "C#": "Programming Language", "Go": "Programming Language",
    "Rust": "Programming Language", "PHP": "Programming Language",
    "Ruby": "Programming Language", "VB6": "Programming Language",
    "HTML": "Frontend", "CSS": "Frontend", "React": "Frontend Framework",
    "Angular": "Frontend Framework", "Vue.js": "Frontend Framework",
    "Next.js": "Frontend Framework", "jQuery": "Frontend Library",
    "Bootstrap": "Frontend Framework", "Tailwind CSS": "Frontend Framework",
    "Sass": "Frontend Styling",
    "Node.js": "Backend Runtime", "Express.js": "Backend Framework",
    "Django": "Backend Framework", "Flask": "Backend Framework",
    "FastAPI": "Backend Framework", "Spring": "Backend Framework",
    "Hibernate": "Backend Framework", ".NET": "Backend Framework",
    "ASP.NET": "Backend Framework", "ASP.NET Core": "Backend Framework",
    "JSP": "Backend Technology", "Servlets": "Backend Technology",
    "Odoo": "ERP / Platform",
    "AWS": "Cloud", "Azure": "Cloud", "Google Cloud": "Cloud",
    "Docker": "DevOps / Infrastructure", "Kubernetes": "DevOps / Infrastructure",
    "Jenkins": "DevOps / Infrastructure", "Terraform": "DevOps / Infrastructure",
    "Ansible": "DevOps / Infrastructure", "GitHub Actions": "DevOps / Infrastructure",
    "Git": "Version Control", "GitHub": "Version Control / Collaboration",
    "GitLab": "Version Control / Collaboration", "IIS": "Web Server",
    "Visual Studio": "Development IDE",
    "SQL": "Database / Query Language", "PostgreSQL": "Database",
    "MySQL": "Database", "Microsoft SQL Server": "Database",
    "Oracle": "Database", "MongoDB": "Database", "Redis": "Database / Cache",
    "Elasticsearch": "Database / Search", "MS Access": "Database",
    "REST API": "API / Architecture", "Web API": "API / Architecture",
    "GraphQL": "API / Architecture", "Microservices": "Architecture",
    "MVC": "Architecture / Pattern", "OOP": "Programming Concept",
    "DSA": "Computer Science Fundamentals", "SDLC": "Software Engineering",
    "Linux": "Operating System", "Unix": "Operating System",
    "Bash": "Scripting", "Selenium": "Testing", "Cypress": "Testing",
    "Playwright": "Testing", "JUnit": "Testing", "PyTest": "Testing",
    "TensorFlow": "Machine Learning", "PyTorch": "Machine Learning",
    "Scikit-learn": "Machine Learning", "Pandas": "Data / ML",
    "NumPy": "Data / ML", "OpenCV": "Computer Vision",
    "LLM": "AI", "Generative AI": "AI", "Machine Learning": "AI",
    "Deep Learning": "AI", "Prompt Engineering": "AI",
    "Power BI": "Analytics / BI", "Tableau": "Analytics / BI",
    "Excel": "Analytics / BI", "Android": "Mobile Platform",
    "Flutter": "Mobile Framework",
}

TECHNOLOGY_TYPES = {
    "REST API": "Technical Capability", "Web API": "Technical Capability",
    "Microservices": "Technical Concept", "MVC": "Technical Concept",
    "OOP": "Technical Concept", "DSA": "Technical Concept",
    "SDLC": "Technical Concept", "LLM": "Technical Concept",
    "Generative AI": "Technical Concept", "Machine Learning": "Technical Concept",
    "Deep Learning": "Technical Concept", "Prompt Engineering": "Technical Capability",
}

def technology_type(name):
    return TECHNOLOGY_TYPES.get(name, "Technology")


# ============================================================
# ROLE / CONTEXT TAXONOMY
# ============================================================

ROLE_FAMILIES = [
    "Frontend", "Backend", "Full Stack", "Mobile", "DevOps / Infrastructure",
    "QA / Testing", "Embedded", "General Software Development", "AI / ML",
    "Data Engineering", "Data / Analytics", "Product / APM", "Unclear",
]

CONTEXTS = [
    "Frontend", "Backend", "Database / Data", "AI / ML", "DevOps / Infrastructure",
    "Mobile", "QA / Testing", "Developer Tools", "Embedded",
    "General Software Development", "Analytics / BI", "Unclear",
]

TITLE_ROLE_RULES = [
    (r"\b(?:machine learning|ml|ai)\s+(?:engineer|developer|scientist)\b", "AI / ML"),
    (r"\b(?:data scientist)\b", "Data / Analytics"),
    (r"\b(?:data analyst)\b", "Data / Analytics"),
    (r"\b(?:data engineer)\b", "Data Engineering"),
    (r"\b(?:devops|site reliability|sre|platform)\s+(?:engineer|developer)\b", "DevOps / Infrastructure"),
    (r"\b(?:qa|quality assurance|test|testing|automation)\s+(?:engineer|developer|analyst)\b", "QA / Testing"),
    (r"\b(?:android|ios|mobile)\s+(?:developer|engineer)\b", "Mobile"),
    (r"\b(?:embedded|firmware)\s+(?:developer|engineer)\b", "Embedded"),
    (r"\bfrontend\b|\bfront[- ]end\b", "Frontend"),
    (r"\bbackend\b|\bback[- ]end\b", "Backend"),
    (r"\bfull[- ]stack\b", "Full Stack"),
    (r"\bsoftware\s+(?:engineer|developer)\b", "General Software Development"),
    (r"\bapplication\s+(?:engineer|developer)\b", "General Software Development"),
    (r"\bprogrammer\b", "General Software Development"),
    (r"\bpython developer\b", "Backend"),
    (r"\bjava developer\b", "Backend"),
    (r"\.net developer\b", "Backend"),
]

TECH_CONTEXT_FALLBACK = {
    "HTML": "Frontend", "CSS": "Frontend", "React": "Frontend",
    "Angular": "Frontend", "Vue.js": "Frontend", "Next.js": "Frontend",
    "jQuery": "Frontend", "Bootstrap": "Frontend", "Tailwind CSS": "Frontend",
    "Sass": "Frontend", "Node.js": "Backend", "Express.js": "Backend",
    "Django": "Backend", "Flask": "Backend", "FastAPI": "Backend",
    "Spring": "Backend", "Hibernate": "Backend", ".NET": "Backend",
    "ASP.NET": "Backend", "ASP.NET Core": "Backend", "JSP": "Backend",
    "Servlets": "Backend", "REST API": "Backend", "Web API": "Backend",
    "GraphQL": "Backend", "Microservices": "Backend",
    "PostgreSQL": "Database / Data", "MySQL": "Database / Data",
    "SQL": "Database / Data", "Microsoft SQL Server": "Database / Data",
    "Oracle": "Database / Data", "MongoDB": "Database / Data",
    "Redis": "Database / Data", "Elasticsearch": "Database / Data",
    "MS Access": "Database / Data", "Pandas": "Data / Analytics",
    "NumPy": "Data / Analytics", "Power BI": "Analytics / BI",
    "Tableau": "Analytics / BI", "Excel": "Analytics / BI",
    "TensorFlow": "AI / ML", "PyTorch": "AI / ML",
    "Scikit-learn": "AI / ML", "OpenCV": "AI / ML",
    "LLM": "AI / ML", "Generative AI": "AI / ML",
    "Machine Learning": "AI / ML", "Deep Learning": "AI / ML",
    "Prompt Engineering": "AI / ML",
    "AWS": "DevOps / Infrastructure", "Azure": "DevOps / Infrastructure",
    "Google Cloud": "DevOps / Infrastructure", "Docker": "DevOps / Infrastructure",
    "Kubernetes": "DevOps / Infrastructure", "Jenkins": "DevOps / Infrastructure",
    "Terraform": "DevOps / Infrastructure", "Ansible": "DevOps / Infrastructure",
    "GitHub Actions": "DevOps / Infrastructure",
    "Git": "Developer Tools", "GitHub": "Developer Tools",
    "GitLab": "Developer Tools", "Visual Studio": "Developer Tools",
    "IIS": "DevOps / Infrastructure",
    "Selenium": "QA / Testing", "Cypress": "QA / Testing",
    "Playwright": "QA / Testing", "JUnit": "QA / Testing",
    "PyTest": "QA / Testing",
    "Android": "Mobile", "Flutter": "Mobile",
    "Linux": "General Software Development", "Unix": "General Software Development",
    "Bash": "DevOps / Infrastructure",
}

ROLE_RELEVANT_TITLE_PATTERNS = [
    r"\bsoftware engineers?\b", r"\bsoftware developers?\b",
    r"\bapplication developers?\b", r"\bassociate software engineers?\b",
    r"\bjunior software engineers?\b", r"\bjunior software developers?\b",
    r"\bgraduate software engineers?\b", r"\bfull[- ]stack (?:developers?|engineers?)\b",
    r"\bfrontend (?:developers?|engineers?)\b", r"\bfront[- ]end (?:developers?|engineers?)\b",
    r"\bbackend (?:developers?|engineers?)\b", r"\bback[- ]end (?:developers?|engineers?)\b",
    r"\bweb (?:developers?|engineers?)\b", r"\bpython developers?\b", r"\bjava developers?\b",
    r"\b\.net developers?\b", r"\bmobile (?:developers?|engineers?)\b", r"\bandroid developers?\b",
    r"\bapplication engineers?\b", r"\bsoftware programmers?\b", r"\bprogrammers?\b",
    r"\bsoftware trainee\b", r"\bgraduate engineer trainee\b",
]

ROLE_ADJACENT_TITLE_PATTERNS = [
    r"\bsdet\b", r"\bsoftware development engineer in test\b",
    r"\bqa engineer\b", r"\btest engineer\b", r"\bqa/test\b",
    r"\bdevops engineer\b", r"\bsite reliability engineer\b", r"\bsre\b",
    r"\bplatform engineer\b", r"\bcloud engineer\b", r"\bdata engineer\b",
    r"\bdata scientist\b", r"\bmachine learning engineer\b", r"\bml engineer\b",
    r"\bai engineer\b", r"\bai developer\b", r"\bautomation engineer\b",
    r"\bembedded engineer\b", r"\bfirmware engineer\b",
]

ROLE_IRRELEVANT_TITLE_PATTERNS = [
    r"\bbusiness development\b", r"\bbde\b", r"\bsales\b", r"\bmarketing\b",
    r"\bcustomer success\b", r"\bcustomer support\b", r"\bsupport engineer\b",
    r"\bimplementation specialist\b", r"\bimplementation engineer\b",
    r"\bcnc\b", r"\bvmc\b", r"\bwelder\b", r"\bfabricator\b",
    r"\bturner\b", r"\bmachine operator\b", r"\boperator\b", r"\bsetter\b",
    r"\bmechanic\b", r"\belectrician\b", r"\btechnician\b",
    r"\bproduction\b", r"\bmanufacturing\b", r"\bmaintenance\b",
    r"\bquality inspector\b", r"\baccountant\b", r"\bhr\b",
    r"\bhuman resources\b", r"\bteacher\b", r"\bpharmac(?:y|ist)\b",
    r"\bmedical store\b", r"\breceptionist\b", r"\bchef\b", r"\bcommis\b",
    r"\bvideo editor\b", r"\btruck dispatcher\b", r"\bfield service\b",
]


# ============================================================
# REQUIREMENT RULES
# ============================================================

PREFERRED_DIRECT = re.compile(
    r"\b(?:preferred|preferable|desirable|optional|nice\s+to\s+have|bonus|plus|advantage)\b", re.I,
)

REQUIRED_DIRECT = re.compile(
    r"\b(?:required|mandatory|essential|must(?:\s+have)?|need(?:s)?|"
    r"experience\s+with|proficien(?:t|cy)|strong\s+(?:knowledge|experience|understanding)|"
    r"knowledge\s+of|expertise\s+in|skilled\s+in|hands[- ]on\s+(?:experience|knowledge)|"
    r"basic\s+knowledge|understanding\s+of)\b", re.I,
)

REQUIRED_SECTION = re.compile(
    r"\b(?:required\s+skills?|skills\s+required|requirements?|qualifications?|"
    r"must\s+have|technical\s+skills?|key\s+skills?|what\s+you\s+bring|"
    r"core\s+technolog(?:y|ies))\b", re.I,
)

STACK_DECLARATION = re.compile(
    r"\b(?:tech(?:nology)?\s+stack|technical\s+stack|core\s+technolog(?:y|ies)|"
    r"stack\s*(?:includes?|:)|built\s+(?:using|with)|developed\s+(?:using|with)|"
    r"implemented\s+(?:using|with)|work\s+with)\b", re.I,
)

def sentence_units(text):
    lines = [x.strip() for x in (text or "").splitlines() if x.strip()]
    out = []
    for line in lines:
        out.extend([s.strip() for s in re.split(r"(?<=[.!?])\s+", line) if s.strip()])
    return out


def extract_local_evidence(text, technology):
    patterns = TECHNOLOGY_ALIASES.get(technology, [])
    units = sentence_units(text)
    for unit in units:
        if any(re.search(p, unit, re.I) for p in patterns):
            return unit[:700]
    return ""


def classify_requirement(text, technology):
    units = sentence_units(text)
    best = None

    for i, unit in enumerate(units):
        if not any(re.search(p, unit, re.I) for p in TECHNOLOGY_ALIASES.get(technology, [])):
            continue

        prev_units = units[max(0, i - 3):i]
        next_units = units[i + 1:i + 3]
        local = " ".join(prev_units + [unit] + next_units)

        has_preferred = bool(PREFERRED_DIRECT.search(unit))
        has_required = bool(REQUIRED_DIRECT.search(unit))
        required_section = any(REQUIRED_SECTION.search(x) for x in prev_units[-2:])
        stack_sentence = bool(STACK_DECLARATION.search(unit))

        if has_preferred and not has_required:
            typ = "preferred"; rank = 4
        elif has_required:
            typ = "required"; rank = 5
        elif required_section:
            typ = "required"; rank = 5
        elif stack_sentence:
            typ = "stack_required"; rank = 4
        elif re.search(r"\b(?:using|work\s+with|build|develop|implement|design|"
                       r"built\s+with|developed\s+with)\b", unit, re.I):
            typ = "stack_required"; rank = 3
        else:
            typ = "mentioned"; rank = 1

        candidate = (rank, typ, unit[:700], local[:1400])
        if best is None or candidate[0] > best[0]:
            best = candidate

    if not best:
        return "mentioned", "", "", "low"

    rank, typ, evidence, context = best
    confidence = "high" if typ in {"required", "preferred"} else ("medium" if evidence else "low")
    return typ, evidence, context, confidence


# ============================================================
# ROLE / TECHNOLOGY CONTEXT
# ============================================================

def classify_role_family(job_title, description):
    title = clean(job_title).lower()
    for pattern, family in TITLE_ROLE_RULES:
        if re.search(pattern, title, re.I):
            return family, "title_primary", "high"

    desc = clean(description).lower()
    for pattern, family in TITLE_ROLE_RULES:
        if re.search(pattern, desc[:4000], re.I):
            return family, "local_role_evidence", "medium"

    return "Unclear", "insufficient_context", "low"


def local_context_for_technology(description, technology):
    units = sentence_units(description)
    patterns = TECHNOLOGY_ALIASES.get(technology, [])
    labels = [
        ("Frontend", r"\bfront(?:end)?[- ]?end\s*[:\-]"),
        ("Backend", r"\bback(?:end)?[- ]?end\s*[:\-]"),
        ("Database / Data", r"\b(?:database|data)\s*(?:technologies|stack|layer)?\s*[:\-]"),
        ("AI / ML", r"\b(?:ai|ml|machine learning|deep learning)\s*(?:stack|technologies|tools)?\s*[:\-]"),
        ("DevOps / Infrastructure", r"\b(?:devops|infrastructure|deployment|cloud)\s*(?:stack|technologies|tools)?\s*[:\-]"),
        ("Mobile", r"\b(?:mobile|android|ios)\s*(?:stack|technologies|tools)?\s*[:\-]"),
        ("QA / Testing", r"\b(?:qa|testing|test automation)\s*(?:stack|technologies|tools)?\s*[:\-]"),
        ("Developer Tools", r"\b(?:developer tools?|version control|source control)\s*[:\-]"),
        ("Embedded", r"\b(?:embedded|firmware)\s*(?:stack|technologies|tools)?\s*[:\-]"),
    ]
    for i, unit in enumerate(units):
        if not any(re.search(p, unit, re.I) for p in patterns):
            continue
        for context, label_pattern in labels:
            if re.search(label_pattern, unit, re.I):
                return context, "explicit_local_evidence", unit[:700], "high"
    return "", "", "", ""

def classify_technology_context(job_title, role_family, technology, description):
    title = clean(job_title).lower()
    local_ctx, local_basis, local_evidence, local_conf = local_context_for_technology(description, technology)
    if local_ctx:
        return local_ctx, "title_primary + local_evidence", local_conf, local_evidence

    title_family = role_family
    if title_family == "AI / ML":
        if technology in {"Python", "TensorFlow", "PyTorch", "Scikit-learn", "Pandas", "NumPy", "OpenCV", "LLM", "Generative AI", "Machine Learning", "Deep Learning", "Prompt Engineering"}:
            return "AI / ML", "title_primary", "high", f"Technology {technology} aligns with explicit AI/ML role title."
        if technology in {"Git", "GitHub", "GitLab", "Visual Studio"}:
            return "Developer Tools", "title_primary + technology_semantics", "high", "Developer tool semantics."
        if technology in {"FastAPI", "Flask", "Django", "Node.js", "REST API", "Web API", "GraphQL"}:
            return "Backend", "title_primary + technology_semantics", "medium", "Backend/API technology in an AI/ML role."
        return TECH_CONTEXT_FALLBACK.get(technology, "Unclear"), "title_primary + technology_semantics", "medium", "Fallback technology context within AI/ML role."

    if title_family == "Data / Analytics":
        if technology in {"Python", "Pandas", "NumPy", "SQL", "PostgreSQL", "MySQL", "Microsoft SQL Server", "Oracle", "Power BI", "Tableau", "Excel"}:
            return "Database / Data", "title_primary", "high", f"Technology {technology} aligns with explicit data/analytics role title."
        if technology in {"Git", "GitHub", "GitLab"}:
            return "Developer Tools", "title_primary + technology_semantics", "high", "Developer tool semantics."
        return TECH_CONTEXT_FALLBACK.get(technology, "Unclear"), "title_primary + technology_semantics", "medium", "Fallback technology context within data role."

    if title_family == "Backend":
        if technology in {"HTML", "CSS", "React", "Angular", "Vue.js", "Next.js", "Bootstrap", "Tailwind CSS", "jQuery"}:
            return "Frontend", "title_primary + technology_semantics", "medium", "Frontend technology remains frontend even in a backend-oriented job."
        if technology in {"Git", "GitHub", "GitLab", "Visual Studio"}:
            return "Developer Tools", "title_primary + technology_semantics", "high", "Developer tool semantics."
        return TECH_CONTEXT_FALLBACK.get(technology, "Backend"), "title_primary + technology_semantics", "medium", "Backend role plus technology semantics."

    if title_family == "Frontend":
        if technology in {"Git", "GitHub", "GitLab", "Visual Studio"}:
            return "Developer Tools", "title_primary + technology_semantics", "high", "Developer tool semantics."
        return TECH_CONTEXT_FALLBACK.get(technology, "Frontend"), "title_primary + technology_semantics", "medium", "Frontend role plus technology semantics."

    if title_family == "Full Stack":
        if technology in {"HTML", "CSS", "React", "Angular", "Vue.js", "Next.js", "Bootstrap", "Tailwind CSS", "jQuery"}:
            return "Frontend", "title_primary + technology_semantics", "high", "Frontend technology in a full-stack role."
        if technology in {"Node.js", "Express.js", "Django", "Flask", "FastAPI", "Spring", ".NET", "ASP.NET", "ASP.NET Core", "REST API", "Web API", "GraphQL", "Microservices"}:
            return "Backend", "title_primary + technology_semantics", "high", "Backend technology in a full-stack role."
        if technology in {"SQL", "PostgreSQL", "MySQL", "Microsoft SQL Server", "Oracle", "MongoDB", "Redis", "Elasticsearch", "MS Access"}:
            return "Database / Data", "title_primary + technology_semantics", "high", "Database technology in a full-stack role."
        if technology in {"Docker", "Kubernetes", "AWS", "Azure", "Google Cloud", "Jenkins", "Terraform", "Ansible"}:
            return "DevOps / Infrastructure", "title_primary + technology_semantics", "high", "Infrastructure technology in a full-stack role."
        if technology in {"Git", "GitHub", "GitLab", "Visual Studio"}:
            return "Developer Tools", "title_primary + technology_semantics", "high", "Developer tool in a full-stack role."
        if technology in {"Python", "Java", "C#", "C++", "C", "Go", "PHP", "Ruby", "TypeScript", "JavaScript"}:
            return "Full Stack", "title_primary", "medium", "General programming language in a full-stack role; no local evidence forcing a sub-context."
        return TECH_CONTEXT_FALLBACK.get(technology, "Unclear"), "title_primary + technology_semantics", "medium", "Fallback context in a full-stack role."

    if title_family == "QA / Testing":
        if technology in {"Selenium", "Cypress", "Playwright", "JUnit", "PyTest"}:
            return "QA / Testing", "title_primary", "high", "Testing technology in a QA/test role."
        if technology in {"Git", "GitHub", "GitLab"}:
            return "Developer Tools", "title_primary + technology_semantics", "high", "Developer tool semantics."
        return TECH_CONTEXT_FALLBACK.get(technology, "Unclear"), "title_primary + technology_semantics", "medium", "Fallback context in a QA role."

    if title_family == "DevOps / Infrastructure":
        if technology in {"Git", "GitHub", "GitLab"}:
            return "Developer Tools", "title_primary + technology_semantics", "high", "Developer tool semantics."
        if technology in {"Python", "JavaScript", "Go", "Bash"}:
            return "DevOps / Infrastructure", "title_primary", "high", "Programming/scripting language in explicit DevOps role."
        return TECH_CONTEXT_FALLBACK.get(technology, "DevOps / Infrastructure"), "title_primary + technology_semantics", "medium", "DevOps role plus technology semantics."

    if title_family == "Mobile":
        if technology in {"Android", "Flutter"}:
            return "Mobile", "title_primary", "high", "Mobile technology in explicit mobile role."
        return TECH_CONTEXT_FALLBACK.get(technology, "Mobile"), "title_primary + technology_semantics", "medium", "Fallback context in mobile role."

    if title_family == "Embedded":
        return "Embedded", "title_primary", "high", "Explicit embedded/firmware role title."

    if title_family == "General Software Development":
        if technology in {"Git", "GitHub", "GitLab", "Visual Studio"}:
            return "Developer Tools", "title_primary + technology_semantics", "high", "Developer tool semantics."
        return TECH_CONTEXT_FALLBACK.get(technology, "General Software Development"), "title_primary + technology_semantics", "medium", "General software-development role plus technology semantics."

    return TECH_CONTEXT_FALLBACK.get(technology, "Unclear"), "technology_semantics", "low", "No stronger title/local evidence."


# ============================================================
# ENTRY LEVEL / ROLE RELEVANCE
# ============================================================

ENTRY_POSITIVE = [
    r"\bfresher(?:s)?\b", r"\bfresh\s+graduates?\b", r"\bfinal[- ]year\s+(?:students?|candidates?)\b",
    r"\bentry[- ]level\b", r"\bnew grad(?:uate)?s?\b", r"\brecent graduate\b",
    r"\bgraduate trainee\b", r"\bcampus hire\b", r"\bno experience(?: required| needed)?\b",
    r"\bstraight out of college\b", r"\bcandidates? straight out of college\b",
    r"\b202[5-9]\s+graduates?\b", r"\b20[3-9]\d\s+graduates?\b", r"\b0\s*(?:-|–|to)\s*[1-9]\d*\s+years?\b",
    r"\b0\s*years?\b",
]

ENTRY_NEGATIVE = [
    r"\bsenior\b", r"\blead\b", r"\bstaff\b", r"\bprincipal\b",
    r"\bmanager\b", r"\bdirector\b", r"\barchitect\b",
]

ENTRY_DISQUALIFYING_EXPERIENCE = [
    r"\b[1-9]\d*\s*\+\s*years?\b", r"\b[1-9]\d*\s*(?:-|–|to)\s*[1-9]\d*\s+years?\b",
    r"\b(?:minimum|at least)\s*[1-9]\d*\s*years?\b",
]

CAREER_LEVEL_RULES = [
    ("executive", [r"\bchief\b", r"\bvice president\b", r"\bvp\b", r"\bavp\b"]),
    ("manager", [r"\bengineering manager\b", r"\bsoftware engineering manager\b", r"\bproduct manager\b", r"\bpeople manager\b", r"\bmanager\b"]),
    ("principal_staff", [r"\bprincipal\b", r"\bstaff engineer\b", r"\bdistinguished engineer\b", r"\bfellow engineer\b"]),
    ("lead", [r"\btechnical lead\b", r"\btech lead\b", r"\bteam lead\b", r"\blead engineer\b", r"\blead developer\b", r"\blead software\b", r"\blead\b"]),
    ("senior_level", [r"\bsenior\b", r"\bsr\.?\b"]),
    ("early_career", [r"\bjunior\b", r"\bjr\.?\b", r"\bassociate\b", r"\btrainee\b", r"\bfresher\b", r"\bgraduate\b", r"\bnew grad(?:uate)?\b", r"\bentry[- ]level\b"]),
]

EXPERIENCE_RANGE_PATTERNS = [
    re.compile(r"\b(\d+)\s*(?:-|–|to)\s*(\d+)\s*years?\b", re.I),
    re.compile(r"\b(\d+)\s*\+\s*years?\b", re.I),
    re.compile(r"\b(?:minimum|at least)\s*(\d+)\s*years?\b", re.I),
]


def extract_experience_years(text):
    mins, maxs = [], []
    for m in EXPERIENCE_RANGE_PATTERNS[0].finditer(text or ""):
        mins.append(int(m.group(1))); maxs.append(int(m.group(2)))
    for pat in EXPERIENCE_RANGE_PATTERNS[1:]:
        for m in pat.finditer(text or ""):
            mins.append(int(m.group(1))); maxs.append(int(m.group(1)))
    return (min(mins) if mins else None, max(maxs) if maxs else None)


def classify_career_level(job_title, description, search_card_text):
    title = clean(str(job_title or "")).lower()
    text = " ".join([str(job_title or ""), str(description or ""), str(search_card_text or "")]).lower()
    exp_min, exp_max = extract_experience_years(text)

    for level, patterns in CAREER_LEVEL_RULES:
        if any(re.search(p, title, re.I) for p in patterns):
            return level, "title_signal", "high", f"Title contains a {level.replace('_', ' ')} signal.", exp_min, exp_max

    if exp_min is not None:
        if exp_min >= 10:
            return "executive", "experience_requirement", "medium", f"Minimum experience is {exp_min}+ years.", exp_min, exp_max
        if exp_min >= 6:
            return "senior_level", "experience_requirement", "high", f"Minimum experience is {exp_min}+ years.", exp_min, exp_max
        if exp_min >= 3:
            return "mid_level", "experience_requirement", "high", f"Minimum experience is {exp_min}+ years.", exp_min, exp_max
        return "early_career", "experience_requirement", "medium", f"Experience starts at {exp_min} years.", exp_min, exp_max

    if re.search(r"\b(?:engineer|developer|software engineer|software developer)\s*(?:ii|2)\b", title, re.I):
        return "mid_level", "title_signal", "medium", "Level II title signal; organization-specific leveling may vary.", exp_min, exp_max

    return "ambiguous", "insufficient_signal", "low", "No decisive career-level signal.", exp_min, exp_max


def classify_entry_level(job_title, description, search_card_text):
    title = clean(job_title or "").lower()
    desc = clean(description or "").lower()
    text = " ".join([title, desc])

    if any(re.search(p, title, re.I) for p in ENTRY_NEGATIVE):
        return "not_entry_level", "Senior/lead/principal/management title signal"

    zero_start_matches = list(re.finditer(r"\b0\s*(?:-|–|to)\s*[1-9]\d*\s+years?\b", text, re.I))
    text_without_zero_ranges = text
    for m in reversed(zero_start_matches):
        text_without_zero_ranges = text_without_zero_ranges[:m.start()] + " " + text_without_zero_ranges[m.end():]

    for p in ENTRY_DISQUALIFYING_EXPERIENCE + [r"\b[1-9]\d*\s+years?\b"]:
        if re.search(p, text_without_zero_ranges, re.I):
            return "not_entry_level", "Experience requirement starts above zero"

    if any(re.search(p, text, re.I) for p in ENTRY_POSITIVE):
        return "confirmed_entry_level", "Posting explicitly supports zero-experience/fresher entry"

    return "ambiguous", "No explicit zero-experience/fresher evidence in title or description"


def classify_role_relevance(job_title, description, search_card_text):
    title = clean(job_title).lower()

    if any(re.search(p, title, re.I) for p in ROLE_IRRELEVANT_TITLE_PATTERNS):
        return "target_role_irrelevant", "Explicitly unrelated occupation in title"

    if any(re.search(p, title, re.I) for p in ROLE_ADJACENT_TITLE_PATTERNS):
        return "target_role_adjacent", "Adjacent technical occupation in title"

    if any(re.search(p, title, re.I) for p in ROLE_RELEVANT_TITLE_PATTERNS):
        return "target_role_relevant", "Software-development occupation in title"

    text = " ".join([title, description or "", search_card_text or ""]).lower()
    software_signals = sum(bool(re.search(p, text, re.I)) for p in [
        r"\bsoftware development\b", r"\bsoftware engineers?\b", r"\bsoftware developers?\b",
        r"\bapplication development\b", r"\bweb development\b", r"\bprogramming\b",
        r"\bdevelop and maintain\b", r"\bdevelop applications\b",
    ])
    technical_signals = sum(bool(re.search(p, text, re.I)) for p in [
        r"\b(?:python|java|javascript|typescript|c\+\+|c#|\.net|react|angular|node(?:\.js)?|sql|html|css|git|api|database)\b",
    ])

    if software_signals >= 2 and technical_signals >= 1:
        return "target_role_relevant", "Multiple software-development signals plus technical evidence"

    return "target_role_adjacent", "Title does not clearly match target role"


# ============================================================
# TEXT CLEANING / EXTRACTION
# ============================================================

BOILERPLATE_PREFIXES = [
    "posted:", "type:", "location:", "how to apply:", "job type:", "salary:",
]

BOILERPLATE_EXACT = {
    "indeed", "apply on indeed", "how to apply", "full job description",
    "job description", "job details and requirements", "about the job",
    "report job", "report this job",
}

BOILERPLATE_END = [
    "is there a problem with this job?", "report job", "report this job",
    "browse jobs", "browse companies", "career advice", "work at indeed",
    "guidelines for safe job search", "© 2026 indeed",
]


def clean_description_for_extraction(description):
    lines = [re.sub(r"[ \t]+", " ", x).strip() for x in (description or "").replace("\r", "\n").split("\n")]
    lines = [x for x in lines if x]
    kept = []
    for line in lines:
        low = line.lower().strip()
        if any(low.startswith(p) for p in BOILERPLATE_PREFIXES): continue
        if low in BOILERPLATE_EXACT: continue
        if any(low == m or low.startswith(m) for m in BOILERPLATE_END): break
        kept.append(line)
    return "\n".join(kept).strip()


def extract_description_from_body(body):
    if not body: return ""
    raw = body.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", x).strip() for x in raw.split("\n")]
    lines = [x for x in lines if x]
    markers = ["full job description", "job description", "job details and requirements", "about the job"]
    start = -1; marker = ""
    for i, line in enumerate(lines):
        low = line.lower()
        for m in markers:
            if m in low: start = i; marker = m; break
        if start >= 0: break
    if start < 0: return ""
    remainder = lines[start][len(marker):].strip(" :-")
    desc = []
    if remainder: desc.append(remainder)
    desc.extend(lines[start + 1:])
    end_markers = ["is there a problem with this job?", "report job", "report this job", "career advice", "browse jobs", "browse companies", "work at indeed", "countries", "help", "esg at indeed", "guidelines for safe job search", "© 2026 indeed"]
    kept = []
    for line in desc:
        low = line.lower()
        if any(low == m or low.startswith(m) for m in end_markers): break
        kept.append(line)
    candidate = "\n".join(kept).strip()
    if len(candidate) < 150: return ""
    return candidate


PROMOTIONAL_PATTERNS = [
    r"^career(?:s)? at\b", r"^benefits of working", r"^why you should join",
    r"^why you should apply", r"^apply for .* roles", r"^apply today",
    r"^join our team", r"^we would love to hear from you",
    r"^our (?:current )?openings\b", r"^openings (?:include|across|for)\b",
    r"^roles (?:include|available|open)\b",
    r"^opportunities (?:include|available|across)\b",
    r"^other (?:openings|roles|opportunities)\b",
]


def is_extraction_relevant_line(line):
    low = clean(line).lower()
    if not low: return False
    if any(re.search(p, low, re.I) for p in PROMOTIONAL_PATTERNS): return False
    if (re.search(r"\b(?:salary|offer|market trends?|skill[- ]wise)\b", low, re.I)
        and re.search(r"\b(?:indicative|aligned|actual offer|depends on|current indian market|business requirement)\b", low, re.I)):
        return False
    if re.search(r"\b(?:required|requirements?|skills?|knowledge|experience|proficien|"
        r"familiar|mandatory|must have|key skills|technical skills|core technology|"
        r"technologies|responsibilities|develop|build|implement|using|work with|"
        r"hands[- ]on|stack|built with|database|frontend|backend|testing|deployment)\b", low, re.I):
        return True
    if len(low) <= 220 and re.search(r"(?:/|,|\||;)", low):
        return True
    return False


# ============================================================
# TECHNOLOGY EXTRACTION
# ============================================================

def technologies_from_description(description, job_title, role_family):
    rows = []
    relevant_lines = []
    normalized_title = re.sub(r"\s+", " ", clean(job_title).lower()).strip()
    for line in (description or "").splitlines():
        if normalized_title and re.sub(r"\s+", " ", clean(line).lower()).strip() == normalized_title: continue
        if is_extraction_relevant_line(line): relevant_lines.append(line)
    extraction_text = "\n".join(relevant_lines)
    if not extraction_text: return rows

    for technology, patterns in TECHNOLOGY_ALIASES.items():
        if not any(re.search(p, extraction_text, re.I) for p in patterns): continue
        req_type, evidence, evidence_context, confidence = classify_requirement(extraction_text, technology)
        context, basis, context_confidence, context_evidence = classify_technology_context(job_title, role_family, technology, description)
        rows.append({
            "technology": technology,
            "technology_normalized": technology,
            "technology_category": TECH_CATEGORIES.get(technology, "Other"),
            "technology_type": technology_type(technology),
            "requirement_type": req_type,
            "technology_confidence": confidence,
            "matched_pattern": next(p for p in patterns if re.search(p, extraction_text, re.I)),
            "evidence": evidence,
            "evidence_context": evidence_context,
            "role_family": role_family,
            "technology_context": context,
            "context_basis": basis,
            "context_confidence": context_confidence,
            "context_evidence": context_evidence,
        })
    return rows


# ============================================================
# BROWSER HELPERS
# ============================================================

def clean(x):
    return re.sub(r"\s+", " ", str(x or "")).strip()


def now():
    return datetime.now(timezone.utc).isoformat()


def fake_id(jk):
    if not jk or not re.fullmatch(r"[a-z0-9]{16}", jk.lower()): return True
    known = {"abcdef0123456789", "0123456789abcdef", "1234567890abcdef", "fedcba9876543210", "9876543210fedcba", "a1b2c3d4e5f67890", "0f1e2d3c4b5a6978", "cdef0123456789ab"}
    if jk.lower() in known: return True
    return False


def jk_from_href(href):
    m = re.search(r"[?&]jk=([A-Za-z0-9]{16})", href or "")
    return m.group(1) if m else ""


def job_url(jk):
    return f"https://in.indeed.com/viewjob?jk={jk}"


async def txt(locator):
    try:
        if await locator.count(): return clean(await locator.first.inner_text(timeout=2500))
    except Exception: pass
    return ""


async def wait_for_search_access(page, max_wait_seconds=300):
    interval = 5
    checks = max(1, max_wait_seconds // interval)
    login_signals = ["sign in to continue", "log in to continue", "please sign in", "please log in", "sign in to view", "log in to view"]
    block_signals = ["verify you are human", "captcha", "unusual traffic", "security check", "additional verification required"]

    for check in range(checks + 1):
        try:
            job_card_count = await page.locator("a[data-jk]").count()
            generic_jk_count = await page.locator("[data-jk]").count()
            if job_card_count > 0 or generic_jk_count > 0:
                print(f"✓ Indeed job results accessible ({max(job_card_count, generic_jk_count)} job cards detected).")
                return "accessible"
            body = clean(await page.locator("body").inner_text(timeout=5000))
            low = body.lower()
            if any(signal in low for signal in block_signals):
                print("⚠ Indeed verification/anti-bot page detected.")
                return "verification"
            if any(signal in low for signal in login_signals):
                if check == 0: print("⚠ Indeed is showing a login-related page. If prompted, log in manually in Chrome.")
                if check < checks:
                    await asyncio.sleep(interval); continue
                return "login_timeout"
            if check < checks:
                if check == 0: print("Waiting for Indeed job results to become available...")
                await asyncio.sleep(interval); continue
            return "no_results"
        except Exception as e:
            if check < checks:
                await asyncio.sleep(interval); continue
            print(f"Could not verify Indeed search access: {e}")
            return "error"


def normalize_for_key(value):
    value = str(value or "").lower()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[^a-z0-9+#. ]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def canonical_job_url(url, job_id=""):
    if job_id: return job_url(job_id)
    return re.sub(r"[?&](?:from|vjk|jk|advn|tracking|trk)=[^&]+", "", str(url or ""))


def discovery_search_metadata(search_url):
    from urllib.parse import parse_qs, urlparse
    qs = parse_qs(urlparse(search_url).query)
    q = qs.get("q", [""])[0]
    mode = "fresher_filter" if "attr(7EQCZ)" in search_url else "keyword_query"
    return q, mode


def merge_discovery_provenance(existing, incoming):
    for field in ["discovery_family", "discovery_mode", "search_url"]:
        vals = []
        for raw in [existing.get(field, ""), incoming.get(field, "")]:
            vals.extend([x.strip() for x in str(raw or "").split(" || ") if x.strip()])
        existing[field] = " || ".join(dict.fromkeys(vals))
    existing["discovery_count"] = int(existing.get("discovery_count", 1) or 1) + 1
    return existing


def content_fingerprint(company, title, description):
    parts = [normalize_for_key(company), normalize_for_key(title), normalize_for_key(description)]
    return "|".join(parts)


def deduplicate_clean_jobs(clean_df):
    if clean_df.empty: return clean_df, pd.DataFrame()
    df = clean_df.copy()
    df["canonical_job_url"] = df.apply(lambda r: canonical_job_url(r.get("job_url", ""), str(r.get("job_id", ""))), axis=1)
    df["content_fingerprint"] = df.apply(lambda r: content_fingerprint(r.get("company_name", ""), r.get("job_title", ""), r.get("description", "")), axis=1)

    duplicate_rows = []
    kept = []
    fp_to_index = {}
    for _, row in df.iterrows():
        fp = row["content_fingerprint"]
        if fp and fp in fp_to_index:
            keep_i = fp_to_index[fp]
            duplicate_rows.append({
                "kept_job_id": kept[keep_i]["job_id"], "duplicate_job_id": row["job_id"],
                "duplicate_type": "content_fingerprint", "kept_job_title": kept[keep_i]["job_title"],
                "duplicate_job_title": row["job_title"], "kept_company": kept[keep_i]["company_name"],
                "duplicate_company": row["company_name"], "kept_content_fingerprint": fp,
            })
            kept[keep_i]["duplicate_job_ids"] = (kept[keep_i].get("duplicate_job_ids", "") + " || " + str(row["job_id"])).strip(" ||")
            kept[keep_i]["duplicate_count"] = int(kept[keep_i].get("duplicate_count", 0) or 0) + 1
            kept[keep_i]["discovery_family"] = " || ".join(dict.fromkeys([x.strip() for x in (str(kept[keep_i].get("discovery_family", "")) + " || " + str(row.get("discovery_family", ""))).split(" || ") if x.strip()]))
            kept[keep_i]["discovery_mode"] = " || ".join(dict.fromkeys([x.strip() for x in (str(kept[keep_i].get("discovery_mode", "")) + " || " + str(row.get("discovery_mode", ""))).split(" || ") if x.strip()]))
            kept[keep_i]["search_url"] = " || ".join(dict.fromkeys([x.strip() for x in (str(kept[keep_i].get("search_url", "")) + " || " + str(row.get("search_url", ""))).split(" || ") if x.strip()]))
        else:
            item = row.to_dict()
            item["duplicate_job_ids"] = ""
            item["duplicate_count"] = 0
            fp_to_index[fp] = len(kept)
            kept.append(item)
    return pd.DataFrame(kept), pd.DataFrame(duplicate_rows)


async def collect_search_jobs(page):
    jobs = {}
    anchors = await page.locator("a[data-jk]").all()
    for a in anchors:
        try:
            jk = clean(await a.get_attribute("data-jk")) or jk_from_href(await a.get_attribute("href"))
            title = clean(await a.inner_text())
            if fake_id(jk) or not title: continue
            if title.lower() in {"date", "1", "2", "3"}: continue
            card = a.locator("xpath=ancestor::*[self::li or self::article][1]")
            company = location = salary = card_text = ""
            if await card.count():
                company = await txt(card.locator("[data-testid='company-name'], .companyName, [class*='companyName']"))
                location = await txt(card.locator("[data-testid='text-location'], .companyLocation, [class*='companyLocation']"))
                salary = await txt(card.locator("[data-testid='attribute_snippet_testid'], .salary-snippet-container, [class*='salary-snippet']"))
                card_text = await txt(card)
            jobs[jk] = {"job_id": jk, "job_url": job_url(jk), "job_title": title, "company_name": company, "location": location, "salary": salary, "search_card_text": card_text, "source": PORTAL}
        except Exception: continue
    return list(jobs.values())


async def scrape_detail(page, job):
    result = {
        **job, "description": "", "clean_description": "", "raw_text": "", "final_url": "",
        "scrape_status": "error", "scrape_error": "", "entry_level_status": "", "entry_level_reason": "",
        "career_level": "", "career_level_source": "", "career_level_confidence": "",
        "career_level_reason": "", "experience_min_years": "", "experience_max_years": "",
        "role_relevance": "", "role_relevance_reason": "", "role_family": "",
        "role_family_source": "", "role_family_confidence": "", "scraped_at": now(),
    }
    try:
        last_error = ""
        navigated = False
        for attempt in range(1, 4):
            try:
                response = await page.goto(job["job_url"], wait_until="domcontentloaded", timeout=45000)
                status = response.status if response else None
                print(f"  HTTP: {status if status is not None else 'unknown'}")
                if status == 403:
                    result["scrape_status"] = "blocked"; result["scrape_error"] = "Indeed/Cloudflare returned HTTP 403"; return result
                navigated = True; break
            except Exception as e:
                last_error = f"{type(e).__name__}: {str(e)[:500]}"
                print(f"  Navigation attempt {attempt}/3 failed: {last_error}")
                try: await page.goto("about:blank", wait_until="commit", timeout=10000)
                except Exception: pass
                await asyncio.sleep(2 + attempt * 2)
        if not navigated:
            result["scrape_error"] = f"Navigation failed after 3 attempts: {last_error}"; return result

        await asyncio.sleep(random.uniform(3, 5))
        result["final_url"] = page.url

        body_raw = await page.locator("body").inner_text(timeout=10000)
        body = clean(body_raw); low = body.lower()

        if any(x in low for x in ["verify you are human", "captcha", "unusual traffic", "security check", "additional verification required"]):
            result["scrape_status"] = "blocked"; result["scrape_error"] = "Indeed verification/CAPTCHA page"; return result

        if any(x in low for x in ["this job has expired", "job has expired", "this job is no longer available", "we can't find this page", "we can’t find this page", "page not found", "job not found"]):
            result["scrape_status"] = "unavailable"; result["scrape_error"] = "Job unavailable/expired"; return result

        candidates = []
        for selector in ["#jobDescriptionText", "[data-testid='jobsearch-JobComponent-description']", ".jobsearch-jobDescriptionText", "[class*='jobDescriptionText']"]:
            try:
                loc = page.locator(selector)
                if await loc.count():
                    value = clean(await loc.first.inner_text(timeout=2500))
                    if value: candidates.append(value)
            except Exception: pass

        description = ""
        for candidate in candidates:
            if len(candidate) >= 150 and candidate.lower() not in {"full job description", "job description", "about the job"}:
                description = candidate; break

        if not description: description = extract_description_from_body(body_raw)

        title = ""
        for selector in ["h1", "[data-testid='jobsearch-JobComponent-title']", "[class*='jobsearch-JobInfoHeader-title']"]:
            title = await txt(page.locator(selector))
            if title: break

        company = await txt(page.locator("[data-testid='inlineHeader-companyName'], [data-testid='company-name'], [class*='jobsearch-InlineCompanyRating']"))
        location = await txt(page.locator("[data-testid='inlineHeader-companyLocation'], [data-testid='text-location']"))

        if title: result["job_title"] = title
        if company: result["company_name"] = company
        if location: result["location"] = location

        result["description"] = description
        result["clean_description"] = clean_description_for_extraction(description)
        result["entry_level_status"], result["entry_level_reason"] = classify_entry_level(result["job_title"], result["clean_description"], result["search_card_text"])
        (result["career_level"], result["career_level_source"], result["career_level_confidence"], result["career_level_reason"], result["experience_min_years"], result["experience_max_years"]) = classify_career_level(result["job_title"], result["clean_description"], result["search_card_text"])
        result["role_relevance"], result["role_relevance_reason"] = classify_role_relevance(result["job_title"], result["clean_description"], result["search_card_text"])
        (result["role_family"], result["role_family_source"], result["role_family_confidence"]) = classify_role_family(result["job_title"], result["clean_description"])
        result["raw_text"] = body

        if description: result["scrape_status"] = "success"
        elif len(body) > 1000:
            result["scrape_status"] = "partial"; result["scrape_error"] = "Page loaded but description could not be isolated"
        else:
            result["scrape_status"] = "empty"; result["scrape_error"] = "Very little usable page text"

    except PlaywrightTimeoutError as e:
        result["scrape_error"] = f"Timeout: {str(e)[:300]}"
    except Exception as e:
        result["scrape_error"] = f"{type(e).__name__}: {str(e)[:500]}"
    return result


# ============================================================
# SAVE / BENCHMARK
# ============================================================

def build_outputs(jobs):
    raw_df = pd.DataFrame(jobs)
    raw_df.to_csv(RAW_OUTPUT, index=False, encoding="utf-8-sig")

    clean_cols = [
        "job_id", "job_url", "job_title", "company_name", "location", "salary",
        "description", "clean_description", "entry_level_status", "entry_level_reason",
        "career_level", "career_level_source", "career_level_confidence",
        "career_level_reason", "experience_min_years", "experience_max_years",
        "role_relevance", "role_relevance_reason", "role_family", "role_family_source",
        "role_family_confidence", "benchmark_eligible", "scrape_status", "source",
        "scraped_at", "discovery_family", "discovery_mode", "search_url", "search_query",
        "search_filter", "discovery_count", "canonical_job_url", "duplicate_job_ids", "duplicate_count",
    ]

    clean_df = raw_df[[c for c in clean_cols if c in raw_df.columns]].copy() if len(raw_df) else pd.DataFrame(columns=clean_cols)

    if len(clean_df):
        clean_df = clean_df[(clean_df["scrape_status"] == "success") & (clean_df["description"].fillna("").str.len() >= 150)].copy()
        clean_df, duplicate_audit = deduplicate_clean_jobs(clean_df)
        duplicate_audit.to_csv(DUPLICATE_AUDIT_OUTPUT, index=False, encoding="utf-8-sig")
        clean_df["benchmark_eligible"] = (clean_df["entry_level_status"].eq("confirmed_entry_level") & clean_df["role_relevance"].eq("target_role_relevant"))

    clean_df.to_csv(CLEAN_OUTPUT, index=False, encoding="utf-8-sig")

    ambiguous_df = clean_df[(clean_df["entry_level_status"] == "ambiguous") | (clean_df["role_relevance"] != "target_role_relevant")].copy()
    ambiguous_df.to_csv(AMBIGUOUS_OUTPUT, index=False, encoding="utf-8-sig")

    tech_rows = []
    for job in jobs:
        if job.get("scrape_status") != "success": continue
        desc = job.get("clean_description", "") or ""
        if len(desc) < 150: continue
        if job.get("role_relevance") == "target_role_irrelevant": continue
        rows = technologies_from_description(desc, job.get("job_title", ""), job.get("role_family", "Unclear"))
        for row in rows:
            tech_rows.append({
                "job_id": job.get("job_id", ""), "job_title": job.get("job_title", ""),
                "company_name": job.get("company_name", ""), **row, "source": PORTAL,
                "role_relevance": job.get("role_relevance", ""),
                "entry_level_status": job.get("entry_level_status", ""),
                "career_level": job.get("career_level", ""),
                "career_level_confidence": job.get("career_level_confidence", ""),
                "benchmark_eligible": bool(job.get("entry_level_status") == "confirmed_entry_level" and job.get("role_relevance") == "target_role_relevant"),
            })

    tech_cols = [
        "job_id", "job_title", "company_name", "technology", "technology_normalized",
        "technology_category", "technology_type", "requirement_type", "technology_confidence",
        "matched_pattern", "evidence", "evidence_context", "role_family", "technology_context",
        "context_basis", "context_confidence", "context_evidence", "source", "role_relevance",
        "entry_level_status", "career_level", "career_level_confidence", "benchmark_eligible",
    ]

    tech_df = pd.DataFrame(tech_rows, columns=tech_cols)
    if len(tech_df):
        rank = {"mentioned": 1, "preferred": 2, "stack_required": 3, "required": 4}
        tech_df["_rank"] = tech_df["requirement_type"].map(rank).fillna(0)
        tech_df = (tech_df.sort_values(["job_id", "technology_normalized", "_rank"], ascending=[True, True, False])
                   .drop_duplicates(["job_id", "technology_normalized"], keep="first").drop(columns=["_rank"]))
    tech_df.to_csv(TECH_OUTPUT, index=False, encoding="utf-8-sig")

    eligible_jobs = set(clean_df.loc[clean_df["benchmark_eligible"], "job_id"].astype(str)) if len(clean_df) else set()
    benchmark = tech_df[tech_df["job_id"].astype(str).isin(eligible_jobs)].copy() if len(tech_df) else tech_df.copy()
    denominator = max(len(eligible_jobs), 1)

    if len(benchmark):
        freq = benchmark.groupby("technology_normalized").agg(
            job_count=("job_id", "nunique"),
            total_mentions=("technology_normalized", "count"),
            required_job_count=("requirement_type", lambda s: s.isin(["required", "stack_required"]).sum()),
            explicit_required_job_count=("requirement_type", lambda s: (s == "required").sum()),
            stack_required_job_count=("requirement_type", lambda s: (s == "stack_required").sum()),
            preferred_job_count=("requirement_type", lambda s: (s == "preferred").sum()),
        ).reset_index()
        freq["job_share"] = freq["job_count"] / denominator
        freq["required_share"] = freq["required_job_count"] / denominator
        freq["preferred_share"] = freq["preferred_job_count"] / denominator
        freq["priority"] = freq["required_share"].apply(lambda x: ("high" if x >= 0.30 else ("medium" if x >= 0.15 else "low")))
        
        type_map = benchmark.groupby("technology_normalized")["technology_type"].first().reset_index()
        category_map = benchmark.groupby("technology_normalized")["technology_category"].first().reset_index()
        context_map = benchmark.groupby(["technology_normalized", "technology_context"]).agg(
            context_job_count=("job_id", "nunique"),
            context_required_job_count=("requirement_type", lambda s: s.isin(["required", "stack_required"]).sum()),
        ).reset_index()
        context_map["context_job_share"] = context_map["context_job_count"] / denominator
        confidence_map = benchmark.groupby("technology_normalized")["technology_confidence"].apply(
            lambda s: ("high" if (s == "high").mean() >= 0.70 else ("medium" if s.isin(["high", "medium"]).mean() >= 0.70 else "low"))
        ).reset_index(name="confidence")

        freq = freq.merge(type_map, on="technology_normalized", how="left").merge(category_map, on="technology_normalized", how="left").merge(confidence_map, on="technology_normalized", how="left")
        freq = freq.sort_values(["required_share", "job_share", "job_count"], ascending=False)
        context_map = context_map.sort_values(["technology_normalized", "context_job_count"], ascending=[True, False])

        eligible_jobs_df = clean_df[clean_df["benchmark_eligible"]].copy() if len(clean_df) else pd.DataFrame()
        role_freq = eligible_jobs_df.groupby("role_family").agg(job_count=("job_id", "nunique")).reset_index() if len(eligible_jobs_df) else pd.DataFrame()
        if len(role_freq):
            role_freq["job_share"] = role_freq["job_count"] / denominator
            role_freq = role_freq.sort_values("job_count", ascending=False)

        if len(benchmark):
            assert benchmark["job_id"].nunique() <= denominator
            assert not benchmark["role_relevance"].isin(["target_role_adjacent", "target_role_irrelevant"]).any()
            assert benchmark["entry_level_status"].eq("confirmed_entry_level").all()
        if len(role_freq):
            assert role_freq["job_count"].sum() == len(eligible_jobs)
    else:
        freq = pd.DataFrame(); context_map = pd.DataFrame(); role_freq = pd.DataFrame()

    freq.to_csv(TECH_FREQ_OUTPUT, index=False, encoding="utf-8-sig")
    context_map.to_csv(TECH_CONTEXT_FREQ_OUTPUT, index=False, encoding="utf-8-sig")
    role_freq.to_csv(ROLE_FREQ_OUTPUT, index=False, encoding="utf-8-sig")

    if len(tech_df):
        career_tech = tech_df[tech_df["career_level"].notna() & (tech_df["career_level"].astype(str) != "")].copy()
        if len(career_tech):
            career_level_denoms = career_tech.groupby("career_level")["job_id"].nunique().to_dict()
            career_tech_freq = career_tech.groupby(["career_level", "technology_normalized"]).agg(
                job_count=("job_id", "nunique"),
                required_job_count=("requirement_type", lambda s: s.isin(["required", "stack_required"]).sum()),
                preferred_job_count=("requirement_type", lambda s: (s == "preferred").sum()),
            ).reset_index()
            career_tech_freq["job_share"] = career_tech_freq.apply(lambda r: r["job_count"] / max(career_level_denoms.get(r["career_level"], 1), 1), axis=1)
            career_tech_freq["required_share"] = career_tech_freq.apply(lambda r: r["required_job_count"] / max(career_level_denoms.get(r["career_level"], 1), 1), axis=1)
            career_tech_freq = career_tech_freq.sort_values(["career_level", "required_share", "job_share"], ascending=[True, False, False])
        else: career_tech_freq = pd.DataFrame()
    else: career_tech_freq = pd.DataFrame()
    career_tech_freq.to_csv(CAREER_TECH_FREQ_OUTPUT, index=False, encoding="utf-8-sig")

    if len(clean_df):
        prov_cols = [c for c in ["job_id", "job_title", "company_name", "discovery_family", "discovery_mode", "search_url", "search_query", "search_filter", "discovery_count"] if c in clean_df.columns]
        clean_df[prov_cols].to_csv(DISCOVERY_PROVENANCE_OUTPUT, index=False, encoding="utf-8-sig")

    return {
        "discovered": len(jobs), "clean_jobs": len(clean_df), "benchmark_jobs": len(eligible_jobs),
        "career_level_jobs": int(clean_df["career_level"].notna().sum()) if len(clean_df) and "career_level" in clean_df.columns else 0,
        "technology_rows": len(tech_df), "benchmark_technology_rows": len(benchmark),
    }


# ============================================================
# MAIN
# ============================================================

async def main():
    print("\n" + "=" * 72)
    print("INDEED INDIA — RESUME GAP FINDER SCRAPER V22 (DB-INTEGRATED)")
    print("=" * 72)

    # --- DB init ---
    db_path = Path(__file__).resolve().parent.parent / "jobs.db"
    db = JobDatabase(str(db_path))
    print(f"💾 DB: {db_path} (existing rows: {db.count()})")
    db_inserted = 0
    db_skipped = 0
    # ---------------

    jobs = []
    seen_ids = set()

    async with async_playwright() as pw:
        print(f"Chrome profile: {PROFILE_DIR}")
        os.makedirs(PROFILE_DIR, exist_ok=True)

        chrome = subprocess.Popen(
            [CHROME_BINARY, f"--user-data-dir={PROFILE_DIR}", f"--remote-debugging-port={CDP_PORT}",
             "--no-first-run", "--no-default-browser-check", "--disable-popup-blocking", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

        browser = None
        try:
            for _ in range(30):
                try:
                    browser = await pw.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}")
                    break
                except Exception: await asyncio.sleep(1)

            if browser is None: raise RuntimeError("Could not connect to Chrome over CDP on port 9222.")
            if not browser.contexts: raise RuntimeError("Chrome connected, but no browser context was exposed.")

            context = browser.contexts[0]
            pages = context.pages
            page = pages[0] if pages else await context.new_page()

            # STAGE 1: DISCOVERY
            print("\n========== STAGE 1: DISCOVERY ==========")
            for search_index, manifest_row in enumerate(SEARCH_MANIFEST, 1):
                search_url = manifest_row["search_url"]
                discovery_family = manifest_row.get("discovery_family", "")
                discovery_mode = manifest_row.get("mode", "")
                if len(seen_ids) >= TARGET_DISCOVERED_JOBS: break

                print(f"\n=== Discovery source {search_index}/{len(SEARCH_URLS)} ===\nURL: {search_url}")
                await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(random.uniform(4, 7))

                access_state = await wait_for_search_access(page, max_wait_seconds=300)
                if access_state == "verification":
                    print("\nComplete the normal Indeed verification manually in the opened Chrome window.\nThen press ENTER here to re-check the search results.\n")
                    try: input("Press ENTER after verification...")
                    except (EOFError, KeyboardInterrupt): print("Stopping safely and preserving progress."); return
                    access_state = await wait_for_search_access(page, max_wait_seconds=60)
                if access_state in {"login_timeout", "no_results", "error"}:
                    print(f"\n⚠ Search source unavailable ({access_state}); moving to next source.")
                    continue

                for page_number in range(1, MAX_DISCOVERY_PAGES_PER_URL + 1):
                    if len(seen_ids) >= TARGET_DISCOVERED_JOBS: break
                    print(f"\n--- Discovery page {page_number} ---")
                    for _ in range(5):
                        await page.mouse.wheel(0, random.randint(700, 1200))
                        await asyncio.sleep(random.uniform(0.8, 1.5))

                    found = await collect_search_jobs(page)
                    print(f"Job cards found: {len(found)}")
                    new_count = 0
                    for job in found:
                        if job["job_id"] not in seen_ids:
                            job["discovery_source"] = f"search_{search_index}"
                            job["discovery_family"] = discovery_family
                            job["discovery_mode"] = discovery_mode
                            job["search_url"] = search_url
                            job["search_query"] = re.search(r"[?&]q=([^&]+)", search_url).group(1) if re.search(r"[?&]q=([^&]+)", search_url) else ""
                            job["search_filter"] = "fresher_entry_level_attribute" if "attr(" in search_url else "keyword_query"
                            job["discovery_count"] = 1
                            seen_ids.add(job["job_id"])
                            jobs.append(job)
                            new_count += 1
                            if len(seen_ids) >= TARGET_DISCOVERED_JOBS: break
                        else:
                            existing = next((x for x in jobs if x["job_id"] == job["job_id"]), None)
                            if existing is not None:
                                merge_discovery_provenance(existing, {"discovery_family": discovery_family, "discovery_mode": discovery_mode, "search_url": search_url})

                    print(f"New unique jobs: {new_count} | Total discovered: {len(seen_ids)}")
                    if len(seen_ids) >= TARGET_DISCOVERED_JOBS: break

                    next_button = None
                    for selector in ["[aria-label='Next Page']", "a[aria-label='Next Page']", "button[aria-label='Next Page']", "a[data-testid='pagination-page-next']"]:
                        try:
                            loc = page.locator(selector)
                            if await loc.count() and await loc.last.is_visible():
                                next_button = loc.last; break
                        except Exception: pass
                    if not next_button:
                        print("No next-page button found. Ending this discovery source."); break
                    try:
                        await next_button.click()
                        await asyncio.sleep(random.uniform(4, 7))
                    except Exception as e:
                        print(f"Could not move to next page: {e}"); break

            print(f"\nDiscovery complete: {len(seen_ids)} unique jobs collected.")

            # STAGE 2: DETAIL EXTRACTION
            print("\n========== STAGE 2: DETAIL EXTRACTION ==========")
            print(f"Discovered: {len(jobs)}")
            results = []
            detail_page = await context.new_page()

            for i, job in enumerate(jobs[:MAX_DETAIL_ATTEMPTS], 1):
                print(f"\n[{i}/{min(MAX_DETAIL_ATTEMPTS, len(jobs))}] {job['job_title']}")
                result = await scrape_detail(detail_page, job)

                if result["scrape_status"] == "blocked":
                    print("\n⚠ Verification/block detected.\nComplete any normal verification manually in Chrome.\nThis scraper does not bypass CAPTCHA/Cloudflare.")
                    results.append(result); build_outputs(results)
                    recovered = False
                    for attempt in range(1, BLOCK_RECOVERY_ATTEMPTS + 1):
                        try: input(f"Press ENTER after verification (retry {attempt}/{BLOCK_RECOVERY_ATTEMPTS})...")
                        except (EOFError, KeyboardInterrupt): print("Stopping safely and preserving progress."); break
                        await asyncio.sleep(2)
                        retry = await scrape_detail(detail_page, job)
                        if retry["scrape_status"] != "blocked":
                            results[-1] = retry; recovered = True; build_outputs(results); print("✓ Recovered."); break
                        results[-1] = retry; build_outputs(results)
                    if not recovered:
                        print("Stopping because the session remains blocked."); break
                    result = results[-1]
                else:
                    results.append(result)

                    # --- DB insert ---
                    if result["scrape_status"] == "success" and len(result.get("description", "")) >= 150:
                        inserted = db.insert_job({
                            'source_portal': 'Indeed',
                            'source_job_id': result.get('job_id', ''),
                            'job_title': result.get('job_title', ''),
                            'company_name': result.get('company_name', ''),
                            'location': result.get('location', ''),
                            'description': result.get('description', ''),
                            'discovery_family': result.get('discovery_family', ''),
                        })
                        if inserted: db_inserted += 1
                        else: db_skipped += 1
                    # ----------------

                    build_outputs(results)

                print(f"Status={result['scrape_status']} | Entry={result.get('entry_level_status')} | Role={result.get('role_relevance')} | Family={result.get('role_family')} | Description={len(result.get('description', ''))} chars")
                if i % CHECKPOINT_EVERY == 0:
                    summary = build_outputs(results)
                    print(f"\nCHECKPOINT: benchmark-eligible={summary['benchmark_jobs']} | tech rows={summary['technology_rows']}")
                await asyncio.sleep(random.uniform(3, 6))

            summary = build_outputs(results)
            print("\n" + "=" * 72)
            print("V22 FINAL SUMMARY")
            print("=" * 72)
            print(f"Discovered jobs:       {summary['discovered']}")
            print(f"Clean jobs:            {summary['clean_jobs']}")
            print(f"Benchmark-eligible:    {summary['benchmark_jobs']}")
            print(f"Career-level jobs:     {summary.get('career_level_jobs', 0)}")
            print(f"Technology rows:       {summary['technology_rows']}")
            print(f"Benchmark tech rows:   {summary['benchmark_technology_rows']}")
            print(f"DB inserted:           {db_inserted}")
            print(f"DB skipped (dup):      {db_skipped}")
            print(f"Output directory:      {OUT_DIR.resolve()}")
            print("\nFiles:")
            for path in [RAW_OUTPUT, CLEAN_OUTPUT, TECH_OUTPUT, TECH_FREQ_OUTPUT, TECH_CONTEXT_FREQ_OUTPUT, ROLE_FREQ_OUTPUT, CAREER_TECH_FREQ_OUTPUT, AMBIGUOUS_OUTPUT]:
                print(f"  - {path}")
            try: await detail_page.close()
            except Exception: pass

        finally:
            try: db.close()
            except Exception: pass
            try: await browser.close()
            except Exception: pass
            try: chrome.terminate(); chrome.wait(timeout=10)
            except Exception: pass


if __name__ == "__main__":
    asyncio.run(main())

