# AI Script Writer — Backend

Backend API for the AI Script Writer project.

## Purpose

This is the FastAPI backend for a Generative AI application that helps users
transform creative ideas into structured scripts through an outline-first
workflow. It is built in phases:

- **Phase 1** — minimal FastAPI foundation (root + health endpoints, Swagger).
- **Phase 2** — PostgreSQL + SQLAlchemy database configuration and models.
- **Phase 3** — authentication: signup, login, JWT, protected endpoints.
- **Phase 4** — Creative Brief API: users create and manage their briefs.
- **Phase 5** — provider-neutral Creative Brief prompt previews and Gemini
  provider integration for later generation workflows.
- **Phase 6** — structured outline generation, review, editing, and approval.
- **Phase 7** — complete script generation from approved outlines.
- **Phase 8** — AI-assisted script revisions and append-only version history.
- **Phase 9** — structured quality evaluations for script versions.

Phases 1–9 describe the current backend implementation. The project is
backend-only; the separate `frontend/` directory is reserved for future work.

## Technology

- Python 3
- FastAPI
- Uvicorn (ASGI server)
- Pydantic and pydantic-settings (request validation and configuration)
- PostgreSQL
- SQLAlchemy
- Alembic
- JWT (`python-jose`)
- Password hashing (`passlib` + `bcrypt`)
- Gemini integration (`google-genai`)
- Docker and Docker Compose for containerized testing

## Directory structure

```
AiScriptWriter/
├── backend/
│   ├── app/
│   │   ├── api/routes/        # Authentication and creative-brief endpoints
│   │   ├── core/              # Settings and authentication/security helpers
│   │   ├── db/models/         # SQLAlchemy entities and relationships
│   │   ├── llm/               # Provider interface, factory, and Gemini client
│   │   ├── prompts/           # Prompt construction for each workflow step
│   │   ├── schemas/           # Pydantic API request/response models
│   │   ├── services/          # Database and workflow operations
│   │   ├── validators/        # Creative-brief semantic validation
│   │   └── main.py            # FastAPI app, middleware, and health checks
│   ├── alembic/               # Database migration environment and revisions
│   ├── scripts/               # Database schema verification utility
│   ├── tests/                 # unittest coverage for routes and services
│   ├── .venv/                 # Local virtual environment (not committed)
│   ├── .env                   # Local settings and secrets (not committed)
│   ├── .env.example
│   ├── .gitignore
│   ├── .dockerignore
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── alembic.ini
│   ├── requirements.txt
│   └── README.md
└── frontend/
    └── .gitkeep
```

## Local installation

```bash
python3 -m venv .venv
```

Activate it:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

Copy the example environment file and fill in your own secret key:

```bash
cp .env.example .env
```

Required variables:

| Variable | Required | Description |
| --- | --- | --- |
| `SECRET_KEY` | Yes | JWT signing secret; use a strong, private value. |
| `DATABASE_URL` | Yes | SQLAlchemy PostgreSQL URL; configure it in the local `.env` or deployment environment. |
| `GEMINI_API_KEY` | Only for Gemini features; required in production | Gemini API credential. |
| `APP_ENV` | No | `development` by default; set to `production` for production validation. |
| `DEBUG` | No | Defaults based on `APP_ENV`; must be false in production. |
| `ALGORITHM` | No | JWT algorithm, default `HS256`. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | JWT lifetime, default `30`. |
| `LLM_PROVIDER` | No | Provider name, default `gemini`. |
| `GEMINI_MODEL` | No | Gemini model, default `gemini-3.6-flash`. |
| `LLM_TIMEOUT_SECONDS` | No | Provider request timeout, default `30`. |
| `CORS_ALLOWED_ORIGINS` | Development: no; production: yes | Comma-separated frontend origins; production requires HTTPS origins. |
| `TRUSTED_HOSTS` | Development: no; production: yes | Comma-separated allowed Host header values. |
| `LOG_LEVEL` | No | Python log level, default `INFO`. |
| `POSTGRES_DB` | Docker Compose: no | Compose database name; defaults to `aiwriter`. |
| `POSTGRES_USER` | Docker Compose: no | Compose database user; defaults to `aiwriter`. |
| `POSTGRES_PASSWORD` | Docker Compose: yes | Private local database password; no default is provided. |

