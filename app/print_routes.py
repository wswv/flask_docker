from flask import Blueprint, request, render_template, flash, redirect, url_for, send_file
from flask_login import current_user, login_required   # ← 关键：从这里导入！
from .models import PrintJob, db
import os
import uuid
from datetime import datetime

print_bp = Blueprint('print', __name__, template_folder='templates')

@print_bp.route('/print')
def print_page():
    stats = db.session.query(PrintJob.filename, db.func.count().label('c')).group_by(PrintJob.filename).order_by(db.desc('c')).limit(10).all()
    return render_template('print.html', stats=stats)

@print_bp.route('/print', methods=['POST'])
def upload_print():
    if 'file' not in request.files:
        return "No file", 400
    file = request.files['file']
    if not file.filename: return "Empty", 400

    path = f"/uploads/{file.filename}"
    file.save(path)
    pdf_path = to_pdf(path)
    pages = get_pdf_pages(pdf_path)

    conn = cups.Connection()
    printer = list(conn.getPrinters().keys())[0]
    job_id = conn.printFile(printer, pdf_path, file.filename, {"ColorModel": "RGB"})

    job = PrintJob(filename=file.filename, user_id=current_user.id if current_user.is_authenticated else 0, pages=pages)
    db.session.add(job)
    db.session.commit()

    return f"Printed {file.filename} ({pages}页) ID:{job_id}"

def get_pdf_pages(pdf_path):
    try:
        out = subprocess.check_output(['pdfinfo', pdf_path])
        for line in out.decode().splitlines():
            if 'Pages:' in line:
                return int(line.split()[1])
    except: pass
    return 1