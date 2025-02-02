FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libsqlite3-0 \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy the entire application first
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create data directory for SQLite
RUN mkdir -p /data && chown 1000:1000 /data

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=sqlite:////data/bot.db

# Run as non-root user
USER 1000

# Command to run the application
CMD ["python", "-m", "app.main"] 