# Roadmap

Pending and possible future work. Completed items move to [roadmap-implemented.md](roadmap-implemented.md), with a timestamp.

## Now

- [ ] Upload `frontend/dist/` to isosavi.com at `/test/rainfall/` and check it against the production API

## Next

- [ ] Year selector: browse by year, using `/api/years` and `/api/dates?year=`
- [ ] Finnish translation: all text is in `frontend/src/strings.ts`. Add a language switch.
- [ ] Longer history in the station panel, e.g. a month or year view (the API allows up to 366 days)
- [ ] Monitoring: get alerted when the ingestion job fails or data stops arriving, e.g. a check that the latest date is at most 2 days old
- [ ] Load older history if wanted: `python -m app.ingest --start YYYY-MM-DD`

## Later / ideas

- Denmark (DMI open data). Checked 2026-09-25:
  - API: `https://opendataapi.dmi.dk` (docs: https://www.dmi.dk/friedata/dokumentation/basics). No key since 2 December 2025; fair use 500 requests per 5 s. `dmi.cma.dk` is a third-party proxy and `dmigw.govcloud.dk` is the old keyed host; use neither.
  - DMI's daily `acc_precip` (climateData) covers Danish calendar days (local midnight to midnight), not 06–06 UTC. Plan: sum the hourly climateData `acc_precip` from 06 UTC to 06 UTC ourselves, and mark a day missing unless all 24 hours are present.
  - About 117 stations with precipitation, all with complete hourly data; most hourly values are manually quality-checked. The station list includes the owner and type; Greenland (127) and the Faroe Islands (22) are also available.
- Iceland (Veðurstofa Íslands, IMO). Checked 2026-09-25:
  - API: `https://api.vedur.is/weather` (OpenAPI spec at `/weather/openapi.json`). No registration or key. Licence CC BY 4.0, terms at https://athuganir.vedur.is/disclaimer?lng=en. The climatology pages (en.vedur.is/climatology/data) only have monthly and yearly totals.
  - 343 active stations with owner and WIGOS ID: 297 automatic (`sj`), 38 manual precipitation stations (`ur`), 8 manned (`sk`). Not all automatic stations have a rain gauge; count them first.
  - Manual stations report 24 h totals at 09 UTC (09–09 UTC), which can't be converted to our 06–06 UTC day. Plan: sum hourly precipitation (`r`) from automatic stations from 06 to 06 UTC; decide separately whether to leave out the 09 UTC stations or show them marked.

- Finnish terrain base map (an API key is available). Check whether the extra detail helps readability.
- Monthly and yearly totals per station, and a map view for them
- Move the frontend from `/test/rainfall/` to its final address, updating `VITE_BASE` and `CORS_ORIGINS`
