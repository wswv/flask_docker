# 1. Dockerfile（加用户版）
FROM python:3.12-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc python3-dev libcups2-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --target=/install -r requirements.txt

FROM python:3.12-slim
WORKDIR /app
# 1. 创建普通用户
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice poppler-utils cups-client \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /usr/bin/soffice && ln -sf /usr/bin/libreoffice /usr/bin/soffice \
    && useradd -m -s /bin/bash appuser \
    && mkdir -p /uploads && chown appuser:appuser /uploads

COPY --from=builder /install /usr/local/lib/python3.12/site-packages
RUN ln -s /usr/local/lib/python3.12/site-packages/bin/gunicorn /usr/local/bin/gunicorn
COPY . .
# 2. 切换用户
USER appuser
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "run:app"]