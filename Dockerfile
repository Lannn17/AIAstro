# ── Stage 1: Build React frontend ─────────────────────────────────────────
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install --legacy-peer-deps
COPY frontend/ ./
RUN npm run build


# ── Stage 2: Python runtime ────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Install system deps required by some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY astrology_api/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY astrology_api/ ./

# Copy built frontend from Stage 1
COPY --from=frontend-builder /app/frontend/dist ./dist

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
