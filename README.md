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

LLM integration, script generation, evaluation and revision will come in later
phases.

This repository is **backend-only**. The previous frontend application has been
removed; the project currently consists solely of this FastAPI backend.

## Technology

- Python 3
- FastAPI
- Uvicorn (ASGI server)
- PostgreSQL
- SQLAlchemy
- JWT (`python-jose`)
- Password hashing (`passlib` + `bcrypt`)

## Directory structure

```
AiScript/
└── backend/
    ├── app/
    │   ├── main.py            # FastAPI app entry point, public / and /health
    │   ├── api/
    │   │   ├── __init__.py    # api_router (combines the routers below)
    │   │   └── routes/
    │   │       ├── auth.py            # signup, login, /me
    │   │       └── creative_briefs.py # creative brief CRUD
    │   ├── core/
    │   │   ├── config.py      # env-driven settings (SECRET_KEY, DATABASE_URL...)
    │   │   └── security.py    # hashing, JWT, get_current_user()
    │   ├── db/
    │   │   ├── base.py        # engine, SessionLocal, Base, get_db()
    │   │   └── models/
    │   │       ├── user.py
    │   │       └── creative_brief.py
    │   ├── schemas/           # Pydantic request/response models
    │   ├── services/          # business/database logic
    │   └── validators/        # semantic validation (genres, lengths, etc.)
    ├── venv/                  # local virtual environment (not committed)
    ├── requirements.txt
    ├── .env                   # local secrets (not committed)
    ├── .env.example
    ├── .gitignore
    └── README.md
```

## Setup

Create a virtual environment:

```bash
python3 -m venv venv
```

Activate it:

```bash
# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
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

| Variable                    | Description                          |
| --------------------------- | ------------------------------------ |
| `SECRET_KEY`                | Secret used to sign JWTs (keep safe) |
| `ALGORITHM`                 | JWT algorithm, default `HS256`       |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime, default `30`       |
| `DATABASE_URL`              | PostgreSQL connection string         |

Create the PostgreSQL database (matching `DATABASE_URL`):

```bash
createdb -O aiwriter aiwriter   # example: role aiwriter, db aiwriter
```

Tables are created automatically on server startup. (Alembic migrations come
in a later phase.)

## Run the server

```bash
uvicorn app.main:app --reload
```

Run from inside the `backend/` directory.

- API root: http://127.0.0.1:8000
- Swagger docs: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
- Health check: http://127.0.0.1:8000/health

## Endpoints

| Method | Path                            | Description                          |
| ------ | ------------------------------- | ------------------------------------ |
| GET    | `/`                             | Confirms the API is running          |
| GET    | `/health`                       | Health check, returns `healthy`      |
| POST   | `/api/v1/auth/signup`           | Create an account                    |
| POST   | `/api/v1/auth/login`            | Log in, returns a JWT                |
| GET    | `/api/v1/auth/me`               | Current user (requires Bearer token) |
| POST   | `/api/v1/creative-briefs`       | Create a creative brief              |
| GET    | `/api/v1/creative-briefs`       | List the user's creative briefs      |
| GET    | `/api/v1/creative-briefs/{id}`  | Get one creative brief               |
| PATCH  | `/api/v1/creative-briefs/{id}`  | Update a creative brief              |
| DELETE | `/api/v1/creative-briefs/{id}`  | Delete a creative brief              |

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

There is currently **no automated test suite** in this repository, so there is
no test command to run yet. When tests are added they will live in a `tests/`
directory and be run with:

```bash
pytest
```

Until then, the API can be exercised manually via Swagger UI or `curl` (see the
examples above).

Never commit `.env`. It contains your `SECRET_KEY`.