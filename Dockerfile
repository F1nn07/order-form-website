# 1. Start from an official Python base image
FROM python:3.10-slim

# Add arguments to accept your user/group IDs from docker-compose
ARG UID=1000
ARG GID=1000

# 2. Set the working directory
WORKDIR /app

# 3. Create a non-root user and group that will match your host user
RUN groupadd -g ${GID} -o appgroup && \
    useradd --shell /bin/bash --uid ${UID} --gid ${GID} -m appuser

# 4. Install system dependencies (run as root)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    libfreetype6-dev \
    libpng-dev \
    libjpeg-dev \
    libx11-6 \
    && rm -rf /var/lib/apt/lists/*

# 5. Upgrade pip
RUN pip install --upgrade pip

# 6. Copy requirements file and change its ownership to the new user
COPY --chown=appuser:appgroup requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 7. Copy the rest of your application's code and change ownership
COPY --chown=appuser:appgroup . .

# 8. Switch from 'root' to the new 'appuser'
USER appuser

# 9. Expose the port
EXPOSE 5001

# 10. Command to run the application
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "app:app"]