# entrypoint.sh
#!/bin/sh
set -e

echo "等待数据库 10 秒..."
for i in $(seq 1 10); do
  mysqladmin ping -h db -u flask -pflaskpass --silent && break
  echo "第 $i 次尝试..."
  sleep 2
done
echo "数据库 OK！"

echo "自动建表 + 创建管理员..."
python -c "
import os
from app import create_app
from app.models import db, User
from sqlalchemy import inspect

app = create_app()
with app.app_context():
    db.create_all()
    
    username = os.getenv('ADMIN_USER', 'admin')
    password = os.getenv('ADMIN_PASS', '123456')
    
    if User.query.filter_by(username=username).first():
        print('管理员已存在')
        print(f'账号: {username}  密码: {password}')
    else:
        # 自动检测字段，永不爆炸！
        inspector = inspect(User)
        columns = {col.key for col in inspector.mapper.column_attrs}
        
        kwargs = {'username': username}
        if 'is_admin' in columns:
            kwargs['is_admin'] = True
        if 'email' in columns:
            kwargs['email'] = f'{username}@local'
        if 'role' in columns:
            kwargs['role'] = 'admin'
        
        admin = User(**kwargs)
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        print('管理员创建成功！')
        print(f'账号: {username}  密码: {password}')
"

exec "$@"