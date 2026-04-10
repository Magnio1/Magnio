# Magnio

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![Cloud Run](https://img.shields.io/badge/Cloud%20Run-deployed-4285F4?logo=googlecloud&logoColor=white)
![Firebase](https://img.shields.io/badge/Firebase-Hosting-FFCA28?logo=firebase&logoColor=black)

**Live:** [magnio.io](https://magnio.io)

Magnio is a small-business automation platform that combines **agentic AI chat** with a complete **lead qualification and intake workflow**. It moves leads from first contact to booked calls with minimal manual work — built on FastAPI, React, and Google Cloud.

### What makes this different

Most AI chat demos call one model and return the result. Magnio runs a **multi-model arena** — 3 LLMs execute in parallel, a judge model synthesizes the best response, and model selection is driven by **benchmark rankings that update without redeploying**. The advisor path uses **hybrid RAG** (keyword expansion + semantic similarity) over a structured knowledge base instead of naive vector search. On the lead side, the entire pipeline from contact form to booked call runs autonomously with human-in-the-loop guardrails only where they matter.

---

## Table of Contents

- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Magnio Chat](#magnio-chat)
- [Lead Automation & Intake](#lead-automation--intake)
- [API Reference](#api-reference)
- [Environment Variables](#environment-variables)
- [Deployment](#deployment)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Firebase Hosting                         │
│                     React + Vite Frontend                       │
│         ┌──────────┐  ┌──────────┐  ┌──────────────┐            │
│         │  /chat   │  │  /#admin │  │ Contact Form │            │
│         └────┬─────┘  └────┬─────┘  └──────┬───────┘            │
└──────────────┼─────────────┼───────────────┼────────────────────┘
               │             │               │
        ┌──────▼─────────────▼───────────────▼──────┐
        │              Cloud Run (FastAPI)          │
        │                                           │
        │  ┌─────────-┐  ┌────────┐  ┌───────────┐  │
        │  │  Arena   │  │Advisor │  │   Leads   │  │
        │  │ 3 models │  │  RAG   │  │  Pipeline │  │
        │  │   +judge │  │        │  │           │  │
        │  └────┬─────┘  └───┬────┘  └─────┬─────┘  │
        └───────┼────────────┼─────────────┼───────-┘
                │            │             │
     ┌──────────▼──-┐  ┌─────▼─────┐  ┌────▼────────-──┐
     │  OpenRouter  │  │ Vertex AI │  │ Firebase RTDB  │
     │  (parallel   │  │ (optional │  │ (leads, state) │
     │   LLM calls) │  │  provider)│  │                │
     └──────────────┘  └───────────┘  └────────────────┘
                                             │
     ┌───────────────┐  ┌───────────┐  ┌─────▼─────┐
     │   Firestore   │  │   Slack   │  │  Cal.com  │
     │  (analytics,  │  │  (alerts) │  │ (bookings)│
     │  evaluations) │  │           │  │           │
     └───────────────┘  └───────────┘  └───────────┘
```

---

## Tech Stack

| Layer        | Technology                                           |
|--------------|------------------------------------------------------|
| Frontend     | React 18, TypeScript, Vite, Tailwind CSS 4           |
| Backend      | FastAPI, Uvicorn, Pydantic                           |
| Database     | Firebase RTDB (leads/workflow), Firestore (analytics)|
| AI           | OpenRouter (multi-model arena), Vertex AI (optional) |
| Hosting      | Firebase Hosting (frontend), Cloud Run (backend)     |
| Secrets      | Google Secret Manager                                |
| Email        | Resend                                               |
| Scheduling   | Cal.com (webhooks)                                   |
| Notifications| Slack (webhooks)                                     |

---

## Project Structure

```
magnio/
├── src/                        # React frontend
│   ├── chat/                   #   Chat UI (Arena + Advisor)
│   ├── components/             #   Landing page, admin panel, intake form
│   ├── App.tsx                 #   Router
│   └── main.tsx                #   Entry point
├── api/                        # FastAPI backend
│   ├── main.py                 #   App setup & middleware
│   ├── routes_chat.py          #   Chat endpoints
│   ├── routes_leads.py         #   Lead & intake endpoints
│   ├── openrouter_client.py    #   OpenRouter multi-model client
│   ├── vertex_ai_client.py     #   Vertex AI client
│   ├── firebase_client.py      #   Firebase Admin SDK init
│   ├── magnio_knowledge.py     #   Hybrid RAG: keyword expansion + semantic similarity search
│   ├── chat_analytics.py       #   Dual-backend eval logging (SQLite local / Firestore prod)
│   └── model_rankings.py       #   Benchmark ranking storage
├── content/chat/               # Advisor knowledge base (JSON)
├── data/                       # Runtime data (rankings, SQLite)
├── scripts/                    # Dev & benchmark utilities
│   ├── dev-all.sh              #   Combined local dev runner
│   └── benchmark_openrouter_models.py
├── docs/                       # Deployment & ops guides
├── Dockerfile                  # Backend container
├── firebase.json               # Firebase Hosting config
└── vite.config.js              # Vite + dev proxy config
```

---

## Getting Started

### Prerequisites

- **Node.js** >= 18
- **Python** >= 3.11
- **OpenRouter API key** ([openrouter.ai](https://openrouter.ai))
- **Firebase project** (for leads/analytics — optional for chat-only dev)

### 1. Clone and install

```bash
git clone https://github.com/your-username/magnio.git
cd magnio

# Frontend
npm install

# Backend
python -m venv .venv
source .venv/bin/activate
pip install -r api/requirements.txt
```

### 2. Configure environment

```bash
cp api/.env.example api/.env
# Edit api/.env with your keys (at minimum, set MAGNIO_OPENROUTER_API_KEY)
```

### 3. Run locally

**Option A — run everything together:**

```bash
npm run dev:all    # Frontend (5173) + Backend (8000) + ngrok tunnel
```

**Option B — run separately:**

```bash
# Terminal 1: Frontend
npm run dev

# Terminal 2: Backend
source .venv/bin/activate
uvicorn api.main:app --reload --port 8000
```

### 4. Open the app

- Landing page: `http://localhost:5173`
- Chat Arena & Advisor: `http://localhost:5173/chat`
- Admin panel: `http://localhost:5173/#admin`

---

## Magnio Chat

`/chat` is the agentic decision surface with two modes:

### Arena

Classifies the prompt by topic, picks 3 ranked models from OpenRouter, runs them in parallel, and synthesizes the best response with a judge model.

- Models are selected per-category from benchmark rankings
- Falls back to OpenRouter's live category list, then to a curated default pool
- Judge model synthesizes the final answer from all candidate outputs

### Advisor

Runs hybrid retrieval (keyword + semantic) over the Magnio knowledge base, then generates a grounded response.

Knowledge content lives in `content/chat/*.json` and covers:
- Positioning and proof framing
- Delivery methodology
- Immersion playbooks
- Qualification guidance
- Agentic offer framing

### Benchmark-driven model routing

Arena routing prefers local benchmark results before falling back to OpenRouter rankings.

```bash
# Run benchmarks for all categories
python scripts/benchmark_openrouter_models.py

# Run for specific categories
python scripts/benchmark_openrouter_models.py --categories technology legal travel

# Preview without writing
python scripts/benchmark_openrouter_models.py --dry-run
```

The pipeline: **discover models → run prompts → score with judge → apply promotion thresholds → write rankings**.

Rankings are stored in `data/openrouter_model_rankings.json` and optionally mirrored to Firestore for runtime reads without redeploying.

### Vertex AI support

Switch the advisor and/or judge to Vertex AI (useful for all-Google environments):

```bash
export MAGNIO_CHAT_ADVISOR_PROVIDER=vertex
export MAGNIO_CHAT_JUDGE_PROVIDER=vertex
export GOOGLE_CLOUD_PROJECT=your-project-id
gcloud auth application-default login
```

Switch back with `export MAGNIO_CHAT_ADVISOR_PROVIDER=openrouter`.

### Analytics & evaluation

- Every `/api/chat/ask` request is logged with mode, topic, models, winner, and latency
- Feedback is attached by `runId` via `POST /api/chat/feedback`
- Firestore mode stores recent cases, long-term summaries, human reviews, and daily rollups
- TTL policies on `expiresAt` handle automatic cleanup

---

## Lead Automation & Intake

The full lead lifecycle:

```
Contact Form  →  Auto-score¹  →  Auto-reply email  →  Slack alert
                                                          │
Admin triage (/#admin)  ←─────────────────────────────────┘
      │
      ├── Mark qualified / lost
      ├── Request details (email)
      └── Schedule follow-up

Cal.com booking  →  Webhook  →  Intake form generated  →  Follow-up flow
```

> **¹ Auto-score** combines five weighted signals — timeline urgency, business impact (revenue/cost keywords, dollar figures), service fit (automation, AI, integration mentions), problem clarity (length, causal language), and buyer readiness (budget, call, proposal mentions) — minus a spam penalty. Leads scoring 75+ are **hot**, 50+ are **warm**, and the rest enter **nurture**.

### Admin panel

1. Open `/#admin` in the browser
2. Enter your `TASKS_API_TOKEN` when prompted
3. Triage leads: mark qualified/lost, request details, schedule follow-ups

---

## API Reference

### Chat

| Method | Endpoint                          | Description                        |
|--------|-----------------------------------|------------------------------------|
| POST   | `/api/chat/ask`                   | Submit a chat query (arena/advisor)|
| GET    | `/api/chat/health`                | System health and config status    |
| GET    | `/api/chat/analytics/summary`     | Aggregated performance metrics     |
| GET    | `/api/chat/evaluations/recent`    | Recent evaluation cases            |
| POST   | `/api/chat/feedback`              | Submit feedback by runId           |

### Leads & Intake

| Method | Endpoint                              | Description                    |
|--------|---------------------------------------|--------------------------------|
| POST   | `/lead`                               | Capture contact form submission|
| GET    | `/admin/leads`                        | List all leads (auth required) |
| POST   | `/admin/leads/{id}/qualify`           | Mark lead as qualified         |
| POST   | `/admin/leads/{id}/lost`              | Mark lead as lost              |
| POST   | `/admin/leads/{id}/intake-token`      | Generate intake link           |
| POST   | `/webhooks/calcom`                    | Cal.com booking webhook        |
| POST   | `/intake/submit`                      | Submit intake form             |

---

## Environment Variables

### Chat

| Variable | Default | Description |
|----------|---------|-------------|
| `MAGNIO_OPENROUTER_API_KEY` | — | OpenRouter API key **(required)** |
| `MAGNIO_CHAT_ARENA_SIZE` | `3` | Number of parallel arena models |
| `MAGNIO_CHAT_JUDGE_MODEL` | `openai/gpt-5.1` | Judge model identifier |
| `MAGNIO_CHAT_ADVISOR_MODEL` | `anthropic/claude-sonnet-4.6` | Advisor model identifier |
| `MAGNIO_CHAT_JUDGE_PROVIDER` | `openrouter` | `openrouter` or `vertex` |
| `MAGNIO_CHAT_ADVISOR_PROVIDER` | `openrouter` | `openrouter` or `vertex` |
| `MAGNIO_CHAT_VERTEX_JUDGE_MODEL` | `gemini-2.5-flash` | Vertex judge model |
| `MAGNIO_CHAT_VERTEX_ADVISOR_MODEL` | `gemini-2.5-flash` | Vertex advisor model |
| `MAGNIO_VERTEX_PROJECT` | — | Google Cloud project ID (for Vertex) |
| `MAGNIO_VERTEX_LOCATION` | `global` | Vertex AI region |
| `MAGNIO_OPENROUTER_TITLE` | `Magnio Chat` | OpenRouter request title |
| `MAGNIO_OPENROUTER_REFERER` | `http://localhost:5173` | OpenRouter HTTP referer |

### Chat Analytics

| Variable | Default | Description |
|----------|---------|-------------|
| `MAGNIO_CHAT_ANALYTICS_BACKEND` | `sqlite` | `sqlite`, `firestore`, or `dual` |
| `MAGNIO_CHAT_ANALYTICS_DB` | `data/chat_analytics.sqlite3` | SQLite DB path |
| `MAGNIO_CHAT_RECENT_TTL_DAYS` | `30` | Recent case retention (days) |
| `MAGNIO_CHAT_CANDIDATE_TTL_DAYS` | `14` | Candidate output retention (days) |
| `MAGNIO_CHAT_MODEL_RANKINGS_BACKEND` | `json` | `json`, `firestore`, or `dual` |
| `MAGNIO_CHAT_MODEL_RANKINGS_PATH` | `data/openrouter_model_rankings.json` | Rankings file path |

### Leads & Infrastructure

| Variable | Default | Description |
|----------|---------|-------------|
| `FIREBASE_DATABASE_URL` | — | Firebase RTDB URL **(required for leads)** |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | — | Service account JSON string |
| `FIREBASE_SERVICE_ACCOUNT_JSON_PATH` | — | Path to service account file |
| `CORS_ALLOW_ORIGINS` | — | Comma-separated allowed origins |
| `MAGNIO_ENV` | — | Set to `dev` to skip webhook secret validation |
| `TASKS_API_TOKEN` | — | Admin API auth token |
| `CALCOM_WEBHOOK_SECRET` | — | Cal.com webhook secret (required in prod) |
| `CALCOM_BOOKING_URL` | — | Cal.com booking link |
| `SLACK_WEBHOOK_URL` | — | Slack notification webhook |
| `RESEND_API_KEY` | — | Resend email API key |
| `RESEND_FROM_EMAIL` | — | Sender email address |
| `RESEND_TO_EMAIL` | — | Recipient email address |
| `RESEND_LEAD_AUTOREPLY_ENABLED` | — | Enable lead auto-reply emails |
| `RESEND_INTAKE_ENABLED` | — | Enable intake emails |
| `RESEND_FOLLOWUP_ENABLED` | — | Enable follow-up emails |
| `INTAKE_FORM_BASE_URL` | `http://localhost:5173/#intake` | Intake form URL prefix |
| `INTAKE_ALLOW_RESUBMIT` | — | Allow intake form resubmission |
| `INTAKE_TOKEN_TTL_HOURS` | `168` | Intake token expiry (hours) |

### Frontend

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_BASE_URL` | — | Backend URL (optional; Vite proxy handles dev) |

---

## Deployment

### Production stack

| Component | Service |
|-----------|---------|
| Frontend  | Firebase Hosting (serves Vite build) |
| Backend   | Cloud Run (Docker container) |
| Database  | Firebase RTDB + Firestore |
| Secrets   | Google Secret Manager |

### Routing

Firebase Hosting rewrites `/api/**`, `/lead`, `/webhooks/**`, `/intake/**`, `/tasks/**`, and `/admin/**` to the Cloud Run `magnio-api` service. Everything else serves the SPA.

### Deploy

```bash
# Build frontend
npm run build

# Deploy frontend
firebase deploy

# Deploy backend (see docs/google-deploy.md for full instructions)
gcloud run deploy magnio-api \
  --source . \
  --region us-central1 \
  --allow-unauthenticated
```

See [docs/google-deploy.md](docs/google-deploy.md) for the full production deployment guide and [docs/github-secrets.md](docs/github-secrets.md) for CI/CD secrets setup.

---

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start Vite dev server (port 5173) |
| `npm run dev:all` | Frontend + backend + ngrok tunnel |
| `npm run build` | Production build |
| `npm run typecheck` | TypeScript type check |
| `npm run lint` | ESLint |
| `python scripts/benchmark_openrouter_models.py` | Generate model rankings |
