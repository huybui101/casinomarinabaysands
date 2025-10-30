from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from .. import db
from ..models import User
import random

auth_bp = Blueprint('auth', __name__)


def generate_account_id():
    # random 9-digit account id
    return str(random.randint(100000000, 999999999))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    # Prepare numeric verification code (OTP-like) stored in session
    if request.method == 'GET' or request.args.get('refresh') == '1':
        session['reg_otp'] = f"{random.randint(100000, 999999)}"

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        phone = request.form.get('phone')
        email = request.form.get('email')
        otp_input = (request.form.get('otp') or '').strip()
        if otp_input != session.get('reg_otp'):
            flash('Mã xác thực không đúng', 'danger')
            return redirect(url_for('auth.register'))
        if not username or not password:
            flash('Vui lòng nhập đầy đủ thông tin', 'danger')
            return redirect(url_for('auth.register'))
        if User.query.filter_by(username=username).first():
            flash('Tên đăng nhập đã tồn tại', 'danger')
            return redirect(url_for('auth.register'))
        uid = generate_account_id()
        while User.query.filter_by(account_id=uid).first():
            uid = generate_account_id()
        u = User(username=username, phone=phone, email=email, account_id=uid)
        u.set_password(password)
        try:
            db.session.add(u)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash('Không thể đăng ký: dữ liệu không hợp lệ hoặc tài khoản đã tồn tại', 'danger')
            return redirect(url_for('auth.register'))
        flash('Đăng ký thành công, vui lòng đăng nhập', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html', otp_code=session.get('reg_otp'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET' or request.args.get('refresh') == '1':
        session['login_otp'] = f"{random.randint(100000, 999999)}"

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        otp_input = (request.form.get('otp') or '').strip()
        if otp_input != session.get('login_otp'):
            flash('Mã xác thực không đúng', 'danger')
            return redirect(url_for('auth.login'))
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            return redirect(url_for('main.home'))
        flash('Sai tài khoản hoặc mật khẩu', 'danger')
    return render_template('auth/login.html', otp_code=session.get('login_otp'))


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
