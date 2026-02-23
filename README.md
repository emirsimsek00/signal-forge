# SignalForge

**AI-powered operations copilot that ingests signals from across your stack, surfaces risks, detects anomalies, and helps you stay ahead of incidents — all from a single dashboard.**

SignalForge pulls data from Reddit, news sources, Zendesk, Stripe, PagerDuty, and system metrics, then runs NLP analysis, risk scoring, and anomaly detection to give your team a real-time operational picture. When something looks off, it tells you — before your customers do.

---

## What It Does

- **Signal Ingestion** — Pulls from 7 sources (Reddit, NewsAPI, Zendesk, Stripe, PagerDuty, Alpha Vantage, and system telemetry) on a configurable schedule. Falls back to realistic demo data when API keys aren't set.
- **NLP Processing** — Every signal runs through sentiment analysis, named entity extraction, auto-summarization, and embedding generation. Mock mode ships out of the box; plug in HuggingFace models for production.
- **Risk Scoring** — Weighted formula combining sentiment, anomaly magnitude, ticket volume, revenue deviation, and engagement. Each score comes with an explanation of what's driving it.
- **Anomaly Detection** — Statistical detectors for volume spikes (Poisson z-score), risk surges, and sentiment drift. Anomalies auto-create incidents and broadcast alerts via WebSocket.
- **Correlation Engine** — Finds related signals using FAISS embedding similarity, temporal proximity, and shared entities. Visualized as an interactive force-directed graph.
- **AI Chat** — Ask natural language questions like *"What Reddit posts mention outages in the last 6 hours?"* and get cited, contextual answers.
- **Forecasting** — Linear regression on financial and system metrics with automatic incident creation when forecasts trend badly.
- **Real-time Alerts** — WebSocket-powered toast notifications for high-risk signals and anomaly events, visible anywhere in the app.

## Screenshots

The dashboard shows live signal counts, risk distribution, sentiment trends, and recent high-risk signals at a glance. Other pages include a signal explorer with filtering, a correlation graph, an anomaly timeline, AI chat, incident management, risk heatmap, executive briefings, and an alerts page.

## Architecture

```
┌─────────────────────────────────────────────────┐
│                   nginx :80                     │
│            reverse proxy + WebSocket            │
├──────────────────────┬──────────────────────────┤
│   Next.js :3000      │     FastAPI :8000        │
│   (frontend)         │     (backend)            │
│                      │                          │
│  Dashboard           │  /api/signals            │
│  Signal Explorer     │  /api/incidents          │
│  Correlation Graph   │  /api/dashboard          │
│  Anomaly Timeline    │  /api/correlation        │
│  AI Chat             │  /api/chat               │
│  Incident Manager    │  /api/anomaly            │
│  Risk Heatmap        │  /api/forecast           │
│  Exec Briefing       │  /api/brief              │
│  Alerts              │  /ws/signals (WebSocket) │
└──────────────────────┴──────────────────────────┘
                       │
            ┌──────────┴──────────┐
            │   SQLite (async)    │
            │   FAISS (in-memory) │
            └─────────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS |
| Backend | FastAPI, SQLAlchemy (async), Pydantic v2 |
| Database | SQLite with aiosqlite (swap for Postgres in prod) |
| Vector Search | FAISS (CPU) for embedding similarity |
| NLP | Mock mode built-in; optional HuggingFace transformers |
| Real-time | WebSocket with auto-reconnect and exponential backoff |
| Infrastructure | Docker multi-stage builds, nginx reverse proxy |

## Getting Started

### Prerequisites

- Python 3.9+
- Node.js 20+
- npm

### Backend

```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Apply migrations (required for production)
alembic upgrade head

# Start the backend
uvicorn backend.main:app --reload
```

The backend starts at `http://localhost:8000`. Mock mode generates realistic demo data without needing any API keys or ML models.

### Database Migrations (Alembic)

SignalForge now uses Alembic for schema changes.

```bash
# Apply latest schema
alembic upgrade head

# Create a new migration after model changes
alembic revision --autogenerate -m "describe change"

# Roll back one migration
alembic downgrade -1
```

