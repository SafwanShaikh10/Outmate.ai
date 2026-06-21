# Outmate.ai — Multi-Agent GTM Intelligence System

> **AI-powered Go-To-Market intelligence platform** that uses a pipeline of autonomous agents to find, enrich, score, and generate personalized outreach for high-growth companies — in real time.

---

## Live Demo

```
Frontend:  http://localhost:5173
Backend:   http://localhost:8000
API Docs:  http://localhost:8000/docs
```

---

## What It Does

Outmate.ai takes a plain-English query like:

> *"Find fast-growing AI SaaS companies in India"*

…and autonomously runs a multi-agent pipeline to:

1. **Understand** the query (intent, location, industry, filters) using an LLM
2. **Search** across 4 linked datasets (companies, YC startups, job postings, acquisitions)
3. **Enrich** each result with hiring signals, tech stack, and funding context
4. **Validate** results using a Critic Agent — triggering self-correction if needed
5. **Score** every lead with an ICP (Ideal Customer Profile) score
6. **Generate** personalized multi-persona outreach copy (CEO / VP Sales / CTO)
7. **Stream** all results live to the UI via Server-Sent Events (SSE)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (React + Vite)                 │
│   - Real-time SSE stream display                                │
│   - Execution timeline with retry indicators                    │
│   - Lead cards with ICP scores + persona email tabs             │
└───────────────────────┬─────────────────────────────────────────┘
                        │  HTTP SSE  /api/query
┌───────────────────────▼─────────────────────────────────────────┐
│                      FastAPI Backend                            │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  GTM Orchestrator                       │   │
│  │  ┌──────────┐ ┌───────────┐ ┌────────┐ ┌──────────┐   │   │
│  │  │ Planner  │→│ Retrieval │→│ Critic │→│   GTM    │   │   │
│  │  │  Agent   │ │  Agent    │ │ Agent  │ │ Strategy │   │   │
│  │  └──────────┘ └───────────┘ └────────┘ └──────────┘   │   │
│  │         ↑ Self-Correction Loop (if Critic rejects) ↑   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌───────────────────────────────────────┐                     │
│  │            SQLite Database            │                     │
│  │  companies | yc_companies             │                     │
│  │  job_postings | acquisitions          │                     │
│  └───────────────────────────────────────┘                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Agent Pipeline

### 1. Planner Agent
Parses the natural language query using the LLM (or rules-based fallback) to extract:
- **Intent**: company search, job postings, YC startups, acquisitions
- **Filters**: location, industry, vertical, YC batch, year
- **Strategy**: structured execution plan with confidence score

### 2. Retrieval Agent
Converts the plan into dynamic SQL and queries across all 4 tables:
- Performs `UNION ALL` across `companies` + `yc_companies` for general searches
- `JOIN`s `job_postings` with `yc_companies`/`companies` for hiring queries
- `JOIN`s `acquisitions` with company tables for M&A searches
- Applies location, industry, role, batch, and year filters dynamically
- Filters out any unknown/unresolvable company names

### 3. Enrichment Agent
Enhances records with:
- Hiring growth signals
- Tech stack indicators
- Funding recency narrative
- Buying intent score narrative

### 4. Critic / Validation Agent
Validates the retrieved results against the original query:
- **Approves** when results are relevant and filters are correct
- **Rejects** and triggers a self-correction loop if results are empty or filters are wrong
- Respects location constraints — never relaxes a location just to get more results

### 5. GTM Strategy Agent
For each company, generates:
- **ICP Score**: Fit, Intent, Growth (0.0–1.0 each)
- **3 Personalized Email Templates**: CEO / VP Sales / CTO
- **GTM Hooks & Angles**: Tailored to industry and hiring signals

---

## Datasets Used

| Dataset | Source | Rows | Description |
|---|---|---|---|
| `companies` | Custom | ~20 | Mock GTM target companies with full signals |
| `yc_companies` | Kaggle (YC directory) | ~3,500 | Y Combinator alumni with batch/vertical |
| `job_postings` | Kaggle (LinkedIn) | ~100K | LinkedIn job postings with company/salary data |
| `acquisitions` | Kaggle (Crunchbase) | ~18,968 | M&A records with acquirer/price data |

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 18, Vite, Vanilla CSS (dark glassmorphism UI) |
| **Backend** | Python 3.10, FastAPI, Uvicorn |
| **Database** | SQLite (via custom `database.py`) |
| **LLM** | Groq API (`llama-3.3-70b-versatile`) with xAI / OpenAI fallback |
| **Streaming** | Server-Sent Events (SSE) |
| **Testing** | Python `unittest` (7 tests) |

