# AI Script Writer

AI Script Writer is a generative-AI application for turning creative ideas
into structured scripts through an outline-first workflow. The current
implementation is a FastAPI backend; the frontend directory is reserved for
future React and Tailwind CSS development.

## Project structure

```text
AiScriptWriter/
├── backend/
│   ├── app/             # FastAPI application and business logic
│   ├── alembic/         # Database migrations
│   ├── scripts/         # Backend maintenance scripts
│   ├── tests/           # Backend tests
│   ├── requirements.txt
│   └── README.md        # Backend setup, configuration, and API details
└── frontend/
    └── .gitkeep         # Reserved for future frontend development
```

The backend has its own detailed setup, configuration, migration, Docker, and
API instructions in [`backend/README.md`](backend/README.md). Run backend
commands from the `backend/` directory.

## Local backend setup

From the project root:

```bash
cd backend
# If a venv exists from before relocating this project, preserve it as .venv
# until the replacement environment is installed and verified.
mv venv .venv
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
```

The checked-in commands assume there is an existing `venv/` to preserve. On a
fresh checkout, omit the `mv` command. Keep the old `.venv/` until the new
environment has been verified.

Configure local settings in `backend/.env`; use `backend/.env.example` as a
reference. Do not commit `.env` or other credentials.

## Frontend

The `frontend/` directory is intentionally only a placeholder. React and
Tailwind CSS have not been initialized.
