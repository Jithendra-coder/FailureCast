FROM node:20-alpine AS frontend-build
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp TMPDIR=/tmp MLFLOW_TRACKING_URI=sqlite:////app/artifacts/mlflow.db
WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
ENV GIT_PYTHON_REFRESH=quiet
COPY backend/ ./backend/
COPY --from=frontend-build /src/frontend/dist ./frontend/dist
RUN mkdir -p data/raw artifacts/models artifacts/experiments && chown -R 10001:10001 /app
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
