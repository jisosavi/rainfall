# Implemented

Completed work, newest first. Times are Finnish time (EEST, UTC+3). Pending work is in [roadmap.md](roadmap.md).

| When | What | Commit |
|---|---|---|
| 2026-09-25 13:49 | Snow depth for Finland (FMI, from 2025): Rainfall / Snow depth switch (snow is the default November–February), snow colour scale, station panel with both measurements and a winter snow-depth chart (deepest this winter, days with snow cover). Renamed to "Nordic weather observations". Database: `daily_precipitation` became `daily_values` with a `parameter` column (migration 0004); API takes `parameter`. | Add snow depth for Finland |
| 2026-09-25 13:25 | About dialog: wider, with a Data section (table of providers: country, provider link, station count on the shown date, licence link), an Updates section (fetch times in UTC and the viewer's time, table of new values and corrections per country) and a Project section (developer, source code, code licence GPL-3.0-or-later, feedback). | About dialog with data table |
| 2026-09-25 12:53 | Sweden added: SMHI stations (about 686, including municipal networks and the armed forces), with the station owner shown in the panel, also for MET Norway. SMHI dates already match FMI's; verified against hourly data and against Finnish and Norwegian neighbours. Monthly `--archive-refresh` job replaces preliminary values with SMHI's corrected archive. Renamed to "Nordic rainfall"; Sweden in the country filter. Database: `stations.owner` (migration 0003). | Add SMHI stations for Sweden |
| 2026-09-25 12:19 | Norway added: MET Norway (Frost API) stations for mainland Norway, Svalbard and Jan Mayen, about 707 stations. Dates aligned to FMI's 06–06 UTC day, verified against hourly data and cross-border neighbours. Country filter (All / Finland / Norway), FI/NO tags, circles that scale with zoom, start view framing both countries. Database: `stations.source` (migration 0002). | Add MET Norway stations |
| 2026-09-25 11:54 | Weather-map colour scale: white (dry) → light blue → blue → yellow → orange → red (20 mm or more), checked for colour-blind separation. The 30-day chart bars use the same colours. | Use a weather-map colour scale for rainfall |
| 2026-09-25 | Code licensed under GPL-3.0-or-later (`LICENSE`). Repository made public. Feedback through GitHub Issues, with feedback and bug report templates, linked from the About dialog. Documentation cleaned up; roadmap split into this file and `roadmap.md`. | Prepare for public repo |
| 2026-09-25 11:32 | Station history endpoint live in production | — |
| 2026-09-25 11:31 | Frontend (`frontend/`): map with rainfall colour classes and hollow no-data circles, date navigation, station panel with a 30-day chart, station list, About dialog, shareable links. Backend: `GET /api/stations/{id}/history`. | Add frontend map app |
| 2026-09-25 10:45 | First production data load by the Railway cron job `rainfall-ingest` (07:15 and 13:15 UTC): 632 dates from 2025-01-01, 172 stations a day | — |
| 2026-09-25 10:28 | FMI ingestion `python -m app.ingest`: backfill on an empty database, re-fetch of the last 10 days, safe to repeat. FMI data conventions verified against the live API. | Add FMI daily precipitation ingestion |
| 2026-09-25 ~10:15 | Railway web service and PostgreSQL deployed at https://rainfall-production.up.railway.app; `/health`, database and CORS verified | — |
| 2026-09-25 10:05 | Backend foundation: FastAPI API, SQLAlchemy models with constraints, Alembic migrations, Railway-ready Docker, tests | Backend scaffold |
