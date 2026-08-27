FROM python:3.12-alpine

WORKDIR /app

# Install runtime deps only, no build tools
RUN apk add --no-cache tini

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py templates/ assets/ content/ ./

# Run as non-root with limited capabilities
USER 65534

EXPOSE 8002

ENTRYPOINT ["/sbin/tini", "--"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002", "--workers", "1", "--log-level", "error"]
