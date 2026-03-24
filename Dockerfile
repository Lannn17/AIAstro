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

# Install system deps (libgomp1 required by ONNX Runtime used by fastembed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY astrology_api/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download embedding model weights into the image (avoids cold-start download)
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('intfloat/multilingual-e5-small')"

# Copy backend source
COPY astrology_api/ ./

# Copy built frontend from Stage 1
COPY --from=frontend-builder /app/frontend/dist ./dist

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
