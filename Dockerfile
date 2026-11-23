FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    SCHEDULER_DB=/data/scheduler.sqlite3

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir fastapi uvicorn jinja2 openpyxl

COPY src ./src
RUN mkdir -p /data

EXPOSE 8000
CMD ["uvicorn", "scheduler.main:app", "--host", "0.0.0.0", "--port", "8000"]
