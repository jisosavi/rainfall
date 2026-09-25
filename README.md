# Nordic rainfall

Daily rainfall at weather stations in Finland, Norway and Sweden on a map, based on open data from FMI, MET Norway and SMHI.

- **Backend:** FastAPI + PostgreSQL on Railway. It serves the API and loads FMI, MET Norway and SMHI data twice a day.
- **Frontend:** Vue 3 + MapLibre + deck.gl. It's a static site, uploaded by hand to `/test/rainfall/` on isosavi.com.
- **API:** https://rainfall-production.up.railway.app (interactive docs at `/docs`)

Plans are in [roadmap.md](roadmap.md), and completed work is in [roadmap-implemented.md](roadmap-implemented.md).

**Feedback:** found a problem or have an idea? [Open an issue](https://github.com/jisosavi/rainfall/issues/new/choose) (you need a GitHub account).

## Structure

```
backend/
  app/api/routes/   HTTP endpoints
  app/db/           SQLAlchemy models and session
  app/ingest/       ingestion: fmi.py (Finland), met.py (Norway), smhi.py (Sweden), service.py (shared)
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
python -m app.ingest        # load data; --source fmi|met|smhi|all (default all)
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
| `SMHI_ARCHIVE_REFRESH_DAYS` | ingest | Days re-loaded by `--archive-refresh`. Default `130`. |
| `FROST_CLIENT_ID` | ingest | MET Norway Frost client ID ([register free](https://frost.met.no/auth/requestCredentials.html)). Without it, MET is skipped. The client secret is not needed. Never commit it. |

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
  - Variables: `DATABASE_URL`, `FROST_CLIENT_ID`
- **rainfall-ingest-archive (cron, monthly):** replaces SMHI's preliminary values with its corrected archive.
  - Same settings as rainfall-ingest, except:
  - Start Command `python -m app.ingest --source smhi --archive-refresh`
  - Cron Schedule `0 8 3 * *` (08:00 UTC on the 3rd of each month)
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

`StationDay` has these fields: `id` (UUID), `source` (`fmi`, `met` or `smhi`), `source_station_id` (FMI fmisid, Frost id such as `SN18700`, or SMHI station number), `name`, `lat`, `lon`, `country` (`FI`, `NO`, `SJ` for Svalbard and Jan Mayen, or `SE`), `region`, `owner` (organisation running the station, when known), `date`, `precipitation_mm`, `has_data`.

`/api/stations` returns the stations FMI reported for that day. A station with a missing value is included with `has_data: false`, and the map shows it as a hollow circle. A station that wasn't operating that day is left out.

## Data conventions

Every stored date D means the same 24 hours in every country: **06 UTC on D to 06 UTC on D+1**.

### FMI (Finland)

These were verified against the live API on 2026-09-25.

- **Source:** WFS stored query `fmi::observations::weather::daily::timevaluepair`, parameter `rrday`, bbox `19,59,32,71`. `region` is FMI's municipality name.
- **Date:** a value labelled date D covers 06 UTC on D to 06 UTC on D+1. It's stored under D, the same date FMI uses. So yesterday's value exists only after 06 UTC today.
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

### MET Norway (Norway, Svalbard, Jan Mayen)

These were verified against the live API on 2026-09-25.

- **Source:** Frost API, element `sum(precipitation_amount P1D)`, `timeoffsets=PT6H`. Series ending at 18 UTC (`PT18H`) cover a different window and are not used. Frost also lists stations abroad; only `NO` and `SJ` are kept.
- **Date:** Frost labels a value by the day its window **ends**: label D covers 06 UTC on D-1 to 06 UTC on D. **It's stored under D-1.** This was checked two ways: against hourly sums at 5 stations, and against Finnish neighbours near the border, which agree best with this alignment (0.9 mm average difference, against about 2.4 mm one day off).
- **Values:** Frost already turns "no precipitation" (`-1`) into `0.0`. Quality codes 0–4 are kept; 5 and above are treated as missing. Frost has no missing-value marker, so a day without a value becomes a `has_data = false` row. `raw_status` holds the value and quality code, e.g. `14.9|q0`, or `missing`.
- **Names:** Frost's upper-case names are shown in normal capitalisation, e.g. "Oslo - Blindern". `region` is the municipality, or the county if there's no municipality.
- **Coverage:** about 707 stations with data in 2026, about 610 reporting on a given day.

### SMHI (Sweden)

These were verified against the live API on 2026-09-25.

- **Source:** SMHI Open Data Meteorological Observations, parameter `5` ("Nederbördsmängd, summa 1 dygn, kl 06"). No registration is needed. There's no all-stations query, so data is fetched per station, 4 requests at a time.
- **Date:** each value has explicit from/to times and a representative day (`ref`), which is the day the window starts, the same as FMI. It's stored as-is. Checked against hourly sums at 5 stations.
- **Periods:** `latest-months` (JSON, about the last 4 months) and `corrected-archive` (CSV, quality-controlled history up to about 3 months ago). The archive is used automatically for older ranges, and monthly by `--archive-refresh`, whose corrected values replace the preliminary ones.
- **Values:** quality `G` (checked) and `Y` (suspicious, or newest and not yet checked) are kept; anything else is treated as missing. `raw_status` holds value and quality, e.g. `4.2|G`. Missing days become `has_data = false` rows.
- **Stations:** SMHI's own plus other owners (municipal networks such as VA Syd, the armed forces), with the owner stored. Names are kept as SMHI writes them, including suffixes such as `A` (automatic). SMHI gives no municipality.

### Licences

FMI, MET Norway and SMHI open data are all CC BY 4.0 (MET Norway also under NLOD 2.0). All three are credited in the map attribution and in the About dialog. Because we process the data (quality filtering, date alignment, missing-day rows), the About dialog says so, as SMHI's terms require.

## Licence

Copyright © 2026 Janne Isosävi

The code is licensed under the [GNU General Public License v3.0 or later](LICENSE). You may use, change and share it, but versions you distribute must stay under the same licence and include their source code.

The rainfall data comes from the Finnish Meteorological Institute, MET Norway and SMHI and is licensed separately under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Credit them when you use it.
