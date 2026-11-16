# PRD: Resume Research Gap Analyser (v2)

**Core Thesis:** To give freshers accurate advice, we cannot rely on LLM
hallucinations or single Job Descriptions. We must build a deterministic,
highly-audited **Market Benchmark Engine** from real job postings, and map
user resumes against that truth.

## 1. Problem Statement

Freshers face the "Experience Paradox". Existing tools optimize for ATS
formatting or mass auto-apply, but they don't tell the user *what to learn*.

> **Decision:** We are pivoting from a "Resume vs. JD matcher" to a
> "Resume vs. Market Aggregate" tool.
> **Why:** Defensibility. Anyone can prompt ChatGPT. Only we will have the
> curated, deduplicated benchmark of the Indian entry-level tech market.

## 2. Architecture & Pipeline Evolution

### Phase 1: Collection & Adapters
- **Foundit V1.3:** Decoupled collection from classification.
- **Indeed V22:** Inline deterministic extraction and 4-tier requirement taxonomy.
- **Naukri V9:** Balanced discovery manifest.

### Phase 2: Stateful Ingestion (DB)
- Migrated from CSVs to a **SQLite Database** (`jobs.db`).
- `content_hash` UNIQUE constraint prevents exact duplicates at the source.
- Scrapers resume where they left off if they crash.

### Phase 3: Cross-Portal Deduplication
- Fuzzy-matching (SequenceMatcher) on job descriptions catches agency spam
  (same job posted on Naukri, Indeed, and Foundit with different IDs).
- Blocking by (company, title) makes it O(n) instead of O(n²).

## 3. Success Metrics
- **Activation:** >80% of users who upload a resume click "Analyze".
- **Actionability:** >50% of users scroll to the bottom of the Gap Report.
- **Trust Signal:** >30% of users click on external learning resources.
- **Retention:** >20% re-analyze after 14 days.

## 4. Out of Scope (v1)
- Auto-Rewriting Resumes.
- Live Job Board Integration.
- B2B College Dashboards.
