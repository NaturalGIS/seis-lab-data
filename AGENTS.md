# Project overview

Seis-Lab-Data is a web application for managing marine survey data. It provides a catalog of projects, survey missions, and survey-related records, with support for spatial and temporal metadata, validation workflows, and publishing.

## Tech stack

- **Language:** Python 3.12+
- **Web framework:** Starlette with Jinja2 templates and Datastar (HTMX-style SSE interactions)
- **ORM:** SQLModel (SQLAlchemy async under the hood)
- **Database:** PostgreSQL with PostGIS
- **Auth:** Authentik (OpenID Connect via authlib)
- **Task queue:** Dramatiq
- **Pub/sub:** Redis
- **Package manager:** uv
- **Dev environment:** Docker Compose (`docker/compose.dev.yaml`)

## Domain model

The core hierarchy is:

```
Project
  └── SurveyMission (many per project)
        └── SurveyRelatedRecord (many per mission)
              └── RecordAsset (many per record)
```

Each of the three main entities (`Project`, `SurveyMission`, `SurveyRelatedRecord`) has:
- An `owner` field (string, the Authentik user `sub`)
- A `status` enum (`DRAFT`, `PUBLISHED`, plus processing states)
- An `is_valid` flag and a `validation_result` JSONB field
- Spatial extent (`bbox_4326`, PostGIS polygon)
- Temporal extent (`temporal_extent_begin`, `temporal_extent_end`)
- Localizable `name` and `description` (JSONB with `en`/`pt` keys)

`SurveyRelatedRecord` additionally references lookup tables: `DatasetCategory`, `DomainType`, and `WorkflowStage`. Records can also have self-referential relationships to other records (`SurveyRelatedRecordSelfLink`).

The local `appuser` table is a write-through cache of Authentik user data (`id`, `username`, `email`), upserted on every successful login. It is not a source of truth — Authentik owns identity.

## Source layout

```
src/seis_lab_data/
  auth.py              # OAuth config, get_user(), requires_auth decorator
  authentik.py         # Authentik admin API helper (fetch user by UUID)
  config.py            # Settings (pydantic-settings)
  constants.py         # Enums, string constants (ADMIN_ROLE, status enums, etc.)
  errors.py            # SeisLabDataError
  events.py            # Event emitter protocol and helpers
  permissions/         # Pure sync permission functions (no DB calls)
  operations/          # Business logic: fetch → check permission → command → emit event
  db/
    models.py          # SQLModel table definitions
    commands/          # Write operations (create, update, delete, upsert)
    queries/           # Read operations (get, list_published, list_accessible, list_*)
    engine.py          # Async engine and session maker
  schemas/             # Pydantic schemas (request/response shapes, IDs)
  migrations/          # Alembic migrations
  webapp/
    app.py             # Starlette app factory and lifespan
    routes/            # Route handlers (auth, projects, surveymissions, surveyrelatedrecords)
    forms/             # WTForms form definitions
```

## Request flow

Routes → Operations → Permissions + DB queries/commands

- **Routes** extract the user from the session (`get_user(request.session["user"])`), get a DB session from `request.state.settings.get_db_session_maker()`, and call operations.
- **Operations** fetch the relevant DB object first, then call a permission function, then call a command and emit an event.
- **Permissions** are pure sync functions that accept model instances (never IDs) and a user — no DB calls inside.
- **Queries** contain three variants per entity for listing: `list_published_*` (unauthenticated), `list_accessible_*` (authenticated, applies ownership/co-ownership filter), and `list_*` (admin, no filter). The operations layer picks the right one.

## Auth and permissions

Authentication uses Authentik via OIDC. After login the user's `sub`, `email`, `preferred_username`, and `groups` are stored in the Starlette session. The `schemas.User` dataclass holds `id` (the `sub`), `email`, `username`, `roles` (from `groups`), and `active`.

Permission rules:
- **Admin** (`ADMIN_ROLE = "admin"` in `constants.py`): full access to everything. Determined by checking `"admin" in user.roles`.
- **Unauthenticated**: read-only access to `PUBLISHED` resources.
- **Authenticated non-admin**: can create projects/missions/records; can read/update/delete/validate resources they own or co-own.
- **Co-ownership**: a project owner is co-owner of all its missions and records; a mission owner is co-owner of all its records.
- **Lookup tables** (`DatasetCategory`, `DomainType`, `WorkflowStage`): admin only for create/delete.

