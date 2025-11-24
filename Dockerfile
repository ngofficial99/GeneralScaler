FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY setup.py .
COPY README.md .

# Install the operator
RUN pip install --no-cache-dir -e .

# Create non-root user
RUN useradd -m -u 1000 operator && chown -R operator:operator /app
USER operator

# Run the operator
CMD ["kopf", "run", "--standalone", "/app/src/generalscaler/operator.py", "--verbose"]
