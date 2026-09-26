from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.routes.health import router as health_router
from app.api.routes.rankings import router as rankings_router
from app.api.routes.stations import router as stations_router
from app.config import get_settings
from app.services.errors import InvalidRequestError, NotFoundError

settings = get_settings()

app = FastAPI(title="Rainfall API", version="0.1.0")

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
    return {"message": "Rainfall API"}
