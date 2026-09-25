# Rainfall

Daily rainfall at Finnish weather stations on a map, based on FMI open data.

- **Backend:** FastAPI + PostgreSQL on Railway. It serves the API and loads FMI data once or twice a day.
- **Frontend:** Vue 3 + MapLibre + deck.gl. It's a static site, uploaded by hand to `/test/rainfall/` on isosavi.com.
- **API:** https://rainfall-production.up.railway.app (interactive docs at `/docs`)

Plans are in [roadmap.md](roadmap.md), and completed work is in [roadmap-implemented.md](roadmap-implemented.md).

**Feedback:** found a problem or have an idea? [Open an issue](https://github.com/jisosavi/rainfall/issues/new/choose) (you need a GitHub account).

## Structure

```
backend/
  app/api/routes/   HTTP endpoints
  app/db/           SQLAlchemy models and session
  app/ingest/       FMI ingestion (python -m app.ingest)
  migrations/       Alembic migrations
  tests/            pytest suite (runs on SQLite)
  Dockerfile, start.sh, railway.json
frontend/
  src/components/   map, legend, date control, station panel, list, about dialog
  src/api.ts        API types and queries
  src/strings.ts    all interface text (UK English)
  src/lib/rainScale.ts  rainfall colour classes
```

## Backend

```sh
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env        # then edit DATABASE_URL
pytest                      # in-memory SQLite, no database needed
alembic upgrade head
uvicorn app.main:app --reload
python -m app.ingest        # load FMI data
```

After a model change: `alembic revision --autogenerate -m "..."`. Review the generated file before committing it.

### Environment variables

| Variable | Used by | Notes |
|---|---|---|
| `DATABASE_URL` | web, ingest | On Railway: `${{Postgres.DATABASE_URL}}`. Both `postgresql://` and `postgres://` URLs are accepted. |
| `CORS_ORIGINS` | web | Comma-separated, e.g. `https://isosavi.com,https://www.isosavi.com` |
| `PORT` | web | `8000`. It must match the target port of the Railway domain. |
| `APP_ENV` | web | `production` on Railway. Not used by the code yet. |
| `INGEST_START_DATE` | ingest | First date loaded into an empty database. Default `2025-01-01`. |
| `INGEST_REFETCH_DAYS` | ingest | Recent days re-fetched on every run. Default `10`. |

## Deployment (Railway)

One project with three services:

- **Postgres:** the Railway PostgreSQL service.
- **rainfall (web):**
  - Root Directory `/backend`
  - Config file `/backend/railway.json`. Railway doesn't look for it under the root directory, so the full path must be set.
  - Variables: `DATABASE_URL`, `CORS_ORIGINS`, `PORT`, `APP_ENV`
  - On start, the service runs the migrations, then uvicorn. The deploy healthcheck is `/health`, which also checks the database.
- **rainfall-ingest (cron):**
  - Root Directory `/backend`, no config file and no healthcheck
  - Start Command `python -m app.ingest`
  - Cron Schedule `15 7,13 * * *` (UTC)
  - Restart Policy Never
  - Variable: `DATABASE_URL`

Pushing to `main` redeploys both services.

## Frontend

```sh
cd frontend
npm install
npm run dev      # http://localhost:5173/test/rainfall/  (/api is proxied to the Railway backend)
npm run build    # type-checks, then writes frontend/dist/
```

**Deploying:** upload the *contents* of `frontend/dist/` to `/test/rainfall/` on the web server. It's a single static page, so no server rewrites are needed.

**Settings:** configured in `frontend/.env.production`:
- `VITE_API_URL`: the backend URL
- `VITE_BASE`: the path the site is served from

If the site moves to a new path, change `VITE_BASE`. If it moves to a new domain, also add that origin to the backend's `CORS_ORIGINS`.

**Local backend:** to run the dev server against a local backend, use `DEV_API_PROXY=http://localhost:8000 npm run dev`.

## API

| Endpoint | Returns |
|---|---|
| `GET /health` | `{"status": "ok", "database": "ok"}`, or 503 if the database is unreachable |
| `GET /api/latest-date` | `{"date"}`: the latest date with at least one value (404 if there is no data) |
| `GET /api/stations?date=` | `{"date", "stations": [StationDay]}`. `date` defaults to the latest date. |
| `GET /api/stations/{id}?date=` | `StationDay` |
| `GET /api/stations/{id}/history?start=&end=` | `{"station_id", "start", "end", "values": [{date, precipitation_mm, has_data}]}`. Defaults to the 30 days ending at the latest date. Maximum 366 days. |
| `GET /api/dates?year=` | `{"dates"}`, newest first |
| `GET /api/years` | `{"years"}`, ascending |

`StationDay` has these fields: `id` (UUID), `source_station_id` (FMI fmisid), `name`, `lat`, `lon`, `country`, `region`, `date`, `precipitation_mm`, `has_data`.

`/api/stations` returns the stations FMI reported for that day. A station with a missing value is included with `has_data: false`, and the map shows it as a hollow circle. A station that wasn't operating that day is left out.

## FMI data conventions

These were verified against the live API on 2026-09-25.

- **Source:** WFS stored query `fmi::observations::weather::daily::timevaluepair`, parameter `rrday`, bbox `19,59,32,71`. `region` is FMI's municipality name.
- **Date:** a value labelled date D covers **06 UTC on D to 06 UTC on D+1**. It's stored under D, the same date FMI uses. So yesterday's value exists only after 06 UTC today.
- **Values:**

  | FMI value | Meaning | Stored as |
  |---|---|---|
  | `-1.0` | no precipitation | `0.0` mm, `has_data = true` |
  | `0.0` | trace (< 0.05 mm) | `0.0` mm, `has_data = true` |
  | `NaN` | missing | `NULL`, `has_data = false` |

  The original FMI text is kept in `raw_status`.
- **Database rules:**
  - `has_data` is true exactly when `precipitation_mm` has a value (check constraint)
  - `precipitation_mm >= 0`
  - `(station_id, date)` is unique
- **Coverage:** about 189 stations since 2025, with about 172 reporting on a given day.
- **Licence:** FMI open data is CC BY 4.0. The credit is shown in the map attribution and in the About dialog.
