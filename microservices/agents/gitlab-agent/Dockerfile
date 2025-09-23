# Use a slim Python image as the base
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required for Python packages (e.g., psycopg2-binary, cryptography)
# Also install curl and wget for health checks and potential external calls
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY agents/gitlab-agent/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared modules
COPY shared /app/shared

# Copy application code
COPY agents/gitlab-agent/ .

# Create a non-root user and switch to it
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

# Expose the port the application runs on
EXPOSE 8007

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8007"]
