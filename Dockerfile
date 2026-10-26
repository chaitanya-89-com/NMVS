FROM node:22-alpine AS frontend-build

WORKDIR /frontend
COPY nmvs_frontend/package.json nmvs_frontend/package-lock.json ./
RUN npm ci
COPY nmvs_frontend/ ./
RUN npm run build

FROM python:3.12-slim

WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=frontend-build /frontend/dist/ /app/static/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NMVS_FRONTEND_DIST=/app/static

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
