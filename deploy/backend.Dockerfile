FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY ai_rag/fastapi-app/requirements*.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY ai_rag/fastapi-app/ .
RUN useradd --uid 10001 --create-home app && mkdir -p /app/state && chown -R app:app /app
USER app
ENV UPLOAD_DIR=/app/files JWT_SECRET_FILE=/app/state/jwt-secret
EXPOSE 9090
CMD ["python","-m","uvicorn","main:app","--host","0.0.0.0","--port","9090","--workers","1","--timeout-graceful-shutdown","10"]
