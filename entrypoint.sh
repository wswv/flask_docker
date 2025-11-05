# entrypoint.sh（自动建号神器）
#!/bin/sh
echo "检查管理员账号..."

python -c "
import os
from app import create_app
from app.models import User, db

app = create_app()
with app.app_context():
    admin = User.query.filter_by(username=os.getenv('ADMIN_USER')).first()
    if not admin:
        admin = User(
            username=os.getenv('ADMIN_USER'),
            email=os.getenv('ADMIN_EMAIL'),
            is_admin=True
        )
        admin.set_password(os.getenv('ADMIN_PASS'))
        db.session.add(admin)
        db.session.commit()
        print('管理员创建成功！')
    else:
        print('管理员已存在，跳过创建')
    print(f"账号: {os.getenv('ADMIN_USER')}")
    print(f"密码: {os.getenv('ADMIN_PASS')}")
"

exec gunicorn -w 2 -b 0.0.0.0:5000 run:app