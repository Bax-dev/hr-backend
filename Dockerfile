FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app
RUN addgroup --system django && adduser --system --ingroup django django
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chown -R django:django /app
USER django
EXPOSE 8000
CMD ["sh", "-c", "gunicorn hr_app_backend.wsgi:application --bind 0.0.0.0:${PORT} --workers 3 --timeout 60"]
