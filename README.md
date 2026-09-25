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

Set `PORT=8000` as well, and use 8000 as the target port when generating the public domain. On start, `start.sh` runs `alembic upgrade head` and then uvicorn. The deploy healthcheck is `/health`, which also checks the DB connection.

## Environment

Copy `backend/.env.example` to `backend/.env` locally and fill in values as needed.

## FMI ingestion

`python -m app.ingest` loads FMI daily precipitation into the database:
- **Empty database:** loads everything from `INGEST_START_DATE` (default `2025-01-01`) to yesterday. This takes about 15 seconds.
- **Otherwise:** re-fetches the last `INGEST_REFETCH_DAYS` days (default 10), because FMI revises recent values.
- **Manual range:** `python -m app.ingest --start 2020-01-01 --end 2020-12-31`.

Runs are safe to repeat: each station and date is stored once and updated on later runs.

### Railway cron service

Add a second service to the same Railway project: + New → GitHub Repo → `rainfall`. Name it e.g. `rainfall-ingest`. In its settings:
- Root Directory: `/backend`
- Leave the config-as-code file path empty. The web service's `/health` healthcheck does not apply to a job that exits.
- Custom Start Command: `python -m app.ingest`
- Cron Schedule: `15 7,13 * * *`. The schedule is in UTC. Yesterday's value is complete after 06 UTC.
- Restart policy: Never
- Variables: `DATABASE_URL=${{Postgres.DATABASE_URL}}`

The first run finds the database empty and loads the full history.
