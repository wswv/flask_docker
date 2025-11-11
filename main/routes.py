from flask import (
    render_template, Blueprint, redirect, url_for, flash,
    request, current_app, send_from_directory
)
from flask_login import login_required, current_user
from models import db, User
from functools import wraps

import os
import cups
import subprocess
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from io import BytesIO
import qrcode
import base64

main_bp = Blueprint('main', __name__, template_folder='templates')

# --- 辅助装饰器 (用于检查是否需要强制修改密码) ---
def password_check(f):
    """如果用户需要修改密码，则强制跳转到修改页面。"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated and getattr(current_user, 'needs_password_change', False):
            flash("出于安全考虑，请先修改您的初始密码。", 'info')
            return redirect(url_for('auth.change_password'))
        return f(*args, **kwargs)
    return decorated_function

# --- CUPS 交互函数 ---
def get_cups_connection():
    """
    尝试连接到 CUPS。CUPS_SERVER 和 CUPS_PORT 从 current_app.config 获取。
    返回 cups.Connection 或 None（并在失败时 flash 错误）。
    """
    try:
        return cups.Connection(
            host=current_app.config.get('CUPS_SERVER'),
            port=current_app.config.get('CUPS_PORT')
        )
    except Exception as e:
        current_app.logger.error(f"无法连接到 CUPS 服务器: {e}")
        flash(f"错误：无法连接到打印服务 ({current_app.config.get('CUPS_SERVER')}:{current_app.config.get('CUPS_PORT')})", 'danger')
        return None

def allowed_file(filename):
    allowed = current_app.config.get('ALLOWED_EXTENSIONS', {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'txt', 'doc', 'docx'})
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed

def convert_to_pdf(filepath, original_filename):
    """
    将非 PDF 文件使用 libreoffice 转换为 PDF，返回最终可打印的文件路径。
    如果已经是 PDF，则直接返回原路径。异常由调用者处理。
    """
    filename = secure_filename(original_filename)
    base, ext = os.path.splitext(filename)

    if ext.lower() == '.pdf':
        return filepath

    upload_folder = current_app.config.get('UPLOAD_FOLDER', os.path.join(os.getcwd(), 'uploads'))
    output_dir = os.path.join(upload_folder, 'converted')
    temp_profile = os.path.join('/tmp', 'lo_temp')
    os.makedirs(temp_profile, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    try:
        command = [
            "libreoffice",
            "--headless",
            f"-env:UserInstallation=file://{temp_profile}",
            "--convert-to", "pdf:writer_pdf_Export",
            "--outdir", output_dir,
            filepath
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            timeout=120
        )
        current_app.logger.info(f"LibreOffice 转换输出: {result.stdout.strip()}")

        unique_filename = os.path.basename(filepath)
        base_name_no_ext, _ = os.path.splitext(unique_filename)
        converted_filename = f"{base_name_no_ext}.pdf"
        converted_path = os.path.join(output_dir, converted_filename)

        if not os.path.exists(converted_path):
            current_app.logger.error(f"转换后的文件路径预期: {converted_path}")
            raise FileNotFoundError(f"转换后的文件未找到: {os.path.basename(converted_path)}. 错误信息: {result.stderr.strip()}")

        return os.path.abspath(converted_path)

    except subprocess.CalledProcessError as e:
        current_app.logger.error(f"文件转换失败 (LibreOffice 错误): {e.stderr}")
        raise Exception(f"文件转换失败: {e.stderr}")
    except Exception as e:
        current_app.logger.error(f"文件转换发生意外错误: {e}")
        raise

# --- 路由定义 ---
@main_bp.route('/')
@main_bp.route('/index')
@login_required
@password_check
def index():
    # 把主页重定向到上传页（也可以改为渲染统计或队列页面）
    return redirect(url_for('main.upload_file'))

@main_bp.route('/upload', methods=['GET', 'POST'])
@login_required
@password_check
def upload_file():
    conn = get_cups_connection()
    printers = conn.getPrinters() if conn else {}

    # --- 二维码生成逻辑 ---
    qr_code_uri = None
    try:
        # 生成访问当前上传页的二维码（包含 host）
        full_url = f"http://{request.host}{url_for('main.upload_file')}"
        img = qrcode.make(full_url)
        buf = BytesIO()
        img.save(buf, format='PNG')
        qr_code_uri = base64.b64encode(buf.getvalue()).decode('utf-8')
    except Exception as e:
        current_app.logger.error(f"二维码生成失败: {e}")
    # --- 二维码生成逻辑结束 ---

    printable_file_path = None
    original_file_path = None

    if request.method == 'POST':
        try:
            current_app.logger.debug(f"POST Form Data: {request.form}")
            current_app.logger.debug(f"POST Files Data: {request.files}")

            printer_name = request.form.get('printer_name')
            file = request.files.get('file')

            if not file or file.filename == '' or not allowed_file(file.filename):
                flash('请选择一个有效的文件！', 'warning')
                return redirect(url_for('main.upload_file'))

            if not printer_name:
                flash('请选择一个打印机！', 'warning')
                return redirect(url_for('main.upload_file'))

            original_filename = secure_filename(file.filename)
            upload_folder = current_app.config.get('UPLOAD_FOLDER', os.path.join(os.getcwd(), 'uploads'))
            os.makedirs(upload_folder, exist_ok=True)
            original_file_path = os.path.join(upload_folder, original_filename)
            file.save(original_file_path)

            # 转换为 PDF（如需）
            printable_file_path = convert_to_pdf(original_file_path, original_filename)

            absolute_printable_file_path = os.path.abspath(printable_file_path)
            current_app.logger.info(f"尝试打印文件(绝对路径): {absolute_printable_file_path} 到打印机: {printer_name}")

            env = os.environ.copy()
            cups_server = current_app.config.get('CUPS_SERVER')
            cups_port = current_app.config.get('CUPS_PORT')
            if cups_server and cups_port:
                env['CUPS_SERVER'] = f"{cups_server}:{cups_port}"

            lp_command = [
                'lp',
                '-d', printer_name,
                '-t', f"Web Print: {original_filename}",
                absolute_printable_file_path
            ]

            subprocess.run(
                lp_command,
                env=env,
                capture_output=True,
                text=True,
                check=True,
                timeout=60
            )

            flash(f"文件 '{original_filename}' 已成功提交到打印机 '{printer_name}'。", 'success')
            return redirect(url_for('main.queue_status'))

        except subprocess.CalledProcessError as e:
            error_msg = f"打印失败 (CUPS 错误): 代码 {e.returncode}. {e.stderr.strip()}"
            current_app.logger.error(error_msg)
            flash(error_msg, 'danger')

        except Exception as e:
            current_app.logger.error(f"文件处理或打印发生意外错误: {e}")
            flash(f"文件处理或打印失败: {e}", 'danger')

        finally:
            # 清理临时文件
            if original_file_path and os.path.exists(original_file_path):
                try:
                    os.remove(original_file_path)
                except OSError as e:
                    current_app.logger.error(f"无法删除原始文件 {original_file_path}: {e}")

            if printable_file_path and os.path.exists(printable_file_path) and printable_file_path != original_file_path:
                try:
                    os.remove(printable_file_path)
                except OSError as e:
                    current_app.logger.error(f"无法删除可打印文件 {printable_file_path}: {e}")

    return render_template('upload.html', printers=printers, qr_code_uri=qr_code_uri)

@main_bp.route('/uploads/<path:filename>')
@login_required
@password_check
def uploaded_file(filename):
    # 小心：公开上传目录可能导致安全问题，请确保访问控制
    folder = current_app.config.get('UPLOAD_FOLDER', os.path.join(os.getcwd(), 'uploads'))
    return send_from_directory(folder, filename, as_attachment=False)

@main_bp.route('/queue')
@login_required
@password_check
def queue_status():
    conn = get_cups_connection()
    if not conn:
        return render_template('queue.html', active_jobs=[], history_jobs=[], status_message="无法连接到打印服务。")

    try:
        jobs = conn.getJobs(which_jobs='all')
        current_app.logger.info(f"CUPS 原始作业数量: {len(jobs)}")

        active_jobs = []
        history_jobs = []

        for job_id, job_data in jobs.items():
            job_state = job_data.get('job-state', 'Unknown')
            job_entry = {
                'id': job_id,
                'printer': job_data.get('printer-name', 'N/A'),
                'title': job_data.get('job-name', 'N/A'),
                'user': job_data.get('job-originating-user-name', 'N/A'),
                'state_id': job_state,
                'state': get_job_state_display(job_state),
                'size': f"{job_data.get('job-k-octets', 0)/1024:.2f} MB",
                'submission_time': datetime.fromtimestamp(job_data.get('time-at-creation', 0)).strftime('%Y-%m-%d %H:%M:%S'),
                'completion_time': datetime.fromtimestamp(job_data.get('time-at-completed', 0)).strftime('%Y-%m-%d %H:%M:%S') if job_state in [9, 8] else 'N/A'
            }

            if job_state in [3, 4, 5, 6, 7]:
                active_jobs.append(job_entry)
            else:
                history_jobs.append(job_entry)

        active_jobs.sort(key=lambda x: x['id'], reverse=True)
        history_jobs.sort(key=lambda x: x['id'], reverse=True)

        return render_template('queue.html', active_jobs=active_jobs, history_jobs=history_jobs, status_message="")

    except Exception as e:
        current_app.logger.error(f"获取队列状态失败: {e}")
        flash("获取打印队列状态失败，请检查 CUPS 连接。", 'danger')
        return render_template('queue.html', active_jobs=[], history_jobs=[], status_message="获取队列失败。")

def get_job_state_display(state_id):
    # CUPS job-state IDs: 3=PENDING, 4=HELD, 5=PROCESSING, 6=STOPPED, 7=STOPPED, 8=CANCELED, 9=COMPLETED
    states = {
        3: '等待打印',
        4: '被挂起',
        5: '正在打印',
        6: '已停止',
        7: '已停止',
        8: '已取消',
        9: '已完成'
    }
    return states.get(state_id, '未知状态')

@main_bp.route('/cancel_job', methods=['POST'])
@login_required
@password_check
def cancel_job():
    job_id_str = request.form.get('job_id')
    if not job_id_str:
        flash('未指定要取消的作业ID。', 'danger')
        return redirect(url_for('main.queue_status'))

    try:
        job_id = int(job_id_str)
        conn = get_cups_connection()
        if not conn:
            return redirect(url_for('main.queue_status'))

        conn.cancelJob(job_id, purge=False)
        flash(f"作业 ID {job_id} 已成功取消。", 'success')

    except ValueError:
        flash('无效的作业ID格式。', 'danger')
    except cups.IPPError as e:
        flash(f"取消作业失败 (CUPS 错误: {e.value})。可能是作业已完成或权限不足。", 'danger')
    except Exception as e:
        current_app.logger.error(f"取消作业发生意外错误: {e}")
        flash(f"取消作业发生意外错误: {e}", 'danger')

    return redirect(url_for('main.queue_status'))