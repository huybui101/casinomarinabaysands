from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from . import db

class SiteSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    site_name = db.Column(db.String(120), default="Site")
    logo_path = db.Column(db.String(255), nullable=True)
    primary_color = db.Column(db.String(20), default="#6f42c1")
    telegram_url = db.Column(db.String(255), default="https://t.me/xiaobaolacky")
    language_default = db.Column(db.String(10), default="vi")

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    phone = db.Column(db.String(30), unique=True, nullable=True)
    password_hash = db.Column(db.String(128), nullable=False)
    withdraw_pin_hash = db.Column(db.String(128), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)
    language = db.Column(db.String(10), default=None)
    avatar_path = db.Column(db.String(255), nullable=True)
    account_id = db.Column(db.String(20), unique=True, nullable=False)

    balance = db.Column(db.Float, default=2000.0)
    income = db.Column(db.Float, default=0.0)
    pnl = db.Column(db.Float, default=0.0)

    # Optional per-user odds overrides (if set, override game defaults 1.98/2.1)
    override_odds_primary = db.Column(db.Float, nullable=True)
    override_odds_secondary = db.Column(db.Float, nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def set_withdraw_pin(self, pin):
        self.withdraw_pin_hash = generate_password_hash(pin)

    def check_withdraw_pin(self, pin):
        return self.withdraw_pin_hash and check_password_hash(self.withdraw_pin_hash, pin)

class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    name_vi = db.Column(db.String(100), nullable=False)
    icon_path = db.Column(db.String(255), nullable=True)
    odds_primary = db.Column(db.Float, default=1.98)
    odds_secondary = db.Column(db.Float, default=1.89)
    enabled = db.Column(db.Boolean, default=True)

class Bet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'))
    round_id = db.Column(db.String(30), index=True)
    selection = db.Column(db.String(50))  # e.g., "LỚN", "NHỎ", "LÀN SÓNG ĐỎ" etc.
    odds = db.Column(db.Float, default=1.98)
    stake = db.Column(db.Float, default=0.0)
    result = db.Column(db.String(20), default=None)  # WIN/LOSE/PENDING
    payout = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    ttype = db.Column(db.String(20))  # DEPOSIT/WITHDRAW
    amount = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='PENDING')
    note = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class BankAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    full_name = db.Column(db.String(100))
    phone = db.Column(db.String(30))
    account_number = db.Column(db.String(50))
    bank_name = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AdBanner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image_path = db.Column(db.String(255))
    title = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class UploadedImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usage = db.Column(db.String(50))  # 'logo'/'game'/'ad'
    path = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class RoundResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    round_id = db.Column(db.String(30), unique=True, index=True)
    # Stores a small JSON string with winners for each group
    # Example: {"pairs": {"0": "LỚN", "1": "NHỎ"}, "waves": "LÀN SÓNG ĐỎ"}
    result_json = db.Column(db.Text, nullable=False)
    settled = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
