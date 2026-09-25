# Next recommended steps for rainfall

This document captures the next engineering milestones after the initial backend scaffold.

## Status (2026-09-25)

Done:
- [x] SQLAlchemy models with constraints (`backend/app/db/models.py`)
- [x] Alembic migrations, initial schema `0001` (`backend/migrations/`)
- [x] API contract implemented with typed responses (section 3)
- [x] Railway-ready Docker: honours `$PORT`, runs migrations on start, non-root, `/health` checks DB
- [x] Config accepts Railway's `postgresql://` URL and comma-separated `CORS_ORIGINS`
- [x] Tests (`backend/tests/`, run on SQLite, no Postgres needed)
- [x] Railway web service deployed at https://rainfall-production.up.railway.app (health, DB and CORS verified)
- [x] FMI ingestion (`backend/app/ingest/`, `python -m app.ingest`), tested against live FMI on SQLite and Postgres

Next:
- [ ] Railway cron service for ingestion (see README)
- [ ] Station history endpoint for the detail panel, e.g. `GET /api/stations/{id}/history?start=&end=`
- [ ] Frontend in `frontend/` (Vite + Vue 3). `npm run build` outputs `frontend/dist/` with base `/test/rainfall/`, which is uploaded manually

### API contract as implemented

- `GET /health` → `{"status": "ok", "database": "ok"}` (503 if DB unreachable)
- `GET /api/latest-date` → `{"date": "YYYY-MM-DD"}` (404 if no data yet)
- `GET /api/stations?date=` → `{"date", "stations": [StationDay]}`. `date` is optional and defaults to the latest date. Returns the active stations FMI reported for that day. A station with a missing value is included with `has_data: false` (hollow circle). A station with no row for that day, e.g. one not yet opened or already closed, is left out.
- `GET /api/stations/{id}?date=` → `StationDay` (`id` is a UUID; 422 if malformed, 404 if unknown)
- `GET /api/dates?year=` → `{"dates": [...]}` newest first; only days with at least one real value
- `GET /api/years` → `{"years": [...]}` ascending

`StationDay` = `id, source_station_id, name, lat, lon, country, region, date, precipitation_mm, has_data`.

### Data rules enforced by the DB

- `has_data = true` ⇔ `precipitation_mm IS NOT NULL` (check constraint)
- `precipitation_mm >= 0`
- unique `(station_id, date)`; that index also covers lookups by `station_id`, so there is no separate one
- `raw_status` stores FMI's original value text, e.g. `-1.0`, `0.0`, `NaN` or `4.5`

### FMI data conventions (verified against the live API, 2026-09-25)

- Source: `fmi::observations::weather::daily::timevaluepair`, parameter `rrday`, bbox `19,59,32,71`. Station id is the FMI `fmisid`. `region` is FMI's municipality name.
- A value labelled date D covers 06 UTC on D to 06 UTC on D+1. We store it under D, the same date FMI uses. Checked against hourly sums at 5 stations.
- `-1.0` means no precipitation: stored as `0.0` mm with `has_data = true`. `0.0` means a trace (< 0.05 mm): stored as `0.0` mm with `has_data = true`. `NaN` means missing: stored as `NULL` with `has_data = false`.
- Coverage: about 189 stations since 2025, about 172 reporting per day. A full year for all stations comes back in one request (about 20 MB); ingestion uses 31-day chunks.

## 1. Add PostgreSQL and Railway environment

- Create a Railway project
- Add a PostgreSQL database
- Copy the generated `DATABASE_URL`
- Add these environment variables:
  - `DATABASE_URL`
  - `APP_ENV=production`
  - `PORT=8000`
  - `CORS_ORIGINS=https://isosavi.com,https://www.isosavi.com`
- Verify the backend responds on `/health`

## 2. Database schema and migrations

Create the schema for:
- `stations`
- `daily_precipitation`

Required columns:
- `stations.id`
- `stations.source_station_id`
- `stations.name`
- `stations.lat`
- `stations.lon`
- `stations.country`
- `stations.region`
- `stations.active`
- `stations.created_at`

- `daily_precipitation.id`
- `daily_precipitation.station_id`
- `daily_precipitation.date`
- `daily_precipitation.precipitation_mm`
- `daily_precipitation.has_data`
- `daily_precipitation.raw_status`
- `daily_precipitation.fetched_at`

Add indexes on:
- `daily_precipitation.date`
- `daily_precipitation.station_id`
- `(station_id, date)` unique key

## 3. Build the backend API contract

The backend should provide:
- `GET /health`
- `GET /api/latest-date`
- `GET /api/stations?date=YYYY-MM-DD`
- `GET /api/stations/{station_id}?date=YYYY-MM-DD`
- `GET /api/dates`
- `GET /api/years`

These are the minimum routes needed for the map and detail panel.

## 4. Implement the FMI ingestion service

Create a backend service for harvesting FMI rainfall data and normalizing it into the database.

Responsibilities:
- fetch latest available weather data
- map station metadata into `stations`
- insert or update daily precipitation rows
- store missing values as `has_data = false`
- deduplicate on `station_id + date`

## 5. Connect the frontend to the backend

Frontend should call the Railway backend, not FMI directly in production.

API contract should be normalized into UI-friendly objects:
- `id`
- `name`
- `lat`
- `lon`
- `country`
- `region`
- `precipitation_mm`
- `has_data`
- `date`

## 6. Frontend UX requirements

- map with station circles on a zoomable base map
- white hollow circles when no data exists
- colored circles based on precipitation amount
- clicking a station opens a right-side detail panel
- default view shows the most recent available date
- date selector and later year selector added as future UI features

## 7. Deployment checklist

When ready:
- deploy backend to Railway from GitHub repo `rainfall`
- use the Railway PostgreSQL service
- set `DATABASE_URL` and production envs
- verify `/health` works
- verify frontend can reach the backend API

## 8. Repository conventions

- Keep this repo as a clean private project named `rainfall`
- keep all technical notes in the repo itself
- use short, project-local docs rather than external notes
- keep backend, database, and deployment config in the repo for reproducibility

## 9. Recommended immediate action

Open the project in a new VS Code window and continue with:
1. PostgreSQL schema creation
2. migration setup
3. backend API routes for `/api/latest-date` and `/api/stations`
4. frontend API contract definition
5. FMI ingestion service design
