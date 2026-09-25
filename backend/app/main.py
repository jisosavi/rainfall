from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.health import router as health_router
from app.api.routes.stations import router as stations_router
from app.config import get_settings

settings = get_settings()

app = FastAPI(title="Rainfall API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(stations_router)


@app.get("/")
def root():
    return {"message": "Rainfall API"}