`SECRET_KEY` is required in every environment. Production additionally requires
a strong non-placeholder `SECRET_KEY`, `GEMINI_API_KEY`, an explicitly supplied
external PostgreSQL `DATABASE_URL`, HTTPS CORS origins, explicit trusted hosts,
and `DEBUG=false`. Keep all credentials in the deployment environment or a
secret manager, never in source control. The local `.env` remains the supported
development configuration file and is ignored by Git.

## Database migrations

Alembic is the only schema initialization/update mechanism; application startup
does not call `Base.metadata.create_all()`. The initial baseline includes all
Phase 1–9 models.

For a fresh, empty PostgreSQL database, set `DATABASE_URL` and run:

```bash
alembic upgrade head
```

For an existing database previously initialized with `create_all()`, do not run
the baseline upgrade against its existing tables. First take a verified backup
and check that the live schema exactly matches the baseline:

```bash
python -m scripts.check_schema
```

Only when the comparison reports an exact match, mark the existing schema as
already being at the baseline. This records migration state without creating,
dropping, or altering application tables or data:

```bash
alembic stamp 6484a3681cc9
alembic current
alembic check
```

If the schema comparison detects differences, stop and inspect/reconcile them
before stamping. The initial baseline is intentionally irreversible to guard
against an accidental downgrade deleting application data.

## Run locally

After applying migrations to the configured development database:

```bash
uvicorn app.main:app --reload
```

Run commands from inside `backend/`.

- API root: http://127.0.0.1:8000
- Swagger docs: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
- Liveness: http://127.0.0.1:8000/health/live (legacy `/health` is retained)
- Readiness (includes a database check): http://127.0.0.1:8000/health/ready

## Docker

Docker Compose is intended for local testing against a new, Compose-managed
PostgreSQL volume. Set `POSTGRES_PASSWORD` in the ignored local `.env` before
starting it; the password has no source-controlled default.

```bash
docker compose up --build
```

Check the Compose file without starting containers with:

```bash
docker compose config
```

Compose applies Alembic migrations before starting the API. Open
http://127.0.0.1:8000/docs. `docker compose down` stops containers but preserves
the named database volume. Do not use this Compose initialization flow to adopt
an existing database; follow the existing-database baseline procedure above.

Build the production image with:

```bash
docker build -t ai-script-writer-backend .
```

The image runs Uvicorn without reload as a non-root user and does not contain
`.env`. For a deployment, inject validated production settings through the
runtime environment, run `alembic upgrade head` once as a deployment step, then
start the image. `DATABASE_URL` can point to an external PostgreSQL service such
as a future AWS RDS instance; no AWS resources or proxy trust are configured by
this project preparation.

## Endpoints

| Method | Path                            | Description                          |
| ------ | ------------------------------- | ------------------------------------ |
| GET    | `/`                             | Confirms the API is running          |
| GET    | `/health`                       | Health check, returns `healthy`      |
| GET    | `/health/live`                   | Application liveness                 |
| GET    | `/health/ready`                  | Database-aware readiness             |
| POST   | `/api/v1/auth/signup`           | Create an account                    |
| POST   | `/api/v1/auth/login`            | Log in, returns a JWT                |
| GET    | `/api/v1/auth/me`               | Current user (requires Bearer token) |
| POST   | `/api/v1/creative-briefs`       | Create a creative brief              |
| GET    | `/api/v1/creative-briefs`       | List the user's creative briefs      |
| GET    | `/api/v1/creative-briefs/{id}`  | Get one creative brief               |
| PATCH  | `/api/v1/creative-briefs/{id}`  | Update a creative brief              |
| DELETE | `/api/v1/creative-briefs/{id}`  | Delete a creative brief              |
| POST   | `/api/v1/creative-briefs/{id}/prompt` | Preview a structured prompt (no LLM call) |
| POST   | `/api/v1/creative-briefs/{id}/outline` | Generate a structured outline |
| GET    | `/api/v1/creative-briefs/{id}/outline` | Get the current outline |
| PATCH  | `/api/v1/creative-briefs/{id}/outline` | Edit an unapproved outline |
| POST   | `/api/v1/creative-briefs/{id}/outline/approve` | Approve and lock an outline |
| POST   | `/api/v1/creative-briefs/{id}/script` | Generate a complete script from an approved outline |
| GET    | `/api/v1/creative-briefs/{id}/script` | Get the current script |
| PATCH  | `/api/v1/creative-briefs/{id}/script` | Apply a basic script correction |
| POST   | `/api/v1/creative-briefs/{id}/script/revisions` | Revise a script using Gemini and revision instructions |
| GET    | `/api/v1/creative-briefs/{id}/script/versions` | List script versions, oldest first |
| GET    | `/api/v1/creative-briefs/{id}/script/versions/{version_number}` | Retrieve a specific script version |
| POST   | `/api/v1/creative-briefs/{id}/script/versions/{version_number}/restore` | Restore old content as a new version |
| POST   | `/api/v1/creative-briefs/{id}/script/versions/{version_number}/evaluations` | Evaluate a specific script version |
| GET    | `/api/v1/creative-briefs/{id}/script/versions/{version_number}/evaluations` | List evaluations for a version, newest first |
| GET    | `/api/v1/creative-briefs/{id}/script/versions/{version_number}/evaluations/{evaluation_id}` | Retrieve one evaluation for a version |

