# catalog-service image (REST lecture, slide 32)
FROM python:3.12-slim

WORKDIR /srv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# Dependencies first: this layer stays cached until requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY data/ data/

# Non-root user: limits the damage if the app is compromised
RUN useradd --create-home appuser
USER appuser

# Cloud Run tells the container which port to listen on through $PORT
ENV PORT=8080 WORKERS=2
EXPOSE 8080
# exec: gunicorn becomes PID 1 and receives the platform's shutdown signal.
# WORKERS must be 1 with STORAGE=memory: each worker would have its own dict
# and see different data (REST lecture, slide 20). With Firestore, any number works.
CMD exec gunicorn --workers ${WORKERS} --bind 0.0.0.0:${PORT} "app:create_app()"
