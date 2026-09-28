import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from pathlib import Path

from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.routes.health import router as health_router
from app.api.routes.rankings import router as rankings_router
from app.api.routes.stations import router as stations_router
from app.config import get_settings
from app.limits import LimitExceeded, RestLimiter, client_ip
from app.mcp_server.server import http_app as mcp_http_app
from app.mcp_server.server import mcp, public_mcp_url
from app.mcp_server.usage import usage
from app.services.errors import InvalidRequestError, NotFoundError

settings = get_settings()

# App log lines (e.g. MCP calls) to stdout: Railway shows everything on stderr as errors.
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
logging.getLogger("app").addHandler(_handler)
logging.getLogger("app").setLevel(logging.INFO)
logging.getLogger("app").propagate = False

mcp_app = mcp_http_app()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # The MCP session manager runs for the app's lifetime.
    async with mcp.session_manager.run():
        yield
    usage.flush()  # store the last minute's MCP call counts


app = FastAPI(
    title="Nordic weather observations API",
    version="0.2.0",
    description="Daily rainfall, snow depth and temperature at Nordic and Estonian weather stations. "
    "For AI agents there is also an MCP server at /mcp.",
    lifespan=lifespan,
)

rest_limiter = RestLimiter(settings.rest_ip_per_minute)


@app.middleware("http")
async def limit_rest_api(request: Request, call_next):
    # A generous per-IP limit on the REST API (the web app itself stays far below it).
    if request.url.path.startswith("/api/"):
        try:
            rest_limiter.check(client_ip(request.headers, request.client.host if request.client else None))
        except LimitExceeded as exc:
            return JSONResponse(status_code=429, content={"detail": str(exc)}, headers={"Retry-After": str(exc.retry_after)})
    return await call_next(request)


# /api/stations returns ~900 stations; compress JSON responses.
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)



# The shared queries raise these; REST answers 404 / 422 with FastAPI's usual {"detail": …}.
@app.exception_handler(NotFoundError)
def _not_found(_: Request, exc: NotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(InvalidRequestError)
def _invalid(_: Request, exc: InvalidRequestError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


app.include_router(health_router)
app.include_router(stations_router)
app.include_router(rankings_router)


@app.get("/")
def root():
    return {"message": "Nordic weather observations API", "docs": "/docs", "mcp": public_mcp_url(), "llms_txt": "/llms.txt"}


STATIC = Path(__file__).parent / "static"


# The raindrop icon (as in the web app), for browsers and for MCP clients showing the connector.
@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(STATIC / "icon-32.png", media_type="image/png")


@app.get("/icon.svg", include_in_schema=False)
def icon_svg():
    return FileResponse(STATIC / "icon.svg", media_type="image/svg+xml")


@app.get("/icon-512.png", include_in_schema=False)
def icon_png():
    return FileResponse(STATIC / "icon-512.png", media_type="image/png")


def llms_txt() -> str:
    base = settings.public_base_url.rstrip("/")
    return f"""# Nordic weather observations

> Daily rainfall, snow depth and mean/min/max temperature from about 2,800 weather stations in
> Finland, Norway (incl. Svalbard), Sweden, Denmark, Greenland, the Faroe Islands, Iceland and
> Estonia, from 2025-01-01, updated twice a day. Open data from the national weather services
> (CC BY 4.0), processed into common daily values. Read-only, no account or key.

## For AI agents

- [MCP server]({base}/mcp): Streamable HTTP. Tools: find_stations, get_station, get_observations,
  get_day_overview, get_rankings, get_data_status; resource weather://conventions.
- [REST API (OpenAPI)]({base}/openapi.json): the same data over plain HTTP; interactive docs at {base}/docs.
- [Web app](https://isosavi.com/test/rainfall/): the map.
- [Source code and full documentation](https://github.com/jisosavi/rainfall)

## Conventions

- Rainfall for day D: 06 UTC on D to 06 UTC on D+1 (Iceland 09-09 UTC). Snow depth: morning of D.
  Temperature: mean over 00-24 UTC; minimum and maximum 18 UTC on D-1 to 18 UTC on D.
- 0 is a real value; has_data false means missing. Values flagged suspect_spatial are shown but left
  out of summaries and rankings.
- Yesterday's data appears after the morning run (07:15 UTC); Estonia's rainfall a day later,
  Iceland's 3-4 days later. Check get_data_status or /api/status.

## Limits and attribution

- MCP: 60 tool calls a minute per session or IP; above 1,200 a minute in total the tools pause for
  15 minutes. REST: 300 requests a minute per IP.
- Credit: "Data: FMI, MET Norway, SMHI, DMI, IMO and Keskkonnaagentuur (CC BY 4.0), processed by
  Nordic weather observations (https://isosavi.com/test/rainfall/)."
"""


@app.get("/llms.txt", include_in_schema=False, response_class=PlainTextResponse)
def llms():
    return llms_txt()


# MCP (Streamable HTTP) at /mcp. Mounted last, so the API routes above take precedence.
app.mount("/", mcp_app)
