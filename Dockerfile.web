FROM python:3.11-slim

WORKDIR /app

# Copy dependency spec first for Docker layer caching
COPY web/requirements.txt /app/web/requirements.txt
RUN pip install --no-cache-dir -r web/requirements.txt

# Copy source code
COPY src/ /app/src/
COPY data/knowledge/ /app/data/knowledge/
COPY web/ /app/web/

WORKDIR /app/web

ENV PORT=8080
ENV PYTHONPATH=/app

EXPOSE 8080

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "120"]
