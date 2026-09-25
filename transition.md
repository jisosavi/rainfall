# Rainfall project transition

This repository is the new home for the rainfall project.

## Project name
- Repository: `rainfall`
- Local folder: `/Users/jki/Documents/Visual Code/rainfall`

## Purpose
Build a rainfall dashboard for Finnish weather stations based on FMI data, with a map view and a detail panel for each station.

## Stack
- Frontend: Vue 3 + TypeScript
- State: Pinia
- Data fetching: TanStack Query
- Map: MapLibre + deck.gl
- Backend: FastAPI
- Database: PostgreSQL on Railway
- Infra: Railway

## Current status
- Local repo created and initialized
- backend scaffold started
- project renamed from the earlier `sademaarat` naming

## Intended architecture
- Frontend reads data from the Railway backend API
- Backend reads from PostgreSQL
- FMI data is ingested into the DB by the backend service
- frontend never calls FMI directly in production

## Deployment goals
- GitHub repo: private `rainfall`
- Backend deploy: Railway
- Database: Railway PostgreSQL
- Frontend: deployed separately on test server with a base path like `/test/rainfall/`

## Environment variables
Required in backend deployment:
- `DATABASE_URL`
- `APP_ENV=production`
- `PORT=8000`
- `CORS_ORIGINS=https://isosavi.com,https://www.isosavi.com`

## Next milestones
1. finalize backend scaffold
2. create DB models and migration schema
3. add API endpoints for latest date and station data
4. connect frontend to backend API
5. build FMI ingestion job
6. deploy backend to Railway
7. deploy frontend to server

## Notes
This transition document is intentionally short and is kept inside the repository so it travels with the project.