Version history is append-only. Every revision or restore creates the next
sequential version and updates the current script. Restoring an older version
does not modify that version or remove later history. All script and version
endpoints require authentication and return `404` when the brief is not owned
by the authenticated user.

## Authentication

All authentication routes live under `/api/v1/auth/`.

### 1. Signup

```
POST /api/v1/auth/signup
```

Request body:

```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "password": "password123"
}
```

The password is hashed with bcrypt before storage and is never returned.
Responses only contain safe user fields (`id`, `name`, `email`, `created_at`).

If the email already exists, the API returns `409 Conflict`.

### 2. Login

```
POST /api/v1/auth/login
```

Request body:

```json
{
  "email": "john@example.com",
  "password": "password123"
}
```

Successful response:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

Invalid credentials return `401 Unauthorized`. The login response never
reveals the stored password hash.

### 3. JWT

`access_token` is a JWT with a `sub` claim set to the user id and an `exp`
claim. The token is signed using `SECRET_KEY` from `.env` and expires after
`ACCESS_TOKEN_EXPIRE_MINUTES`.

### 4. Protected endpoint — `/me`

```
GET /api/v1/auth/me
Authorization: Bearer <access_token>
```

Returns the currently authenticated user:

```json
{
  "id": 1,
  "name": "John Doe",
  "email": "john@example.com",
  "created_at": "2026-10-07T15:05:02Z"
}
```

Missing, invalid, tampered or expired tokens return `401 Unauthorized`.

### Example requests (curl)

