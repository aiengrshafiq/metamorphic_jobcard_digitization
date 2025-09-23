# ---- Build Stage ----
# This stage installs Python dependencies into a clean directory
FROM python:3.11-slim-bullseye as builder

WORKDIR /install

# Install build-time dependencies
RUN pip install --no-cache-dir --upgrade pip
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix="/install" -r requirements.txt


# --- Final Stage ---
# Start from the same base image
FROM python:3.11-slim-bullseye

# --- THIS IS THE CRITICAL FIX ---
# Install the required system libraries for WeasyPrint in the FINAL image
# Using the recommended list for Debian-based systems
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    python3-cffi \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*
# --------------------------------

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory
WORKDIR /app

# Copy the pre-installed Python packages from the builder stage
COPY --from=builder /install /usr/local

# Copy the application code
COPY . .

# Create a non-root user for security
RUN useradd --create-home appuser
USER appuser

# Expose the port the app runs on
EXPOSE 8000

# Health check (your existing one is good)
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request, sys; urllib.request.urlopen('http://localhost:8000/health', timeout=3)" || exit 1

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--proxy-headers", "--forwarded-allow-ips", "*"]