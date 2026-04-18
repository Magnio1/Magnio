# JobRadar — Feature Overview

## What it is

JobRadar is an AI-powered job intelligence system built into Magnio. It automatically scrapes job postings from multiple sources, scores each one against your specific profile using Claude, and surfaces a ranked triage dashboard where you can review, pursue, or bypass roles — with a full AI Advisor chat per job.

---

## Pipeline

Running the pipeline is a single button click ("Run Pipeline"). Under the hood it's a three-stage sequence that takes 2–4 minutes end-to-end.

### Stage 1 — Scrape

Four job sources are scraped in parallel and written to Firestore `jobs_raw` with `status: pending`:

| Source | Label | How |
|--------|-------|-----|
| YC Work at a Startup | `YC` | Public HTML + JSON extraction from ycombinator.com/jobs |
| Greenhouse | `GH` | Public job board API, no auth needed |
| Lever | `LV` | Public Lever board HTML + job detail pages |
| Ashby | `AH` | Public Ashby posting API (`api.ashbyhq.com`) |
| Workable | `WK` | Public apply API (`apply.workable.com`) |

Each source has two lanes:
- **Watchlist** — companies you explicitly track (high signal)
- **Discovery** — a broader startup list for net-new finds

The default Greenhouse discovery set is intentionally bounded. It now includes a small healthtech slice as well, so roles from companies like Komodo Health can surface without turning the run into a global Greenhouse crawl.

Duplicate roles (same company + title seen before) are deduplicated before scoring so Claude never re-scores a job it already evaluated.

### Stage 2 — Score

Every `pending` job gets scored by **Claude Sonnet 4.6** in parallel (up to 8 concurrent workers). The scoring prompt includes:

- Your full profile context — loaded from `content/chat/*.json` knowledge chunks tagged `fit`, `proof`, `operations`, or `agentic`
- The full job description (capped at 6,000 characters)
- A hard-coded list of **red-flag patterns** specific to your career goals (configurator roles, no-AI-scope, body-shop models, pure ML research, etc.)

Claude returns structured JSON written to `jobs_enriched`:

| Field | Description |
|-------|-------------|
| `fit_score` | 0–100 integer |
| `summary` | 2–3 sentence honest fit assessment |
| `red_flags` | Specific flags detected in this JD |
| `strengths` | Specific matches between you and the role |
| `positioning_note` | How to frame Actus/Magnio/CIC for this specific role |
| `outreach_draft` | Personalized 2–3 sentence cold-outreach opening |
| `recommendation` | `pursue` / `review` / `bypass` |

**Scoring rubric:**

| Score | Signal |
|-------|--------|
| 85–100 | Exceptional — agentic systems, production delivery, measurable impact |
| 70–84 | Strong — most criteria met, minor gaps |
| 55–69 | Mixed — worth a look if pipeline is thin |
| 40–54 | Weak — significant misalignment |
| 0–39 | Bypass — configurator, no AI scope, or clear deal-breaker |

### Stage 3 — Rank & Shortlist

Top N jobs are ranked (`pursue` first, then `review`, each group sorted by score descending) and marked `shortlisted: true` in Firestore. The run metadata is logged to `pipeline_runs`.

---

## Dashboard

### Header stats bar

Three live counters update instantly as you triage:

- **Pursue / Review** — AI recommendation counts (how many roles Claude flagged at each tier)
- **Pursuing** — your personal count of roles you've decided to pursue (increments when you click the Pursue button)

### Job cards (left panel)

Each card shows:
- Source badge (`YC` / `GH` / `LV` / `AH`) and collection lane (`Watchlist` / `Discovery`)
- Fit score badge (color-coded: emerald ≥85, blue ≥70, amber ≥55, orange ≥40, red below)
- AI recommendation badge
- Location + remote flag
- 2-line summary
- Up to 2 red flags inline (with overflow count)
- **Pursue** / **Bypass** action buttons + direct link to the original posting

Status changes (Pursue → Bypass → Undo) are persisted to the API immediately.

### AI Advisor chat (right panel)

Selecting any job opens a full streaming chat grounded in that specific role's data. The advisor knows:

- The full job description
- Your fit score and the reasoning behind it
- All identified red flags and strengths
- Your positioning note and outreach draft for that role

**Suggested prompts:**
- *Why did this score the way it did?*
- *What are my biggest risks here?*
- *Rewrite the outreach for this role*
- *Which story should I lead with?*

Responses stream in real time and render full markdown — headers, bullet lists, bold text, inline code.

---

## Data model

```
jobs_raw          ← scraped job, status: pending → scored → approved / bypassed
jobs_enriched     ← Claude output keyed by job_id
pipeline_runs     ← run metadata per execution
```

---

## Key design decisions

- **Profile context is personal** — the scorer loads your actual knowledge chunks, not a generic resume. This is why fit scores feel accurate rather than keyword-matched.
- **Red flags are explicit** — not inferred by Claude on the fly. They're hard-coded patterns based on past misses (configurator roles, no agentic scope, etc.) so the model can't hallucinate them away.
- **Deduplication is key** — the same role posted across multiple sources or re-scraped on subsequent runs won't inflate your queue or waste scoring tokens.
- **Watchlist vs Discovery lanes** — lets you separate high-signal companies you already care about from net-new discoveries, so you can filter your triage accordingly.
