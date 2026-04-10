FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential curl \
  && rm -rf /var/lib/apt/lists/*

COPY api/requirements.txt /app/requirements.txt
RUN pip install --upgrade pip \
  && pip install -r /app/requirements.txt

# Copy all files
COPY . /app/

EXPOSE 8080

CMD ["python", "-c", "import sys; sys.path.insert(0, '/app'); from api.app import app; import uvicorn; import os; port = int(os.environ.get('PORT', 8080)); print(f'Starting server on port {port}'); uvicorn.run(app, host='0.0.0.0', port=port, log_level='info', access_log=True, loop='asyncio', workers=1, timeout_keep_alive=120)"]
