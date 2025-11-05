# Dockerfile
FROM python:3.12-slim AS builder
WORKDIR /app

# 1. 编译 pycups 必须的头文件
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc python3-dev libcups2-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2. 运行时镜像
FROM python:3.12-slim
WORKDIR /app

# 安装运行依赖 + 强制覆盖 soffice 软链
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice poppler-utils cups-client \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /usr/bin/soffice \
    && ln -sf /usr/bin/libreoffice /usr/bin/soffice

# 复制 Python 包
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY . .

EXPOSE 5000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "run:app"]