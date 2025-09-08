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
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy the application code
COPY . .

# Create a non-root user for security
RUN useradd -m appuser
USER appuser

# Expose the port the app runs on
EXPOSE 8000

# Use a Python-based health check that doesn't require installing extra packages
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request, sys; urllib.request.urlopen('http://localhost:8000/health', timeout=3)" || exit 1

# --- THIS IS THE CORRECTED COMMAND ---
# We only need --forwarded-allow-ips for Gunicorn. The middleware will handle the rest.
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--forwarded-allow-ips", "*", "app.main:app", "--bind", "0.0.0.0:8000"]