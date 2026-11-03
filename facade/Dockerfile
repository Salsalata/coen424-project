# Local-only facade (the cloud uses Cloud Run's traffic split instead)
FROM python:3.12-slim
WORKDIR /srv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
RUN useradd --create-home appuser
USER appuser
ENV PORT=8080
EXPOSE 8080
CMD exec gunicorn --workers 2 --threads 8 --bind 0.0.0.0:${PORT} "app:create_app()"
