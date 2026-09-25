# rainfall

Private backend project for the FMI precipitation map app.

This repo is intended to be deployed to Railway as a backend service.

## Local project structure

- `backend/` — FastAPI backend
- `backend/app/` — application code
- `backend/requirements.txt` — Python dependencies
- `backend/Dockerfile` — Railway build image

## GitHub

Create a private GitHub repository named `rainfall` and push this repository to it.

## Local development

```sh
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest                      # runs on in-memory SQLite
alembic upgrade head        # against DATABASE_URL from .env
uvicorn app.main:app --reload
```

New migration after a model change: `alembic revision --autogenerate -m "..."`, then review the file.

## Railway

In the Railway service settings:
- Root Directory: `/backend`
- Config file path: `/backend/railway.json` (Railway does not look for it under the root directory)
- Variables: `DATABASE_URL=${{Postgres.DATABASE_URL}}`, `APP_ENV=production`, `CORS_ORIGINS=https://isosavi.com,https://www.isosavi.com`

Railway sets `PORT` itself. On start, `start.sh` runs `alembic upgrade head` and then uvicorn. The deploy healthcheck is `/health`, which also checks the DB connection.

## Environment

Copy `backend/.env.example` to `backend/.env` locally and fill in values as needed.
