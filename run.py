import os
from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

# --- 导入配置和模型 (绝对导入) ---
from config import Config 
from models import db, User 

# 【新增导入】用于数据库初始化和安全操作
from werkzeug.security import generate_password_hash
from sqlalchemy.exc import IntegrityError, OperationalError
from main.routes import main_bp
from auth.routes import auth_bp



def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # 启用 CSRF 保护
    CSRFProtect(app)
    
    # 初始化 SQLAlchemy
    db.init_app(app) # 仅初始化扩展，不执行创建表操作
    
    # 初始化 Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login' 
    login_manager.login_message = "请先登录以访问此页面。"
    login_manager.login_message_category = "warning"
    
    @login_manager.user_loader
    def load_user(user_id):
        # 使用推荐的 db.session.get 风格
        return db.session.get(User, int(user_id))

    # 注册蓝图
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)

    # 【关键修改：数据库初始化逻辑已移除】
        
    return app

def initialize_database(app):
    """
    在应用上下文中执行数据库的创建和初始管理员用户的创建。
    此函数仅应在首次设置时被调用一次。
    """
    with app.app_context():
        app.logger.info("Starting database and default user initialization...")
        
        # 1. 确保表结构存在
        # 捕获 OperationalError 以防多进程竞争，尽管在 ENTRYPOINT 中运行能有效避免。
        try:
            db.create_all()
            app.logger.info("Database tables ensured.")
        except OperationalError as e:
            # 这种情况在单线程初始化中不常见，但作为安全措施保留。
            app.logger.error(f"Error during db.create_all(): {e}")
            return # 初始化失败，停止
        
        # 2. 检查并创建默认用户
        try:
            if db.session.scalar(db.select(User).filter_by(username='admin')) is None:
                admin_user = User(username='admin', is_admin=True) 
                
                # 设置初始密码并强制要求修改
                admin_user.password_hash = generate_password_hash('password123')
                admin_user.needs_password_change = True # 确保初始登录后需要修改

                db.session.add(admin_user)
                db.session.commit()
                app.logger.info("Admin user 'admin' created successfully and requires password change.")
            else:
                app.logger.info("Admin user 'admin' already exists. Skipping creation.")
            
        except IntegrityError:
            db.session.rollback()
            app.logger.warning("Admin user 'admin' already exists. Rolling back session.")
        except OperationalError:
            db.session.rollback()
            app.logger.warning("Database operational error during admin creation, likely lock contention. Rolling back.")
            
# 【Gunicorn 启动入口】
app = create_app()


if __name__ == '__main__':
    # 【本地开发入口】
    print("Running Flask development server. Use 'python setup_db.py' for initialization.")
    app.run(host='0.0.0.0', port=5000, debug=True)