FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY alembic.ini start.sh ./
COPY migrations ./migrations
COPY app ./app

RUN chmod +x start.sh && useradd --create-home --uid 1000 appuser
USER appuser

EXPOSE 8000

# Railway injects PORT; start.sh runs migrations, then uvicorn.
CMD ["./start.sh"]
