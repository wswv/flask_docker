# entrypoint.sh（兼容 mariadb-client）
#!/bin/sh
set -e

echo "等待数据库 10 秒..."
for i in $(seq 1 10); do
  mysqladmin ping -h db -u flask -pflaskpass --silent && break
  echo "第 $i 次尝试..."
  sleep 2
done

echo "数据库 OK！自动建表 + 创建管理员..."
python -c "
import os
from app import create_app
from app.models import db, User

app = create_app()
with app.app_context():
    db.create_all()
    admin = User.query.filter_by(username=os.getenv('ADMIN_USER', 'admin')).first()
    if not admin:
        admin = User(username=os.getenv('ADMIN_USER', 'admin'),
                    email=os.getenv('ADMIN_EMAIL', 'admin@local'),
                    is_admin=True)
        admin.set_password(os.getenv('ADMIN_PASS', '123456'))
        db.session.add(admin)
        db.session.commit()
        print('管理员创建成功！')
    print(f'账号: {os.getenv(\"ADMIN_USER\", \"admin\")}')
    print(f'密码: {os.getenv(\"ADMIN_PASS\", \"123456\")}')
"

exec "$@"