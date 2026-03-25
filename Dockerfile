FROM python:3.11-slim

WORKDIR /app

# Install system dependencies required by Presidio / spacy
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download the spacy English NLP model for PII detection
RUN python -m spacy download en_core_web_sm

# Copy application source code
COPY app/ ./app/

# Expose the gateway port
EXPOSE 8000

# Start the FastAPI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
