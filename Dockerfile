# Use Python 3.11 as base image
FROM python:3.11-slim

# Set working directory in the container
WORKDIR /app

# Install system dependencies including PostgreSQL client
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py database.py models.py utils.py ./
COPY templates/ ./templates/
COPY static/ ./static/

# Set environment variables
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# Expose the port the app will run on
EXPOSE 5000

# Command to run the application
CMD ["flask", "run", "--host", "0.0.0.0"]