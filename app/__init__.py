import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_babel import Babel
from flask_wtf.csrf import CSRFProtect
from datetime import timedelta
from sqlalchemy import text

# Globals
db = SQLAlchemy()
login_manager = LoginManager()
babel = Babel()
csrf = CSRFProtect()


def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")

    # Basic config
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(os.path.dirname(__file__), '..', 'app.db')}"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["REMEMBER_COOKIE_DURATION"] = timedelta(days=14)
    app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "uploads")
    # Make template edits visible without full server restart during development
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Init extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    csrf.init_app(app)

    # Babel/i18n
    app.config["BABEL_DEFAULT_LOCALE"] = "vi"
    app.config["BABEL_TRANSLATION_DIRECTORIES"] = os.path.join(app.root_path, "i18n")
    babel.init_app(app)

    # Jinja filter: format odds without unnecessary trailing zeros (e.g., 2.1 not 2.10)
    def _format_odds(value):
        try:
            s = f"{float(value):.2f}".rstrip('0').rstrip('.')
            return s
        except Exception:
            return value
    app.jinja_env.filters['odds'] = _format_odds

    from .models import User, SiteSetting

    # Expose CSRF token helper into templates
    from flask_wtf.csrf import generate_csrf
    @app.context_processor
    def inject_csrf_token():
        return dict(csrf_token=generate_csrf)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    from .routes.auth import auth_bp
    from .routes.main import main_bp
    from .routes.betting import betting_bp
    from .routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(betting_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")

    # Create DB
    with app.app_context():
        db.create_all()
        # Lightweight schema guard for SQLite when models change after initial creation
        try:
            cols = [r[1] for r in db.session.execute(text("PRAGMA table_info('user')")).fetchall()]
            def add_col(name, coltype, default_clause=""):
                if name not in cols:
                    db.session.execute(text(f"ALTER TABLE user ADD COLUMN {name} {coltype} {default_clause}"))
            add_col('withdraw_pin_hash', 'VARCHAR(128)')
            add_col('language', 'VARCHAR(10)')
            add_col('avatar_path', 'VARCHAR(255)')
            add_col('account_id', 'VARCHAR(20)')
            add_col('balance', 'FLOAT', 'DEFAULT 2000.0')
            add_col('income', 'FLOAT', 'DEFAULT 0.0')
            add_col('pnl', 'FLOAT', 'DEFAULT 0.0')
            add_col('override_odds_primary', 'FLOAT')
            add_col('override_odds_secondary', 'FLOAT')
            db.session.commit()
        except Exception:
            db.session.rollback()
        # Ensure SiteSetting exists
        if SiteSetting.query.first() is None:
            s = SiteSetting(site_name="MARINA BAY SANDS", primary_color="#6f42c1", telegram_url="https://t.me/xiaobaolacky")
            db.session.add(s)
            db.session.commit()
        # Ensure an admin user exists (demo)
        from .models import User
        if not User.query.filter_by(is_admin=True).first():
            admin = User(username="admin", account_id="000000001", is_admin=True)
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()
        # One-time fix: set odds_secondary 2.1 -> 1.89 for existing games if unchanged
        try:
            from .models import Game
            updated = Game.query.filter(Game.odds_secondary == 2.1).update({Game.odds_secondary: 1.89})
            if updated:
                db.session.commit()
        except Exception:
            db.session.rollback()

    return app
