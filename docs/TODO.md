# TODO Roadmap

## Phase 1: Complete the core backend

- Add CRUD endpoints for creating and editing agents
- Add richer approval workflows with reviewer roles and comments
- Store workflow runs as first-class records
- Add database migrations with Alembic
- Add structured policy definitions for tool access and environment restrictions

## Phase 2: Deepen observability

- Replace placeholder token and cost fields with actual provider metering
- Add LangSmith span metadata conventions
- Add filtering by agent, workflow, owner, and time range
- Introduce alerting thresholds for policy violations and budget overages

## Phase 3: Improve the dashboard

- Add live refresh and drill-down detail pages
- Add action controls for pause, resume, and kill switch from the UI
- Add approval review actions directly in the dashboard
- Visualize workflow state transitions and guardrail outcomes

## Phase 4: Production readiness

- Add unit and integration tests
- Add CI for linting, type checking, and API smoke tests
- Add authentication and RBAC
- Add deployment manifests for cloud hosting
- Introduce event streaming and external log sinks

## Phase 5: Portfolio polish

- Add screenshots and architecture diagrams
- Record a short demo flow video
- Add benchmark or incident scenario walkthroughs
- Add a second enterprise workflow such as procurement or access reviews
