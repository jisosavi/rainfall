# Implemented

Completed work, newest first. Times are Finnish time (EEST, UTC+3). Pending work is in [roadmap.md](roadmap.md).

| When | What | Commit |
|---|---|---|
| 2026-09-25 12:19 | Norway added: MET Norway (Frost API) stations for mainland Norway, Svalbard and Jan Mayen, about 707 stations. Dates aligned to FMI's 06–06 UTC day, verified against hourly data and cross-border neighbours. Country filter (All / Finland / Norway), FI/NO tags, circles that scale with zoom, start view framing both countries. Database: `stations.source` (migration 0002). | Add MET Norway stations |
| 2026-09-25 11:54 | Weather-map colour scale: white (dry) → light blue → blue → yellow → orange → red (20 mm or more), checked for colour-blind separation. The 30-day chart bars use the same colours. | Use a weather-map colour scale for rainfall |
| 2026-09-25 | Code licensed under GPL-3.0-or-later (`LICENSE`). Repository made public. Feedback through GitHub Issues, with feedback and bug report templates, linked from the About dialog. Documentation cleaned up; roadmap split into this file and `roadmap.md`. | Prepare for public repo |
| 2026-09-25 11:32 | Station history endpoint live in production | — |
| 2026-09-25 11:31 | Frontend (`frontend/`): map with rainfall colour classes and hollow no-data circles, date navigation, station panel with a 30-day chart, station list, About dialog, shareable links. Backend: `GET /api/stations/{id}/history`. | Add frontend map app |
| 2026-09-25 10:45 | First production data load by the Railway cron job `rainfall-ingest` (07:15 and 13:15 UTC): 632 dates from 2025-01-01, 172 stations a day | — |
| 2026-09-25 10:28 | FMI ingestion `python -m app.ingest`: backfill on an empty database, re-fetch of the last 10 days, safe to repeat. FMI data conventions verified against the live API. | Add FMI daily precipitation ingestion |
| 2026-09-25 ~10:15 | Railway web service and PostgreSQL deployed at https://rainfall-production.up.railway.app; `/health`, database and CORS verified | — |
| 2026-09-25 10:05 | Backend foundation: FastAPI API, SQLAlchemy models with constraints, Alembic migrations, Railway-ready Docker, tests | Backend scaffold |