If you already have an existing production DB created before Alembic:

1. Take a DB backup.
2. Generate and validate a baseline migration against that schema.
3. Use `alembic stamp head` only after confirming schema parity.

For greenfield environments, just run `alembic upgrade head`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000` to see the dashboard.

### Docker (production)

```bash
docker compose up --build
```

This starts the backend, frontend, and nginx reverse proxy. The app is served on port 80.
The backend container is configured to run `alembic upgrade head` on startup (`RUN_DB_MIGRATIONS=true` in `docker-compose.yml`).

## Configuration

Copy `.env.example` to `.env` and fill in any keys you want to use:

```bash
cp .env.example .env
```

If an env value contains spaces (for example `NEWSAPI_KEYWORDS`), wrap it in quotes:
`NEWSAPI_KEYWORDS="cybersecurity,outage,data breach"`.

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | SQLAlchemy async URL | No (defaults to SQLite) |
| `AUTO_CREATE_SCHEMA` | Auto-run `Base.metadata.create_all` at startup | No (set `false` in production) |
| `RUN_DB_MIGRATIONS` | Run `alembic upgrade head` before backend start (container mode) | No |
| `USE_MOCK_ML` | Use mock NLP models | No (defaults to true) |
| `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` | Reddit API access | No |
| `NEWSAPI_KEY` | NewsAPI.org key | No |
| `ZENDESK_SUBDOMAIN` / `ZENDESK_API_KEY` | Zendesk integration | No |
| `STRIPE_API_KEY` | Stripe event ingestion | No |
| `PAGERDUTY_API_KEY` | PagerDuty incident sync | No |
| `ALPHA_VANTAGE_KEY` | Financial market data | No |
| `INGESTION_INTERVAL_SECONDS` | Seconds between ingestion cycles | No (defaults to 300) |

No API keys are required to run the app — demo data kicks in automatically.

## Running Tests

```bash
source .venv/bin/activate
python -m pytest backend/tests/ -v
```

The test suite covers ingestion, NLP pipeline, risk scoring, correlation engine, anomaly detection, forecasting, incident management, and API transitions.

## Project Structure

```
backend/
├── api/            # FastAPI route handlers
├── anomaly/        # Statistical anomaly detection
├── correlation/    # Multi-strategy signal correlator + graph builder
├── forecasting/    # Time-series forecasting engine
├── ingestion/      # Data source connectors + demo data generator
├── models/         # SQLAlchemy models + Pydantic schemas
├── nlp/            # Sentiment, entities, embeddings, summarization
├── risk/           # Weighted risk scoring with explainability
├── tests/          # pytest test suite (40 tests)
├── workers/        # Background scheduler
├── config.py       # Pydantic settings
├── database.py     # Async SQLAlchemy engine
├── incident_manager.py  # Auto-incident creation from anomalies + forecasts
└── main.py         # FastAPI app entry point

frontend/
├── src/
│   ├── app/        # Next.js pages (10 routes)
│   ├── components/ # Sidebar, AlertToast
│   ├── hooks/      # useWebSocket
│   └── lib/        # API client
└── next.config.ts
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/signals` | List signals with filtering and pagination |
| POST | `/api/signals/ingest` | Trigger manual ingestion |
| GET | `/api/dashboard/overview` | Dashboard KPIs and charts |
| GET | `/api/incidents` | List incidents |
| POST | `/api/incidents` | Create incident |
| POST | `/api/incidents/{id}/transition` | Acknowledge, resolve, reopen, dismiss |
| GET | `/api/correlation/{id}` | Find correlated signals |
| GET | `/api/correlation/{id}/graph` | Build correlation graph |
| POST | `/api/chat` | AI chat query |
| GET | `/api/anomaly/recent` | Recent anomaly events |
| GET | `/api/anomaly/status` | Anomaly detection summary |
| GET | `/api/forecast/{metric}` | Generate time-series forecast |
| GET | `/api/brief` | Executive briefing |
| WS | `/ws/signals` | Real-time signal + alert stream |
| GET | `/api/health` | Health check |

## License

MIT
