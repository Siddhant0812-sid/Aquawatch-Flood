# AquaWatch Flood: AI Coding Agent Guide

## Project purpose

AquaWatch is a local development and demo application for:

- mapping flood extent in Assam and the Brahmaputra basin from Sentinel-1 SAR data;
- forecasting 24-hour, 48-hour, and 72-hour flood risk from rainfall and river-level data; and
- presenting both capabilities in a React/Leaflet dashboard backed by FastAPI.

The repository is currently a project skeleton. Treat the existing design documents as the requirements baseline and do not assume that planned files or features already exist.

## Requirements and documentation map

Read the relevant document before changing behavior:

- `README.md`: short project summary and current repository status.
- `implementation-plan.md`: active one-week demo scope, target folder layout, delivery priorities, and definition of done.
- `TRD.md`: technology choices, model boundaries, API overview, performance targets, and testing requirements.
- `BACKEND_SCHEMA.md`: canonical request/response shapes and in-memory data objects.
- `APP_FLOW.md`: user journeys, backend interactions, startup behavior, and error flows.
- `UI_UX_DESIGN.md`: screen behavior, accessibility, visual language, and user-facing limitations.
- `.env.example`: supported local configuration names and defaults.

When documents conflict, prefer the active one-week demo scope in `implementation-plan.md`, then the API contracts in `BACKEND_SCHEMA.md`, then the broader technical detail in `TRD.md`. Update directly related documentation when an intentional contract or behavior changes.

## Current scope and architectural boundaries

The active implementation target is a mock-data local demo:

- Implement the backend and frontend as a simple monorepo-style project.
- Keep the API contract stable so mock adapters can later be replaced by real data and ML adapters.
- Use file-based inputs and in-memory runtime state; do not add a database.
- Do not add Docker, cloud deployment, microservices, authentication, or persistent result storage unless the requirements are explicitly revised.
- Real Earth Engine, telemetry, and model integrations are later adapters, not prerequisites for the demo.
- Keep mock mode first-class and controlled by configuration (`USE_MOCK_DATA`, `USE_MOCK_MODELS`).

The planned top-level areas are `backend/`, `frontend/`, `data/`, `models/`, `scripts/`, and tests as described in `implementation-plan.md`. Follow that separation when creating files rather than placing application logic at the repository root.

## Stable backend API

The demo must support these endpoints:

- `GET /health`
- `GET /stations`
- `GET /segment?date=YYYY-MM-DD`
- `GET /forecast?station_id=<id>`
- `POST /simulate-alert`

Use the schemas in `BACKEND_SCHEMA.md` as the source of truth. Preserve field names, types, risk labels, and error response shape. If an endpoint must evolve, update its schema documentation and frontend consumers together.

Expected backend characteristics:

- FastAPI with Uvicorn for local serving.
- Configuration loaded from environment variables, with `.env.example` documenting supported values.
- CORS enabled for the local frontend during development.
- Models and derived results may be cached in memory, but caches must be safe to lose on restart.
- Errors from unavailable data or integrations should be returned explicitly using the project’s standard error shape; do not silently substitute successful-looking responses.

## Frontend expectations

Use React with function components and hooks, Leaflet/react-leaflet for the map, and a chart library such as Recharts or Chart.js for forecasts. The required user-facing views are:

1. Dashboard with flood overlay, station markers/list, date selection, and overall risk.
2. Station detail with a 72-hour chart, danger-level reference, risk score, contributing factors, and clearly labelled simulated alert action.
3. About/data sources with limitations and attribution.

Risk must always be represented by both a text label and color. Do not imply that Sentinel-1 imagery is real-time: show the actual acquisition date and disclose revisit limitations.

## Data and ML guidance

- Use deterministic mock data so tests and screenshots are reproducible.
- Keep data loading, feature engineering, route handling, and model adapters separate.
- Define interfaces around segmentation and forecasting so U-Net/LSTM or later alternatives can replace mocks without changing API consumers.
- Keep the no-database design: source files are read locally and derived results live only for the process lifetime.
- Never commit Earth Engine credentials, tokens, `.env` files, private telemetry, generated outputs, or model artifacts that are not intentionally tracked.
- Follow the documented Assam bounding box and input conventions when implementing real-data adapters.

## Coding conventions

- Prefer small, typed modules with clear responsibilities and existing project patterns.
- Validate request parameters at the API boundary and use explicit domain types for responses.
- Keep route handlers thin; put business logic in services/adapters.
- Avoid broad exception handling, silent fallbacks, and `any`-style escapes. Log or return actionable errors using the project’s established mechanism.
- Preserve backward compatibility for the documented API and mock mode.
- Keep user-facing copy clear about demo behavior, uncertainty, data gaps, and the absence of real notifications.
- Add comments only for non-obvious decisions; do not comment self-explanatory code.

## Validation workflow

Before coding, inspect the relevant requirements and existing files. After coding:

1. Run focused backend unit/API tests for changed behavior.
2. Run frontend type-check/lint/tests for changed UI behavior.
3. Exercise the affected endpoint or UI flow in mock mode when practical.
4. Run the repository’s available build/test commands; do not invent a new toolchain without need.
5. Check that no secrets, generated data, or unrelated files were added.
6. Update the relevant documentation if contracts, setup, or limitations changed.

Because the repository may not yet contain package manifests or source code, first identify the available commands before attempting to run them. Do not report a command as passing when its tooling or implementation does not exist.

## Local setup expectations

Use `.env.example` as the template for local configuration. Important defaults include:

- backend at `127.0.0.1:8000`;
- frontend API base at `http://127.0.0.1:8000`;
- `USE_MOCK_DATA=true`;
- `USE_MOCK_MODELS=true`;
- local data directories under `data/`;
- `Asia/Kolkata` as the default timezone.

Keep setup instructions reproducible and local. If dependencies are added, update the appropriate manifest and document the install/run commands.

## Definition of done for changes

A change is complete when it:

- addresses the requested behavior without unrelated refactors;
- follows the documented architecture and preserves stable API contracts;
- works in mock mode without external credentials;
- includes focused tests or an appropriate validation path;
- handles invalid input and unavailable data explicitly;
- updates directly related documentation;
- leaves the worktree free of secrets and unintended generated artifacts.

