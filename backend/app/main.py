from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.routes.health import router as health_router
from app.api.routes.rankings import router as rankings_router
from app.api.routes.stations import router as stations_router
from app.config import get_settings
from app.mcp_server.server import http_app as mcp_http_app
from app.mcp_server.server import mcp, public_mcp_url
from app.services.errors import InvalidRequestError, NotFoundError

settings = get_settings()

mcp_app = mcp_http_app()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # The MCP session manager runs for the app's lifetime.
    async with mcp.session_manager.run():
        yield


app = FastAPI(
    title="Nordic weather observations API",
    version="0.2.0",
    description="Daily rainfall, snow depth and temperature at Nordic and Estonian weather stations. "
    "For AI agents there is also an MCP server at /mcp.",
    lifespan=lifespan,
)

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
    return {"message": "Nordic weather observations API", "docs": "/docs", "mcp": public_mcp_url()}


# MCP (Streamable HTTP) at /mcp. Mounted last, so the API routes above take precedence.
app.mount("/", mcp_app)
