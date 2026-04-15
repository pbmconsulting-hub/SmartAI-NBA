FROM python:3.11-slim
WORKDIR /app

# Create non-root user
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure the app user owns writable directories
RUN mkdir -p /app/db /app/logs /app/cache \
    && chown -R appuser:appuser /app/db /app/logs /app/cache

EXPOSE 8501 8000

# Health check: Streamlit exposes /_stcore/health
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"]

USER appuser
CMD ["streamlit", "run", "Smart_Picks_Pro_Home.py", "--server.port=8501", "--server.address=0.0.0.0"]
