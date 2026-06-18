FROM python:3.11-slim

WORKDIR /app

# Install system dependencies if any are needed (e.g. gcc for compiling)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install python packages
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and data files
COPY backend/app ./backend/app
COPY frontend ./frontend
COPY ["GHG Sheet .xlsx", "."]

# Expose port 8000
EXPOSE 8000

# Run seeder to initialize SQLite and start FastAPI
CMD ["sh", "-c", "python -m backend.app.seeder && uvicorn backend.app.main:app --host 0.0.0.0 --port 8000"]
