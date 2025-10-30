from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from ..models import SiteSetting, Game, Bet, Transaction, BankAccount
from .. import db
from datetime import datetime, timedelta
import pytz

main_bp = Blueprint('main', __name__)

VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

GAME_LIST_KEYS = [
    ("phi_thuyen", "PHI THUYỀN MAY MẮN"),
    ("may_man_den", "MAY MẮN ĐẾN"),
    ("ngoi_sao", "NGÔI SAO MAY MẮN"),
    ("so_xo_dem_nguoc", "SỔ XỐ ĐẾM NGƯỢC"),
    ("rat_vui", "RẤT VUI"),
    ("nhanh_len_so_xo", "NHANH LÊN SỔ XỐ"),
    ("nhanh_1", "NHANH 1"),
    ("nhanh_2", "NHANH 2"),
    ("nhanh_3", "NHANH 3"),
    ("nhanh_4", "NHANH 4"),
    ("nhanh_5", "NHANH 5"),
    ("nhanh_6", "NHANH 6"),
    ("pk10", "SINGAPORE PK 10"),
    ("cuoc_hanh_phuc", "CƯỢC HẠNH PHÚC"),
    ("hanh_phuc_1", "HẠNH PHÚC 1"),
    ("hanh_phuc_2", "HẠNH PHÚC 2"),
    ("hanh_phuc_3", "HẠNH PHÚC 3"),
    ("hanh_phuc_4", "HẠNH PHÚC 4"),
    ("hanh_phuc_5", "HẠNH PHÚC 5"),
    ("hanh_phuc_6", "HẠNH PHÚC 6"),
    ("hanh_phuc_7", "HẠNH PHÚC 7"),
    ("hanh_phuc_9", "HẠNH PHÚC 9"),
    ("so_xo_singapore", "SỐ XỐ SINGAPORE"),
]


def ensure_games():
    for key, name_vi in GAME_LIST_KEYS:
        if not Game.query.filter_by(key=key).first():
            db.session.add(Game(key=key, name_vi=name_vi))
    db.session.commit()


@main_bp.before_app_request
def before_request():
    # ensure games exist
    ensure_games()
    # Lazy settlement tick: on each request, settle any ended rounds
    try:
        from flask import current_app
        from ..utils.settlement import settle_due_rounds
        settle_due_rounds(current_app.config.get('SECRET_KEY', 'dev-secret-key'))
    except Exception:
        # Never block the request due to settlement errors
        pass


@main_bp.route('/')
@login_required
def home():
    settings = SiteSetting.query.first()
    games = Game.query.filter_by(enabled=True).all()
    from ..models import AdBanner
    banners = AdBanner.query.order_by(AdBanner.created_at.desc()).all()
    now_vn = datetime.now(VN_TZ)
    return render_template(
        'main/home.html',
        settings=settings,
        games=games,
        banners=banners,
        now_vn=now_vn,
        hide_balance=True,
        hide_logout=True,
    )


@main_bp.route('/casino')
@login_required
def casino():
    games = Game.query.filter_by(enabled=True).all()
    return render_template('main/casino.html', games=games, hide_balance=True, hide_logout=True)


@main_bp.route('/lottery')
@login_required
def lottery():
    games = Game.query.filter_by(enabled=True).all()
    return render_template('main/lottery.html', games=games, hide_balance=True, hide_logout=True)


@main_bp.route('/lobby')
@login_required
def lobby():
    games = Game.query.filter_by(enabled=True).all()
    return render_template('main/lobby.html', games=games, hide_balance=True, hide_logout=True)


@main_bp.route('/me')
@login_required
def me():
    bank = BankAccount.query.filter_by(user_id=current_user.id).first()
    settings = SiteSetting.query.first()
    return render_template('main/me.html', bank=bank, settings=settings)


@main_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        lang = request.form.get('language')
        size = request.form.get('font_size')
        current_user.language = lang
        pin = request.form.get('withdraw_pin')
        if pin:
            try:
                if 4 <= len(pin) <= 6 and pin.isdigit():
                    current_user.set_withdraw_pin(pin)
                    flash('Đã cập nhật mật khẩu rút tiền', 'success')
                else:
                    flash('Mật khẩu rút tiền phải 4-6 chữ số', 'danger')
            except Exception:
                pass
        db.session.commit()
        flash('Đã lưu cài đặt', 'success')
        return redirect(url_for('main.settings'))
    return render_template('main/settings.html')


