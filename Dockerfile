# Use official Playwright Python image which has python and browser dependencies preinstalled
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set working directory
WORKDIR /app

# Copy dependency list
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code files
COPY . .

# Expose port for local dashboard server
EXPOSE 8000

# Set Python to output logs directly (unbuffered)
ENV PYTHONUNBUFFERED=1

# Execute startup command
CMD ["sh", "start.sh"]