## Dev workflow

The dev stack runs via Docker Compose:

```bash
docker compose -f docker/compose.dev.yaml exec -ti webapp uv run <command>
```

Common commands:
- `seis-lab-data db upgrade` — apply migrations
- `seis-lab-data db generate-migration '<description>'` — autogenerate a migration from model changes (always prefer this over hand-writing migrations)

## Async UI processing pattern

State-mutating operations (create, update, delete, validate, publish) are not handled synchronously in the route. Instead, they follow this pipeline:

```
Browser (Datastar) → Route → Dramatiq actor (enqueue) → Redis broker
                  ↑                                           ↓
             SSE stream                            Worker process (actor runs)
                  ↑                                           ↓
           Route (pubsub)  ←─── Redis pub/sub ───  Progress published to topic
```

### 1. Route enqueues task and opens SSE stream

The route immediately enqueues the actor via `.send(...)`, then subscribes to a per-request Redis progress topic and streams results back to the browser as SSE using `DatastarResponse`. The request ID is generated in the route and passed to the actor so both sides use the same topic name (`progress:{request_id}`).

```python
tasks.create_project.send(
    raw_request_id=str(request_id),
    raw_to_create=to_create.model_dump_json(),
    raw_initiator=json.dumps(dataclasses.asdict(user)),
)
# then stream SSE from produce_event_stream_for_topic(...)
return DatastarResponse(event_streamer(), status_code=202)
```

### 2. Dramatiq actor executes in a worker process

Actors are defined in `processing/tasks.py` with `@dramatiq.actor`. Dependencies (DB session, Redis client, settings) are injected via custom middleware and decorators (`@decorators.sld_settings`, `@decorators.redis_client`, `@decorators.session_maker`). The actor calls the same operations layer as the route would, publishing `ProcessingMessage` objects to the Redis topic as it progresses.

```python
await redis_client.publish(
    topic_name,
    schemas.ProcessingMessage(
        request_id=request_id,
        status=ProcessingStatus.RUNNING,
        message="Creating project...",
    ).model_dump_json(),
)
```

### 3. Route relays progress to the browser via SSE

`produce_event_stream_for_topic()` in `webapp/routes/common.py` loops over Redis pubsub messages and yields Datastar SSE events:
- `RUNNING` messages are appended to a feedback `<output>` element in the page.
- `SUCCESS` or `FAILED` triggers the appropriate handler, which may redirect, patch other DOM elements, or chain another task.

There is also `produce_event_stream_for_item_updates()` for long-lived subscriptions to entity-specific topics (e.g. `project-updated:{project_id}`), used by detail pages to receive live updates while the user is viewing an item.

### 4. Datastar updates the DOM

The frontend uses [Datastar](https://data-star.dev/) directives (`data-on:click`, `data-attr`, `data-text`, etc.) on HTML elements. Form submissions go via `@post(...)` which keeps the SSE connection open. The server pushes `patch_elements` SSE events that Datastar applies directly to the DOM, either appending progress messages or replacing whole sections of the page.

### Redis topic naming

| Template | Used for |
|---|---|
| `progress:{request_id}` | Per-operation progress during task execution |
| `project-updated:{project_id}` | Project field changes |
| `project-status-changed:{project_id}` | Project status transitions |
| `project-validity-changed:{project_id}` | Project validation result changes |
| `project-deleted:{project_id}` | Project deletion |
| (same pattern for survey missions and records) | |

### Broker setup

`processing/broker.py` configures a `RedisBroker` with four middleware layers:
- `AsyncIO` — runs actors in an async event loop
- `SeisLabDataSettingsMiddleware` — provides app settings
- `AsyncRedisPubSubMiddleware` — manages the Redis client for pub/sub
- `AsyncSqlAlchemyDbMiddleware` — manages the async DB engine and session maker

## Key conventions

- Migrations are always generated by Alembic (`db generate-migration`), never written by hand.
- Avoid single-line or thin wrapper helper functions — inline the logic instead.
- Imports always at the top of the module, never inside functions.
- The `appuser` table is named to avoid colliding with PostgreSQL's reserved `user` keyword.
- Localizable fields (`name`, `description`) are JSONB with `en` and `pt` keys.
- All IDs are `NewType` wrappers over `uuid.UUID` or `str` (e.g. `ProjectId`, `UserId`).
