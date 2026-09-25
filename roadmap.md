# Roadmap

Pending and possible future work. Completed items move to [roadmap-implemented.md](roadmap-implemented.md), with a timestamp.

## Now

- [ ] Upload `frontend/dist/` to isosavi.com at `/test/rainfall/` and check it against the production API

## Next

- [ ] Top 15 rankings, as a "List | Top 15" switch in the left column; uses the existing measurement, country and date controls:
  - Rainfall: totals for Week / Month / Year (up to the shown date) and rolling Last 30 days
  - Snow depth: Now, Winter (deepest since 1 October), Winter (days with snow cover)
  - Coverage rule: by default only stations with data on at least 90% of the period's days, with a switch to show all; each row shows its coverage (e.g. 29/30 days)
  - Rank numbers next to the top 15 on the map; clicking a row opens the station
  - Backend: `GET /api/rankings?parameter=&period=&date=&country=&limit=15&min_coverage=`

- [ ] Year selector: browse by year, using `/api/years` and `/api/dates?year=`
- [ ] Finnish translation: all text is in `frontend/src/strings.ts`. Add a language switch.
- [ ] Longer history in the station panel, e.g. a month or year view (the API allows up to 366 days)
- [ ] Monitoring: get alerted when the ingestion job fails or data stops arriving, e.g. a check that the latest date is at most 2 days old
- [ ] Load older history if wanted: `python -m app.ingest --start YYYY-MM-DD`

- [ ] Iceland (IMO). Decided 2026-09-25: rainfall from automatic stations only (hourly values summed 06–06 UTC); manual 09 UTC stations used for snow depth only. Add it to the country filter (zooms to Iceland).

## Later / ideas

- Germany: official DWD Open Data https://www.dwd.de/EN/ourservices/opendata/opendata.html (climate data at opendata.dwd.de) and the open-source JSON API Bright Sky https://brightsky.dev/docs/#/ built on it. Prefer DWD as the source of record; check licence (believed CC BY 4.0), the daily rainfall window and snow depth.
- Naming: with the Baltics, Poland and Germany the app would no longer be only "Nordic"; decide on a title (e.g. "Northern Europe weather observations") before adding them.
- Poland: https://api.meteo.pl/ and https://github.com/mrcnpdlk/weather-api. Note: api.meteo.pl is, as far as known, ICM's (University of Warsaw) forecast-model API, which needs a key; station observations come from IMGW-PIB (https://danepubliczne.imgw.pl, free). Check which gives daily rainfall and snow depth per station, the day definition and licence.
- Lithuania: https://api.meteo.lt/ (LHMT, the official service). Check how far back station observations go (it may offer only recent hourly data, which we'd sum 06–06 UTC), licence, snow depth and station metadata.
- Latvia: open data at https://data.gov.lv/dati/lv/dataset/hidrometeorologiskie-noverojumi (LVĢMC hydrometeorological observations, the official source) and the community project https://github.com/kristapsbe/meteo_server (useful as a reference for parsing). Check licence, day definition, snow depth and station metadata as for the other countries.
- Estonia: weather observations API at https://nordapi.ee/docs/estonia/ee-weather-observations. First confirm who runs it and its licence (the official source is the Estonian Environment Agency, Keskkonnaagentuur / ilmateenistus.ee), then check day definition, snow depth and station metadata as for the other countries.

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
