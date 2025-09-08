# ---- Build Stage ----
# Use an official Python runtime as a parent image
FROM python:3.11-slim-bullseye as builder

# Set the working directory
WORKDIR /app

# Install build-time dependencies
RUN pip install --no-cache-dir --upgrade pip
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Final Stage ---
FROM python:3.11-slim-bullseye

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory
WORKDIR /app

# Copy the installed packages from the builder stage
COPY --from-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy the application code
COPY . .

# Create a non-root user for security
RUN useradd -m appuser
USER appuser

# Expose the port the app runs on
EXPOSE 8000

# --- THIS IS THE FIX ---
# Point the health check to a dedicated /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run the application using Gunicorn, a production-ready web server
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "app.main:app", "--bind", "0.0.0.0:8000"]