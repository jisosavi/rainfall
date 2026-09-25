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

- Finnish terrain base map (an API key is available). Check whether the extra detail helps readability.
- Monthly and yearly totals per station, and a map view for them
- Move the frontend from `/test/rainfall/` to its final address, updating `VITE_BASE` and `CORS_ORIGINS`
