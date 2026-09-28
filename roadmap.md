# Roadmap

Pending and possible future work. Completed items move to [roadmap-implemented.md](roadmap-implemented.md), with a timestamp.

## Now

- [ ] Estonia: check whether the agency's API pauses at weekends (no new data after 25 Sept 02 UTC, a Friday, as of Monday 28 Sept morning). If it's a pattern, say so in the About dialog.

## Next

- [ ] Year selector: browse by year, using `/api/years` and `/api/dates?year=`
- [ ] Finnish translation: all text is in `frontend/src/strings.ts`. Add a language switch.
- [ ] Longer history in the station panel, e.g. a month or year view (the API allows up to 366 days)
- [ ] Monitoring: get alerted when the ingestion job fails or data stops arriving, e.g. a check that the latest date is at most 2 days old
- [ ] Load older history if wanted: `python -m app.ingest --start YYYY-MM-DD`
- [ ] Custom domain for the API and MCP server, e.g. `weather.agents.isosavi.com`: add the domain in Railway, a CNAME record to Railway's target in the domain's DNS, then update `PUBLIC_BASE_URL` and the address in the README and About dialog (the docs check compares them). The Railway address keeps working, so saved connectors don't break.
- [ ] Phones: frame the map to the visible area between the top box and an open List / Top 15 sheet (now the sheet can cover the stations being ranked).

## Later / ideas

- Greenland snow depth from CARRA (Copernicus Arctic Regional Reanalysis, ~2.5 km), shown as a model estimate and clearly marked as such, since DMI publishes no Greenland snow depth. Check CARRA's publication delay (likely months; ERA5-Land ~1 week, coarser), the GRIB/NetCDF processing needs (xarray, cfgrib) and the attribution text. Any access key goes in a Railway variable and `backend/.env`, never the repo.

- Greenland snow depth: DMI publishes none (checked 2026-09-26, in both climateData and metObs). A possible source is Asiaq (Greenland's survey agency); check what it offers and its licence.

- Germany: official DWD Open Data https://www.dwd.de/EN/ourservices/opendata/opendata.html (climate data at opendata.dwd.de) and the open-source JSON API Bright Sky https://brightsky.dev/docs/#/ built on it. Prefer DWD as the source of record; check licence (believed CC BY 4.0), the daily rainfall window and snow depth.
- Naming: decided on 2026-09-27 to keep "Nordic weather observations" with Estonia. Revisit if Poland or Germany are added (e.g. "Northern Europe weather observations").
- MCP: submit the connector to Anthropic's connector directory (needs e.g. a privacy policy page and a support contact); consider temperature and snow in the MCP server name and a nicer address first.
- Poland: https://api.meteo.pl/ and https://github.com/mrcnpdlk/weather-api. Note: api.meteo.pl is, as far as known, ICM's (University of Warsaw) forecast-model API, which needs a key; station observations come from IMGW-PIB (https://danepubliczne.imgw.pl, free). Check which gives daily rainfall and snow depth per station, the day definition and licence.
- Lithuania: https://api.meteo.lt/ (LHMT, the official service). Check how far back station observations go (it may offer only recent hourly data, which we'd sum 06–06 UTC), licence, snow depth and station metadata.
- Latvia: open data at https://data.gov.lv/dati/lv/dataset/hidrometeorologiskie-noverojumi (LVĢMC hydrometeorological observations, the official source) and the community project https://github.com/kristapsbe/meteo_server (useful as a reference for parsing). Check licence, day definition, snow depth and station metadata as for the other countries.
- Estonia, more stations: the climate API has only the 25 weather stations. The agency's live XML feed (https://www.ilmateenistus.ee/ilma_andmed/xml/observations.php, 154 stations including precipitation stations, updated every 10 minutes) has no history, so those stations could only be collected from now on (store the hourly values and build days from them).
- Estonia, yearly corrections: the agency validates its climate data once a year, in the first quarter. Add a yearly job (like Sweden's monthly `--archive-refresh`) that re-fetches the previous year for `kaa`.

- Finnish terrain base map. Check whether the extra detail helps readability.
- Monthly and yearly totals per station, and a map view for them
- Move the frontend from `/test/rainfall/` to its final address, updating `VITE_BASE` and `CORS_ORIGINS`