---

## Setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- A free [Groq API key](https://console.groq.com)

### 1. Clone the repo

```bash
git clone https://github.com/SafwanShaikh10/Outmate.ai.git
cd Outmate.ai
```

### 2. Backend setup

```bash
pip install -r backend/requirements.txt
```

Create a `.env` file in the project root:

```env
GROK_API_KEY=gsk_your_groq_api_key_here
```

> **Note:** The system automatically detects Groq keys (starting with `gsk_`) and routes to `llama-3.3-70b-versatile`. If Groq is unavailable, it falls back to a robust rules-based parser — so the app works even without a key.

### 3. Import datasets

The SQLite database (`backend/gtm_database.db`) is not included in the repo (too large). To recreate it:

```bash
# Import Crunchbase acquisitions (download acq.csv from Kaggle)
python -m backend.db_import --file backend/acq.csv

# Import YC companies + job postings (optional, handled by db_import_extra.py)
python -m backend.db_import_extra
```

### 4. Start the backend

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

### 5. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**

---

## Example Queries

```
Find fast-growing AI SaaS companies in India
Find high-growth fintech companies in the US
Search for acquisitions in the Consumer category
Find YC Batch 2022 companies in the vertical B2B SaaS
Find companies hiring engineers in New York
```

---

## API Reference

### `GET /api/query?q={query}`

Streams the multi-agent execution pipeline as Server-Sent Events.

**Events emitted:**

| Event | Description |
|---|---|
| `log` | Agent step log message |
| `agent_step` | Planner/Retrieval/Critic/Strategy step details |
| `result` | Final results (companies, ICP scores, email snippets) |
| `error` | Error message if pipeline fails |

### `GET /api/cache`

Returns all cached query results.

### `DELETE /api/cache`

Clears the query cache.

---

## Running Tests

```bash
python -m pytest backend/test_orchestrator.py -v
```

**Test coverage:**
- ✅ Database search filters
- ✅ Query hash / caching
- ✅ Full orchestrator execution stream
- ✅ Self-correction loop
- ✅ Acquisitions query
- ✅ Job postings query
- ✅ Unknown company filtering

---

## Key Features

| Feature | Description |
|---|---|
| 🧠 **LLM Query Understanding** | Groq LLM parses intent, location, industry from free-text |
| 🔄 **Self-Correction Loops** | Critic Agent rejects bad plans; Orchestrator retries with fixed filters |
| 📍 **Location Filtering** | Location constraints are strictly enforced — India results stay in India |
| 🚫 **No Unknown Companies** | Unresolvable company names are filtered out automatically |
| 💾 **Query Cache** | MD5-keyed result cache with view/clear API endpoints |
| 📡 **SSE Streaming** | Results stream live step-by-step as agents complete |
| 🎯 **ICP Scoring** | Fit, Intent, Growth scores per company |
| ✉️ **Multi-Persona Outreach** | Personalized CEO / VP Sales / CTO email templates |
| 🔁 **Graceful Fallback** | Rules-based parser activates if LLM is unavailable |

---

## Project Structure

```
Outmate.ai/
├── backend/
│   ├── agents.py           # All 5 agent classes (Planner, Retrieval, Enrichment, Critic, GTM)
│   ├── orchestrator.py     # Multi-agent loop with retry, cache, SSE streaming
│   ├── main.py             # FastAPI app with /api/query SSE endpoint
│   ├── database.py         # SQLite schema + connection helpers
│   ├── mock_db.py          # Mock company database (fallback / demo data)
│   ├── db_import.py        # CLI tool to import Crunchbase acq.csv
│   ├── db_import_extra.py  # CLI tool to import YC + job postings datasets
│   ├── test_orchestrator.py# 7 unit tests
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx         # Main React dashboard (SSE client, timeline, lead cards)
│   │   └── index.css       # Premium dark-mode CSS (glassmorphism, animations)
│   ├── index.html
│   └── package.json
├── .env.example            # Template for environment variables
├── .gitignore
└── README.md
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROK_API_KEY` | Optional | Groq API key (`gsk_...`) or xAI Grok key (`xai-...`) |
| `GEMINI_API_KEY` | Optional | Google Gemini API key (fallback LLM) |
| `OPENAI_API_KEY` | Optional | OpenAI API key (fallback LLM) |
| `DATABASE_URL` | Optional | PostgreSQL URL (leave blank to use local SQLite) |

> The system works without any API key using its built-in rules-based parser.

---

## License

MIT © 2024 Safwan Shaikh
