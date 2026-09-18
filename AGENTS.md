# Sativoice - Project Overview

Sativoice is a voice AI platform for building and deploying conversational AI agents with telephony and WebRTC support.

## Project Structure

```
sativoice/
├── api/              # Backend - FastAPI application
├── ui/               # Frontend - Next.js application
├── scripts/          # Helper scripts for local development
├── docs/             # Mintlify documentation
├── pipecat/          # Pipecat framework (git submodule)
├── dograh-livekit/   # LiveKit agent bridge (OSS path)
├── docker-compose.yaml       # Production/OSS deployment
├── docker-compose-local.yaml # Local development services
```

## Tech Stack

- **Backend**: Python with FastAPI
- **Frontend**: Next.js 15 with React 19, TypeScript, Tailwind CSS
- **Database**: PostgreSQL with SQLAlchemy (async)
- **Cache/Queue**: Redis with ARQ for background tasks
- **Storage**: MinIO (S3-compatible) for audio files

## Local Development

Contributor setup and service startup are documented in `docs/contribution/setup.mdx`.

## Environment Configuration

- `api/.env` - Backend environment variables. Source this when running diagnostic scripts or one-off services against the dev DB (e.g. `python -m api.services.admin_utils.local_exec`).
- `api/.env.test` - Test-only environment variables. Source this when running pytest so tests hit the test DB and never the dev/prod credentials in `api/.env`.
- `ui/.env` - Frontend environment variables

Typical invocation:

```bash
# Tests
source venv/bin/activate && set -a && source api/.env.test && set +a && python -m pytest api/tests/...

# LiveKit bridge tests (mocked — no live LiveKit server or external API keys needed)
source venv/bin/activate && uv pip install -e './dograh-livekit[dev]' && pytest dograh-livekit/tests/ -xvs

# Diagnostics / scripts
source venv/bin/activate && set -a && source api/.env && set +a && python -m api.services.admin_utils.local_exec
```

CI runs the bridge suite on pull requests touching `dograh-livekit/**` via `.github/workflows/livekit-bridge-tests.yml` (see `docs/contribution/setup.mdx` → Continuous Integration).

## Directory Scope: dograh-livekit/

- `dograh-livekit/` is the **LiveKit AgentServer implementation** (the OSS telephony bridge). It registers a `dograh-agent` worker that serves both SIP inbound (LiveKit SIP trunk + dispatch rules) and Room inbound (direct room creation with metadata) patterns.
- It connects to the Dograh **internal API** (`/api/internal/*`) via `DograhClient` (authenticated with `X-Internal-Token`) for runtime workflow config, session records, and KB search.
- It is **self-contained**: its `pyproject.toml` depends only on livekit agents/plugins, agno, httpx, and pydantic — it does **not** import from `api/` or `ui/`.
- The bridge container is opt-in via the `livekit` compose profile (`docker compose --profile livekit up -d`); dispatch rules are synced best-effort from the `api` process on publish and startup (`api/services/livekit_bridge/sync.py`). See `docs/integrations/telephony/livekit.mdx` for the user-facing guide.

## Provider Ecosystem: Audit & Deprecation Conventions

The provider registry (`api/services/configuration/registry.py` for voice AI services, `api/services/telephony/registry.py` for telephony) is the source of truth for which integrations exist. Every provider must be registered, validated, and constructible before it is considered "used".

### Auditing a provider (before removing anything)

1. Verify **real usage** first — live questioning is the only proof that a provider has zero production use. Query the production DB before any removal:
   - `organization_configurations` where `key = 'MODEL_CONFIGURATION_V2'` and `value` JSON contains the provider name
   - `telephony_configurations` grouped by `provider`
   - `workflow_runs` grouped by `mode` (telephony) or `extra` JSON (voice)
2. Measure **test coverage** — a provider with no dedicated test file under `api/tests/` (factory, validator, or routes) is a candidate for flagging.
3. Measure **maintenance burden** — churn in the last 6 months (`git log --since=...` on the provider's files), external dependency weight (pipecat extras in the submodule's `pyproject.toml`), and the presence of no-op API-key validators in `check_validity.py`.
4. Record findings under `.fusion/tasks/<TASK>/audit-report.md` before changing code.

### Deprecating (soft, backward-compatible — preferred first step)

- Add the provider value to `DEPRECATED_PROVIDERS` in `api/services/configuration/registry.py` with an actionable message (name migration targets), and pass `deprecation_message=` to the provider's `provider_model_config(...)` so the schema (and UI) carries `deprecated` + `deprecation_message`.
- `check_validity.py` logs a warning when a deprecated provider validates — it must **never** block validation (existing configs keep working).
- Mark the provider deprecated in the docs (`docs/configurations/voice.mdx`, `docs/configurations/transcriber.mdx`).
- Add/extend regression tests in `api/tests/test_provider_audit.py` asserting: deprecation metadata present, provider still constructs + validates, and non-deprecated providers are untouched.

### Removing (hard — only after the DB query above returns zero rows)

- Follow the Phase 2/3 checklist in `.fusion/tasks/DOGR-005/deprecation-plan.md`.
- **Never** delete enum values in `api/enums.py` or `ServiceProviders` — stored JSON/DB rows reference them. Keep them with a deprecation comment.
- No provider migration is needed: provider columns are `VARCHAR` (the run-mode Postgres ENUM was already dropped).
- Do not create Alembic migrations for provider add/remove — the schema intentionally does not enumerate providers.
