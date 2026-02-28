FROM python:3.11-slim AS base

WORKDIR /app

COPY pyproject.toml .
COPY backend/ ./backend/
RUN pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    USE_MOCK_ML=true \
    DATABASE_URL=sqlite+aiosqlite:///./signalforge.db

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