@main_bp.route('/deposit')
@login_required
def deposit():
    # Show deposit page with optional image and Telegram link
    from ..models import SiteSetting
    settings = SiteSetting.query.first()
    return render_template('main/deposit.html', settings=settings)


@main_bp.route('/withdraw', methods=['GET', 'POST'])
@login_required
def withdraw():
    from ..models import SiteSetting
    settings = SiteSetting.query.first()
    error = None
    success = None
    if request.method == 'POST':
        amount = float(request.form.get('amount') or 0)
        pin = request.form.get('pin')
        if amount < 100:
            error = 'Số tiền tối thiểu rút là 100$'
        elif amount > current_user.balance:
            error = 'Số dư không đủ'
        elif not current_user.check_withdraw_pin(pin):
            error = 'Mật khẩu rút tiền không đúng'
        else:
            current_user.balance -= amount
            t = Transaction(user_id=current_user.id, ttype='WITHDRAW', amount=amount, status='SUCCESS')
            db.session.add(t)
            db.session.commit()
            success = 'Yêu cầu rút tiền đã tạo thành công'
    return render_template('main/withdraw.html', error=error, success=success, settings=settings)


@main_bp.route('/history/bets')
@login_required
def history_bets():
    # Load bets and compute remaining time until result for each round (10-min schedule, VN time)
    bets = Bet.query.filter_by(user_id=current_user.id).order_by(Bet.created_at.desc()).all()
    game_map = {g.id: g for g in Game.query.all()}

    def localize_status(result: str, lang: str):
        lang = (lang or 'vi').lower()
        m = {
            'PENDING': {'vi': 'CHỜ KẾT QUẢ', 'en': 'PENDING'},
            'WIN': {'vi': 'THẮNG', 'en': 'WIN'},
            'LOSE': {'vi': 'THUA', 'en': 'LOSE'},
            None: {'vi': '-', 'en': '-'},
        }
        return (m.get(result) or m[None]).get(lang, (m.get(result) or m[None])['vi'])

    now_vn = datetime.now(VN_TZ)
    enriched = []
    for b in bets:
        try:
            date_part = b.round_id[:8]
            slot = int(b.round_id[-3:])
            day = datetime.strptime(date_part, '%Y%m%d')
            day = VN_TZ.localize(day)
            end_time = day + timedelta(minutes=(slot + 1) * 10)
            remaining = int((end_time - now_vn).total_seconds())
            if remaining < 0:
                remaining = 0
        except Exception:
            remaining = 0
        enriched.append({
            'time': b.created_at.astimezone(VN_TZ).strftime('%Y-%m-%d %H:%M'),
            'game_name': game_map.get(b.game_id).name_vi if game_map.get(b.game_id) else str(b.game_id),
            'round_id': b.round_id,
            'selection': b.selection,
            'stake': b.stake,
            'status_label': localize_status(b.result, current_user.language or 'vi'),
            'payout': b.payout,
            'remaining': remaining,
        })

    return render_template('main/history_bets.html', bets=enriched)


@main_bp.route('/history/deposits')
@login_required
def history_deposits():
    txs = Transaction.query.filter_by(user_id=current_user.id, ttype='DEPOSIT').order_by(Transaction.created_at.desc()).all()
    return render_template('main/history_deposit.html', txs=txs)


@main_bp.route('/history/withdraws')
@login_required
def history_withdraws():
    txs = Transaction.query.filter_by(user_id=current_user.id, ttype='WITHDRAW').order_by(Transaction.created_at.desc()).all()
    return render_template('main/history_withdraw.html', txs=txs)


@main_bp.route('/account', methods=['GET', 'POST'])
@login_required
def account_info():
    from ..vn_banks import VIETNAMESE_BANKS
    bank = BankAccount.query.filter_by(user_id=current_user.id).first()
    message = None
    if request.method == 'POST':
        fullname = request.form.get('full_name')
        phone = request.form.get('phone')
        account_number = request.form.get('account_number')
        bank_name = request.form.get('bank_name')
        if not bank:
            bank = BankAccount(user_id=current_user.id)
            db.session.add(bank)
        bank.full_name = fullname
        bank.phone = phone
        bank.account_number = account_number
        bank.bank_name = bank_name
        db.session.commit()
        message = 'Lưu thành công'
    return render_template('main/account_info.html', bank=bank, banks=VIETNAMESE_BANKS, message=message)