```bash
# Signup
curl -X POST http://127.0.0.1:8000/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"name":"John Doe","email":"john@example.com","password":"password123"}'

# Login
curl -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"john@example.com","password":"password123"}'

# Me (replace the token)
curl http://127.0.0.1:8000/api/v1/auth/me \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

### Testing with Swagger

1. Open http://127.0.0.1:8000/docs
2. Call `POST /api/v1/auth/signup` to create an account.
3. Call `POST /api/v1/auth/login` and copy the returned `access_token`.
4. Click the **Authorize** button and paste the raw `access_token` value. Swagger
   UI adds the `Bearer ` prefix automatically for a bearer-type scheme.
5. Call `GET /api/v1/auth/me` — it will use the authorized token automatically.

## Creative Brief API

Creative briefs are the input that starts the script workflow. Every endpoint
requires a Bearer token, and every brief is owned by the authenticated user.

### Ownership & security

- The owner is always taken from the JWT (`get_current_user()`), never from the
  request body — an incoming `user_id` is ignored.
- A user can only **create, read, update and delete their own** briefs.
- Reading, updating or deleting another user's brief returns `404 Not Found`
  (the same response as a missing brief), so nothing leaks across users.

### Create a brief

```
POST /api/v1/creative-briefs
```

Required headers:

```
Authorization: Bearer <access_token>
Content-Type: application/json
```

Sample request:

```json
{
  "topic": "A student discovers that an abandoned hostel room is connected to several disappearances.",
  "genre": "Horror",
  "output_format": "Short Film / Screenplay",
  "language": "English",
  "tone": "Dark and suspenseful",
  "target_audience": "Young adults",
  "duration": "5 minutes",
  "characters": "Rahul, Aman, Hostel Warden",
  "setting": "College hostel at night",
  "key_points": "Discovery, investigation, supernatural revelation, final twist",
  "detail_level": "Detailed",
  "special_instructions": "Build suspense gradually and end with a strong twist."
}
```

The response contains the saved brief (with `id`, `created_at`, `updated_at`).
No AI/LLM call happens — the brief is only stored.

### List, get, update, delete

| Method | Path                           | Returns                          |
| ------ | ------------------------------ | -------------------------------- |
| GET    | `/api/v1/creative-briefs`      | List of the user's briefs        |
| GET    | `/api/v1/creative-briefs/{id}` | One brief (404 if not owned)     |
| PATCH  | `/api/v1/creative-briefs/{id}` | Updated brief (only provided fields are changed) |
| DELETE | `/api/v1/creative-briefs/{id}` | `{"message": "Creative brief deleted"}` |

`PATCH` accepts any subset of the create fields. Passing an invalid value
returns `422`.

### Prompt preview (Phase 5)

```
POST /api/v1/creative-briefs/{id}/prompt
Authorization: Bearer <access_token>
```

Returns provider-neutral `system_instructions` and separately delimited
`user_content` for the authenticated user's brief. Brief values are untrusted
data and cannot replace the system instructions. This endpoint never calls
Gemini and does not create an outline or script.

Gemini support is isolated behind `app.llm` for later generation phases; no
Phase 5 API route invokes the provider.

## Outline generation (Phase 6)

Outline generation combines the stored Creative Brief prompt with trusted
JSON-only outline instructions and calls the configured Gemini provider. The
result must contain a title, logline, and three to five acts; each act has a
title, summary, and one or more beats. Invalid model output is rejected and is
never saved.

All outline endpoints require a Bearer token and only work with briefs owned by
that user:

| Method | Path | Behavior |
| ------ | ---- | -------- |
| POST | `/api/v1/creative-briefs/{id}/outline` | Generates and saves the first outline (`201`). |
| GET | `/api/v1/creative-briefs/{id}/outline` | Retrieves the current outline. |
| PATCH | `/api/v1/creative-briefs/{id}/outline` | Replaces structured content before approval. |
| POST | `/api/v1/creative-briefs/{id}/outline/approve` | Approves and locks the outline. |

To replace an existing unapproved outline, send `{"regenerate": true}` to the
generate endpoint. A duplicate request without that explicit flag returns
`409`. Approved outlines cannot be edited or regenerated.

## Script generation (Phase 7)

Script generation requires an approved outline belonging to the authenticated
user. The provider receives separately delimited Creative Brief and approved
outline data, plus trusted instructions tailored to the selected output format:
YouTube / Long-form, Short Film / Screenplay, or Advertisement. Empty,
incomplete, or oversized provider responses are rejected before storage.

| Method | Path | Behavior |
| ------ | ---- | -------- |
| POST | `/api/v1/creative-briefs/{id}/script` | Generates and saves the first script (`201`). |
| GET | `/api/v1/creative-briefs/{id}/script` | Retrieves the current script. |
| PATCH | `/api/v1/creative-briefs/{id}/script` | Replaces script text for basic corrections. |

To replace an existing script, send `{"regenerate": true}` to the generate
endpoint. A duplicate request without that explicit flag returns `409`.
Regeneration never changes the approved outline. Script revisions and restores
are recorded as append-only script versions.

### Validation

- `genre` must be `Horror`, `Comedy` or `Drama`.
- `output_format` must be `YouTube / Long-form`, `Short Film / Screenplay` or
  `Advertisement`.
- `detail_level` must be `Concise`, `Standard` or `Detailed`.
- `topic` is required and cannot be blank/whitespace.
- Fields are trimmed of surrounding whitespace before storage.

### Example (curl)

```bash
# Login and take the token
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"john@example.com","password":"password123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Create a brief
curl -X POST http://127.0.0.1:8000/api/v1/creative-briefs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{...brief json...}'

# List briefs
curl http://127.0.0.1:8000/api/v1/creative-briefs -H "Authorization: Bearer $TOKEN"

# Update (PATCH)
curl -X PATCH http://127.0.0.1:8000/api/v1/creative-briefs/1 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tone": "Darker and slower burn"}'

# Delete
curl -X DELETE http://127.0.0.1:8000/api/v1/creative-briefs/1 \
  -H "Authorization: Bearer $TOKEN"
```

### Testing with Swagger

1. Authorize with a Bearer token (see the Authentication section).
2. Under the **Creative Briefs** tag, `POST /api/v1/creative-briefs` to create.
3. Use the returned `id` with the GET/PATCH/DELETE operations to view, edit and
   delete it.

## Tests

Tests use Python's built-in `unittest`, mocked LLM providers, and in-memory
SQLite databases; they do not make live Gemini requests. From `backend/`, run:

```bash
python -m compileall app tests
python -m unittest discover -s tests -v
python -m pip check
```

Never commit `.env`. It contains secrets including `SECRET_KEY` and, if
configured, `GEMINI_API_KEY`.
