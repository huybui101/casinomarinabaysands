from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
from ..models import SiteSetting, Game, UploadedImage, AdBanner, User, Bet, Transaction
from .. import db

admin_bp = Blueprint('admin', __name__, template_folder='../templates/admin')


def admin_required(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Bạn không có quyền truy cập', 'danger')
            return redirect(url_for('auth.login'))
        return func(*args, **kwargs)
    return wrapper


@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    games = Game.query.all()
    settings = SiteSetting.query.first()
    return render_template('admin/dashboard.html', games=games, settings=settings)


@admin_bp.route('/users')
@login_required
@admin_required
def users():
    q = request.args.get('q', '').strip()
    users_q = User.query
    if q:
        users_q = users_q.filter((User.username.ilike(f"%{q}%")) | (User.account_id.ilike(f"%{q}%")))
    users_q = users_q.order_by(User.created_at.desc())
    users_list = users_q.limit(200).all()
    return render_template('admin/users.html', users=users_list, q=q)

@admin_bp.route('/users/<int:user_id>/odds', methods=['POST'])
@login_required
@admin_required
def user_odds(user_id: int):
    u = User.query.get_or_404(user_id)
    def parse_float(val):
        try:
            return float(val)
        except Exception:
            return None
    if request.form.get('clear') == '1':
        u.override_odds_primary = None
        u.override_odds_secondary = None
    else:
        p = parse_float(request.form.get('override_odds_primary'))
        s = parse_float(request.form.get('override_odds_secondary'))
        u.override_odds_primary = p
        u.override_odds_secondary = s
    db.session.commit()
    from flask import redirect
    return redirect(url_for('admin.users', q=str(user_id)))


@admin_bp.route('/bets')
@login_required
@admin_required
def bets():
    q = request.args.get('q', '').strip()
    bets_q = Bet.query.order_by(Bet.created_at.desc())
    if q:
        try:
            uid = int(q)
            bets_q = bets_q.filter(Bet.user_id == uid)
        except Exception:
            bets_q = bets_q
    bets_list = bets_q.limit(300).all()
    games = {g.id: g.name_vi for g in Game.query.all()}
    users = {u.id: u.username for u in User.query.all()}
    return render_template('admin/bets.html', bets=bets_list, games=games, users=users, q=q)


@admin_bp.route('/transactions')
@login_required
@admin_required
def transactions():
    txs = Transaction.query.order_by(Transaction.created_at.desc()).limit(300).all()
    users = {u.id: u.username for u in User.query.all()}
    return render_template('admin/transactions.html', txs=txs, users=users)


@admin_bp.route('/deposits')
@login_required
@admin_required
def deposits():
    txs = Transaction.query.filter_by(ttype='DEPOSIT').order_by(Transaction.created_at.desc()).limit(300).all()
    users = {u.id: u.username for u in User.query.all()}
    return render_template('admin/deposits.html', txs=txs, users=users)


@admin_bp.route('/withdraws')
@login_required
@admin_required
def withdraws():
    txs = Transaction.query.filter_by(ttype='WITHDRAW').order_by(Transaction.created_at.desc()).limit(300).all()
    users = {u.id: u.username for u in User.query.all()}
    return render_template('admin/withdraws.html', txs=txs, users=users)


@admin_bp.route('/reports')
@login_required
@admin_required
def reports():
    # Simple KPIs
    user_count = User.query.count()
    bet_count = Bet.query.count()
    tx_count = Transaction.query.count()
    total_deposit = db.session.query(db.func.coalesce(db.func.sum(Transaction.amount), 0.0)).filter(Transaction.ttype=='DEPOSIT').scalar() or 0.0
    total_withdraw = db.session.query(db.func.coalesce(db.func.sum(Transaction.amount), 0.0)).filter(Transaction.ttype=='WITHDRAW').scalar() or 0.0
    total_balance = db.session.query(db.func.coalesce(db.func.sum(User.balance), 0.0)).scalar() or 0.0
    return render_template('admin/reports.html', user_count=user_count, bet_count=bet_count, tx_count=tx_count, total_deposit=total_deposit, total_withdraw=total_withdraw, total_balance=total_balance)


@admin_bp.route('/promotions')
@login_required
@admin_required
def promotions():
    return render_template('admin/placeholder.html', title='Khuyến mãi & VIP', description='Trang quản lý chương trình thưởng, mã khuyến mãi, VIP, hoàn tiền. (Sẽ bổ sung)')


@admin_bp.route('/affiliates')
@login_required
@admin_required
def affiliates():
    return render_template('admin/placeholder.html', title='Đối tác Affiliate', description='Quản lý đối tác và hoa hồng. (Sẽ bổ sung)')


@admin_bp.route('/payments')
@login_required
@admin_required
def payments():
    return render_template('admin/placeholder.html', title='Ví điện tử & Thanh toán', description='Quản lý phương thức thanh toán, cấu hình ví. (Sẽ bổ sung)')


@admin_bp.route('/support')
@login_required
@admin_required
def support():
    return render_template('admin/placeholder.html', title='Hỗ trợ khách hàng', description='Gửi thông báo, tin nhắn hoặc email đến người chơi. (Sẽ bổ sung)')


@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def settings():
    settings = SiteSetting.query.first()
    # Load uploaded images to allow choosing a logo from the media library
    logo_choices = UploadedImage.query.filter_by(usage='logo').order_by(UploadedImage.created_at.desc()).all()
    ui_images = UploadedImage.query.order_by(UploadedImage.created_at.desc()).all()
    if request.method == 'POST':
        settings.site_name = request.form.get('site_name')
        settings.primary_color = request.form.get('primary_color')
        settings.telegram_url = request.form.get('telegram_url')

        # Optional: set/clear the site logo
        if request.form.get('clear_logo') == 'on':
            settings.logo_path = None
        else:
            logo_image_id = request.form.get('logo_image_id')
            if logo_image_id:
                try:
                    img = UploadedImage.query.get(int(logo_image_id))
                    if img:
                        settings.logo_path = img.path
                except Exception:
                    pass

        # Optional: homepage Deposit/Withdraw images
        dep_img = request.form.get('deposit_image_path')
        wdr_img = request.form.get('withdraw_image_path')
        settings.deposit_image_path = dep_img or None
        settings.withdraw_image_path = wdr_img or None

        db.session.commit()
        flash('Đã lưu cài đặt', 'success')
        return redirect(url_for('admin.settings'))
    return render_template('admin/settings.html', settings=settings, logos=logo_choices, ui_images=ui_images)


@admin_bp.route('/users/<int:user_id>/adjust', methods=['POST'])
@login_required
@admin_required
def adjust_balance(user_id: int):
    u = User.query.get_or_404(user_id)
    try:
        amount = float(request.form.get('amount') or '0')
    except Exception:
        amount = 0.0
    action = request.form.get('action')  # 'credit' or 'debit'
    note = (request.form.get('note') or '').strip()
    if amount <= 0:
        flash('Số tiền phải lớn hơn 0', 'danger')
        return redirect(url_for('admin.users', q=str(u.id)))
    delta = amount if action == 'credit' else -amount
    if action == 'debit' and (u.balance or 0) + delta < 0:
        flash('Số dư không đủ để trừ', 'danger')
        return redirect(url_for('admin.users', q=str(u.id)))
    u.balance = float((u.balance or 0.0) + delta)
    t = Transaction(user_id=u.id, ttype='ADMIN_ADJUST', amount=amount, status='SUCCESS', note=f"{action.upper()}: {note}")
    db.session.add(t)
    db.session.commit()
    flash('Đã cập nhật số dư người dùng', 'success')
    return redirect(url_for('admin.users', q=str(u.id)))


@admin_bp.route('/games', methods=['GET', 'POST'])
@login_required
@admin_required
def games():
    games = Game.query.order_by(Game.name_vi.asc()).all()
    game_images = UploadedImage.query.filter_by(usage='game').order_by(UploadedImage.created_at.desc()).all()
    if request.method == 'POST':
        for g in games:
            odds_primary = request.form.get(f'odds_primary_{g.id}')
            odds_secondary = request.form.get(f'odds_secondary_{g.id}')
            g.odds_primary = float(odds_primary or g.odds_primary)
            g.odds_secondary = float(odds_secondary or g.odds_secondary)
            g.enabled = True if request.form.get(f'enabled_{g.id}') == 'on' else False
            # Handle icon assignment
            if request.form.get(f'clear_icon_{g.id}') == 'on':
                g.icon_path = None
            else:
                icon_val = request.form.get(f'icon_{g.id}')
                if icon_val:
                    g.icon_path = icon_val
        db.session.commit()
        flash('Đã cập nhật tỷ lệ trò chơi', 'success')
        return redirect(url_for('admin.games'))
    return render_template('admin/games.html', games=games, game_images=game_images)


ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@admin_bp.route('/images', methods=['GET', 'POST'])
@login_required
@admin_required
def images():
    if request.method == 'POST':
        if 'image' not in request.files:
            flash('Không có tệp', 'danger')
            return redirect(url_for('admin.images'))
        file = request.files['image']
        usage = request.form.get('usage')
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(save_path)
            # Optional background removal if rembg is installed
            if request.form.get('remove_bg') == 'on':
                try:
                    from rembg import remove
                    from PIL import Image
                    input_image = Image.open(save_path)
                    output = remove(input_image)
                    output_path = os.path.join(current_app.config['UPLOAD_FOLDER'], f"bg_removed_{filename}")
                    output.save(output_path)
                    os.remove(save_path)
                    final_path = output_path
                except Exception:
                    final_path = save_path
            else:
                final_path = save_path
            rel_path = os.path.relpath(final_path, current_app.root_path).replace('\\', '/')
            db.session.add(UploadedImage(usage=usage, path='/' + rel_path))
            db.session.commit()
            flash('Tải ảnh thành công', 'success')
            return redirect(url_for('admin.images'))
    images = UploadedImage.query.order_by(UploadedImage.created_at.desc()).all()
    return render_template('admin/images.html', images=images)


@admin_bp.route('/banners', methods=['GET', 'POST'])
@login_required
@admin_required
def banners():
    """Manage advertising banners using images uploaded with usage='ad'."""
    ads = UploadedImage.query.filter_by(usage='ad').order_by(UploadedImage.created_at.desc()).all()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            img_id = request.form.get('image_id')
            try:
                img = UploadedImage.query.get(int(img_id))
                if img:
                    db.session.add(AdBanner(image_path=img.path))
                    db.session.commit()
                    flash('Đã thêm banner', 'success')
            except Exception:
                db.session.rollback()
        elif action == 'delete':
            banner_id = request.form.get('banner_id')
            b = AdBanner.query.get(banner_id)
            if b:
                db.session.delete(b)
                db.session.commit()
                flash('Đã xóa banner', 'success')
        return redirect(url_for('admin.banners'))
    banners = AdBanner.query.order_by(AdBanner.created_at.desc()).all()
    return render_template('admin/banners.html', ads=ads, banners=banners)


@admin_bp.route('/images/delete/<int:image_id>', methods=['POST'])
@login_required
@admin_required
def delete_image(image_id):
    img = UploadedImage.query.get_or_404(image_id)
    try:
        abs_path = os.path.join(current_app.root_path, img.path.strip('/'))
        if os.path.exists(abs_path):
            os.remove(abs_path)
    except Exception:
        pass
    db.session.delete(img)
    db.session.commit()
    flash('Đã xóa ảnh', 'success')
    return redirect(url_for('admin.images'))
