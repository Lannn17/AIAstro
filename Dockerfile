# ── Stage 1: Build React frontend ─────────────────────────────────────────
FROM node:22.12.0-slim AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install --legacy-peer-deps
COPY frontend/ ./
COPY CHANGELOG.md /app/CHANGELOG.md
RUN npm run build


# ── Stage 2: Python runtime ────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY astrology_api/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-small')"

COPY astrology_api/ ./

COPY --from=frontend-builder /app/frontend/dist ./dist

RUN ls -la /app/dist/ && cat /app/dist/index.html | head -5

EXPOSE 7860
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]