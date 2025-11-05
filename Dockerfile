# Dockerfile（兼容 Debian Trixie）
FROM python:3.12-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc python3-dev libcups2-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --target=/install -r requirements.txt

FROM python:3.12-slim
WORKDIR /app

# 关键：mysql-client → mariadb-client
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice poppler-utils cups-client mariadb-client \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /usr/bin/soffice && ln -sf /usr/bin/libreoffice /usr/bin/soffice \
    && useradd -m -s /bin/bash appuser \
    && mkdir -p /uploads && chown appuser:appuser /uploads

COPY --from=builder /install /usr/local/lib/python3.12/site-packages
RUN ln -s /usr/local/lib/python3.12/site-packages/bin/gunicorn /usr/local/bin/gunicorn

COPY . .
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

USER appuser
ENTRYPOINT ["/bin/sh", "/app/entrypoint.sh"]
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "run:app"]