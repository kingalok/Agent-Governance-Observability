# Agent Governance Observability

A production-style proof of concept for AI agent governance and observability. This repository is designed as a CTO-portfolio demo that shows how agent inventory, ownership, risk controls, approvals, runtime telemetry, and enterprise workflows can fit together in a pragmatic platform.

## Stack

- Python 3.11+
- FastAPI
- LangGraph
- LangChain
- LangSmith tracing hooks
- SQLite for local demo persistence
- Next.js dashboard frontend

## Repository Structure

- `backend/` FastAPI API, SQLite models, governance services, and workflow orchestration stubs
- `frontend/` Next.js dashboard for agent inventory and runtime visibility
- `docs/` architecture notes and delivery roadmap
- `infra/` container and local deployment scaffolding
- `scripts/` local helper scripts

## What This Demo Covers

- Agent registry
- Owner and team mapping
- Risk tiers: `low`, `medium`, `high`
- Tool permission controls
- Runtime logs
- Approval checkpoints for high-risk actions
- Token and cost tracking placeholders
- Kill switch and pause controls
- One enterprise workflow demo: regulated data export review

## Quick Start

### 1. Backend

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
cp ../.env.example .env
uvicorn app.main:app --reload --port 8000
```

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### 2. Frontend

```bash
cd frontend
npm install
cp ../.env.example .env.local
npm run dev
```

Dashboard: [http://localhost:3000](http://localhost:3000)

## Environment

Use `.env.example` as the starting point for both apps. The backend will create a local SQLite database automatically.

## Demo Flow

1. Open the dashboard to view registered agents, ownership, risk profile, and runtime state.
2. Trigger the demo workflow from `POST /api/v1/workflows/demo/run`.
3. High-risk actions create an approval checkpoint before the action is marked executable.
4. Runtime logs, approval events, and placeholder usage metrics are persisted to SQLite.
5. Agents can be paused or kill-switched via the API.

## Next Steps

See [docs/TODO.md](/Users/Alok_Sharma/Documents/myrepo/Agent-Governance-Observability/docs/TODO.md) for the implementation roadmap and [docs/architecture.md](/Users/Alok_Sharma/Documents/myrepo/Agent-Governance-Observability/docs/architecture.md) for the platform design notes.
