# app/__init__.py（终极版·吃到饭了）
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
import redis

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()

# 关键：改成 Flask-SQLAlchemy 官方标准变量名
def create_app():
    app = Flask(__name__)
    
    # 1. 读取 compose 里喂的变量
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
        'SQLALCHEMY_DATABASE_URI',
        'mysql+pymysql://flask:flaskpass@localhost:3306/flaskdb'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['REDIS_URL'] = os.getenv('REDIS_URL', 'redis://redis:6379/0')

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    # 注册蓝图
    from .routes import auth, main
    from .print_routes import print_bp
    app.register_blueprint(auth)
    app.register_blueprint(main)
    app.register_blueprint(print_bp)

    return app