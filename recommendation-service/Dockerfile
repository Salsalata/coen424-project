# recommendation-service image: ONE image for v1 and v2; the RECOMMENDER
# environment variable picks the version (REST lecture, slide 32).
FROM python:3.12-slim

WORKDIR /srv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/

RUN useradd --create-home appuser
USER appuser

ENV PORT=8080
EXPOSE 8080
# Threads: v2 spends most of its time waiting for Gemini, so each worker
# handles several requests at once while waiting.
CMD exec gunicorn --workers 2 --threads 4 --timeout 60 --bind 0.0.0.0:${PORT} "app:create_app()"
