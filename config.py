# config.py

import os

# 定义基础目录 (这是容器的工作目录)
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # --- 基本配置 ---
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your_secret_key_123')

    # --- CUPS 配置（从环境变量读取，优先使用 env） ---
    CUPS_SERVER = os.environ.get('CUPS_SERVER', os.environ.get('CUPS_SERVER_IP', '10.1.1.219'))
    CUPS_PORT = int(os.environ.get('CUPS_PORT', os.environ.get('CUPS_SERVER_PORT', 631)))

    # --- 文件/上传配置（可通过 env 覆盖） ---
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', os.path.join(basedir, 'uploads'))
    # MAX_CONTENT_LENGTH 以字节为单位；可通过 env 传入整数（例如 33554432 为 32MB）
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))
    # ALLOWED_EXTENSIONS 可以用逗号分隔字符串传入，例如 "pdf,doc,docx"
    ALLOWED_EXTENSIONS = set(
        (os.environ.get('ALLOWED_EXTENSIONS', 'pdf,doc,docx,xls,xlsx,txt')).split(',')
    )

    # --- 数据库配置 ---
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'users.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False