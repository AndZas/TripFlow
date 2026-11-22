FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app/API
COPY API/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && mkdir .state \
    && chown 10001:10001 .state

COPY API/tripflow_api ./tripflow_api
COPY shared/data/destinations.json /app/shared/data/destinations.json

USER 10001:10001
EXPOSE 8000
CMD ["sh", "-c", "exec python -m uvicorn tripflow_api.main:app --host 0.0.0.0 --port \"${PORT:-8000}\""]
